def get_tag_at_cursor(prompt_text: str, cursor_pos: int) -> tuple[str | None, int, int]:
    """
    Identifies the tag at the given cursor position in the prompt string.
    A tag is a segment of text separated by commas, unless the comma is within parentheses.
    Returns:
        - The stripped tag string (or "" if segment is empty/all spaces).
        - The start index of the raw segment in the original prompt_text.
        - The end index of the raw segment (comma position or EOL) in the original prompt_text.
    If no tag is found for the cursor position, returns (None, -1, -1).
    """
    search_start_idx_raw = 0
    paren_level = 0

    for i, char in enumerate(prompt_text):
        if char == '(':
            paren_level += 1
        elif char == ')':
            if paren_level > 0:
                paren_level -= 1
        elif char == ',' and paren_level == 0:
            # Current raw segment is prompt_text[search_start_idx_raw : i]
            # i is the index of the comma.
            if search_start_idx_raw <= cursor_pos <= i: # Cursor in this raw segment's span (inclusive of comma for left-association)
                stripped_content = prompt_text[search_start_idx_raw:i].strip()
                return stripped_content if stripped_content else "", search_start_idx_raw, i

            search_start_idx_raw = i + 1 # Next raw segment starts after this comma

    # After the loop, check the last segment (or the only segment if no commas)
    # This segment runs from search_start_idx_raw to the end of the prompt.
    if search_start_idx_raw <= cursor_pos <= len(prompt_text):
        stripped_content = prompt_text[search_start_idx_raw:].strip()
        return stripped_content if stripped_content else "", search_start_idx_raw, len(prompt_text)

    return None, -1, -1

if __name__ == '__main__':
    def run_test(prompt, cursor, expected_tag, expected_raw_start, expected_raw_end):
        tag, raw_start, raw_end = get_tag_at_cursor(prompt, cursor)
        print(f"Prompt: '{prompt}', Cursor: {cursor}")
        print(f"  -> Got: ('{tag}', {raw_start}, {raw_end})")
        print(f"  -> Exp: ('{expected_tag}', {expected_raw_start}, {expected_raw_end})")
        assert tag == expected_tag and raw_start == expected_raw_start and raw_end == expected_raw_end
        print("  OK")

    run_test("tag1", 0, "tag1", 0, 4)
    run_test("tag1", 3, "tag1", 0, 4)
    run_test("tag1", 4, "tag1", 0, 4)

    run_test("tag1, tag2", 0, "tag1", 0, 4)
    run_test("tag1, tag2", 3, "tag1", 0, 4)
    run_test("tag1, tag2", 4, "tag1", 0, 4) # On comma, associated with "tag1" (raw segment [0,4])
    run_test("tag1, tag2", 5, "tag2", 5, 10) # Cursor on space. Raw segment " tag2" is [5,10]. Stripped "tag2".
    run_test("tag1, tag2", 6, "tag2", 5, 10) # Cursor on 't'. Raw segment " tag2" is [5,10]. Stripped "tag2".

    run_test("  leading space, tag2", 0, "leading space", 0, 15) # Raw seg "  leading space" is [0,15]
    run_test("  leading space, tag2", 1, "leading space", 0, 15)
    run_test("  leading space, tag2", 2, "leading space", 0, 15)
    run_test("  leading space, tag2", 14, "leading space", 0, 15)
    run_test("  leading space, tag2", 15, "leading space", 0, 15)

    run_test("tag with space, tag2", 10, "tag with space", 0, 14)
    run_test("tag (with parens), tag2", 0, "tag (with parens)", 0, 17)
    run_test("tag (with parens), tag2", 5, "tag (with parens)", 0, 17)
    run_test("tag (with parens), tag2", 17, "tag (with parens)", 0, 17)

    # Prompt: "tag1,middle (paren, still middle),tag3"
    # "tag1" segment: [0,4] (ends at first comma)
    # "middle (paren, still middle)" segment: [5,33] (starts after first comma, ends at second comma)
    # "tag3" segment: [34,38] (starts after second comma, ends at EOL)
    run_test("tag1,middle (paren, still middle),tag3", 15, "middle (paren, still middle)", 5, 33)

    run_test("tag1,,tag3", 0, "tag1", 0, 4)
    run_test("tag1,,tag3", 4, "tag1", 0, 4)
    run_test("tag1,,tag3", 5, "", 5, 5)    # Empty raw segment [5,5]
    run_test("tag1,,tag3", 6, "tag3", 6, 10) # Raw segment "tag3" is [6,10] (after empty segment)

    run_test("size difference, other", 0, "size difference", 0, 15)
    run_test("size difference, other", 4, "size difference", 0, 15)
    run_test("size difference, other", 5, "size difference", 0, 15)
    run_test("size difference, other", 15, "size difference", 0, 15)

    run_test("trailing space  ", 0, "trailing space", 0, 16)
    run_test("trailing space  ", 15, "trailing space", 0, 16)
    run_test("trailing space  ", 16, "trailing space", 0, 16)

    run_test("", 0, "", 0, 0)
    run_test("   ", 0, "", 0, 3) # Raw segment is "   "
    run_test("   ", 3, "", 0, 3)

    print("All get_tag_at_cursor tests passed.")

