import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { findBlockInMarkdown } from '../../static/editor-utils.js';

function lines(md) { return md.split('\n'); }

describe('findBlockInMarkdown', () => {

    describe('headings', () => {
        test('h1 plain text', () => {
            const result = findBlockInMarkdown(lines('# Hello World'), 'Hello World');
            assert.deepEqual(result, { start: 0, end: 13 });
        });

        test('h2 with numbered prefix is NOT stripped (bug fix)', () => {
            const md = '## 1. Introduction: The New Normal';
            const result = findBlockInMarkdown(lines(md), '1. Introduction: The New Normal');
            assert.deepEqual(result, { start: 0, end: md.length });
        });

        test('h2 without numbered prefix', () => {
            const md = '## Mastering Your Environment';
            const result = findBlockInMarkdown(lines(md), 'Mastering Your Environment');
            assert.deepEqual(result, { start: 0, end: md.length });
        });

        test('h3', () => {
            const md = '### Deep Dive';
            const result = findBlockInMarkdown(lines(md), 'Deep Dive');
            assert.deepEqual(result, { start: 0, end: md.length });
        });
    });

    describe('lists', () => {
        test('bullet item plain text', () => {
            const md = '- Simple bullet';
            const result = findBlockInMarkdown(lines(md), 'Simple bullet');
            assert.deepEqual(result, { start: 0, end: md.length });
        });

        test('bullet item with bold and escaped brackets', () => {
            const md = '- **Managing heat intolerance.**\\[content here\\]';
            const result = findBlockInMarkdown(lines(md), 'Managing heat intolerance.[content here]');
            assert.deepEqual(result, { start: 0, end: md.length });
        });

        test('numbered list item strips number prefix', () => {
            const md = '1. First item';
            const result = findBlockInMarkdown(lines(md), 'First item');
            assert.deepEqual(result, { start: 0, end: md.length });
        });

        test('numbered list item does not confuse heading with same text', () => {
            const md = '## 2. Section Title\n2. Section Title';
            const heading = findBlockInMarkdown(lines(md), '2. Section Title');
            // heading keeps its number; list item strips it — only the heading matches
            assert.deepEqual(heading, { start: 0, end: 19 });
        });
    });

    describe('inline formatting', () => {
        test('bold', () => {
            const result = findBlockInMarkdown(lines('**Bold text**'), 'Bold text');
            assert.deepEqual(result, { start: 0, end: 13 });
        });

        test('italic', () => {
            const result = findBlockInMarkdown(lines('*italic text*'), 'italic text');
            assert.deepEqual(result, { start: 0, end: 13 });
        });

        test('inline code', () => {
            const result = findBlockInMarkdown(lines('Use `npm install` here'), 'Use npm install here');
            assert.deepEqual(result, { start: 0, end: 22 });
        });

        test('strikethrough', () => {
            const result = findBlockInMarkdown(lines('~~old text~~'), 'old text');
            assert.deepEqual(result, { start: 0, end: 12 });
        });

        test('escaped brackets', () => {
            const result = findBlockInMarkdown(lines('See \\[content here\\]'), 'See [content here]');
            assert.deepEqual(result, { start: 0, end: 20 });
        });
    });

    describe('blockquote', () => {
        test('blockquote prefix stripped', () => {
            const md = '> Some quoted text';
            const result = findBlockInMarkdown(lines(md), 'Some quoted text');
            assert.deepEqual(result, { start: 0, end: md.length });
        });
    });

    describe('multiline and offset', () => {
        test('finds line in multiline markdown', () => {
            const md = '# Title\n\nSome paragraph\n\n## Section';
            // 'Some paragraph' starts at offset 9 (8 chars + newline)
            const result = findBlockInMarkdown(lines(md), 'Some paragraph');
            assert.deepEqual(result, { start: 9, end: 23 });
        });

        test('minOffset skips earlier matches', () => {
            const md = '- Item\n- Item';
            const first  = findBlockInMarkdown(lines(md), 'Item');
            const second = findBlockInMarkdown(lines(md), 'Item', first.end + 1);
            assert.deepEqual(first,  { start: 0, end: 6 });
            assert.deepEqual(second, { start: 7, end: 13 });
        });

        test('offset arithmetic accounts for newlines', () => {
            const md = 'line one\nline two\nline three';
            const result = findBlockInMarkdown(lines(md), 'line three');
            assert.deepEqual(result, { start: 18, end: 28 });
        });
    });

    describe('not found', () => {
        test('returns null when text not present', () => {
            const result = findBlockInMarkdown(lines('# Hello'), 'Goodbye');
            assert.equal(result, null);
        });

        test('returns null when all lines are before minOffset', () => {
            const md = '- Item';
            const result = findBlockInMarkdown(lines(md), 'Item', 999);
            assert.equal(result, null);
        });
    });
});
