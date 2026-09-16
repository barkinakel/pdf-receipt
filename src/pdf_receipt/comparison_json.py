"""Versioned endpoint evidence export, independent of Markdown rendering."""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict
import json
import re
from typing import TYPE_CHECKING
from .comparison_groups import GROUP_OPERATION_LIMIT

if TYPE_CHECKING:
    from .comparison import ComparisonResult
    from .alignment import TokenEvidence


def render_json(comparison: ComparisonResult) -> str:
    result, metrics = comparison.alignment, comparison.metrics
    line_starts = [0] + [m.end() for m in re.finditer(r"\r\n|\r|\n", comparison.markdown)]

    def token_data(token: TokenEvidence, source: bool) -> dict[str, object]:
        return {"index": token.index, "raw_text": token.raw_text,
                "normalized_text": token.normalized_text,
                "span": asdict(token.source_span), "page": token.page_no if source else None,
                "line": None if source else bisect_right(line_starts, token.source_span.start),
                "joined_normalized_text": token.joined_normalized_text,
                "line_end_hyphen_spans": [asdict(span) for span in token.line_end_hyphen_spans],
                "line_end_parts": list(token.line_end_parts)}

    def rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
        return {"numerator": numerator, "denominator": denominator,
                "value": numerator / denominator if denominator else None}

    selected = comparison.groups[:comparison.issue_limit]
    shown = sum(len(group.operations) for group in selected)
    total = sum(len(group.operations) for group in comparison.groups)
    data = {
        "schema_version": "1.0",
        "inputs": {"pdf_name": comparison.pdf.name, "markdown_name": comparison.markdown_path.name},
        "settings": {"case_profile": result.case_profile, "lookahead_tokens": result.lookahead_tokens,
                     "markdown_dialect": "commonmark+pipe_tables", "issue_limit": comparison.issue_limit,
                     "group_operation_limit": GROUP_OPERATION_LIMIT, "excerpt_character_limit": 800,
                     "group_ranking": "operation_count_descending_then_alignment_order"},
        "evidence_limits": {"source": "PDF text layer, not ground truth", "ocr_performed": False,
                            "visual_fidelity_verified": False, "table_structure_verified": False,
                            "equation_meaning_verified": False, "image_fidelity_verified": False},
        "coverage": {"page_count": len(comparison.pdf.pages),
                     "unverified_pages": [i for i, counts in enumerate(comparison.page_counts, 1) if not counts],
                     "pages": [{"page": i, "source_tokens": sum(dict(counts).values()),
                                "counts": {kind: dict(counts).get(kind, 0) for kind in
                                           ("match", "deletion", "substitution", "order_risk")}}
                               for i, counts in enumerate(comparison.page_counts, 1)]},
        "counts": {"source_tokens": metrics.source_token_count, "target_tokens": metrics.target_token_count,
                   "matches": metrics.matched_source_count, "normalized_matches": metrics.normalized_match_count,
                   "contextual_hyphen_matches": metrics.contextual_hyphen_match_count,
                   "missing": metrics.unexplained_deletion_count, "added": metrics.unexpected_insertion_count,
                   "substitutions": metrics.substitution_count, "order_risks": metrics.order_risk_count},
        "rates": {"accepted_transfer": rate(metrics.matched_source_count, metrics.source_token_count),
                  "loss": rate(metrics.unexplained_loss_numerator, metrics.source_token_count),
                  "addition": rate(metrics.unexpected_addition_numerator, metrics.target_token_count)},
        "source_tokens": [token_data(token, True) for token in result.source_tokens],
        "target_tokens": [token_data(token, False) for token in result.target_tokens],
        "operations": [{"index": index, "type": op.type.value, "match_kind": op.match_kind.value,
                        "source_index": op.source_index, "target_index": op.target_index,
                        "source_context": asdict(op.source_context), "target_context": asdict(op.target_context),
                        "hyphen_decisions": list(op.hyphen_decisions)}
                       for index, op in enumerate(result.operations)],
        "displayed_groups": [{"type": group.operations[0].type.value,
                              "operation_indexes": list(range(group.first_operation,
                                                              group.first_operation + len(group.operations)))}
                             for group in selected],
        "images": [{"line": line, "target": target, "status": status}
                   for line, target, status in comparison.images],
        "truncation": {"occurrence_details_complete": True, "operations_omitted": 0,
                       "groups_total": len(comparison.groups), "groups_shown": len(selected),
                       "groups_omitted": len(comparison.groups) - len(selected),
                       "markdown_difference_operations_shown": shown,
                       "markdown_difference_operations_omitted": total - shown,
                       "json_text_truncated": False},
    }
    return json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