import re

def apply_weight_to_tag(
    prompt_text: str,
    stripped_tag_content: str,
    raw_segment_start_idx: int,
    raw_segment_end_idx: int,
    direction: str,
    weight_step: float = 0.1,
    max_weight: float = 2.0, # Max weight typically used
    min_weight_remove: float = 0.1 # Below this, tag is de-emphasized or weight removed
) -> str:
    """
    Applies or adjusts weight to a specific tag segment in the prompt.
    - prompt_text: The full original prompt.
    - stripped_tag_content: The identified tag, stripped of whitespace and any existing weighting.
    - raw_segment_start_idx: The start index of the raw segment in prompt_text that contains this tag.
    - raw_segment_end_idx: The end index of the raw segment.
    - direction: "up" or "down".
    - weight_step: How much to change the weight by.
    """
    if stripped_tag_content is None:
        return prompt_text

    effective_weight = 1.0
    # Start with the assumption that stripped_tag_content is the base text
    current_processing_text = stripped_tag_content
    final_base_tag_text = stripped_tag_content # This will be updated if unwrapping occurs

    # Iteratively unwrap to find the innermost content and the outermost weight
    # Regex: r"\s*\((.*):\s*([\d.]+)\s*\)\s*"
    # \s*\(   : Optional whitespace then an opening parenthesis
    # (.*)    : Group 1, captures the content (non-greedy due to later parts of regex with re.fullmatch)
    #           For content that might have balanced parens not part of weighting, this is okay.
    #           If content can have unbalanced parens or colons, this regex might need to be more specific
    #           like ([^:]+) for the part before colon if colon is not allowed in base tag text.
    #           However, `(.*)` is generally fine for `(content:weight)` if `content` is simple or balanced.
    # :\s*    : A colon, followed by optional whitespace
    # ([\d.]+) : Group 2, captures the weight (digits and dots)
    # \s*\)\s* : Optional whitespace then a closing parenthesis, optional trailing whitespace
    # re.DOTALL might be useful if content could span newlines, but typically tags are single line.

    # More precise regex for typical A1111 prompt syntax:
    # It assumes the "content" part does not contain a colon followed by numbers at its very end.
    # This regex tries to capture "anything" as content, then weight.
    # `\s*\((.+?):\s*([\d.]+)\s*\)\s*` with `re.DOTALL` might be safer if content can be complex
    # but `(.+)` is greedy. `([^:]+)` is good if no colons in base tag.
    # Using `(.*)` with `fullmatch` is usually okay as it forces the whole string to fit the pattern.

    _pattern = re.compile(r"\s*\((.*):\s*([\d.]+)\s*\)\s*")

    temp_base = current_processing_text
    while True:
        match = _pattern.fullmatch(temp_base)
        if match:
            effective_weight = float(match.group(2)) # Outermost weight found
            temp_base = match.group(1).strip()       # New potential base
            final_base_tag_text = temp_base          # Update final base
        else:
            final_base_tag_text = temp_base.strip() # Ensure the final one is stripped
            break

    # Handle case where original stripped_tag_content was just "tag" (no parens, no weight)
    # In this case, the loop above won't run, effective_weight remains 1.0,
    # and final_base_tag_text is the original stripped_tag_content. This is correct.

    if direction == "up":
        new_weight = round(effective_weight + weight_step, 2)
        if new_weight > max_weight:
            new_weight = max_weight
    elif direction == "down":
        new_weight = round(effective_weight - weight_step, 2) # Corrected: use effective_weight
        if new_weight < 0:
            new_weight = 0
    else:
        return prompt_text

    # Formatting the new tag
    new_tag_str = ""
    # If final_base_tag_text became empty through stripping (e.g. original was "(( :0.5):0.8)")
    # and new weight is 1.0, new_tag_str should be empty.
    # If final_base_tag_text is empty and new weight is other than 1.0, it becomes e.g. "(:1.20)"
    if not final_base_tag_text and abs(new_weight - 1.0) < 0.001: # Handles "(:1.0)" -> ""
        new_tag_str = ""
    elif abs(new_weight - 1.0) < 0.001: # Effectively 1.0 for a non-empty base
        new_tag_str = final_base_tag_text
    elif new_weight <= 0:
        # Format as (base:0.0) or (base:0) for weights at or below zero.
        # Python's default float to string usually gives shortest representation.
        new_tag_str = f"({final_base_tag_text}:{max(0.0, new_weight)})"
    else: # Standard weighting
        new_tag_str = f"({final_base_tag_text}:{new_weight})"

    # The segment to replace is prompt_text[raw_segment_start_idx : raw_segment_end_idx]
    # This segment includes the original tag and its surrounding whitespace within the comma-separated part.
    # We need to preserve spacing if possible, or just replace the raw segment with the new tag string.
    # If the raw segment was "  tag  " and new tag is "(tag:1.1)", output "  (tag:1.1)  " ?
    # Or just replace "  tag  " with "(tag:1.1)"? The latter is simpler and usually fine.

    pre_segment_of_prompt = prompt_text[:raw_segment_start_idx]
    post_segment_of_prompt = prompt_text[raw_segment_end_idx:]
    original_raw_segment_text = prompt_text[raw_segment_start_idx:raw_segment_end_idx]

    middle_chunk = ""
    if not stripped_tag_content: # Segment was empty or all spaces
        if not new_tag_str: # And new tag is also empty (e.g. weight became 1.0)
            # Preserve original spaces if any, otherwise it's just empty on empty
            middle_chunk = original_raw_segment_text
        else: # weighting an empty/space tag to something like (:1.10)
            middle_chunk = new_tag_str
    else:
        # Check if this is the first effective tag and if the raw segment is just spaces around content
        is_first_segment_in_prompt = True
        for char_idx in range(raw_segment_start_idx):
            if not prompt_text[char_idx].isspace():
                is_first_segment_in_prompt = False
                break

        # Find leading/trailing spaces within the current raw segment
        content_start_in_segment = original_raw_segment_text.find(stripped_tag_content)
        leading_spaces_in_segment = original_raw_segment_text[:content_start_in_segment]
        trailing_spaces_in_segment = original_raw_segment_text[content_start_in_segment + len(stripped_tag_content):]

        if is_first_segment_in_prompt and \
           original_raw_segment_text == (leading_spaces_in_segment + stripped_tag_content + trailing_spaces_in_segment):
            # If it's the first tag, and the segment is perfectly composed of spaces + content + spaces,
            # then replace with new_tag_str, effectively collapsing segment spaces.
            # However, we need to be careful not to lose a deliberate single leading space if prompt starts like " tag".
            # A simpler rule: if it's the first segment, and it has leading spaces, new tag replaces stripped_tag_content + its own spaces.
            # The most problematic case was "  tag1  , tag2" -> "(tag1:1.10), tag2"
            # Here, raw_segment_start_idx is 0.
            if raw_segment_start_idx == 0: # It's the very first segment of the prompt string
                 middle_chunk = new_tag_str # Collapse spaces for the very first segment
            else: # For subsequent segments, preserve their leading space (typically one after comma)
                middle_chunk = leading_spaces_in_segment + new_tag_str + trailing_spaces_in_segment

        else: # Not the first segment, or complex structure not just spaces around.
              # Preserve leading/trailing spaces of the segment.
            middle_chunk = leading_spaces_in_segment + new_tag_str + trailing_spaces_in_segment

    return pre_segment_of_prompt + middle_chunk + post_segment_of_prompt


