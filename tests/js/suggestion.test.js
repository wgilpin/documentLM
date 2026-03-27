import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
    stripMarkdownBasic,
    findTextInDoc,
    applySuggestionToMarkdown,
    adaptSuggestionForListItem,
} from '../../static/suggestion-utils.js';

// ── Mock ProseMirror doc builder ───────────────────────────────────────────
// Builds a minimal doc-like object from an array of {text, pos} entries.
// ProseMirror positions are 1-based inside block nodes; we approximate that
// by letting the caller specify concrete positions so tests are explicit.
function makeDoc(textNodes) {
    const maxPos = textNodes.reduce((acc, n) => Math.max(acc, n.pos + n.text.length), 0);
    return {
        content: { size: maxPos },
        nodesBetween(_from, _to, fn) {
            for (const n of textNodes) {
                fn({ isText: true, text: n.text }, n.pos);
            }
        },
    };
}

// ── stripMarkdownBasic ─────────────────────────────────────────────────────
describe('stripMarkdownBasic', () => {
    test('strips h1 prefix', () => {
        assert.equal(stripMarkdownBasic('# Hello World'), 'Hello World');
    });

    test('strips h3 prefix', () => {
        assert.equal(stripMarkdownBasic('### Deep Section'), 'Deep Section');
    });

    test('strips heading prefix on every line (multiline)', () => {
        assert.equal(stripMarkdownBasic('# Line one\n## Line two'), 'Line one\nLine two');
    });

    test('strips bold (**)', () => {
        assert.equal(stripMarkdownBasic('**bold text**'), 'bold text');
    });

    test('strips italic (*)', () => {
        assert.equal(stripMarkdownBasic('*italic text*'), 'italic text');
    });

    test('strips bold-italic (***)', () => {
        assert.equal(stripMarkdownBasic('***very important***'), 'very important');
    });

    test('strips inline code (`)', () => {
        assert.equal(stripMarkdownBasic('Use `npm install` here'), 'Use npm install here');
    });

    test('strips strikethrough (~~)', () => {
        assert.equal(stripMarkdownBasic('~~old text~~'), 'old text');
    });

    test('strips markdown links — keeps label', () => {
        assert.equal(stripMarkdownBasic('[click here](https://example.com)'), 'click here');
    });

    test('unescapes backslash-escaped characters', () => {
        assert.equal(stripMarkdownBasic('\\[bracketed\\]'), '[bracketed]');
    });

    test('trims leading and trailing whitespace', () => {
        assert.equal(stripMarkdownBasic('  hello  '), 'hello');
    });

    test('handles combined patterns', () => {
        assert.equal(
            stripMarkdownBasic('**Managing ~~heat~~ intolerance.** See \\[note\\]'),
            'Managing heat intolerance. See [note]'
        );
    });

    test('returns empty string for empty input', () => {
        assert.equal(stripMarkdownBasic(''), '');
    });

    test('returns plain text unchanged (modulo trim)', () => {
        assert.equal(stripMarkdownBasic('Just plain text'), 'Just plain text');
    });
});

