"""Sequential offline comparison of explicitly paired endpoints."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys

from . import comparison as cp
from . import structural_integrity as si
from .comparison_json import render_json


@dataclass(frozen=True)
class Pair:
    id: str
    pdf: Path
    markdown: Path
    error: str | None


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_pairs(path: Path) -> tuple[Pair, ...]:
    with si._long_path(path).open(encoding="utf-8-sig") as handle:
        data = json.load(handle, object_pairs_hook=_object)
    if not isinstance(data, dict) or set(data) != {"schema_version", "pairs"} or data["schema_version"] != "1.0":
        raise ValueError("Pair list requires schema_version '1.0' and pairs")
    if not isinstance(data["pairs"], list) or not data["pairs"]:
        raise ValueError("pairs must be a nonempty array")
    result, ids, endpoints = [], set(), set()
    for item in data["pairs"]:
        if not isinstance(item, dict) or set(item) != {"id", "pdf", "markdown"}:
            raise ValueError("Each pair requires exactly id, pdf and markdown")
        identifier = item["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", identifier):
            raise ValueError("Pair id must contain 1-64 ASCII letters, digits, underscores or hyphens, starting with a letter or digit")
        if identifier.casefold() in ids:
            raise ValueError(f"Duplicate pair id: {identifier}")
        ids.add(identifier.casefold())
        paths = []
        for field in ("pdf", "markdown"):
            value = item[field]
            if not isinstance(value, str) or not value.strip() or "\0" in value:
                raise ValueError(f"Pair {identifier}: {field} must be a nonempty path")
            local = Path(value).expanduser()
            if (local.drive or local.root) and not local.is_absolute():
                raise ValueError("Drive-relative paths are ambiguous; use an absolute path")
            paths.append((path.parent / local).resolve())
        key = tuple(paths)
        if key in endpoints:
            raise ValueError(f"Duplicate endpoint pair: {identifier}")
        endpoints.add(key)
        error = None
        try:
            cp.validate_inputs(*paths)
        except (ValueError, OSError) as exc:
            error = str(exc)
        result.append(Pair(identifier, *paths, error))
    return tuple(result)


def _targets(root: Path, identifier: str) -> list[tuple[str, Path]]:
    return [("Markdown", root / f"pair-{identifier}.md"), ("JSON", root / f"pair-{identifier}.json")]


def preflight(pairs: tuple[Pair, ...], manifest: Path, root: Path) -> None:
    if not si._long_path(root).is_dir():
        raise ValueError("Output directory must already exist")
    protected = {manifest.resolve()} | {p for pair in pairs for p in (pair.pdf, pair.markdown)}
    targets = [root / "batch_summary.md", root / "batch_summary.json"]
    targets.extend(path for pair in pairs for _, path in _targets(root, pair.id))
    for target in targets:
        resolved = target.resolve()
        if resolved in protected or os.path.lexists(si._long_path(target)):
            raise ValueError(f"Report path exists or collides with an input/output: {target}")
        protected.add(resolved)


def run_batch(pairs: tuple[Pair, ...], root: Path, *, case_profile: str, issue_limit: int) -> dict:
    rows = []
    for pair in pairs:
        row = {"id": pair.id, "pdf": str(pair.pdf), "markdown": str(pair.markdown),
               "status": "failed", "error": pair.error, "has_differences": None,
               "unverified_pages": None, "counts": None, "reports": []}
        try:
            if pair.error is not None:
                raise ValueError(pair.error)
            result = cp.read_comparison(pair.pdf, pair.markdown, case_profile=case_profile, issue_limit=issue_limit)
            metrics = result.metrics
            row["counts"] = {"source_tokens": metrics.source_token_count, "target_tokens": metrics.target_token_count,
                             "missing": metrics.unexplained_deletion_count, "added": metrics.unexpected_insertion_count,
                             "substitutions": metrics.substitution_count, "order_risks": metrics.order_risk_count}
            row["has_differences"] = bool(result.groups)
            row["unverified_pages"] = [i for i, counts in enumerate(result.page_counts, 1) if not counts]
            rendered = [cp.render_markdown(result), render_json(result)]
            written = cp.write_reports(_targets(root, pair.id), rendered)
            row["reports"] = [{"kind": item.kind, "path": item.path.name,
                               "status": "written" if item.error is None else "failed", "error": item.error}
                              for item in written]
            errors = [item.error for item in written if item.error is not None]
            row["error"] = "; ".join(errors) if errors else None
            row["status"] = "failed" if errors else "success"
        except Exception as exc:
            row["error"] = str(exc)
        finally:
            # Release document-sized evidence before reading the next pair.
            result = None
            rendered = None
        if row["status"] == "failed":
            print(f"Pair {pair.id} failed: {row['error']}", file=sys.stderr)
        rows.append(row)
    return {"schema_version": "1.0", "report_type": "comparison_batch",
            "settings": {"case_profile": case_profile, "issue_limit": issue_limit},
            "totals": {"pairs": len(rows), "succeeded": sum(r["status"] == "success" for r in rows),
                       "failed": sum(r["status"] == "failed" for r in rows)},
            "evidence_limits": "PDF text is not ground truth; differences and unverified pages are not execution failures.",
            "pairs": rows}


def summary_markdown(data: dict) -> str:
    totals = data["totals"]
    lines = ["# Batch comparison", "", f"Pairs: {totals['pairs']}; succeeded: {totals['succeeded']}; failed: {totals['failed']}.",
             "", data["evidence_limits"], "", "| Pair | Status | Differences | Unverified pages | Reports / error |",
             "| --- | --- | --- | --- | --- |"]
    for row in data["pairs"]:
        links = " ".join(f"[{r['kind']}]({r['path']})" for r in row["reports"] if r["status"] == "written")
        details = links + (" " + cp._code(row["error"]) if row["error"] is not None else "")
        differences = "unknown" if row["has_differences"] is None else str(row["has_differences"]).lower()
        pages = "unknown" if row["unverified_pages"] is None else ", ".join(map(str, row["unverified_pages"])) or "none"
        lines.append(f"| {row['id']} | {row['status']} | {differences} | {pages} | {details} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pdf-receipt compare-batch", description="Compare explicit PDF/Markdown pairs offline, sequentially, without models. Pair paths are relative to the list file. All reports use exclusive creation.")
    parser.add_argument("pairs", type=Path, help="UTF-8 JSON pair list, schema_version 1.0")
    parser.add_argument("--output-dir", type=Path, required=True, help="Existing directory for pair reports and batch_summary.md/json; no overwrites")
    parser.add_argument("--case-profile", choices=("unicode", "turkic"), default="unicode")
    parser.add_argument("--issue-limit", type=cp._positive, default=50, help="Maximum Markdown groups per pair (default 50); JSON retains all occurrences")
    args = parser.parse_args(argv)
    try:
        manifest, root = args.pairs.expanduser().resolve(), args.output_dir.expanduser().resolve()
        pairs = load_pairs(manifest)
        preflight(pairs, manifest, root)
        data = run_batch(pairs, root, case_profile=args.case_profile, issue_limit=args.issue_limit)
        written = cp.write_reports([("batch Markdown", root / "batch_summary.md"), ("batch JSON", root / "batch_summary.json")],
                                   [summary_markdown(data), json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n"])
        return int(bool(data["totals"]["failed"] or any(item.error is not None for item in written)))
    except Exception as exc:
        print(f"Batch comparison failed: {exc}", file=sys.stderr)
        return 1
