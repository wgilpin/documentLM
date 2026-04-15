import { Editor, Extension } from '@tiptap/core';
import StarterKit   from '@tiptap/starter-kit';
import Focus        from '@tiptap/extension-focus';
import { Markdown } from 'tiptap-markdown';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

// ── Chapter-aware globals ────────────────────────────────────────────────
const chapterList = document.getElementById('chapter-list');
const DOC_ID = chapterList ? chapterList.dataset.docId : 'unknown-doc';

let activeChapterId = null;
let mountEl = null;
let contentInput = null;
let aiBtn = null;

let pendingSelection = { start: 0, end: 0, text: '' };
let lastChangeIsAi   = false;

// ── Persistent LocalStorage History (per-chapter) ────────────────────────
let localHistory = [];
let localHistoryIndex = -1;
let historyDebounce = null;

function getHistoryKey() {
    return `tiptap-history-${DOC_ID}-${activeChapterId || 'default'}`;
}

function loadHistory() {
    localHistory = [];
    localHistoryIndex = -1;
    try {
        const saved = localStorage.getItem(getHistoryKey());
        if (saved) {
            localHistory = JSON.parse(saved);
            localHistoryIndex = localHistory.length - 1;
        }
    } catch(e) {}

    if (contentInput) {
        if (localHistory.length === 0) {
            localHistory.push(contentInput.value);
            localHistoryIndex = 0;
        } else if (localHistory[localHistoryIndex] !== contentInput.value) {
            localHistory.push(contentInput.value);
            localHistoryIndex++;
        }
    }
}

function saveToHistory(text) {
    if (localHistory[localHistoryIndex] === text) return;

    if (localHistoryIndex < localHistory.length - 1) {
        localHistory = localHistory.slice(0, localHistoryIndex + 1);
    }

    localHistory.push(text);
    if (localHistory.length > 50) localHistory.shift();
    localHistoryIndex = localHistory.length - 1;

    try { localStorage.setItem(getHistoryKey(), JSON.stringify(localHistory)); } catch(e) {}

    if (window.tiptapEditor) updateToolbar(window.tiptapEditor);
}

function canUndoLocal() { return localHistoryIndex > 0; }
function canRedoLocal() { return localHistoryIndex < localHistory.length - 1; }

// ── Active block tracking ─────────────────────────────────────────────────
let activeBlockPos  = null;
let activeBlockNode = null;