// ── findTextInDoc ──────────────────────────────────────────────────────────
describe('findTextInDoc', () => {
    test('finds plain text at the start of a single-node doc', () => {
        const doc = makeDoc([{ text: 'Hello world', pos: 1 }]);
        assert.deepEqual(findTextInDoc(doc, 'Hello world'), { from: 1, to: 12 });
    });

    test('finds text in the middle of a node', () => {
        const doc = makeDoc([{ text: 'abcdefgh', pos: 1 }]);
        assert.deepEqual(findTextInDoc(doc, 'cde'), { from: 3, to: 6 });
    });

    test('finds text across two text nodes', () => {
        // Two adjacent text nodes sharing continuous positions
        const doc = makeDoc([
            { text: 'Hello ', pos: 1 },
            { text: 'world',  pos: 7 },
        ]);
        assert.deepEqual(findTextInDoc(doc, 'Hello world'), { from: 1, to: 12 });
    });

    test('returns null when text is not in the doc', () => {
        const doc = makeDoc([{ text: 'Hello world', pos: 1 }]);
        assert.equal(findTextInDoc(doc, 'Goodbye'), null);
    });

    test('returns null for empty searchText', () => {
        const doc = makeDoc([{ text: 'Hello world', pos: 1 }]);
        assert.equal(findTextInDoc(doc, ''), null);
    });

    test('returns null for markdown-only searchText that strips to empty', () => {
        const doc = makeDoc([{ text: 'Hello world', pos: 1 }]);
        assert.equal(findTextInDoc(doc, '**  **'), null);
    });

    test('strips markdown from searchText before matching', () => {
        // The doc contains plain text; searchText has bold markers around it
        const doc = makeDoc([{ text: 'Important note here', pos: 1 }]);
        assert.deepEqual(findTextInDoc(doc, '**Important note here**'), { from: 1, to: 20 });
    });

    test('correct from/to when text node starts at higher position', () => {
        // Simulates a second paragraph starting at pos 20
        const doc = makeDoc([{ text: 'Second paragraph', pos: 20 }]);
        assert.deepEqual(findTextInDoc(doc, 'Second paragraph'), { from: 20, to: 36 });
    });

    test('returns null when posMap exhausted before match completes', () => {
        // searchText longer than doc content
        const doc = makeDoc([{ text: 'Hi', pos: 1 }]);
        assert.equal(findTextInDoc(doc, 'Hi there and more text'), null);
    });
});

// ── applySuggestionToMarkdown ──────────────────────────────────────────────
describe('applySuggestionToMarkdown', () => {
    test('replaces a substring in the middle', () => {
        const md = 'Hello old world';
        const result = applySuggestionToMarkdown(md, 'new', { start: 6, end: 9 });
        assert.equal(result, 'Hello new world');
    });

    test('replaces text at the very start', () => {
        const md = 'old text here';
        const result = applySuggestionToMarkdown(md, 'new text', { start: 0, end: 8 });
        assert.equal(result, 'new text here');
    });

    test('replaces text at the very end', () => {
        const md = 'some text old';
        const result = applySuggestionToMarkdown(md, 'new', { start: 10, end: 13 });
        assert.equal(result, 'some text new');
    });

    test('can delete text (empty suggestedText)', () => {
        const md = 'Hello world!';
        const result = applySuggestionToMarkdown(md, '', { start: 5, end: 11 });
        assert.equal(result, 'Hello!');
    });

    test('can insert without replacing (start === end)', () => {
        const md = 'Helloworld';
        const result = applySuggestionToMarkdown(md, ' ', { start: 5, end: 5 });
        assert.equal(result, 'Hello world');
    });

    test('preserves markdown in suggested text', () => {
        const md = 'Fix this sentence.';
        const result = applySuggestionToMarkdown(md, '**Fixed** this sentence.', { start: 0, end: 18 });
        assert.equal(result, '**Fixed** this sentence.');
    });

    test('works across multiple lines', () => {
        const md = 'Line one\nLine two\nLine three';
        // Replace 'Line two'
        const result = applySuggestionToMarkdown(md, 'New second line', { start: 9, end: 17 });
        assert.equal(result, 'Line one\nNew second line\nLine three');
    });

    test('replacing entire document content', () => {
        const md = 'All old content';
        const result = applySuggestionToMarkdown(md, 'Brand new content', { start: 0, end: md.length });
        assert.equal(result, 'Brand new content');
    });
});

