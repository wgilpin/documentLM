import pytest
from writer.services.document_service import find_fuzzy_block


def test_fuzzy_block_perfect_match():
    content = "Prefix. ~~old word~~ ***new word*** Suffix."
    old_text = "old word"
    new_text = "new word"
    start_hint = 8

    start_idx, end_idx = find_fuzzy_block(content, old_text, new_text, start_hint)
    assert start_idx != -1
    assert end_idx != -1
    assert content[start_idx:end_idx] == "~~old word~~ ***new word***"


def test_fuzzy_block_tiptap_escaped():
    # TipTap sometimes escapes brackets or formatting with backslashes
    content = "Prefix. \~\\~old word\\~\\~ \*\*\*new word\*\*\* Suffix."
    old_text = "old word"
    new_text = "new word"
    start_hint = 8

    start_idx, end_idx = find_fuzzy_block(content, old_text, new_text, start_hint)
    assert start_idx != -1
    assert content[start_idx:end_idx].startswith(r"\~\~")
    assert content[start_idx:end_idx].endswith(r"\*\*\*")


def test_fuzzy_block_trailing_punctuation():
    # TipTap could push trailing punctuation attached to words.
    content = "Text. ~~old text.~~ ***new text.*** Next."
    old_text = "old text."
    new_text = "new text."
    start_hint = 6

    start_idx, end_idx = find_fuzzy_block(content, old_text, new_text, start_hint)
    assert start_idx != -1
    assert content[start_idx:end_idx] == "~~old text.~~ ***new text.***"


def test_fuzzy_block_multi_line_markdown():
    # Because of our format logic, multiline blocks receive individual tags per line
    content = "Top.\n~~old 1~~\n~~old 2~~\n***new 1***\n***new 2.\n*** Bottom."
    
    # Notice that the user text contains punctuation
    old_text = "old 1\nold 2"
    new_text = "new 1\nnew 2."
    start_hint = 5

    start_idx, end_idx = find_fuzzy_block(content, old_text, new_text, start_hint)
    assert start_idx != -1
    assert end_idx != -1
    
    extracted = content[start_idx:end_idx]
    # It must capture the final asterisk sequence after the new text finishes
    assert extracted.startswith("~~old")
    assert extracted.endswith("***")


def test_fuzzy_block_collision_avoidance():
    # Ensure start_hint prevents it from picking up a duplicate older text block
    content = "~~old dup~~ ***new dup*** ... some long text ... ~~old target~~ ***new target***"
    
    old_text = "old target"
    new_text = "new target"
    
    # We tell it to look near index 50, avoiding the duplicate at index 0
    start_hint = 50
    start_idx, end_idx = find_fuzzy_block(content, old_text, new_text, start_hint)
    
    assert start_idx > 10 # It explicitly skips the first duplicate block!
    assert content[start_idx:end_idx] == "~~old target~~ ***new target***"


def test_fuzzy_block_handles_no_words():
    # If the text has no alphanumerics, fallback should gracefully abort
    content = "~~!!!~~ ***...***"
    start_idx, end_idx = find_fuzzy_block(content, "!!!", "...", 0)
    assert start_idx == -1
    assert end_idx == -1