function updateAiButton(editor) {
    if (!mountEl || !aiBtn) return;
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

function getFmtActiveChecks(ed) {
    return [
        [fmtButtons.bold,   () => ed.isActive('bold')],
        [fmtButtons.italic, () => ed.isActive('italic')],
        [fmtButtons.h1,     () => ed.isActive('heading', { level: 1 })],
        [fmtButtons.h2,     () => ed.isActive('heading', { level: 2 })],
        [fmtButtons.h3,     () => ed.isActive('heading', { level: 3 })],
        [fmtButtons.ul,     () => ed.isActive('bulletList')],
        [fmtButtons.ol,     () => ed.isActive('orderedList')],
        [fmtButtons.quote,  () => ed.isActive('blockquote')],
        [fmtButtons.code,   () => ed.isActive('codeBlock')],
    ];
}

function updateToolbar(editor) {
    const canUndo = canUndoLocal();
    const canRedo = canRedoLocal();
    undoBtn.disabled = !canUndo;
    redoBtn.disabled = !canRedo;
    undoBtn.title = canUndo
        ? (lastChangeIsAi ? 'Undo AI change' : 'Undo')
        : 'Nothing to undo';
    redoBtn.title = canRedo ? 'Redo' : 'Nothing to redo';
    for (const [btn, check] of getFmtActiveChecks(editor)) {
        btn.classList.toggle('toolbar-btn--active', check());
    }
}

// ── Suggestion Decorations ─────────────────────────────────────────────────
const suggestionsPluginKey = new PluginKey('suggestions');
let pendingSuggestions = []; // [{id, original_text, suggested_text}]
let pendingAiPmRange = null;        // {from, to} captured at AI-button click time
let pendingAiMdRange = null;        // {start, end} markdown char offsets at AI-button click time
const suggestionRanges = new Map(); // suggestion id → {pm: {from,to}, md: {start,end}}


function buildSuggestionDecorations(doc) {
    const decorations = [];
    for (const s of pendingSuggestions) {
        const stored = suggestionRanges.get(s.id);
        const range = (stored?.pm) ?? findTextInDoc(doc, s.original_text);
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
function initSuggestionObserver() {
    const container = document.getElementById('inline-suggestions');
    if (!container) return;

    function absorbCard(node) {
        if (node.nodeType !== 1 || !node.dataset.suggestion) return;
        try {
            const s = JSON.parse(node.dataset.suggestion);
            if (s && s.id && !pendingSuggestions.some(p => p.id === s.id)) {
                pendingSuggestions.push(s);
                if (pendingAiPmRange) {
                    suggestionRanges.set(s.id, { pm: pendingAiPmRange, md: pendingAiMdRange });
                    pendingAiPmRange = null;
                    pendingAiMdRange = null;
                }
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
        }
    }).observe(container, { childList: true });
}

window.acceptSuggestion = async function(btn) {
    const card = btn.closest('.suggestion-card');
    if (!card) return;
    const s = JSON.parse(card.dataset.suggestion);
    card.style.opacity = '0.5'; card.style.pointerEvents = 'none';
    document.getElementById(`suggestion-${s.id}`)?.remove();

    const stored = suggestionRanges.get(s.id);
    if (stored?.md && contentInput) {
        const md = window.tiptapEditor.storage.markdown.getMarkdown();
        const newMd = applySuggestionToMarkdown(md, s.suggested_text, stored.md);
        window.tiptapEditor.commands.setContent(newMd);
        contentInput.value = newMd;
        // Save to the chapter endpoint
        const putUrl = contentInput.getAttribute('hx-put');
        if (putUrl) {
            fetch(putUrl, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: newMd }),
            }).catch(e => console.error('[suggestion] immediate save failed:', e));
        }
    } else {
        const range = findTextInDoc(window.tiptapEditor.state.doc, s.original_text);
        if (range) {
            window.tiptapEditor.chain()
                .deleteRange(range)
                .insertContentAt(range.from, stripMarkdownBasic(s.suggested_text))
                .run();
        }
    }

    pendingSuggestions = pendingSuggestions.filter(p => p.id !== s.id);
    suggestionRanges.delete(s.id);
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
    suggestionRanges.delete(s.id);
    refreshDecorations();
    card.remove();

    try {
        await fetch(`/api/suggestions/${s.id}/reject`, { method: 'POST' });
    } catch(e) {
        console.error('[suggestion] reject failed:', e);
    }
};

// ── Editor creation ──────────────────────────────────────────────────────
function createEditor(el, content) {
    return new Editor({
        element: el,
        extensions: [
            StarterKit.configure({ history: false }),
            Markdown,
            Focus.configure({ className: 'has-focus', mode: 'deepest' }),
            SuggestionDecorations,
        ],
        content: content,
        onUpdate({ editor }) {
            const md = editor.storage.markdown.getMarkdown();
            if (contentInput) {
                contentInput.value = md;
                contentInput.dispatchEvent(new Event('tiptap-changed'));
            }
            updateToolbar(editor);

            clearTimeout(historyDebounce);
            historyDebounce = setTimeout(() => {
                saveToHistory(md);
            }, 600);
        },
        onTransaction({ editor }) {
            updateToolbar(editor);
            updateAiButton(editor);
        },
    });
}

// ── Chapter activation ───────────────────────────────────────────────────
function saveCurrentChapter() {
    if (!window.tiptapEditor || !contentInput) return;
    const md = window.tiptapEditor.storage.markdown.getMarkdown();
    contentInput.value = md;
    // Trigger save via HTMX
    const putUrl = contentInput.getAttribute('hx-put');
    if (putUrl) {
        fetch(putUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: md }),
        }).catch(e => console.error('[chapter] save failed:', e));
    }
}

