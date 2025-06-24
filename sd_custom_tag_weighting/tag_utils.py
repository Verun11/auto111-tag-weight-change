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
            if search_start_idx_raw <= cursor_pos <= i:
                stripped_content = prompt_text[search_start_idx_raw:i].strip()
                return stripped_content if stripped_content else "", search_start_idx_raw, i
            search_start_idx_raw = i + 1

    if search_start_idx_raw <= cursor_pos <= len(prompt_text):
        stripped_content = prompt_text[search_start_idx_raw:].strip()
        return stripped_content if stripped_content else "", search_start_idx_raw, len(prompt_text)

    return None, -1, -1

import re

def apply_weight_to_tag(
    prompt_text: str,
    stripped_tag_content: str,
    raw_segment_start_idx: int,
    raw_segment_end_idx: int,
    direction: str,
    weight_step: float = 0.1,
    max_weight: float = 2.0,
    min_weight_remove: float = 0.1
) -> str:
    if stripped_tag_content is None:
        return prompt_text

    effective_weight = 1.0
    text_to_unwrap = stripped_tag_content

    artist_prefix = ""
    if text_to_unwrap.lower().startswith("artist:"):
        artist_prefix = text_to_unwrap[:7]
        text_to_unwrap = text_to_unwrap[7:].lstrip()

    _pattern = re.compile(r"\s*\((.*?):\s*([\d.]+)\s*\)\s*")

    base_content_of_stripped_tag = text_to_unwrap
    final_innermost_content = base_content_of_stripped_tag

    match_outer = _pattern.fullmatch(base_content_of_stripped_tag)
    if match_outer:
        effective_weight = float(match_outer.group(2))
        content_inside_outer_weight = match_outer.group(1).strip()

        current_stripping_text = content_inside_outer_weight
        final_innermost_content = current_stripping_text
        while True:
            match_inner = _pattern.fullmatch(current_stripping_text)
            if match_inner:
                current_stripping_text = match_inner.group(1).strip()
                final_innermost_content = current_stripping_text
            else:
                final_innermost_content = current_stripping_text.strip()
                break
    else:
        final_innermost_content = base_content_of_stripped_tag.strip()

    final_base_tag_text = final_innermost_content

    if direction == "up":
        new_weight = round(effective_weight + weight_step, 2)
        if new_weight > max_weight:
            new_weight = max_weight
    elif direction == "down":
        new_weight = round(effective_weight - weight_step, 2)
        if new_weight < 0:
            new_weight = 0
    else:
        return prompt_text # Should not happen with controlled inputs

    new_tag_str_content = ""
    if not final_base_tag_text and abs(new_weight - 1.0) < 0.001:
        new_tag_str_content = ""
    elif abs(new_weight - 1.0) < 0.001:
        new_tag_str_content = final_base_tag_text
    elif new_weight <= 0:
        new_tag_str_content = f"({final_base_tag_text}:{max(0.0, new_weight)})"
    else:
        new_tag_str_content = f"({final_base_tag_text}:{new_weight})"

    new_tag_str = artist_prefix + new_tag_str_content

    if artist_prefix:
        if new_tag_str_content == final_base_tag_text:
             new_tag_str = artist_prefix + final_base_tag_text
        elif not final_base_tag_text and not new_tag_str_content :
             new_tag_str = artist_prefix

    pre_segment_of_prompt = prompt_text[:raw_segment_start_idx]
    post_segment_of_prompt = prompt_text[raw_segment_end_idx:]
    original_raw_segment_text = prompt_text[raw_segment_start_idx:raw_segment_end_idx]

    middle_chunk = ""
    if not stripped_tag_content:
        if not new_tag_str:
            middle_chunk = original_raw_segment_text
        else:
            middle_chunk = new_tag_str
    else:
        is_first_segment_in_prompt = True
        for char_idx in range(raw_segment_start_idx):
            if not prompt_text[char_idx].isspace():
                is_first_segment_in_prompt = False
                break

        content_start_in_segment = original_raw_segment_text.find(stripped_tag_content)
        leading_spaces_in_segment = original_raw_segment_text[:content_start_in_segment]
        trailing_spaces_in_segment = original_raw_segment_text[content_start_in_segment + len(stripped_tag_content):]

        if is_first_segment_in_prompt and \
           original_raw_segment_text == (leading_spaces_in_segment + stripped_tag_content + trailing_spaces_in_segment):
            if raw_segment_start_idx == 0:
                 middle_chunk = new_tag_str
            else:
                middle_chunk = leading_spaces_in_segment + new_tag_str + trailing_spaces_in_segment
        else:
            middle_chunk = leading_spaces_in_segment + new_tag_str + trailing_spaces_in_segment

    return pre_segment_of_prompt + middle_chunk + post_segment_of_prompt

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
    run_test("tag1, tag2", 4, "tag1", 0, 4)
    run_test("tag1, tag2", 5, "tag2", 5, 10)
    run_test("tag1, tag2", 6, "tag2", 5, 10)
    run_test("  leading space, tag2", 0, "leading space", 0, 15)
    run_test("  leading space, tag2", 15, "leading space", 0, 15)
    run_test("tag (with parens), tag2", 0, "tag (with parens)", 0, 17)
    run_test("tag1,middle (paren, still middle),tag3", 15, "middle (paren, still middle)", 5, 33)
    run_test("tag1,,tag3", 5, "", 5, 5)
    run_test("trailing space  ", 0, "trailing space", 0, 16)
    run_test("", 0, "", 0, 0)
    run_test("   ", 0, "", 0, 3)
    print("All get_tag_at_cursor tests passed.")

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
    # Corrected raw_end for (tag1:1.1) which is 9 chars long, comma at index 9
    run_apply_test("(tag1:1.1), tag2", "(tag1:1.1)", 0, 9, "up", "(tag1:1.2), tag2")
    run_apply_test("(tag1:1.1), tag2", "(tag1:1.1)", 0, 9, "down", "tag1, tag2")
    run_apply_test("tag1, tag2", "tag1", 0, 4, "down", "(tag1:0.9), tag2")
    run_apply_test("(tag1:0.1), tag2", "(tag1:0.1)", 0, 9, "down", "(tag1:0.0), tag2")
    run_apply_test("(tag1:0.0), tag2", "(tag1:0.0)", 0, 9, "down", "(tag1:0.0), tag2")
    run_apply_test("(tag1:2.0), tag2", "(tag1:2.0)", 0, 9, "up", "(tag1:2.0), tag2")
    run_apply_test("size difference, other", "size difference", 0, 15, "up", "(size difference:1.1), other")
    run_apply_test("tag (with parens), other", "tag (with parens)", 0, 17, "up", "(tag (with parens):1.1), other")
    run_apply_test("  tag1  , tag2", "tag1", 0, 8, "up", "(tag1:1.1), tag2")
    run_apply_test("  (size difference:1.5)  , other", "(size difference:1.5)", 0, 28, "down", "(size difference:1.4), other", step=0.1)
    run_apply_test("(tag1:1.0), tag2", "(tag1:1.0)", 0, 9, "up", "(tag1:1.1), tag2")
    run_apply_test("(tag1:1.0), tag2", "(tag1:1.0)", 0, 9, "down", "(tag1:0.9), tag2")

    p1 = apply_weight_to_tag("tag", "tag", 0, 3, "up")
    p2 = apply_weight_to_tag(p1, "(tag:1.1)", 0, len(p1), "up")
    assert p2 == "(tag:1.2)"
    p3 = apply_weight_to_tag(p2, "(tag:1.2)", 0, len(p2), "down")
    assert p3 == "(tag:1.1)"
    p4 = apply_weight_to_tag(p3, "(tag:1.1)", 0, len(p3), "down")
    assert p4 == "tag"

    nested_input_tag = "((tag:0.5):1.5)"
    corrected_nested = apply_weight_to_tag(nested_input_tag, nested_input_tag, 0, len(nested_input_tag), "up")
    assert corrected_nested == "(tag:1.6)"

    empty_base_weighted = "(:1.1)"
    res_ebw = apply_weight_to_tag(empty_base_weighted, empty_base_weighted, 0, 6, "up")
    assert res_ebw == "(:1.2)"
    res_ebw_down = apply_weight_to_tag(empty_base_weighted, empty_base_weighted, 0, 6, "down")
    assert res_ebw_down == ""

    print("\n--- Artist tag tests ---")
    run_apply_test("artist:kloah, other", "artist:kloah", 0, 12, "up", "artist:(kloah:1.1), other")
    run_apply_test("artist: kloah, other", "artist: kloah", 0, 13, "up", "artist:(kloah:1.1), other")
    run_apply_test("artist:(kloah:1.1), other", "artist:(kloah:1.1)", 0, 19, "up", "artist:(kloah:1.2), other")
    run_apply_test("artist:(kloah:1.1), other", "artist:(kloah:1.1)", 0, 19, "down", "artist:kloah, other")
    run_apply_test("artist:kloah, other", "artist:kloah", 0, 12, "down", "artist:(kloah:0.9), other")
    run_apply_test("artist:(kloah:0.1), other", "artist:(kloah:0.1)", 0, 19, "down", "artist:(kloah:0.0), other")
    run_apply_test("artist:name (with parens), other", "artist:name (with parens)", 0, 28, "up", "artist:(name (with parens):1.1), other")
    run_apply_test("artist:(name (with parens):1.1), other", "artist:(name (with parens):1.1)", 0, 35, "down", "artist:name (with parens), other")
    run_apply_test("ARTIST:kloah, other", "ARTIST:kloah", 0, 12, "up", "ARTIST:(kloah:1.1), other")
    run_apply_test("ARTIST:(kloah:1.1), other", "ARTIST:(kloah:1.1)", 0, 19, "down", "ARTIST:kloah, other")
    run_apply_test("artist:    kloah, other", "artist:    kloah", 0, 19, "up", "artist:(kloah:1.1), other")
    run_apply_test("artist: (kloah:1.1), other", "artist: (kloah:1.1)", 0, 20, "down", "artist:kloah, other")

    print("All apply_weight_to_tag tests passed.")
