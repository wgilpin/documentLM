import { Editor, Extension } from '@tiptap/core';
import StarterKit   from '@tiptap/starter-kit';
import Focus        from '@tiptap/extension-focus';
import { Markdown } from 'tiptap-markdown';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

const mountEl      = document.getElementById('tiptap-mount');
const contentInput = document.getElementById('document-content');
const aiBtn        = document.getElementById('ai-block-btn');

let pendingSelection = { start: 0, end: 0, text: '' };
let lastChangeIsAi   = false;

// ── Persistent LocalStorage History ───────────────────────────────────────
const docIdMatch = contentInput.getAttribute('hx-put')?.match(/\/documents\/(.+)$/);
const DOC_ID = docIdMatch ? docIdMatch[1] : 'unknown-doc';
const HISTORY_KEY = `tiptap-history-${DOC_ID}`;

let localHistory = [];
let localHistoryIndex = -1;

try {
    const saved = localStorage.getItem(HISTORY_KEY);
    if (saved) {
        localHistory = JSON.parse(saved);
        localHistoryIndex = localHistory.length - 1;
    }
} catch(e) {}

// If history is completely empty, initialize it with current server doc state
if (localHistory.length === 0) {
    localHistory.push(contentInput.value);
    localHistoryIndex = 0;
} else if (localHistory[localHistoryIndex] !== contentInput.value) {
    // If server doc state (initial load) differs from last local history (e.g. another device edited), pin it
    localHistory.push(contentInput.value);
    localHistoryIndex++;
}

let historyDebounce = null;

function saveToHistory(text) {
    if (localHistory[localHistoryIndex] === text) return;

    if (localHistoryIndex < localHistory.length - 1) {
        localHistory = localHistory.slice(0, localHistoryIndex + 1);
    }

    localHistory.push(text);
    if (localHistory.length > 50) localHistory.shift();
    localHistoryIndex = localHistory.length - 1;

    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(localHistory)); } catch(e) {}

    if (window.tiptapEditor) updateToolbar(window.tiptapEditor);
}

function canUndoLocal() { return localHistoryIndex > 0; }
function canRedoLocal() { return localHistoryIndex < localHistory.length - 1; }

// ── Active block tracking ─────────────────────────────────────────────────
let activeBlockPos  = null;
let activeBlockNode = null;

function updateAiButton(editor) {
    const { state, view } = editor;
    const { $from } = state.selection;
    let depth = $from.depth;
    while (depth > 0 && !$from.node(depth).isBlock) depth--;

    if (depth > 0) {
        activeBlockPos  = $from.before(depth);
        activeBlockNode = $from.node(depth);
        try {
            const coords      = view.coordsAtPos($from.pos);
            const wrapperRect = mountEl.getBoundingClientRect();
            const top         = coords.top - wrapperRect.top + mountEl.scrollTop;
            aiBtn.style.top     = top + 'px';
            aiBtn.style.display = 'block';
            return;
        } catch (err) {
            console.warn('[aiBtn] coordsAtPos threw:', err);
        }
    }
    aiBtn.style.display = 'none';
    activeBlockPos  = null;
    activeBlockNode = null;
}

// ── Undo/redo toolbar ─────────────────────────────────────────────────────
const undoBtn = document.getElementById('undo-btn');
const redoBtn = document.getElementById('redo-btn');

// ── Formatting toolbar ────────────────────────────────────────────────────
const fmtButtons = {
    bold:  document.getElementById('fmt-bold'),
    italic: document.getElementById('fmt-italic'),
    h1: document.getElementById('fmt-h1'),
    h2: document.getElementById('fmt-h2'),
    h3: document.getElementById('fmt-h3'),
    ul: document.getElementById('fmt-ul'),
    ol: document.getElementById('fmt-ol'),
    quote: document.getElementById('fmt-quote'),
    code: document.getElementById('fmt-code'),
};

