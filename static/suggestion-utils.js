/**
 * Pure utility functions for the AI suggestion / accept flow.
 * Extracted here so they can be tested without the full editor DOM environment.
 */

/**
 * Strip common markdown syntax from a string, returning plain text.
 * Used to match ProseMirror node text (which is already plain) against
 * markdown source that may contain decoration characters.
 *
 * @param {string} text
 * @returns {string}
 */
export function stripMarkdownBasic(text) {
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

/**
 * Find a plain-text substring inside a ProseMirror document, returning the
 * ProseMirror {from, to} positions.  The searchText is stripped of markdown
 * before matching so that a markdown original_text can locate its rendered
 * position.
 *
 * @param {import('@tiptap/pm/model').Node} doc
 * @param {string} searchText
 * @returns {{ from: number, to: number } | null}
 */
export function findTextInDoc(doc, searchText) {
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

/**
 * When a suggestion replaces a list item and contains multiple lines,
 * indent lines after the first to create a nested sublist at the
 * original item's indentation level.
 *
 * @param {string} md           Full markdown source
 * @param {string} suggestedText The replacement text
 * @param {{ start: number, end: number }} mdRange Offsets into md
 * @returns {string} Adapted suggestedText (unchanged when not applicable)
 */
export function adaptSuggestionForListItem(md, suggestedText, mdRange) {
    const originalLine = md.slice(mdRange.start, mdRange.end);
    const prefixMatch = originalLine.match(/^(\s*(?:\d+\.|[-*+])\s+)/);
    if (!prefixMatch) return suggestedText;

    const indent = ' '.repeat(prefixMatch[1].length);
    const lines = suggestedText.split('\n');
    if (lines.length <= 1) return suggestedText;

    return lines
        .map((line, i) => (i === 0 || line === '') ? line : indent + line)
        .join('\n');
}

/**
 * Splice a suggestion's text into a markdown string at the given character
 * offsets, returning the resulting markdown.
 *
 * @param {string} md           Full markdown source
 * @param {string} suggestedText The replacement text (may include markdown)
 * @param {{ start: number, end: number }} mdRange Offsets into md
 * @returns {string}
 */
export function applySuggestionToMarkdown(md, suggestedText, mdRange) {
    const adaptedText = adaptSuggestionForListItem(md, suggestedText, mdRange);
    return md.slice(0, mdRange.start) + adaptedText + md.slice(mdRange.end);
}
