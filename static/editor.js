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
            const domNode = view.nodeDOM(activeBlockPos);
            if (domNode?.nodeType === 1) {
                const wrapperRect = mountEl.getBoundingClientRect();
                const rect        = domNode.getBoundingClientRect();
                aiBtn.style.top     = (rect.top - wrapperRect.top + mountEl.scrollTop) + 'px';
                aiBtn.style.display = 'block';
                return;
            }
        } catch (_) {}
    }
    aiBtn.style.display = 'none';
    activeBlockPos  = null;
    activeBlockNode = null;
}

// ── Undo/redo toolbar ─────────────────────────────────────────────────────
const undoBtn = document.getElementById('undo-btn');
const redoBtn = document.getElementById('redo-btn');

function updateToolbar(editor) {
    const canUndo = editor.can().undo();
    const canRedo = editor.can().redo();
    undoBtn.disabled = !canUndo;
    redoBtn.disabled = !canRedo;
    undoBtn.title = canUndo
        ? (lastChangeIsAi ? 'Undo AI change' : 'Undo')
        : 'Nothing to undo';
    redoBtn.title = canRedo ? 'Redo' : 'Nothing to redo';
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

// ── AI block button → open modal with block as context ────────────────────

// Find a block's markdown line by matching plain text, searching forward from minOffset.
function findBlockInMarkdown(lines, nodeText, minOffset = 0) {
    let offset = 0;
    for (const line of lines) {
        if (offset >= minOffset) {
            const plain = line
                .replace(/^#{1,6}\s+/, '')
                .replace(/^[-*+]\s+/, '')
                .replace(/^\d+\.\s+/, '')
                .trim();
            if (plain === nodeText) {
                return { start: offset, end: offset + line.length };
            }
        }
        offset += line.length + 1;
    }
    return null;
}

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

aiBtn.addEventListener('click', () => {
    const { state } = editor;
    const { from, to, empty } = state.selection;
    const md    = editor.storage.markdown.getMarkdown();
    const lines = md.split('\n');

    let selStart, selEnd, selText;
    let blockPositions = [];

    if (empty) {
        // Cursor only — use active block
        if (activeBlockPos === null || !activeBlockNode) return;
        const found = findBlockInMarkdown(lines, activeBlockNode.textContent.trim());
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
        if (blocks.length === 0) return;

        // Find first block, then subsequent blocks searching forward to avoid
        // false matches when two blocks have identical text.
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

    console.log('[AI btn] selStart=%d selEnd=%d selText=%o', selStart, selEnd, selText);

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