const fmtActiveChecks = [
    [fmtButtons.bold,   () => editor.isActive('bold')],
    [fmtButtons.italic, () => editor.isActive('italic')],
    [fmtButtons.h1,     () => editor.isActive('heading', { level: 1 })],
    [fmtButtons.h2,     () => editor.isActive('heading', { level: 2 })],
    [fmtButtons.h3,     () => editor.isActive('heading', { level: 3 })],
    [fmtButtons.ul,     () => editor.isActive('bulletList')],
    [fmtButtons.ol,     () => editor.isActive('orderedList')],
    [fmtButtons.quote,  () => editor.isActive('blockquote')],
    [fmtButtons.code,   () => editor.isActive('codeBlock')],
];

function updateToolbar(editor) {
    const canUndo = canUndoLocal();
    const canRedo = canRedoLocal();
    undoBtn.disabled = !canUndo;
    redoBtn.disabled = !canRedo;
    undoBtn.title = canUndo
        ? (lastChangeIsAi ? 'Undo AI change' : 'Undo')
        : 'Nothing to undo';
    redoBtn.title = canRedo ? 'Redo' : 'Nothing to redo';
    for (const [btn, check] of fmtActiveChecks) {
        btn.classList.toggle('toolbar-btn--active', check());
    }
}

// ── Suggestion Decorations ─────────────────────────────────────────────────
const suggestionsPluginKey = new PluginKey('suggestions');
let pendingSuggestions = []; // [{id, original_text, suggested_text}]

function stripMarkdownBasic(text) {
    return text
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/\*\*\*(.+?)\*\*\*/gs, '$1')
        .replace(/\*\*(.+?)\*\*/gs, '$1')
        .replace(/\*(.+?)\*/gs, '$1')
        .replace(/`(.+?)`/gs, '$1')
        .replace(/~~(.+?)~~/gs, '$1')
        .replace(/\[(.+?)\]\(.+?\)/g, '$1')
        .replace(/\\(.)/g, '$1')
        .trim();
}

function findTextInDoc(doc, searchText) {
    const plainText = stripMarkdownBasic(searchText);
    if (!plainText) return null;

    let text = '';
    const posMap = [];

    doc.nodesBetween(0, doc.content.size, (node, pos) => {
        if (node.isText) {
            for (let i = 0; i < node.text.length; i++) {
                posMap.push(pos + i);
                text += node.text[i];
            }
        }
    });

    const idx = text.indexOf(plainText);
    if (idx === -1 || idx + plainText.length > posMap.length) return null;

    return {
        from: posMap[idx],
        to: posMap[idx + plainText.length - 1] + 1,
    };
}

function buildSuggestionDecorations(doc) {
    const decorations = [];
    for (const s of pendingSuggestions) {
        const range = findTextInDoc(doc, s.original_text);
        if (!range) continue;

        decorations.push(
            Decoration.inline(range.from, range.to, {
                class: 'suggestion-old',
                'data-suggestion-id': s.id,
            })
        );

        const textSpan = document.createElement('span');
        textSpan.className = 'suggestion-new';
        textSpan.textContent = ' ' + stripMarkdownBasic(s.suggested_text);

        const btnsSpan = document.createElement('span');
        btnsSpan.className = 'suggestion-btns';
        btnsSpan.innerHTML = `
            <button class="btn" title="Accept"
                style="padding:0.3rem;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;cursor:pointer;"
                onmouseover="this.style.backgroundColor='#dcfce7'" onmouseout="this.style.backgroundColor='#f0fdf4'"
                onclick="window.acceptSuggestion(this)">
                <span class="material-symbols-outlined" style="font-size:1.1rem;font-weight:600;">check</span>
            </button>
            <div style="width:1px;height:1.2rem;background:#e0e0e0;"></div>
            <button class="btn" title="Reject"
                style="padding:0.3rem;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;cursor:pointer;"
                onmouseover="this.style.backgroundColor='#fee2e2'" onmouseout="this.style.backgroundColor='#fef2f2'"
                onclick="window.rejectSuggestion(this)">
                <span class="material-symbols-outlined" style="font-size:1.1rem;font-weight:600;">close</span>
            </button>
        `;

        const widget = document.createElement('span');
        widget.className = 'suggestion-card suggestion-new-group';
        widget.dataset.suggestion = JSON.stringify({ id: s.id, original_text: s.original_text, suggested_text: s.suggested_text });
        widget.contentEditable = 'false';
        widget.appendChild(textSpan);
        widget.appendChild(btnsSpan);

        decorations.push(
            Decoration.widget(range.to, widget, { side: 1, key: `sug-new-${s.id}` })
        );
    }
    return DecorationSet.create(doc, decorations);
}