if __name__ == '__main__':
    # (Continue existing tests for get_tag_at_cursor)
    # ... (previous run_test calls) ...
    print("\n--- apply_weight_to_tag tests ---")

    def run_apply_test(p, tag, s, e, direction, expected_p, step=0.1):
        print(f"Orig: '{p}' | Tag='{tag}' ({s},{e}) | Dir={direction}")
        new_p = apply_weight_to_tag(p, tag, s, e, direction, weight_step=step)
        print(f"New:  '{new_p}'")
        print(f"Exp:  '{expected_p}'")
        assert new_p == expected_p
        print(" OK")

    run_apply_test("tag1, tag2", "tag1", 0, 4, "up", "(tag1:1.1), tag2")
    run_apply_test("tag1, tag2", "tag2", 5, 10, "up", "tag1, (tag2:1.1)")
    run_apply_test("(tag1:1.1), tag2", "(tag1:1.1)", 0, 11, "up", "(tag1:1.2), tag2") # Note: length of (tag1:1.1) is 11
    run_apply_test("(tag1:1.1), tag2", "(tag1:1.1)", 0, 11, "down", "tag1, tag2") # Becomes 1.0
    run_apply_test("tag1, tag2", "tag1", 0, 4, "down", "(tag1:0.9), tag2")
    run_apply_test("(tag1:0.1), tag2", "(tag1:0.1)", 0, 11, "down", "(tag1:0.0), tag2") # Goes to 0.0
    run_apply_test("(tag1:0.0), tag2", "(tag1:0.0)", 0, 11, "down", "(tag1:0.0), tag2") # Stays at 0.0
    run_apply_test("(tag1:2.0), tag2", "(tag1:2.0)", 0, 11, "up", "(tag1:2.0), tag2") # Max weight (assuming 2.0 is max)

    # Test with spaces in tag content (which is stripped_tag_content)
    run_apply_test("size difference, other", "size difference", 0, 15, "up", "(size difference:1.1), other")
    run_apply_test("tag (with parens), other", "tag (with parens)", 0, 17, "up", "(tag (with parens):1.1), other")

    # Test replacing segment with spaces
    run_apply_test("  tag1  , tag2", "tag1", 0, 8, "up", "(tag1:1.1), tag2")

    # Test with existing weight and complex tag
    # For "  (size difference:1.5)  , other", get_tag_at_cursor(..., 3) -> ("(size difference:1.5)", 0, 28)
    run_apply_test("  (size difference:1.5)  , other", "(size difference:1.5)", 0, 28, "down", "(size difference:1.4), other", step=0.1)

    print("\n--- Retesting last case with simplified expectation ---") # This comment block is now less relevant
    run_apply_test("  (size difference:1.5)  , other", "(size difference:1.5)", 0, 28, "down", "(size difference:1.4), other", step=0.1)

    # Test removing weight
    # For "(tag1:1.0), tag2", get_tag_at_cursor(..., 1) -> ("(tag1:1.0)", 0, 11)
    run_apply_test("(tag1:1.0), tag2", "(tag1:1.0)", 0, 11, "up", "(tag1:1.1), tag2")
    run_apply_test("(tag1:1.0), tag2", "(tag1:1.0)", 0, 11, "down", "(tag1:0.9), tag2")


    print("\n--- Nested/Repeated weighting tests ---")
    p1 = apply_weight_to_tag("tag", "tag", 0, 3, "up")
    # p1 is "(tag:1.1)"
    # For apply_weight_to_tag(p1, "(tag:1.1)", 0, len(p1), "up")
    # stripped_tag_content = "(tag:1.1)", raw_start=0, raw_end=len("(tag:1.1)") which is 9
    p2 = apply_weight_to_tag(p1, "(tag:1.1)", 0, len(p1), "up")
    print(f"Test: tag -> up -> up. Result: {p2}, Expected: (tag:1.2)")
    assert p2 == "(tag:1.2)"

    p3 = apply_weight_to_tag(p2, "(tag:1.2)", 0, len(p2), "down")
    print(f"Test: (tag:1.2) -> down. Result: {p3}, Expected: (tag:1.1)")
    assert p3 == "(tag:1.1)"

    p4 = apply_weight_to_tag(p3, "(tag:1.1)", 0, len(p3), "down")
    print(f"Test: (tag:1.1) -> down. Result: {p4}, Expected: tag")
    assert p4 == "tag"

    complex_tag_content = "amazon (taitaitaira)"
    prompt_c1 = complex_tag_content
    weighted_c1 = apply_weight_to_tag(prompt_c1, complex_tag_content, 0, len(prompt_c1), "up")
    expected_wc1 = f"({complex_tag_content}:1.1)"
    print(f"Test: '{complex_tag_content}' -> up. Result: '{weighted_c1}', Expected: '{expected_wc1}'")
    assert weighted_c1 == expected_wc1

    weighted_c2 = apply_weight_to_tag(weighted_c1, weighted_c1, 0, len(weighted_c1), "up")
    expected_wc2 = f"({complex_tag_content}:1.2)"
    print(f"Test: '{weighted_c1}' -> up. Result: '{weighted_c2}', Expected: '{expected_wc2}'")
    assert weighted_c2 == expected_wc2

    weighted_c3 = apply_weight_to_tag(weighted_c2, weighted_c2, 0, len(weighted_c2), "up")
    expected_wc3 = f"({complex_tag_content}:1.3)"
    print(f"Test: '{weighted_c2}' -> up. Result: '{weighted_c3}', Expected: '{expected_wc3}'")
    assert weighted_c3 == expected_wc3

    nested_input_tag = "((tag:0.5):1.5)"
    corrected_nested = apply_weight_to_tag(nested_input_tag, nested_input_tag, 0, len(nested_input_tag), "up")
    expected_corrected_nested = "(tag:1.6)"
    print(f"Test: '{nested_input_tag}' -> up. Result: '{corrected_nested}', Expected: '{expected_corrected_nested}'")
    assert corrected_nested == expected_corrected_nested

    empty_base_weighted = "(:1.1)"
    # Manually calculate length for test: "(:1.1)" is 6 chars
    res_ebw = apply_weight_to_tag(empty_base_weighted, empty_base_weighted, 0, 6, "up")
    exp_ebw = "(:1.2)"
    print(f"Test: '{empty_base_weighted}' -> up. Result: '{res_ebw}', Expected: '{exp_ebw}'")
    assert res_ebw == exp_ebw

    res_ebw_down = apply_weight_to_tag(empty_base_weighted, empty_base_weighted, 0, 6, "down")
    exp_ebw_down = ""
    print(f"Test: '{empty_base_weighted}' -> down. Result: '{res_ebw_down}', Expected: '{exp_ebw_down}'")
    assert res_ebw_down == exp_ebw_down


    print("All apply_weight_to_tag tests passed.")