window.activateChapter = function activateChapter(chapterId, docId) {
    if (chapterId === activeChapterId) return;

    // Save current chapter
    saveCurrentChapter();

    // Destroy current editor
    if (window.tiptapEditor) {
        window.tiptapEditor.destroy();
        window.tiptapEditor = null;
    }

    // Capture previous ID before reassigning
    const prevChapterId = activeChapterId;
    activeChapterId = chapterId;

    // Convert previous active chapter to card via server-rendered HTML
    if (prevChapterId) {
        const prevEl = document.getElementById('chapter-' + prevChapterId);
        if (prevEl) {
            // PUT saves content, response is the rendered card partial
            fetch(`/api/documents/${docId}/chapters/${prevChapterId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'HX-Request': 'true' },
                body: JSON.stringify({}),
            }).then(r => r.text()).then(cardHtml => {
                // Use the server-rendered card directly
                prevEl.outerHTML = cardHtml;
                const newCard = document.getElementById('chapter-' + prevChapterId);
                if (newCard) htmx.process(newCard);
            }).catch(e => console.error('[chapter] save/card failed:', e));
        }
    }

    // Fetch the chapter editor partial
    fetch(`/api/documents/${docId}/chapters/${chapterId}`, {
        headers: { 'HX-Request': 'true' },
    }).then(r => r.text()).then(html => {
        const el = document.getElementById('chapter-' + chapterId);
        if (el) {
            el.outerHTML = html;
            htmx.process(document.getElementById('chapter-' + chapterId));
        }

        // Mount TipTap on the new chapter (scope to this chapter's element)
        const newChapterEl = document.getElementById('chapter-' + chapterId);
        mountEl = newChapterEl ? newChapterEl.querySelector('#tiptap-mount') : null;
        contentInput = newChapterEl ? newChapterEl.querySelector('.chapter-content-textarea') : null;
        aiBtn = newChapterEl ? newChapterEl.querySelector('#ai-block-btn') : null;

        if (mountEl && contentInput) {
            loadHistory();
            const editor = createEditor(mountEl, contentInput.value);
            window.tiptapEditor = editor;
            mountEl.classList.remove('tiptap-editor--loading');
            updateToolbar(editor);
        }
    });
};

window.scrollToChapter = function scrollToChapter(chapterId) {
    const el = document.getElementById('chapter-' + chapterId);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Activate on click from TOC
        const docId = chapterList ? chapterList.dataset.docId : '';
        if (docId) activateChapter(chapterId, docId);
    }
};

// ── Initial mount: activate the first chapter editor ─────────────────────
(function initFirstChapter() {
    const editorEl = document.querySelector('.chapter-editor');
    if (!editorEl) return;

    activeChapterId = editorEl.dataset.chapterId;
    mountEl = editorEl.querySelector('#tiptap-mount');
    contentInput = editorEl.querySelector('.chapter-content-textarea');
    aiBtn = editorEl.querySelector('#ai-block-btn');

    if (!mountEl || !contentInput) return;

    loadHistory();
    const editor = createEditor(mountEl, contentInput.value);
    window.tiptapEditor = editor;
    mountEl.classList.remove('tiptap-editor--loading');
    updateToolbar(editor);
    initSuggestionObserver();
})();

// ── Undo/redo buttons & Shortcuts ─────────────────────────────────────────
undoBtn.addEventListener('click', () => {
    if (!canUndoLocal() || !window.tiptapEditor) return;
    lastChangeIsAi = false;
    localHistoryIndex--;
    const oldText = localHistory[localHistoryIndex];
    window.tiptapEditor.commands.setContent(oldText, false);
    if (contentInput) {
        contentInput.value = oldText;
        contentInput.dispatchEvent(new Event('tiptap-changed'));
    }
    updateToolbar(window.tiptapEditor);
});

redoBtn.addEventListener('click', () => {
    if (!canRedoLocal() || !window.tiptapEditor) return;
    localHistoryIndex++;
    const newText = localHistory[localHistoryIndex];
    window.tiptapEditor.commands.setContent(newText, false);
    if (contentInput) {
        contentInput.value = newText;
        contentInput.dispatchEvent(new Event('tiptap-changed'));
    }
    updateToolbar(window.tiptapEditor);
});

document.addEventListener('keydown', (e) => {
    if (!mountEl || !mountEl.contains(e.target)) return;
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
fmtButtons.bold.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleBold().run());
fmtButtons.italic.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleItalic().run());
fmtButtons.h1.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleHeading({ level: 1 }).run());
fmtButtons.h2.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleHeading({ level: 2 }).run());
fmtButtons.h3.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleHeading({ level: 3 }).run());
fmtButtons.ul.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleBulletList().run());
fmtButtons.ol.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleOrderedList().run());
fmtButtons.quote.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleBlockquote().run());
fmtButtons.code.addEventListener('click', () => window.tiptapEditor?.chain().focus().toggleCodeBlock().run());
document.getElementById('fmt-hr').addEventListener('click', () => window.tiptapEditor?.chain().focus().setHorizontalRule().run());

// ── AI block button → open modal with block as context ────────────────────
import { findBlockInMarkdown } from './editor-utils.js';
import { stripMarkdownBasic, findTextInDoc, applySuggestionToMarkdown } from './suggestion-utils.js';

// Highlight DOM nodes for a set of ProseMirror positions, return cleanup fn.
function highlightBlocks(positions) {
    const editor = window.tiptapEditor;
    if (!editor) return () => {};
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

document.addEventListener('click', (e) => {
    if (!aiBtn || e.target !== aiBtn) return;
    e.stopPropagation();
    const editor = window.tiptapEditor;
    if (!editor) return;
    const { state } = editor;
    const { from, to, empty } = state.selection;
    const md    = editor.storage.markdown.getMarkdown();
    const lines = md.split('\n');

    let selStart, selEnd, selText;
    let blockPositions = [];

    if (empty) {
        if (activeBlockPos === null || !activeBlockNode) return;
        const nodeText = activeBlockNode.textContent.trim();
        const found = findBlockInMarkdown(lines, nodeText);
        if (!found) return;
        selStart = found.start;
        selEnd   = found.end;
        selText  = md.slice(selStart, selEnd);
        blockPositions = [activeBlockPos];
    } else {
        const blocks = [];
        state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.isTextblock && node.textContent.trim()) {
                blocks.push({ text: node.textContent.trim(), pos });
            }
        });
        if (blocks.length === 0) return;

        const first = findBlockInMarkdown(lines, blocks[0].text);
        if (!first) return;
        let last = first;
        let searchFrom = first.end;
        for (let i = 1; i < blocks.length; i++) {
            const found = findBlockInMarkdown(lines, blocks[i].text, searchFrom);
            if (!found) return;
            last = found;
            searchFrom = found.end;
        }

        selStart = first.start;
        selEnd   = last.end;
        selText  = md.slice(selStart, selEnd);
        blockPositions = blocks.map(b => b.pos);
    }

    if (!selText) return;

    if (empty) {
        pendingAiPmRange = {
            from: activeBlockPos + 1,
            to:   activeBlockPos + 1 + activeBlockNode.content.size,
        };
    } else {
        pendingAiPmRange = { from, to };
    }
    pendingAiMdRange = { start: selStart, end: selEnd };

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
const editorPane = document.querySelector('.editor-pane');
if (editorPane) {
    new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.id === 'document-content') {
                    htmx.process(node);
                    lastChangeIsAi = true;
                    if (window.tiptapEditor) {
                        window.tiptapEditor.commands.setContent(node.value || '');
                    }
                }
            }
        }
    }).observe(editorPane, { childList: true, subtree: true });
}

// ── Responsive toolbar overflow ────────────────────────────────────────────
const toolbarContainer = document.getElementById('middle-panel-editor');
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

// ── insertBoundedSuggestion: insert generated text at current cursor position ──
window.insertBoundedSuggestion = function insertBoundedSuggestion(text) {
    if (!window.tiptapEditor || !text) return;
    window.tiptapEditor.chain().focus().insertContent(text).run();
    const panel = document.getElementById('bounded-suggestion');
    if (panel) panel.remove();
    const bundlingPanel = document.getElementById('bundling-panel');
    if (bundlingPanel) bundlingPanel.remove();
};

// ── Bundling panel: shown on heading/empty block selection ────────────────
(function () {
    let _bundlingPanel = null;

    function _removeBundlingPanel() {
        if (_bundlingPanel) {
            _bundlingPanel.remove();
            _bundlingPanel = null;
        }
        const suggestionEl = document.getElementById('bounded-suggestion');
        if (suggestionEl) suggestionEl.remove();
    }

    function _createBundlingPanel(docId) {
        if (_bundlingPanel) return;

        const panel = document.createElement('div');
        panel.id = 'bundling-panel';
        panel.className = 'bundling-panel';
        panel.innerHTML = `
            <div class="bundling-panel-header">
                <strong>Generate with Evidence</strong>
                <button class="bundling-panel-close" title="Cancel, type myself">&#10005;</button>
            </div>
            <div class="bundling-snippets" id="bundling-snippets-list">
                <p class="bundling-loading">Loading snippets…</p>
            </div>
            <div class="bundling-intent-wrap">
                <textarea class="bundling-intent-input" placeholder="Describe what to write (required)…" maxlength="500" rows="3"></textarea>
                <div class="bundling-intent-count">0/500</div>
            </div>
            <div id="bundling-result"></div>
            <div class="bundling-actions">
                <button class="btn btn-primary bundling-generate-btn" disabled>Generate ✨</button>
                <button class="btn bundling-cancel-btn">Cancel / type myself</button>
            </div>
        `;

        document.body.appendChild(panel);
        _bundlingPanel = panel;

        const currentMountEl = document.getElementById('tiptap-mount');
        if (currentMountEl) {
            const rect = currentMountEl.getBoundingClientRect();
            panel.style.cssText = `position:fixed;z-index:8888;top:${Math.min(rect.top + 80, window.innerHeight - 400)}px;left:${Math.min(rect.right + 8, window.innerWidth - 360)}px;width:340px;`;
        }

        fetch(`/api/documents/${docId}/snippets`, {
            headers: { 'HX-Request': 'true' }
        }).then(r => r.text()).then(html => {
            const listEl = panel.querySelector('#bundling-snippets-list');
            if (!listEl) return;
            listEl.innerHTML = '<p class="bundling-snippets-label">Select snippets (optional):</p><div id="bundling-snippet-checkboxes"></div>';
            const checkboxes = panel.querySelector('#bundling-snippet-checkboxes');
            const tmp = document.createElement('div');
            tmp.innerHTML = html;
            const cards = tmp.querySelectorAll('.snippet-card');
            if (cards.length === 0) {
                checkboxes.innerHTML = '<p class="bundling-no-snippets">No snippets in bank.</p>';
            } else {
                cards.forEach(card => {
                    const id = card.id.replace('snippet-', '');
                    const text = card.querySelector('.snippet-text')?.textContent?.trim() || '';
                    const label = document.createElement('label');
                    label.className = 'bundling-snippet-label';
                    label.innerHTML = `<input type="checkbox" value="${id}"> <span>${text.substring(0, 80)}${text.length > 80 ? '…' : ''}</span>`;
                    checkboxes.appendChild(label);
                });
            }
        });

        const intentInput = panel.querySelector('.bundling-intent-input');
        const intentCount = panel.querySelector('.bundling-intent-count');
        const generateBtn = panel.querySelector('.bundling-generate-btn');

        intentInput.addEventListener('input', () => {
            const len = intentInput.value.length;
            intentCount.textContent = `${len}/500`;
            generateBtn.disabled = len === 0;
        });

        generateBtn.addEventListener('click', async () => {
            const intent = intentInput.value.trim();
            if (!intent) return;

            const checkedBoxes = panel.querySelectorAll('#bundling-snippet-checkboxes input[type="checkbox"]:checked');
            const snippetIds = Array.from(checkedBoxes).map(cb => cb.value);

            const cursorContext = (() => {
                if (!window.tiptapEditor) return '';
                const { state } = window.tiptapEditor;
                const { $from } = state.selection;
                return $from.node($from.depth)?.textContent || '';
            })();

            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating…';

            try {
                const resp = await fetch(`/api/documents/${docId}/bounded-generate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'HX-Request': 'true' },
                    body: JSON.stringify({ snippet_ids: snippetIds, intent, cursor_context: cursorContext }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    alert('Generation failed: ' + (err.detail || resp.status));
                    return;
                }
                const html = await resp.text();
                const resultEl = panel.querySelector('#bundling-result');
                if (resultEl) {
                    resultEl.innerHTML = html;
                    const suggestion = resultEl.querySelector('#bounded-suggestion');
                    if (suggestion) {
                        const text = suggestion.dataset.suggestedText;
                        if (text) window.insertBoundedSuggestion(text);
                    }
                }
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate ✨';
            }
        });

        panel.querySelector('.bundling-cancel-btn').addEventListener('click', _removeBundlingPanel);
        panel.querySelector('.bundling-panel-close').addEventListener('click', _removeBundlingPanel);

        return panel;
    }

    function _setupBundlingTrigger() {
        if (!window.tiptapEditor) return;

        window.tiptapEditor.on('selectionUpdate', ({ editor }) => {
            const { state } = editor;
            const { $from } = state.selection;
            const node = $from.node($from.depth);

            const isHeading = node.type.name === 'heading';
            const isEmpty = node.textContent.trim() === '';

            if ((isHeading || isEmpty) && DOC_ID && DOC_ID !== 'unknown-doc') {
                if (!_bundlingPanel) {
                    _createBundlingPanel(DOC_ID);
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(_setupBundlingTrigger, 500));
    } else {
        setTimeout(_setupBundlingTrigger, 500);
    }
}());

// ── Document View: text selection → Save to Scratchpad ────────────────────
(function () {
    let _saveTooltip = null;

    function _removeTooltip() {
        if (_saveTooltip) {
            _saveTooltip.remove();
            _saveTooltip = null;
        }
    }

    document.addEventListener('mouseup', function (e) {
        if (_saveTooltip && _saveTooltip.contains(e.target)) return;

        const sourceBody = document.getElementById('source-view-body');
        if (!sourceBody) { _removeTooltip(); return; }
        if (!sourceBody.contains(e.target)) { _removeTooltip(); return; }

        const sel = window.getSelection();
        const selText = sel ? sel.toString().trim() : '';
        if (!selText) { _removeTooltip(); return; }

        let charOffset = 0;
        let node = sel.anchorNode;
        while (node && node !== sourceBody) {
            if (node.dataset && node.dataset.charOffset !== undefined) {
                charOffset = parseInt(node.dataset.charOffset, 10) || 0;
                break;
            }
            node = node.parentElement;
        }

        _removeTooltip();
        const tooltip = document.createElement('div');
        tooltip.className = 'snippet-save-tooltip';
        tooltip.textContent = 'Save to Scratchpad';
        tooltip.style.cssText = 'position:fixed;z-index:9999;background:#1a1a2e;color:#fff;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:0.85rem;';
        tooltip.style.left = e.clientX + 'px';
        tooltip.style.top = (e.clientY - 36) + 'px';
        document.body.appendChild(tooltip);
        _saveTooltip = tooltip;

        tooltip.addEventListener('click', function () {
            const docId = DOC_ID;
            const sourceViewContent = document.getElementById('source-view-content');
            const sourceId = sourceViewContent ? sourceViewContent.dataset.sourceId : null;

            const payload = { text: selText, char_offset: charOffset };
            if (sourceId) payload.source_id = sourceId;

            fetch('/api/documents/' + docId + '/snippets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'HX-Request': 'true' },
                body: JSON.stringify(payload),
            }).then(function (resp) {
                if (!resp.ok) return;
                return resp.text();
            }).then(function (html) {
                if (!html) return;
                const snippetList = document.getElementById('snippet-list');
                if (snippetList) {
                    const empty = snippetList.querySelector('.snippet-bank-empty');
                    if (empty) empty.remove();
                    const el = document.createElement('div');
                    el.innerHTML = html;
                    snippetList.prepend(el.firstChild);
                }
                if (typeof switchRightTab === 'function') switchRightTab('snippets');
            });
            _removeTooltip();
        });
    });

    document.addEventListener('mousedown', function (e) {
        if (_saveTooltip && !_saveTooltip.contains(e.target)) {
            _removeTooltip();
        }
    });
}());

