"""Presentation-only grouping of immutable direct-comparison operations."""
from __future__ import annotations

from dataclasses import dataclass

from . import alignment as al

GROUP_OPERATION_LIMIT = 40


@dataclass(frozen=True)
class DifferenceGroup:
    first_operation: int
    operations: tuple[al.AlignmentOperation, ...]


def _adjacent(left: al.AlignmentOperation, right: al.AlignmentOperation) -> bool:
    if left.type != right.type:
        return False
    for a, b in ((left.source_token, right.source_token),
                 (left.target_token, right.target_token)):
        if a is None and b is None:
            continue
        if a is None or b is None or b.index != a.index + 1 or a.page_no != b.page_no:
            return False
    return True


def group_differences(result: al.AlignmentResult) -> tuple[DifferenceGroup, ...]:
    """Group consecutive same-kind operations; rank by size, then original order.

    Page boundaries, matches, nonconsecutive endpoints and the display cap split
    groups. Operations are retained verbatim, never relabeled or realigned.
    """
    groups: list[DifferenceGroup] = []
    pending: list[al.AlignmentOperation] = []
    first = 0
    for index, operation in enumerate(result.operations):
        if pending and (operation.type == al.OperationType.MATCH
                        or len(pending) == GROUP_OPERATION_LIMIT
                        or not _adjacent(pending[-1], operation)):
            groups.append(DifferenceGroup(first, tuple(pending)))
            pending = []
        if operation.type != al.OperationType.MATCH:
            if not pending:
                first = index
            pending.append(operation)
    if pending:
        groups.append(DifferenceGroup(first, tuple(pending)))
    return tuple(sorted(groups, key=lambda group: (-len(group.operations), group.first_operation)))
