import difflib


def build_line_diff_segments(left_line, right_line):
    left_segments = []
    right_segments = []
    matcher = difflib.SequenceMatcher(None, left_line, right_line)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if i1 != i2:
            left_segments.append((i1, i2, "diff_delete" if tag == "delete" else "diff_replace"))
        if j1 != j2:
            right_segments.append((j1, j2, "diff_insert" if tag == "insert" else "diff_replace"))
    return left_segments, right_segments


def compare_text_lines(left_lines, right_lines):
    max_lines = max(len(left_lines), len(right_lines))
    left_highlights = {}
    right_highlights = {}
    left_markers = {}
    right_markers = {}
    left_display_lines = []
    right_display_lines = []
    diff_count = 0

    for index in range(max_lines):
        left_line = left_lines[index] if index < len(left_lines) else None
        right_line = right_lines[index] if index < len(right_lines) else None
        left_display_lines.append(left_line if left_line is not None else "<<< 缺失 >>>")
        right_display_lines.append(right_line if right_line is not None else "<<< 缺失 >>>")
        if left_line == right_line:
            continue

        diff_count += 1
        line_no = index + 1
        if left_line is None:
            left_markers[line_no] = "-"
            right_markers[line_no] = "!"
            left_highlights[line_no] = [(None, None, "missing")]
            right_highlights[line_no] = [(None, None, "missing")]
        elif right_line is None:
            left_markers[line_no] = "!"
            right_markers[line_no] = "-"
            left_highlights[line_no] = [(None, None, "missing")]
            right_highlights[line_no] = [(None, None, "missing")]
        else:
            left_markers[line_no] = "!"
            right_markers[line_no] = "!"
            left_segments, right_segments = build_line_diff_segments(left_line, right_line)
            left_highlights[line_no] = left_segments
            right_highlights[line_no] = right_segments

    return {
        "left_display_lines": left_display_lines,
        "right_display_lines": right_display_lines,
        "left_highlights": left_highlights,
        "right_highlights": right_highlights,
        "left_markers": left_markers,
        "right_markers": right_markers,
        "diff_count": diff_count,
    }