// ── scrollToCharOffset: scroll Document View to a given character offset ──
window.scrollToCharOffset = function scrollToCharOffset(sourceId, offset) {
    function _scrollToOffset() {
        const container = document.getElementById('source-view-body');
        if (!container) return;
        const paras = container.querySelectorAll('[data-char-offset]');
        let best = null;
        let bestOff = -1;
        paras.forEach(function (el) {
            const elOff = parseInt(el.dataset.charOffset, 10);
            if (elOff <= offset && elOff > bestOff) {
                bestOff = elOff;
                best = el;
            }
        });
        if (best) {
            best.scrollIntoView({ behavior: 'smooth', block: 'start' });
            best.classList.add('source-para--highlight');
            setTimeout(function () { best.classList.remove('source-para--highlight'); }, 2000);
        }
    }

    if (typeof switchMiddleTab === 'function') switchMiddleTab('source-viewer');

    const viewContent = document.getElementById('source-view-content');
    if (viewContent && viewContent.dataset.sourceId === sourceId) {
        _scrollToOffset();
        return;
    }

    const target = document.getElementById('source-view-container');
    if (!target) return;
    fetch('/api/sources/' + sourceId + '/view', { headers: { 'HX-Request': 'true' } })
        .then(function (resp) { return resp.ok ? resp.text() : null; })
        .then(function (html) {
            if (!html) return;
            target.innerHTML = html;
            _scrollToOffset();
        });
};

// ── Toolbar dropdown close on click ────────────────────────────────────────
document.addEventListener('click', () => {
    const m = document.getElementById('toolbar-more-menu');
    if (m) m.hidden = true;
});
