"""Diff utilities using difflib."""
import difflib
from dataclasses import dataclass
from enum import Enum


class DiffType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class DiffLine:
    type: DiffType
    old_line: str
    new_line: str
    old_line_no: int
    new_line_no: int


def compute_diff(text_old: str, text_new: str) -> list[DiffLine]:
    """Compute line-level diff between two texts.

    Returns a list of DiffLine objects representing the changes.
    Uses difflib's SequenceMatcher for intelligent matching.
    """
    if not text_old and not text_new:
        return []

    old_lines = text_old.splitlines() if text_old else []
    new_lines = text_new.splitlines() if text_new else []

    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    result = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                result.append(DiffLine(
                    type=DiffType.UNCHANGED,
                    old_line=old_lines[i1 + k],
                    new_line=new_lines[j1 + k],
                    old_line_no=i1 + k + 1,
                    new_line_no=j1 + k + 1,
                ))
        elif tag == "replace":
            # Pair up replaced lines; similar lines become MODIFIED,
            # dissimilar lines become separate REMOVED + ADDED.
            old_slice = old_lines[i1:i2]
            new_slice = new_lines[j1:j2]
            max_len = max(len(old_slice), len(new_slice))
            for k in range(max_len):
                old_l = old_slice[k] if k < len(old_slice) else ""
                new_l = new_slice[k] if k < len(new_slice) else ""
                if old_l and new_l:
                    ratio = difflib.SequenceMatcher(None, old_l, new_l).ratio()
                    if ratio >= 0.5:
                        result.append(DiffLine(
                            type=DiffType.MODIFIED,
                            old_line=old_l,
                            new_line=new_l,
                            old_line_no=i1 + k + 1,
                            new_line_no=j1 + k + 1,
                        ))
                    else:
                        result.append(DiffLine(
                            type=DiffType.REMOVED,
                            old_line=old_l,
                            new_line="",
                            old_line_no=i1 + k + 1,
                            new_line_no=0,
                        ))
                        result.append(DiffLine(
                            type=DiffType.ADDED,
                            old_line="",
                            new_line=new_l,
                            old_line_no=0,
                            new_line_no=j1 + k + 1,
                        ))
                elif new_l:
                    result.append(DiffLine(
                        type=DiffType.ADDED,
                        old_line="",
                        new_line=new_l,
                        old_line_no=0,
                        new_line_no=j1 + k + 1,
                    ))
                elif old_l:
                    result.append(DiffLine(
                        type=DiffType.REMOVED,
                        old_line=old_l,
                        new_line="",
                        old_line_no=i1 + k + 1,
                        new_line_no=0,
                    ))
        elif tag == "delete":
            for k in range(i2 - i1):
                result.append(DiffLine(
                    type=DiffType.REMOVED,
                    old_line=old_lines[i1 + k],
                    new_line="",
                    old_line_no=i1 + k + 1,
                    new_line_no=0,
                ))
        elif tag == "insert":
            for k in range(j2 - j1):
                result.append(DiffLine(
                    type=DiffType.ADDED,
                    old_line="",
                    new_line=new_lines[j1 + k],
                    old_line_no=0,
                    new_line_no=j1 + k + 1,
                ))

    return result
