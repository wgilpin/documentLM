/**
 * Find a block's location in a markdown string by matching its plain-text
 * content against each line (after stripping markdown syntax).
 *
 * @param {string[]} lines     - The markdown split on '\n'
 * @param {string}   nodeText  - Plain-text content of the ProseMirror node
 * @param {number}   minOffset - Skip lines whose start offset < minOffset
 * @returns {{ start: number, end: number } | null}
 */
export function findBlockInMarkdown(lines, nodeText, minOffset = 0) {
    let offset = 0;
    for (const line of lines) {
        if (offset >= minOffset) {
            const isHeading = /^#{1,6}\s+/.test(line);
            let plain = line
                .replace(/^#{1,6}\s+/, '')
                .replace(/^[-*+]\s+/, '');
            if (!isHeading) plain = plain.replace(/^\d+\.\s+/, '');
            plain = plain
                .replace(/^>\s*/, '')
                .replace(/\*\*(.+?)\*\*/g, '$1')
                .replace(/\*(.+?)\*/g, '$1')
                .replace(/`(.+?)`/g, '$1')
                .replace(/~~(.+?)~~/g, '$1')
                .replace(/\\(.)/g, '$1')
                .trim();
            if (plain === nodeText) {
                return { start: offset, end: offset + line.length };
            }
        }
        offset += line.length + 1;
    }
    return null;
}