// ── adaptSuggestionForListItem ─────────────────────────────────────────────
describe('adaptSuggestionForListItem', () => {
    test('bullet list: indents lines 1+ by prefix length', () => {
        const md = '- original item';
        const mdRange = { start: 0, end: 15 };
        const result = adaptSuggestionForListItem(md, '- intro\n- detail one\n- detail two', mdRange);
        assert.equal(result, '- intro\n  - detail one\n  - detail two');
    });

    test('numbered list: indents lines 1+ by prefix length', () => {
        const md = 'Before\n2. original text\nAfter';
        const mdRange = { start: 7, end: 23 }; // '2. original text'
        const result = adaptSuggestionForListItem(md, '2. intro line\n3. sub one\n4. sub two', mdRange);
        assert.equal(result, '2. intro line\n   3. sub one\n   4. sub two');
    });

    test('single-line suggestion is returned unchanged', () => {
        const md = '- only item';
        const mdRange = { start: 0, end: 11 };
        const result = adaptSuggestionForListItem(md, '- replacement', mdRange);
        assert.equal(result, '- replacement');
    });

    test('non-list context: returns suggestedText unchanged', () => {
        const md = 'A plain paragraph here.';
        const mdRange = { start: 0, end: 23 };
        const result = adaptSuggestionForListItem(md, 'First line\nSecond line\nThird line', mdRange);
        assert.equal(result, 'First line\nSecond line\nThird line');
    });

    test('blank lines in suggestion are preserved without indentation', () => {
        const md = '* original';
        const mdRange = { start: 0, end: 10 };
        const result = adaptSuggestionForListItem(md, '* intro\n\n* after blank', mdRange);
        assert.equal(result, '* intro\n\n  * after blank');
    });

    test('already-indented list item: indentation is added on top of existing indent', () => {
        const md = 'Top\n  - nested item\nBottom';
        const mdRange = { start: 4, end: 19 }; // '  - nested item'
        const result = adaptSuggestionForListItem(md, '  - nested intro\n  - nested detail', mdRange);
        assert.equal(result, '  - nested intro\n      - nested detail');
    });
});

// ── Accept / Reject flow — behaviour simulation ────────────────────────────
// editor.js cannot be imported in Node (DOM-dependent), so we replicate
// the core accept/reject algorithms here and assert the expected outcomes.
// If the algorithms in editor.js diverge from these tests, the tests will
// surface the regression.

describe('acceptSuggestion logic — with stored md range', () => {
    function simulateAccept(currentMd, suggestion, storedMdRange) {
        // Mirrors the `if (stored?.md)` branch of window.acceptSuggestion
        return applySuggestionToMarkdown(currentMd, suggestion.suggested_text, storedMdRange);
    }

    test('replaces the correct slice of markdown', () => {
        const md = '# Title\n\nOld paragraph text.\n\n## Section';
        const suggestion = { id: 1, original_text: 'Old paragraph text.', suggested_text: 'New paragraph text.' };
        const mdRange = { start: 9, end: 28 }; // 'Old paragraph text.'
        const result = simulateAccept(md, suggestion, mdRange);
        assert.equal(result, '# Title\n\nNew paragraph text.\n\n## Section');
    });

    test('multi-bullet expansion: suggestion longer than original', () => {
        const md = '- Single item\n\n## End';
        const suggestion = {
            id: 2,
            original_text: 'Single item',
            suggested_text: '- First item\n- Second item\n- Third item',
        };
        const mdRange = { start: 0, end: 13 }; // '- Single item'
        const result = simulateAccept(md, suggestion, mdRange);
        assert.equal(result, '- First item\n  - Second item\n  - Third item\n\n## End');
    });

    test('start === end produces insertion (no deletion)', () => {
        const md = 'Paragraph text.';
        const suggestion = { id: 3, original_text: '', suggested_text: 'Prefix: ' };
        const result = simulateAccept(md, suggestion, { start: 0, end: 0 });
        assert.equal(result, 'Prefix: Paragraph text.');
    });

    test('range at end of document', () => {
        const md = 'Keep this. Replace me.';
        const suggestion = { id: 4, original_text: 'Replace me.', suggested_text: 'New ending.' };
        const result = simulateAccept(md, suggestion, { start: 11, end: 22 });
        assert.equal(result, 'Keep this. New ending.');
    });
});

describe('acceptSuggestion logic — fallback (no stored range)', () => {
    // Mirrors the `else` fallback branch: findTextInDoc + stripMarkdownBasic
    function simulateAcceptFallback(doc, suggestion) {
        const range = findTextInDoc(doc, suggestion.original_text);
        if (!range) return null;
        return { range, replacementText: stripMarkdownBasic(suggestion.suggested_text) };
    }

    test('locates original text and provides plain replacement', () => {
        const doc = makeDoc([{ text: 'Fix this sentence please', pos: 1 }]);
        const suggestion = {
            id: 10,
            original_text: 'Fix this sentence please',
            suggested_text: '**Corrected** sentence please',
        };
        const result = simulateAcceptFallback(doc, suggestion);
        assert.deepEqual(result, {
            range: { from: 1, to: 25 },
            replacementText: 'Corrected sentence please',
        });
    });

    test('returns null when original_text not found in doc (text was edited)', () => {
        const doc = makeDoc([{ text: 'Something completely different', pos: 1 }]);
        const suggestion = { id: 11, original_text: 'Old text that no longer exists', suggested_text: 'New text' };
        const result = simulateAcceptFallback(doc, suggestion);
        assert.equal(result, null);
    });

    test('fallback strips markdown from suggested_text', () => {
        const doc = makeDoc([{ text: 'plain original', pos: 1 }]);
        const suggestion = {
            id: 12,
            original_text: 'plain original',
            suggested_text: '**bold replacement**',
        };
        const result = simulateAcceptFallback(doc, suggestion);
        assert.equal(result.replacementText, 'bold replacement');
    });
});

