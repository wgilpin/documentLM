import { Editor }   from '@tiptap/core';
import StarterKit   from '@tiptap/starter-kit';
import Focus        from '@tiptap/extension-focus';
import { Markdown } from 'tiptap-markdown';

const mountEl      = document.getElementById('tiptap-mount');
const contentInput = document.getElementById('document-content');
const aiBtn        = document.getElementById('ai-block-btn');

let pendingSelection = { start: 0, end: 0, text: '' };
let lastChangeIsAi   = false;

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
    const canUndo = editor.can().undo();
    const canRedo = editor.can().redo();
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

// ── Editor ────────────────────────────────────────────────────────────────
const editor = new Editor({
    element: mountEl,
    extensions: [
        StarterKit,
        Markdown,
        Focus.configure({ className: 'has-focus', mode: 'deepest' }),
    ],
    content: contentInput.value,
    onUpdate({ editor }) {
        contentInput.value = editor.storage.markdown.getMarkdown();
        contentInput.dispatchEvent(new Event('tiptap-changed'));
        updateToolbar(editor);
    },
    onTransaction({ editor }) {
        updateToolbar(editor);
        updateAiButton(editor);
    },
});

window.tiptapEditor = editor;
mountEl.classList.remove('tiptap-editor--loading');
updateToolbar(editor);

// ── Undo/redo buttons ─────────────────────────────────────────────────────
undoBtn.addEventListener('click', () => {
    lastChangeIsAi = false;
    editor.chain().focus().undo().run();
});
redoBtn.addEventListener('click', () => editor.chain().focus().redo().run());

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
import { findBlockInMarkdown } from '/static/editor-utils.js';

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
