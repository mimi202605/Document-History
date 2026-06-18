"""Tests for diff utilities."""
from dochistory.utils.diff_utils import compute_diff, DiffLine, DiffType


class TestComputeDiff:
    def test_identical_text_no_changes(self):
        text = "line1\nline2\nline3"
        result = compute_diff(text, text)
        assert all(line.type == DiffType.UNCHANGED for line in result)
        assert len(result) == 3

    def test_added_line(self):
        old = "line1\nline2"
        new = "line1\nline2\nline3"
        result = compute_diff(old, new)
        added = [l for l in result if l.type == DiffType.ADDED]
        assert len(added) == 1
        assert added[0].new_line == "line3"

    def test_removed_line(self):
        old = "line1\nline2\nline3"
        new = "line1\nline3"
        result = compute_diff(old, new)
        removed = [l for l in result if l.type == DiffType.REMOVED]
        assert len(removed) == 1
        assert removed[0].old_line == "line2"

    def test_modified_line(self):
        old = "line1\nold line\nline3"
        new = "line1\nnew line\nline3"
        result = compute_diff(old, new)
        modified = [l for l in result if l.type == DiffType.MODIFIED]
        assert len(modified) == 1
        assert modified[0].old_line == "old line"
        assert modified[0].new_line == "new line"

    def test_empty_old_text(self):
        result = compute_diff("", "new content")
        added = [l for l in result if l.type == DiffType.ADDED]
        assert len(added) == 1

    def test_empty_new_text(self):
        result = compute_diff("old content", "")
        removed = [l for l in result if l.type == DiffType.REMOVED]
        assert len(removed) == 1

    def test_both_empty(self):
        result = compute_diff("", "")
        assert result == []

    def test_multiple_changes(self):
        old = "keep1\nremove1\nkeep2\nremove2"
        new = "keep1\nadd1\nkeep2\nadd2"
        result = compute_diff(old, new)
        types = [l.type for l in result]
        assert DiffType.ADDED in types
        assert DiffType.REMOVED in types
        assert DiffType.UNCHANGED in types
