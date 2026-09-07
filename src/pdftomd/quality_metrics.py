"""Quality Report v2 metrics derived solely from ordered alignment results."""

from __future__ import annotations

from dataclasses import dataclass

from . import alignment

REPRESENTATIVE_ISSUE_LIMIT = 8
EXPLAINED_DELETION_KINDS = frozenset(
    (
        alignment.MatchKind.FIGURE,
        alignment.MatchKind.FURNITURE,
        alignment.MatchKind.FOOTNOTE,
    )
)
EXPLAINED_ADDITION_KINDS = frozenset((alignment.MatchKind.TABLE_REPETITION,))


@dataclass(frozen=True)
class RepresentativeIssue:
    """One occurrence-level issue with its bounded alignment context."""

    operation: alignment.AlignmentOperation
    source_context: tuple[alignment.TokenEvidence, ...]
    target_context: tuple[alignment.TokenEvidence, ...]


@dataclass(frozen=True)
class StageMetrics:
    """Counts and rates for exactly one alignment stage."""

    stage: alignment.AlignmentStage
    source_token_count: int
    target_token_count: int
    normalized_match_count: int
    contextual_hyphen_match_count: int
    explained_deletion_count: int
    unexplained_deletion_count: int
    unexpected_insertion_count: int
    explained_addition_count: int
    substitution_count: int
    order_risk_count: int
    representative_issues: tuple[RepresentativeIssue, ...] = ()

    def __post_init__(self) -> None:
        if self.source_accounted_count != self.source_token_count:
            raise ValueError(
                "source accounting identity failed: "
                f"{self.source_accounted_count} != {self.source_token_count}"
            )
        if self.target_accounted_count != self.target_token_count:
            raise ValueError(
                "target accounting identity failed: "
                f"{self.target_accounted_count} != {self.target_token_count}"
            )

    @property
    def matched_source_count(self) -> int:
        """Accepted matches, including contextual line-end-hyphen matches."""
        return self.normalized_match_count + self.contextual_hyphen_match_count

    @property
    def source_accounted_count(self) -> int:
        return (
            self.matched_source_count
            + self.explained_deletion_count
            + self.unexplained_deletion_count
            + self.substitution_count
            + self.order_risk_count
        )

    @property
    def target_accounted_count(self) -> int:
        return (
            self.matched_source_count
            + self.explained_addition_count
            + self.unexpected_insertion_count
            + self.substitution_count
            + self.order_risk_count
        )

    @property
    def unexplained_loss_numerator(self) -> int:
        return self.unexplained_deletion_count + self.substitution_count

    @property
    def unexpected_addition_numerator(self) -> int:
        return self.unexpected_insertion_count + self.substitution_count

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    @property
    def normalized_exact_transfer_rate(self) -> float | None:
        return self._rate(self.matched_source_count, self.source_token_count)

    @property
    def accounted_for_loss_rate(self) -> float | None:
        return self._rate(self.explained_deletion_count, self.source_token_count)

    @property
    def unexplained_loss_rate(self) -> float | None:
        return self._rate(self.unexplained_loss_numerator, self.source_token_count)

    @property
    def unexpected_addition_rate(self) -> float | None:
        return self._rate(
            self.unexpected_addition_numerator,
            self.target_token_count,
        )


def summarize_alignment(
    result: alignment.AlignmentResult,
    *,
    issue_limit: int = REPRESENTATIVE_ISSUE_LIMIT,
) -> StageMetrics:
    """Count one alignment without rematching or flattening occurrences."""
    counts = {
        "normalized": 0,
        "hyphen": 0,
        "explained_deletion": 0,
        "unexplained_deletion": 0,
        "unexpected_insertion": 0,
        "explained_addition": 0,
        "substitution": 0,
        "order_risk": 0,
    }
    issues: list[RepresentativeIssue] = []

    for operation in result.operations:
        if operation.type == alignment.OperationType.MATCH:
            if operation.match_kind == alignment.MatchKind.NORMALIZED:
                counts["normalized"] += 1
            elif operation.match_kind == alignment.MatchKind.LINE_END_HYPHEN_JOIN:
                counts["hyphen"] += 1
            else:
                raise ValueError(f"unsupported match kind: {operation.match_kind}")
        elif operation.type == alignment.OperationType.DELETION:
            key = (
                "explained_deletion"
                if operation.match_kind in EXPLAINED_DELETION_KINDS
                else "unexplained_deletion"
            )
            counts[key] += 1
        elif operation.type == alignment.OperationType.INSERTION:
            key = (
                "explained_addition"
                if operation.match_kind in EXPLAINED_ADDITION_KINDS
                else "unexpected_insertion"
            )
            counts[key] += 1
        elif operation.type == alignment.OperationType.SUBSTITUTION:
            counts["substitution"] += 1
        elif operation.type == alignment.OperationType.ORDER_RISK:
            counts["order_risk"] += 1
        else:  # pragma: no cover - enum exhaustiveness guard
            raise ValueError(f"unsupported operation type: {operation.type}")

        if operation.type != alignment.OperationType.MATCH and len(issues) < issue_limit:
            issues.append(
                RepresentativeIssue(
                    operation=operation,
                    source_context=result.source_tokens[
                        operation.source_context.start : operation.source_context.end
                    ],
                    target_context=result.target_tokens[
                        operation.target_context.start : operation.target_context.end
                    ],
                )
            )

    return StageMetrics(
        stage=result.stage,
        source_token_count=len(result.source_tokens),
        target_token_count=len(result.target_tokens),
        normalized_match_count=counts["normalized"],
        contextual_hyphen_match_count=counts["hyphen"],
        explained_deletion_count=counts["explained_deletion"],
        unexplained_deletion_count=counts["unexplained_deletion"],
        unexpected_insertion_count=counts["unexpected_insertion"],
        explained_addition_count=counts["explained_addition"],
        substitution_count=counts["substitution"],
        order_risk_count=counts["order_risk"],
        representative_issues=tuple(issues),
    )