const suggestionPlugin = new Plugin({
    key: suggestionsPluginKey,
    state: {
        init(_, { doc }) {
            return buildSuggestionDecorations(doc);
        },
        apply(tr, old) {
            if (tr.getMeta(suggestionsPluginKey)) {
                return buildSuggestionDecorations(tr.doc);
            }
            return old.map(tr.mapping, tr.doc);
        },
    },
    props: {
        decorations(state) {
            return suggestionsPluginKey.getState(state);
        },
    },
});

const SuggestionDecorations = Extension.create({
    name: 'suggestionDecorations',
    addProseMirrorPlugins() {
        return [suggestionPlugin];
    },
});

function refreshDecorations() {
    if (!window.tiptapEditor) return;
    window.tiptapEditor.view.dispatch(
        window.tiptapEditor.state.tr.setMeta(suggestionsPluginKey, true)
    );
}

// Watch #inline-suggestions for cards added by HTMX (initial load or new creation).
// This avoids relying on HTMX event name casing which is unreliable across browsers.
function initSuggestionObserver() {
    const container = document.getElementById('inline-suggestions');
    if (!container) return;

    function absorbCard(node) {
        if (node.nodeType !== 1 || !node.dataset.suggestion) return;
        try {
            const s = JSON.parse(node.dataset.suggestion);
            if (s && s.id && !pendingSuggestions.some(p => p.id === s.id)) {
                pendingSuggestions.push(s);
                return true;
            }
        } catch(e) {}
        return false;
    }

    new MutationObserver((mutations) => {
        let changed = false;
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (absorbCard(node)) changed = true;
            }
        }
        if (changed) {
            refreshDecorations();
            // positionSuggestionCards is called inside refreshDecorations via rAF
        }
    }).observe(container, { childList: true });
}

window.acceptSuggestion = async function(btn) {
    const card = btn.closest('.suggestion-card');
    if (!card) return;
    const s = JSON.parse(card.dataset.suggestion);
    card.style.opacity = '0.5'; card.style.pointerEvents = 'none';
    document.getElementById(`suggestion-${s.id}`)?.remove();

    const range = findTextInDoc(window.tiptapEditor.state.doc, s.original_text);
    if (range) {
        window.tiptapEditor.chain()
            .deleteRange(range)
            .insertContentAt(range.from, stripMarkdownBasic(s.suggested_text))
            .run();
    }

    pendingSuggestions = pendingSuggestions.filter(p => p.id !== s.id);
    refreshDecorations();
    card.remove();

    try {
        await fetch(`/api/suggestions/${s.id}/accept`, { method: 'POST' });
    } catch(e) {
        console.error('[suggestion] accept failed:', e);
    }
};

window.rejectSuggestion = async function(btn) {
    const card = btn.closest('.suggestion-card');
    if (!card) return;
    const s = JSON.parse(card.dataset.suggestion);
    card.style.opacity = '0.5'; card.style.pointerEvents = 'none';
    document.getElementById(`suggestion-${s.id}`)?.remove();

    pendingSuggestions = pendingSuggestions.filter(p => p.id !== s.id);
    refreshDecorations();
    card.remove();

    try {
        await fetch(`/api/suggestions/${s.id}/reject`, { method: 'POST' });
    } catch(e) {
        console.error('[suggestion] reject failed:', e);
    }
};

