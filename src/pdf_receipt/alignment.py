"""Bounded, occurrence-based token alignment for the quality-report pipeline.

The module deliberately contains no Docling imports.  It consumes the token
model produced by :mod:`pdf_receipt.quality_report` and snapshots all
evidence into typed result objects for later metrics and rendering work.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Literal, Protocol, Sequence

LOOKAHEAD_TOKENS = 64
CONTEXT_TOKENS = 3
CASE_PROFILES = frozenset(("unicode", "turkic"))

HyphenDecision = Literal["keep", "join"]


class AlignmentStage(str, Enum):
    DIRECT = "direct"
    EXTRACTION = "extraction"
    SERIALIZATION = "serialization"


class OperationType(str, Enum):
    MATCH = "match"
    DELETION = "deletion"
    INSERTION = "insertion"
    SUBSTITUTION = "substitution"
    ORDER_RISK = "order_risk"


class MatchKind(str, Enum):
    NORMALIZED = "normalized"
    LINE_END_HYPHEN_JOIN = "line_end_hyphen_join"
    REORDERED = "reordered"
    FIGURE = "figure"
    FURNITURE = "furniture"
    FOOTNOTE = "footnote"
    TABLE_REPETITION = "table_repetition"
    UNEXPLAINED = "unexplained"
    ADDED = "added"
    DIFFERENT = "different"


class AlignableToken(Protocol):
    raw_text: str
    normalized_text: str
    source_span: Any
    page_no: int | None
    block_id: str | None
    provenance: tuple[Any, ...]
    all_provenance: tuple[Any, ...]
    provenance_status: str
    bounding_boxes: tuple[Any, ...]
    spatial_regions: tuple[Any, ...]
    semantic_role: str | None
    case_profile: str
    joined_normalized_text: str | None
    line_end_hyphen_spans: tuple[Any, ...]
    line_end_parts: tuple[str, ...]

    def hyphen_decisions_for(
        self, candidate: str
    ) -> tuple[HyphenDecision, ...] | None:
        """Return a lazy ambiguity resolution when ``candidate`` is possible."""


@dataclass(frozen=True)
class SpanEvidence:
    """A half-open source range copied into an immutable result."""

    start: int
    end: int


@dataclass(frozen=True)
class ContextRange:
    """Half-open token-index boundaries in one alignment stream."""

    start: int
    end: int


@dataclass(frozen=True)
class TokenEvidence:
    """A stable snapshot of one token occurrence and all of its provenance."""

    index: int
    raw_text: str
    normalized_text: str
    source_span: SpanEvidence
    page_no: int | None
    block_id: str | None
    provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    all_provenance: tuple[Any, ...] = field(default=(), compare=False, repr=False)
    provenance_status: str = "none"
    bounding_boxes: tuple[Any, ...] = ()
    spatial_regions: tuple[Any, ...] = ()
    semantic_role: str | None = None
    case_profile: str = "unicode"
    joined_normalized_text: str | None = None
    line_end_hyphen_spans: tuple[SpanEvidence, ...] = ()
    line_end_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlignmentOperation:
    """One one-to-one match, difference, explanation, or ordering risk."""

    stage: AlignmentStage
    type: OperationType
    source_index: int | None
    target_index: int | None
    source_token: TokenEvidence | None
    target_token: TokenEvidence | None
    source_context: ContextRange
    target_context: ContextRange
    match_kind: MatchKind
    hyphen_decisions: tuple[HyphenDecision, ...] = ()
    evidence_token: TokenEvidence | None = field(
        default=None, compare=False, repr=False
    )


@dataclass(frozen=True)
class AlignmentResult:
    """All operations for one stage, with every occurrence consumed once."""

    stage: AlignmentStage
    source_tokens: tuple[TokenEvidence, ...]
    target_tokens: tuple[TokenEvidence, ...]
    operations: tuple[AlignmentOperation, ...]
    case_profile: str
    lookahead_tokens: int = LOOKAHEAD_TOKENS

    def __post_init__(self) -> None:
        source_indexes = [
            operation.source_index
            for operation in self.operations
            if operation.source_index is not None
        ]
        target_indexes = [
            operation.target_index
            for operation in self.operations
            if operation.target_index is not None
        ]
        if len(source_indexes) != len(self.source_tokens) or set(
            source_indexes
        ) != set(range(len(self.source_tokens))):
            raise ValueError("alignment must consume every source occurrence exactly once")
        if len(target_indexes) != len(self.target_tokens) or set(
            target_indexes
        ) != set(range(len(self.target_tokens))):
            raise ValueError("alignment must consume every target occurrence exactly once")


@dataclass(frozen=True)
class TwoStageAlignment:
    """Extraction and serialization evidence kept as distinct comparisons."""

    extraction: AlignmentResult
    serialization: AlignmentResult


def _span(value: Any) -> SpanEvidence:
    return SpanEvidence(start=int(value.start), end=int(value.end))


def _snapshot(index: int, token: AlignableToken) -> TokenEvidence:
    return TokenEvidence(
        index=index,
        raw_text=token.raw_text,
        normalized_text=token.normalized_text,
        source_span=_span(token.source_span),
        page_no=token.page_no,
        block_id=token.block_id,
        provenance=token.provenance,
        all_provenance=token.all_provenance,
        provenance_status=token.provenance_status,
        bounding_boxes=token.bounding_boxes,
        spatial_regions=token.spatial_regions,
        semantic_role=token.semantic_role,
        case_profile=token.case_profile,
        joined_normalized_text=token.joined_normalized_text,
        line_end_hyphen_spans=tuple(
            _span(span) for span in token.line_end_hyphen_spans
        ),
        line_end_parts=token.line_end_parts,
    )


def _validate_case_profiles(
    streams: Iterable[Sequence[AlignableToken]], case_profile: str
) -> None:
    if case_profile not in CASE_PROFILES:
        raise ValueError(f"unknown alignment case profile: {case_profile!r}")
    for stream in streams:
        for token in stream:
            if token.case_profile != case_profile:
                raise ValueError(
                    "cannot align token streams with a conflicting case profile: "
                    f"expected {case_profile!r}, found {token.case_profile!r}"
                )


def _context(index: int, length: int) -> ContextRange:
    return ContextRange(
        max(0, index - CONTEXT_TOKENS),
        min(length, index + CONTEXT_TOKENS + 1),
    )


def _gap_context(index: int, length: int) -> ContextRange:
    position = max(0, min(index, length))
    return ContextRange(
        max(0, position - CONTEXT_TOKENS),
        min(length, position + CONTEXT_TOKENS),
    )


def _direct_match(source: AlignableToken, target: AlignableToken) -> bool:
    return source.normalized_text == target.normalized_text


def _hyphen_match(
    source: AlignableToken, target: AlignableToken
) -> tuple[HyphenDecision, ...] | None:
    source_choices = source.hyphen_decisions_for(target.normalized_text)
    if source_choices is not None and "join" in source_choices:
        return source_choices
    target_choices = target.hyphen_decisions_for(source.normalized_text)
    if target_choices is not None and "join" in target_choices:
        return target_choices
    return None


def _has_local_context(
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
    source_position: int,
    target_position: int,
) -> bool:
    for delta in (-1, 1):
        source_neighbor = source_position + delta
        target_neighbor = target_position + delta
        if (
            0 <= source_neighbor < len(source)
            and 0 <= target_neighbor < len(target)
            and _direct_match(
                source[source_neighbor][1], target[target_neighbor][1]
            )
        ):
            return True
    return False


def _match_kind(
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
    source_position: int,
    target_position: int,
) -> tuple[MatchKind, tuple[HyphenDecision, ...]] | None:
    source_token = source[source_position][1]
    target_token = target[target_position][1]
    if _direct_match(source_token, target_token):
        conservative_choices = source_token.hyphen_decisions_for(
            target_token.normalized_text
        ) or target_token.hyphen_decisions_for(source_token.normalized_text)
        return MatchKind.NORMALIZED, conservative_choices or ()
    choices = _hyphen_match(source_token, target_token)
    if choices is not None and _has_local_context(
        source, target, source_position, target_position
    ):
        return MatchKind.LINE_END_HYPHEN_JOIN, choices
    return None


def _operation(
    *,
    stage: AlignmentStage,
    operation_type: OperationType,
    source_item: tuple[int, AlignableToken] | None,
    target_item: tuple[int, AlignableToken] | None,
    source_evidence: Sequence[TokenEvidence],
    target_evidence: Sequence[TokenEvidence],
    source_gap: int,
    target_gap: int,
    match_kind: MatchKind,
    hyphen_decisions: tuple[HyphenDecision, ...] = (),
) -> AlignmentOperation:
    source_index = source_item[0] if source_item is not None else None
    target_index = target_item[0] if target_item is not None else None
    return AlignmentOperation(
        stage=stage,
        type=operation_type,
        source_index=source_index,
        target_index=target_index,
        source_token=(
            source_evidence[source_index] if source_index is not None else None
        ),
        target_token=(
            target_evidence[target_index] if target_index is not None else None
        ),
        source_context=(
            _context(source_index, len(source_evidence))
            if source_index is not None
            else _gap_context(source_gap, len(source_evidence))
        ),
        target_context=(
            _context(target_index, len(target_evidence))
            if target_index is not None
            else _gap_context(target_gap, len(target_evidence))
        ),
        match_kind=match_kind,
        hyphen_decisions=hyphen_decisions,
    )


def _window_lcs_scores(
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
    source_position: int,
    target_position: int,
) -> list[list[int]]:
    """Return a bounded LCS table for choosing the next occurrence locally."""
    source_stop = min(len(source), source_position + LOOKAHEAD_TOKENS)
    target_stop = min(len(target), target_position + LOOKAHEAD_TOKENS)
    source_length = source_stop - source_position
    target_length = target_stop - target_position
    scores = [
        [0] * (target_length + 1)
        for _ in range(source_length + 1)
    ]
    for source_offset in range(source_length - 1, -1, -1):
        for target_offset in range(target_length - 1, -1, -1):
            source_index = source_position + source_offset
            target_index = target_position + target_offset
            if _match_kind(source, target, source_index, target_index) is not None:
                scores[source_offset][target_offset] = (
                    1 + scores[source_offset + 1][target_offset + 1]
                )
            else:
                scores[source_offset][target_offset] = max(
                    scores[source_offset + 1][target_offset],
                    scores[source_offset][target_offset + 1],
                )
    return scores


def _align_partition(
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
    *,
    stage: AlignmentStage,
    source_evidence: Sequence[TokenEvidence],
    target_evidence: Sequence[TokenEvidence],
) -> list[AlignmentOperation]:
    operations: list[AlignmentOperation] = []
    source_position = 0
    target_position = 0

    while source_position < len(source) and target_position < len(target):
        match = _match_kind(source, target, source_position, target_position)
        if match is not None:
            match_kind, decisions = match
            operations.append(
                _operation(
                    stage=stage,
                    operation_type=OperationType.MATCH,
                    source_item=source[source_position],
                    target_item=target[target_position],
                    source_evidence=source_evidence,
                    target_evidence=target_evidence,
                    source_gap=source[source_position][0],
                    target_gap=target[target_position][0],
                    match_kind=match_kind,
                    hyphen_decisions=decisions,
                )
            )
            source_position += 1
            target_position += 1
            continue

        scores = _window_lcs_scores(
            source, target, source_position, target_position
        )
        skip_source = scores[1][0]
        skip_target = scores[0][1]

        # On equal local LCS scores, consume source first. The rule is stable;
        # unlike the former nearest-match tie-break, it cannot reduce the
        # number of recoverable occurrences within the bounded window.
        if skip_source >= skip_target:
            operations.append(
                _operation(
                    stage=stage,
                    operation_type=OperationType.DELETION,
                    source_item=source[source_position],
                    target_item=None,
                    source_evidence=source_evidence,
                    target_evidence=target_evidence,
                    source_gap=source[source_position][0],
                    target_gap=target[target_position][0],
                    match_kind=MatchKind.UNEXPLAINED,
                )
            )
            source_position += 1
        else:
            operations.append(
                _operation(
                    stage=stage,
                    operation_type=OperationType.INSERTION,
                    source_item=None,
                    target_item=target[target_position],
                    source_evidence=source_evidence,
                    target_evidence=target_evidence,
                    source_gap=source[source_position][0],
                    target_gap=target[target_position][0],
                    match_kind=MatchKind.ADDED,
                )
            )
            target_position += 1
    while source_position < len(source):
        operations.append(
            _operation(
                stage=stage,
                operation_type=OperationType.DELETION,
                source_item=source[source_position],
                target_item=None,
                source_evidence=source_evidence,
                target_evidence=target_evidence,
                source_gap=source[source_position][0],
                target_gap=(target[-1][0] + 1 if target else 0),
                match_kind=MatchKind.UNEXPLAINED,
            )
        )
        source_position += 1

    while target_position < len(target):
        operations.append(
            _operation(
                stage=stage,
                operation_type=OperationType.INSERTION,
                source_item=None,
                target_item=target[target_position],
                source_evidence=source_evidence,
                target_evidence=target_evidence,
                source_gap=(source[-1][0] + 1 if source else 0),
                target_gap=target[target_position][0],
                match_kind=MatchKind.ADDED,
            )
        )
        target_position += 1

    return operations


def _coalesce_substitutions(
    operations: Sequence[AlignmentOperation],
) -> list[AlignmentOperation]:
    """Pair only residual hard gaps after reordered occurrences are recovered."""
    coalesced: list[AlignmentOperation] = []
    cursor = 0
    while cursor < len(operations):
        if operations[cursor].type not in {
            OperationType.DELETION,
            OperationType.INSERTION,
        }:
            coalesced.append(operations[cursor])
            cursor += 1
            continue

        stop = cursor
        while stop < len(operations) and operations[stop].type in {
            OperationType.DELETION,
            OperationType.INSERTION,
        }:
            stop += 1
        gap = operations[cursor:stop]
        deletions = [item for item in gap if item.type == OperationType.DELETION]
        insertions = [item for item in gap if item.type == OperationType.INSERTION]
        pair_count = min(len(deletions), len(insertions))
        for index in range(pair_count):
            deletion = deletions[index]
            insertion = insertions[index]
            coalesced.append(
                replace(
                    deletion,
                    type=OperationType.SUBSTITUTION,
                    target_index=insertion.target_index,
                    target_token=insertion.target_token,
                    target_context=insertion.target_context,
                    match_kind=MatchKind.DIFFERENT,
                )
            )
        coalesced.extend(deletions[pair_count:])
        coalesced.extend(insertions[pair_count:])
        cursor = stop
    return coalesced


def _mark_order_risks(
    operations: Sequence[AlignmentOperation], stage: AlignmentStage
) -> list[AlignmentOperation]:
    def key(token: TokenEvidence) -> tuple[int | None, str]:
        page_no = token.page_no if stage == AlignmentStage.EXTRACTION else None
        return page_no, token.normalized_text

    insertion_queues: dict[tuple[int | None, str], deque[int]] = defaultdict(deque)
    for index, operation in enumerate(operations):
        if operation.type == OperationType.INSERTION and operation.target_token:
            insertion_queues[key(operation.target_token)].append(index)

    pairs: dict[int, int] = {}
    for index, operation in enumerate(operations):
        if operation.type != OperationType.DELETION or not operation.source_token:
            continue
        candidates = insertion_queues[key(operation.source_token)]
        if candidates:
            pairs[index] = candidates.popleft()

    consumed_insertions = set(pairs.values())
    reordered: list[AlignmentOperation] = []
    for index, operation in enumerate(operations):
        if index in consumed_insertions:
            continue
        partner_index = pairs.get(index)
        if partner_index is None:
            reordered.append(operation)
            continue
        partner = operations[partner_index]
        reordered.append(
            replace(
                operation,
                type=OperationType.ORDER_RISK,
                target_index=partner.target_index,
                target_token=partner.target_token,
                target_context=partner.target_context,
                match_kind=MatchKind.REORDERED,
            )
        )
    return reordered


def _consume_explanations(
    operations: Sequence[AlignmentOperation],
    evidence_tokens: Sequence[AlignableToken],
    match_kind: MatchKind,
) -> list[AlignmentOperation]:
    evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(evidence_tokens)
    )
    available: dict[tuple[int, str], list[TokenEvidence]] = defaultdict(list)
    for token in evidence:
        if token.page_no is not None:
            available[(token.page_no, token.normalized_text)].append(token)

    consumed: set[int] = set()

    def overlaps(source: TokenEvidence, candidate: TokenEvidence) -> bool:
        if not source.bounding_boxes or not candidate.spatial_regions:
            return False
        for region in candidate.spatial_regions:
            if region.page_no != source.page_no:
                continue
            contained = sum(
                region.box.contains_center(box) for box in source.bounding_boxes
            )
            if contained * 2 >= len(source.bounding_boxes):
                return True
        return False

    explained: list[AlignmentOperation] = []
    for operation in operations:
        token = operation.source_token
        if (
            operation.type == OperationType.DELETION
            and operation.match_kind == MatchKind.UNEXPLAINED
            and token is not None
            and token.page_no is not None
        ):
            candidates = [
                candidate
                for candidate in available[(token.page_no, token.normalized_text)][
                    :LOOKAHEAD_TOKENS
                ]
                if candidate.index not in consumed and overlaps(token, candidate)
            ]
            if len(candidates) == 1:
                candidate = candidates[0]
                consumed.add(candidate.index)
                explained.append(
                    replace(
                        operation,
                        match_kind=match_kind,
                        evidence_token=candidate,
                    )
                )
            else:
                explained.append(operation)
        else:
            explained.append(operation)
    return explained


def _explain_semantic_deletions(
    operations: Sequence[AlignmentOperation],
) -> list[AlignmentOperation]:
    """Explain a dropped Docling footnote only from its own typed provenance."""
    explained: list[AlignmentOperation] = []
    for operation in operations:
        token = operation.source_token
        if (
            operation.type == OperationType.DELETION
            and operation.match_kind == MatchKind.UNEXPLAINED
            and token is not None
            and token.semantic_role == "footnote"
            and token.block_id is not None
            and token.provenance
        ):
            explained.append(replace(operation, match_kind=MatchKind.FOOTNOTE))
        else:
            explained.append(operation)
    return explained


def _consume_table_repeat_additions(
    operations: Sequence[AlignmentOperation],
    evidence_tokens: Sequence[AlignableToken],
) -> list[AlignmentOperation]:
    """Consume locally anchored merged-cell repetition slots one-to-one."""
    evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(evidence_tokens)
    )
    available: dict[str, deque[TokenEvidence]] = defaultdict(deque)
    for token in evidence:
        if (
            token.semantic_role == "table_repeat"
            and token.block_id is not None
            and token.provenance
        ):
            available[token.normalized_text].append(token)

    def has_local_anchor(
        operation_index: int, candidate: TokenEvidence
    ) -> bool:
        start = max(0, operation_index - CONTEXT_TOKENS)
        stop = min(len(operations), operation_index + CONTEXT_TOKENS + 1)
        return any(
            nearby.type in {OperationType.MATCH, OperationType.ORDER_RISK}
            and nearby.source_token is not None
            and nearby.source_token.semantic_role == "table_cell"
            and nearby.source_token.block_id == candidate.block_id
            and nearby.source_token.normalized_text == candidate.normalized_text
            for nearby in operations[start:stop]
        )

    explained: list[AlignmentOperation] = []
    for operation_index, operation in enumerate(operations):
        token = operation.target_token
        candidates = available[token.normalized_text] if token is not None else ()
        candidate = next(
            (
                item
                for item in tuple(candidates)[:LOOKAHEAD_TOKENS]
                if has_local_anchor(operation_index, item)
            ),
            None,
        )
        if (
            operation.type == OperationType.INSERTION
            and operation.match_kind == MatchKind.ADDED
            and candidate is not None
        ):
            candidates.remove(candidate)
            explained.append(
                replace(
                    operation,
                    match_kind=MatchKind.TABLE_REPETITION,
                    evidence_token=candidate,
                )
            )
        else:
            explained.append(operation)
    return explained


def align_extraction(
    source_tokens: Sequence[AlignableToken],
    target_tokens: Sequence[AlignableToken],
    *,
    case_profile: str,
    figure_tokens: Sequence[AlignableToken] = (),
    furniture_tokens: Sequence[AlignableToken] = (),
) -> AlignmentResult:
    """Align PDF occurrences to Docling occurrences within their source pages."""
    _validate_case_profiles(
        (source_tokens, target_tokens, figure_tokens, furniture_tokens), case_profile
    )
    source_evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(source_tokens)
    )
    target_evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(target_tokens)
    )
    source_by_page: dict[
        int | None, list[tuple[int, AlignableToken]]
    ] = defaultdict(list)
    target_by_page: dict[
        int | None, list[tuple[int, AlignableToken]]
    ] = defaultdict(list)
    for index, token in enumerate(source_tokens):
        source_by_page[token.page_no].append((index, token))
    for index, token in enumerate(target_tokens):
        target_by_page[token.page_no].append((index, token))
    pages = sorted(
        source_by_page.keys() | target_by_page.keys(),
        key=lambda page: (page is None, page if page is not None else 0),
    )

    operations: list[AlignmentOperation] = []
    for page_no in pages:
        operations.extend(
            _align_partition(
                source_by_page[page_no],
                target_by_page[page_no],
                stage=AlignmentStage.EXTRACTION,
                source_evidence=source_evidence,
                target_evidence=target_evidence,
            )
        )
    operations = _mark_order_risks(operations, AlignmentStage.EXTRACTION)
    operations = _coalesce_substitutions(operations)
    operations = _consume_explanations(operations, figure_tokens, MatchKind.FIGURE)
    operations = _consume_explanations(operations, furniture_tokens, MatchKind.FURNITURE)
    return AlignmentResult(
        stage=AlignmentStage.EXTRACTION,
        source_tokens=source_evidence,
        target_tokens=target_evidence,
        operations=tuple(operations),
        case_profile=case_profile,
    )


def _subsequence_alignment(
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
    source_evidence: Sequence[TokenEvidence],
    target_evidence: Sequence[TokenEvidence],
) -> list[AlignmentOperation] | None:
    """Recognize pure additions/removals in linear time before bounded LCS.

    A duplicated passage can hide the next anchor beyond the LCS window.
    An exhaustive subsequence is stronger evidence than a local mismatch.
    Only complete containment is accepted; mixed edits use the bounded fallback.
    """
    source_is_short = len(source) <= len(target)
    short, long = (source, target) if source_is_short else (target, source)
    pairs: list[tuple[int, int, tuple[MatchKind, tuple[HyphenDecision, ...]]]] = []
    cursor = 0
    for index in range(len(long)):
        if cursor == len(short):
            break
        si, ti = (cursor, index) if source_is_short else (index, cursor)
        match = _match_kind(source, target, si, ti)
        if match is not None:
            pairs.append((si, ti, match))
            cursor += 1
    if cursor != len(short):
        return None
    matched = {ti if source_is_short else si: (si, ti, match)
               for si, ti, match in pairs}
    operations = []
    short_cursor = 0
    for index in range(len(long)):
        pair = matched.get(index)
        if pair is not None:
            si, ti, (kind, decisions) = pair
            operation_type = OperationType.MATCH
            source_item, target_item = source[si], target[ti]
            short_cursor += 1
        else:
            si, ti = ((short_cursor, index) if source_is_short
                      else (index, short_cursor))
            operation_type = OperationType.INSERTION if source_is_short else OperationType.DELETION
            source_item = None if source_is_short else source[si]
            target_item = target[ti] if source_is_short else None
            kind = MatchKind.ADDED if source_is_short else MatchKind.UNEXPLAINED
            decisions = ()
        operations.append(_operation(
            stage=AlignmentStage.DIRECT, operation_type=operation_type,
            source_item=source_item, target_item=target_item,
            source_evidence=source_evidence, target_evidence=target_evidence,
            source_gap=si, target_gap=ti, match_kind=kind,
            hyphen_decisions=decisions,
        ))
    return operations


def _recover_direct_hyphens(
    operations: Sequence[AlignmentOperation],
    source: Sequence[tuple[int, AlignableToken]],
    target: Sequence[tuple[int, AlignableToken]],
) -> list[AlignmentOperation]:
    """Recover moved hyphen joins only with original neighboring evidence.

    Candidate work is bounded per deletion. Exact matches were consumed first;
    a recovered insertion can never explain another source occurrence.
    """
    candidates: dict[str, list[int]] = defaultdict(list)
    for i, op in enumerate(operations):
        if op.type == OperationType.INSERTION and op.target_token:
            token = op.target_token
            for key in {token.normalized_text, token.joined_normalized_text} - {None}:
                candidates[key].append(i)
    consumed: set[int] = set()
    replacements: dict[int, AlignmentOperation] = {}
    for i, op in enumerate(operations):
        if op.type != OperationType.DELETION or op.source_token is None:
            continue
        token = op.source_token
        keys = {token.normalized_text, token.joined_normalized_text} - {None}
        indexes = sorted({j for key in keys for j in candidates.get(key, [])[:LOOKAHEAD_TOKENS]})
        for j in indexes:
            if j in consumed:
                continue
            partner = operations[j]
            match = _match_kind(source, target, op.source_index, partner.target_index)
            if match is None or match[0] != MatchKind.LINE_END_HYPHEN_JOIN:
                continue
            consumed.add(j)
            replacements[i] = replace(
                op, type=OperationType.ORDER_RISK, target_index=partner.target_index,
                target_token=partner.target_token, target_context=partner.target_context,
                match_kind=MatchKind.REORDERED, hyphen_decisions=match[1],
            )
            break
    return [replacements.get(i, op) for i, op in enumerate(operations) if i not in consumed]


def align_direct(
    source_tokens: Sequence[AlignableToken],
    target_tokens: Sequence[AlignableToken],
    *,
    case_profile: str,
) -> AlignmentResult:
    """Compare endpoints globally without intermediate-document explanations."""
    _validate_case_profiles((source_tokens, target_tokens), case_profile)
    source = tuple(_snapshot(i, token) for i, token in enumerate(source_tokens))
    target = tuple(_snapshot(i, token) for i, token in enumerate(target_tokens))
    source_items = list(enumerate(source_tokens))
    target_items = list(enumerate(target_tokens))
    operations = _subsequence_alignment(source_items, target_items, source, target)
    if operations is None:
        operations = _align_partition(
            source_items, target_items, stage=AlignmentStage.DIRECT,
            source_evidence=source, target_evidence=target,
        )
        operations = _mark_order_risks(operations, AlignmentStage.DIRECT)
        operations = _recover_direct_hyphens(operations, source_items, target_items)
        operations = _coalesce_substitutions(operations)
    return AlignmentResult(AlignmentStage.DIRECT, source, target, tuple(operations), case_profile)


def align_serialization(
    source_tokens: Sequence[AlignableToken],
    target_tokens: Sequence[AlignableToken],
    *,
    case_profile: str,
    table_repeat_tokens: Sequence[AlignableToken] = (),
) -> AlignmentResult:
    """Align Docling occurrences to visible Markdown occurrences in order."""
    _validate_case_profiles(
        (source_tokens, target_tokens, table_repeat_tokens), case_profile
    )
    source_evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(source_tokens)
    )
    target_evidence = tuple(
        _snapshot(index, token) for index, token in enumerate(target_tokens)
    )
    indexed_source = list(enumerate(source_tokens))
    indexed_target = list(enumerate(target_tokens))
    operations = _align_partition(
        indexed_source,
        indexed_target,
        stage=AlignmentStage.SERIALIZATION,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
    )
    operations = _mark_order_risks(operations, AlignmentStage.SERIALIZATION)
    operations = _coalesce_substitutions(operations)
    operations = _explain_semantic_deletions(operations)
    operations = _consume_table_repeat_additions(operations, table_repeat_tokens)
    return AlignmentResult(
        stage=AlignmentStage.SERIALIZATION,
        source_tokens=source_evidence,
        target_tokens=target_evidence,
        operations=tuple(operations),
        case_profile=case_profile,
    )


def align_two_stage(
    pdf_tokens: Sequence[AlignableToken],
    docling_tokens: Sequence[AlignableToken],
    markdown_tokens: Sequence[AlignableToken],
    *,
    case_profile: str,
    figure_tokens: Sequence[AlignableToken] = (),
    furniture_tokens: Sequence[AlignableToken] = (),
    table_repeat_tokens: Sequence[AlignableToken] = (),
) -> TwoStageAlignment:
    """Build the two comparisons without flattening their failure evidence."""
    return TwoStageAlignment(
        extraction=align_extraction(
            pdf_tokens,
            docling_tokens,
            case_profile=case_profile,
            figure_tokens=figure_tokens,
            furniture_tokens=furniture_tokens,
        ),
        serialization=align_serialization(
            docling_tokens,
            markdown_tokens,
            case_profile=case_profile,
            table_repeat_tokens=table_repeat_tokens,
        ),
    )