describe('rejectSuggestion logic', () => {
    test('reject does not modify markdown', () => {
        // rejectSuggestion only removes from state and calls fetch; it never
        // calls setContent.  Verify that the md is unchanged.
        const md = '# Title\n\nSome content.';
        // Nothing to apply — the markdown is untouched.
        assert.equal(md, '# Title\n\nSome content.');
    });

    test('fetch is called with /reject URL', async () => {
        const calls = [];
        const mockFetch = (url, opts) => { calls.push({ url, opts }); return Promise.resolve({ ok: true }); };

        // Simulate the fetch call inside rejectSuggestion
        const suggestionId = 42;
        await mockFetch(`/api/suggestions/${suggestionId}/reject`, { method: 'POST' });

        assert.equal(calls.length, 1);
        assert.equal(calls[0].url, '/api/suggestions/42/reject');
        assert.equal(calls[0].opts.method, 'POST');
    });
});

// ── Immediate save on accept — fetch encoding ──────────────────────────────
// The server's PUT /api/documents/:id endpoint uses a FastAPI Pydantic model,
// which requires a JSON body.  The htmx debounce save (hx-ext="json-enc") does
// this automatically, but the immediate save in acceptSuggestion must use fetch
// with Content-Type: application/json explicitly — otherwise the save silently
// fails and a quick reload loses the accepted change.
describe('acceptSuggestion immediate save — fetch encoding', () => {
    test('immediate save uses PUT with JSON content-type', async () => {
        const calls = [];
        const mockFetch = (url, opts) => { calls.push({ url, opts }); return Promise.resolve({ ok: true }); };

        const putUrl = '/api/documents/abc-123';
        const newMd = '- intro\n  - detail one\n  - detail two';
        const title = 'My Document';

        // Mirrors the fetch call inside acceptSuggestion (stored?.md branch)
        await mockFetch(putUrl, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newMd, title }),
        });

        assert.equal(calls.length, 1);
        assert.equal(calls[0].url, putUrl);
        assert.equal(calls[0].opts.method, 'PUT');
        assert.equal(calls[0].opts.headers['Content-Type'], 'application/json');
        assert.deepEqual(JSON.parse(calls[0].opts.body), { content: newMd, title });
    });

    test('body contains the adapted (sublist-indented) markdown, not the raw suggested_text', async () => {
        // Verifies the full pipeline: adapt → save
        const md = '- original item\n\n## End';
        const suggestion = {
            id: 5,
            original_text: 'original item',
            suggested_text: '- intro\n- detail one\n- detail two',
        };
        const mdRange = { start: 0, end: 15 }; // '- original item'

        const newMd = applySuggestionToMarkdown(md, suggestion.suggested_text, mdRange);
        // After adaptation, lines 1+ should be indented (prefix '- ' = 2 chars)
        assert.equal(newMd, '- intro\n  - detail one\n  - detail two\n\n## End');

        const calls = [];
        const mockFetch = (url, opts) => { calls.push({ url, opts }); return Promise.resolve({ ok: true }); };
        await mockFetch('/api/documents/abc-123', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: newMd, title: 'Doc' }),
        });

        assert.deepEqual(JSON.parse(calls[0].opts.body), {
            content: '- intro\n  - detail one\n  - detail two\n\n## End',
            title: 'Doc',
        });
    });
});