// ── Editor ────────────────────────────────────────────────────────────────
const editor = new Editor({
    element: mountEl,
    extensions: [
        StarterKit.configure({ history: false }),
        Markdown,
        Focus.configure({ className: 'has-focus', mode: 'deepest' }),
        SuggestionDecorations,
    ],
    content: contentInput.value,
    onUpdate({ editor }) {
        const md = editor.storage.markdown.getMarkdown();
        contentInput.value = md;
        contentInput.dispatchEvent(new Event('tiptap-changed'));
        updateToolbar(editor);

        clearTimeout(historyDebounce);
        historyDebounce = setTimeout(() => {
            saveToHistory(md);
        }, 600); // 600ms inactivity before snapping history
    },
    onTransaction({ editor }) {
        updateToolbar(editor);
        updateAiButton(editor);
    },
});

window.tiptapEditor = editor;
mountEl.classList.remove('tiptap-editor--loading');
updateToolbar(editor);
initSuggestionObserver();

// ── Undo/redo buttons & Shortcuts ─────────────────────────────────────────
undoBtn.addEventListener('click', () => {
    if (!canUndoLocal()) return;
    lastChangeIsAi = false;
    localHistoryIndex--;
    const oldText = localHistory[localHistoryIndex];
    editor.commands.setContent(oldText, false);
    contentInput.value = oldText;
    contentInput.dispatchEvent(new Event('tiptap-changed'));
    updateToolbar(editor);
});

redoBtn.addEventListener('click', () => {
    if (!canRedoLocal()) return;
    localHistoryIndex++;
    const newText = localHistory[localHistoryIndex];
    editor.commands.setContent(newText, false);
    contentInput.value = newText;
    contentInput.dispatchEvent(new Event('tiptap-changed'));
    updateToolbar(editor);
});

mountEl.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        e.shiftKey ? redoBtn.click() : undoBtn.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        redoBtn.click();
    }
});

// ── Formatting buttons ────────────────────────────────────────────────────
fmtButtons.bold.addEventListener('click', () => editor.chain().focus().toggleBold().run());
fmtButtons.italic.addEventListener('click', () => editor.chain().focus().toggleItalic().run());
fmtButtons.h1.addEventListener('click', () => editor.chain().focus().toggleHeading({ level: 1 }).run());
fmtButtons.h2.addEventListener('click', () => editor.chain().focus().toggleHeading({ level: 2 }).run());
fmtButtons.h3.addEventListener('click', () => editor.chain().focus().toggleHeading({ level: 3 }).run());
fmtButtons.ul.addEventListener('click', () => editor.chain().focus().toggleBulletList().run());
fmtButtons.ol.addEventListener('click', () => editor.chain().focus().toggleOrderedList().run());
fmtButtons.quote.addEventListener('click', () => editor.chain().focus().toggleBlockquote().run());
fmtButtons.code.addEventListener('click', () => editor.chain().focus().toggleCodeBlock().run());
document.getElementById('fmt-hr').addEventListener('click', () => editor.chain().focus().setHorizontalRule().run());

// ── AI block button → open modal with block as context ────────────────────
import { findBlockInMarkdown } from './editor-utils.js';

// Highlight DOM nodes for a set of ProseMirror positions, return cleanup fn.
function highlightBlocks(positions) {
    const nodes = positions
        .map(pos => { try { return editor.view.nodeDOM(pos); } catch (_) { return null; } })
        .filter(n => n?.nodeType === 1);
    nodes.forEach(n => n.classList.add('ai-selected'));
    return () => nodes.forEach(n => n.classList.remove('ai-selected'));
}

let clearAiHighlight = null;

document.getElementById('command-modal').addEventListener('close', () => {
    clearAiHighlight?.();
    clearAiHighlight = null;
});

aiBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const { state } = editor;
    const { from, to, empty } = state.selection;
    const md    = editor.storage.markdown.getMarkdown();
    const lines = md.split('\n');

    let selStart, selEnd, selText;
    let blockPositions = [];

    console.log('[AI btn] click — empty:', empty, 'activeBlockPos:', activeBlockPos, 'node:', activeBlockNode?.textContent?.slice(0, 40));
    if (empty) {
        // Cursor only — use active block
        if (activeBlockPos === null || !activeBlockNode) { console.warn('[AI btn] no active block — pos:', activeBlockPos, 'node:', activeBlockNode); return; }
        const nodeText = activeBlockNode.textContent.trim();
        const found = findBlockInMarkdown(lines, nodeText);
        console.log('[AI btn] nodeText:', nodeText.slice(0, 60), '| found:', !!found);
        if (!found) return;
        selStart = found.start;
        selEnd   = found.end;
        selText  = md.slice(selStart, selEnd);
        blockPositions = [activeBlockPos];
    } else {
        // Text selection — collect all text blocks within [from, to]
        const blocks = [];
        state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.isTextblock && node.textContent.trim()) {
                blocks.push({ text: node.textContent.trim(), pos });
            }
        });
        if (blocks.length === 0) { console.warn('[AI btn] no blocks in selection'); return; }

        // Find first block, then subsequent blocks searching forward to avoid
        // false matches when two blocks have identical text.
        const first = findBlockInMarkdown(lines, blocks[0].text);
        if (!first) { console.warn('[AI btn] first block not found in markdown:', blocks[0].text.slice(0, 60)); return; }
        let last = first;
        let searchFrom = first.end;
        for (let i = 1; i < blocks.length; i++) {
            const found = findBlockInMarkdown(lines, blocks[i].text, searchFrom);
            if (!found) { console.warn('[AI btn] block not found:', blocks[i].text.slice(0, 60)); return; }
            last = found;
            searchFrom = found.end;
        }

        selStart = first.start;
        selEnd   = last.end;
        selText  = md.slice(selStart, selEnd);
        blockPositions = blocks.map(b => b.pos);
    }

    if (!selText) { console.warn('[AI btn] empty selText'); return; }

    clearAiHighlight?.();
    clearAiHighlight = highlightBlocks(blockPositions);

    pendingSelection = { start: selStart, end: selEnd, text: selText };
    document.getElementById('modal-sel-start').value = selStart;
    document.getElementById('modal-sel-end').value   = selEnd;
    document.getElementById('modal-sel-text').value  = selText;

    const preview = document.getElementById('modal-sel-preview');
    const previewText = document.getElementById('modal-sel-preview-text');
    if (selText) {
        previewText.textContent = `"${selText.length > 200 ? selText.slice(0, 200) + '…' : selText}"`;
        preview.removeAttribute('hidden');
    } else {
        preview.setAttribute('hidden', '');
    }

    const modal = document.getElementById('command-modal');
    modal.style.cssText = '';
    modal.showModal();
});

// ── OOB swap: chat agent replaces #document-content textarea ──────────────
const editorPane = mountEl.closest('.editor-pane');
new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (node.id === 'document-content') {
                htmx.process(node);
                lastChangeIsAi = true;
                editor.commands.setContent(node.value || '');
            }
        }
    }
}).observe(editorPane, { childList: true, subtree: true });

// ── Responsive toolbar overflow ────────────────────────────────────────────
const toolbarContainer = document.querySelector('.tiptap-editor');
if (toolbarContainer) {
    const updateOverflow = () => {
        const w = toolbarContainer.clientWidth;
        const hide3 = w < 640, hide2 = w < 470;
        document.querySelectorAll('.toolbar-overflow-group--3').forEach(el => el.style.display = hide3 ? 'none' : '');
        document.querySelectorAll('.toolbar-overflow-group--2').forEach(el => el.style.display = hide2 ? 'none' : '');
        document.querySelectorAll('.toolbar-overflow-section--3').forEach(el => el.style.display = hide3 ? 'block' : '');
        document.querySelectorAll('.toolbar-overflow-section--2').forEach(el => el.style.display = hide2 ? 'block' : '');
    };
    new ResizeObserver(updateOverflow).observe(toolbarContainer);
}