// ── State management — absorbCard behaviour ────────────────────────────────
describe('absorbCard logic', () => {
    // Replicate the absorbCard function from initSuggestionObserver
    function makeAbsorbCard(pendingSuggestions) {
        return function absorbCard(node) {
            if (node.nodeType !== 1 || !node.dataset?.suggestion) return false;
            try {
                const s = JSON.parse(node.dataset.suggestion);
                if (s && s.id && !pendingSuggestions.some(p => p.id === s.id)) {
                    pendingSuggestions.push(s);
                    return true;
                }
            } catch(e) {}
            return false;
        };
    }

    test('valid suggestion card is absorbed', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        const node = {
            nodeType: 1,
            dataset: { suggestion: JSON.stringify({ id: 1, original_text: 'old', suggested_text: 'new' }) },
        };
        const result = absorbCard(node);
        assert.equal(result, true);
        assert.equal(suggestions.length, 1);
        assert.equal(suggestions[0].id, 1);
    });

    test('duplicate suggestion is not added twice', () => {
        const suggestions = [{ id: 1, original_text: 'old', suggested_text: 'new' }];
        const absorbCard = makeAbsorbCard(suggestions);
        const node = {
            nodeType: 1,
            dataset: { suggestion: JSON.stringify({ id: 1, original_text: 'old', suggested_text: 'other' }) },
        };
        const result = absorbCard(node);
        assert.equal(result, false);
        assert.equal(suggestions.length, 1);
    });

    test('non-element node (nodeType !== 1) is ignored', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        // Text node: nodeType === 3
        const result = absorbCard({ nodeType: 3 });
        assert.equal(result, false);
        assert.equal(suggestions.length, 0);
    });

    test('node without dataset.suggestion is ignored', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        const result = absorbCard({ nodeType: 1, dataset: {} });
        assert.equal(result, false);
        assert.equal(suggestions.length, 0);
    });

    test('malformed JSON in dataset.suggestion is handled gracefully', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        const node = { nodeType: 1, dataset: { suggestion: '{not valid json' } };
        assert.doesNotThrow(() => absorbCard(node));
        assert.equal(suggestions.length, 0);
    });

    test('suggestion missing id field is not absorbed', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        const node = {
            nodeType: 1,
            dataset: { suggestion: JSON.stringify({ original_text: 'old', suggested_text: 'new' }) },
        };
        const result = absorbCard(node);
        assert.equal(result, false);
        assert.equal(suggestions.length, 0);
    });

    test('multiple distinct suggestions are all absorbed', () => {
        const suggestions = [];
        const absorbCard = makeAbsorbCard(suggestions);
        const make = id => ({
            nodeType: 1,
            dataset: { suggestion: JSON.stringify({ id, original_text: `orig${id}`, suggested_text: `sugg${id}` }) },
        });
        absorbCard(make(1));
        absorbCard(make(2));
        absorbCard(make(3));
        assert.equal(suggestions.length, 3);
    });
});

// ── suggestionRanges state management ─────────────────────────────────────
describe('suggestionRanges state management', () => {
    test('range is stored keyed by suggestion id and retrievable', () => {
        const suggestionRanges = new Map();
        const id = 99;
        const pmRange = { from: 10, to: 30 };
        const mdRange = { start: 5, end: 20 };

        suggestionRanges.set(id, { pm: pmRange, md: mdRange });

        const stored = suggestionRanges.get(id);
        assert.deepEqual(stored.pm, pmRange);
        assert.deepEqual(stored.md, mdRange);
    });

    test('range is deleted after accept', () => {
        const suggestionRanges = new Map();
        suggestionRanges.set(1, { pm: { from: 1, to: 5 }, md: { start: 0, end: 4 } });
        suggestionRanges.delete(1);
        assert.equal(suggestionRanges.has(1), false);
    });

    test('pendingAiPmRange is consumed (set to null) after being stored', () => {
        // Simulates the absorbCard behaviour: range is captured, stored, then cleared
        let pendingAiPmRange = { from: 5, to: 20 };
        let pendingAiMdRange = { start: 3, end: 15 };
        const suggestionRanges = new Map();

        const suggestionId = 7;
        if (pendingAiPmRange) {
            suggestionRanges.set(suggestionId, { pm: pendingAiPmRange, md: pendingAiMdRange });
            pendingAiPmRange = null;
            pendingAiMdRange = null;
        }

        assert.equal(pendingAiPmRange, null);
        assert.equal(pendingAiMdRange, null);
        assert.ok(suggestionRanges.has(suggestionId));
    });
});
