"""Local, fact-based regression evaluation; deliberately outside the product CLI."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf_receipt import comparison as cp
from pdf_receipt import structural_integrity as si
from pdf_receipt.comparison_batch import _object
from pdf_receipt.comparison_json import render_json


def _keys(value: object, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label} requires exactly: {', '.join(sorted(keys))}")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _path(base: Path, value: str) -> Path:
    if not _text(value) or "\0" in value:
        raise ValueError("Expected a nonempty local path")
    path = Path(value).expanduser()
    if (path.drive or path.root) and not path.is_absolute():
        raise ValueError("Ambiguous drive/root-relative path")
    return (base / path).resolve()


def validate_fact(fact: dict) -> None:
    common = {"id", "kind", "basis", "provenance", "side", "page"}
    additions = {"sequence_count": {"tokens", "count"},
                 "sequence_order": {"before", "after"},
                 "operation_span": {"span", "operation", "count"}}
    if not isinstance(fact, dict) or not isinstance(fact.get("kind"), str) or fact["kind"] not in additions:
        raise ValueError("Unsupported fact kind")
    _keys(fact, common | additions[fact["kind"]], "Fact")
    if not _text(fact["id"]) or not _text(fact["provenance"]) or fact["basis"] not in {"independent", "regression"}:
        raise ValueError("Fact requires id, provenance and independent/regression basis")
    if fact["side"] not in {"source", "target"}:
        raise ValueError("Fact side must be source or target")
    if fact["side"] == "source":
        if not _integer(fact["page"]) or fact["page"] < 1:
            raise ValueError("Source facts require a one-based page")
    elif fact["page"] is not None:
        raise ValueError("Target facts require page null; Markdown has no inferred PDF pages")
    for key in ("tokens", "before", "after"):
        if key in fact and (not isinstance(fact[key], list) or not fact[key] or not all(_text(t) for t in fact[key])):
            raise ValueError("Sequence must be a nonempty array of explicit normalized token strings")
    if "count" in fact and not _integer(fact["count"]):
        raise ValueError("Expected count must be a nonnegative integer")
    if fact["kind"] == "operation_span":
        span = fact["span"]
        if (not isinstance(span, list) or len(span) != 2 or not all(_integer(n) for n in span)
                or span[0] >= span[1] or fact["count"] < 1):
            raise ValueError("Operation fact requires a nonempty [start,end) span and positive count")
        if fact["operation"] not in {"match", "deletion", "insertion", "substitution", "order_risk"}:
            raise ValueError("Unknown expected operation")


def load_manifest(path: Path) -> dict:
    with si._long_path(path).open(encoding="utf-8-sig") as handle:
        data = json.load(handle, object_pairs_hook=_object)
    _keys(data, {"schema_version", "case_profile", "cases"}, "Manifest")
    if data["schema_version"] != "1.0" or data["case_profile"] not in {"unicode", "turkic"}:
        raise ValueError("Unsupported manifest version or case profile")
    if not isinstance(data["cases"], list) or not data["cases"]:
        raise ValueError("Cases must be a nonempty array")
    ids = set()
    for case in data["cases"]:
        _keys(case, {"id", "dataset", "revision", "sample_id", "terms", "provenance", "category", "pdf", "markdown", "facts"}, "Case")
        for field in ("id", "dataset", "revision", "sample_id", "terms", "provenance"):
            if not _text(case[field]):
                raise ValueError(f"Case {field} must be documented")
        if case["id"] in ids or case["category"] not in {"natural", "controlled"}:
            raise ValueError("Duplicate case ID or unsupported category")
        ids.add(case["id"])
        for side in ("pdf", "markdown"):
            _keys(case[side], {"path", "sha256"}, side)
            _path(path.parent, case[side]["path"])
            if not isinstance(case[side]["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", case[side]["sha256"]):
                raise ValueError("Expected lowercase SHA-256 digest")
        if not isinstance(case["facts"], list) or not case["facts"]:
            raise ValueError("Each case requires explicit facts")
        fact_ids = set()
        for fact in case["facts"]:
            validate_fact(fact)
            if fact["id"] in fact_ids:
                raise ValueError("Duplicate fact ID within case")
            fact_ids.add(fact["id"])
    return data


def evaluate_fact(data: dict, fact: dict) -> dict:
    """Consume schema 1.0 occurrence evidence without re-tokenizing expectations."""
    row = {"id": fact["id"], "basis": fact["basis"], "provenance": fact["provenance"],
           "expected": fact, "status": "error", "observed": None, "error": None}
    try:
        validate_fact(fact)
        if data["schema_version"] != "1.0" or not data["truncation"]["occurrence_details_complete"]:
            raise ValueError("Complete comparison schema 1.0 evidence required")
        if fact["side"] == "source" and fact["page"] > data["coverage"]["page_count"]:
            raise ValueError("Source page is outside the document")
        tokens = [t for t in data[fact["side"] + "_tokens"] if fact["side"] == "target" or t["page"] == fact["page"]]
        if fact["side"] == "source" and fact["page"] in data["coverage"]["unverified_pages"]:
            raise ValueError("Source page has no comparable text; facts are unverified")

        def occurrences(sequence: list[str], *, overlapping: bool = False) -> list[list[int]]:
            # Counts allocate disjoint occurrences; order checks inspect every
            # possible anchor start so overlapping repetitions remain ambiguous.
            found, cursor = [], 0
            while cursor + len(sequence) <= len(tokens):
                selected = tokens[cursor:cursor + len(sequence)]
                if [t["normalized_text"] for t in selected] == sequence:
                    found.append([t["index"] for t in selected])
                    cursor += 1 if overlapping else len(sequence)
                else:
                    cursor += 1
            return found

        if fact["kind"] == "sequence_count":
            found = occurrences(fact["tokens"])
            indexes = {i for occurrence in found for i in occurrence}
            row["observed"] = {"count": len(found), "occurrence_indexes": found,
                               "tokens": [t for t in tokens if t["index"] in indexes]}
            passed = len(found) == fact["count"]
        elif fact["kind"] == "sequence_order":
            before = occurrences(fact["before"], overlapping=True)
            after = occurrences(fact["after"], overlapping=True)
            indexes = {i for occurrence in before + after for i in occurrence}
            row["observed"] = {"before": before, "after": after,
                               "tokens": [t for t in tokens if t["index"] in indexes]}
            if len(before) > 1 or len(after) > 1:
                raise ValueError("Ambiguous ordering anchors; each must occur exactly once")
            passed = bool(before and after and before[0][-1] < after[0][0])
        else:
            start, end = fact["span"]
            intersecting = [t for t in tokens if t["span"]["start"] < end and t["span"]["end"] > start]
            if not intersecting or intersecting[0]["span"]["start"] != start or intersecting[-1]["span"]["end"] != end:
                raise ValueError("Span must start/end on exact token boundaries")
            indexes = {t["index"] for t in intersecting}
            operations = [op for op in data["operations"] if op[fact["side"] + "_index"] in indexes]
            row["observed"] = {"count": len(operations), "operations": operations, "tokens": intersecting}
            passed = len(operations) == fact["count"] and all(op["type"] == fact["operation"] for op in operations)
        row["status"] = "pass" if passed else "fail"
    except (ValueError, KeyError, TypeError) as exc:
        row["error"] = str(exc)
    return row


def _verify(paths: dict[str, Path], case: dict) -> None:
    for side, path in paths.items():
        digest = sha256()
        with si._long_path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != case[side]["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {side}")


def evaluate(manifest: dict, base: Path) -> dict:
    rows = []
    for case in manifest["cases"]:
        row = {"metadata": {k: v for k, v in case.items() if k != "facts"}, "status": "error",
               "inputs_verified": False, "facts": [], "error": None}
        try:
            paths = {side: _path(base, case[side]["path"]) for side in ("pdf", "markdown")}
            _verify(paths, case)
            result = cp.read_comparison(paths["pdf"], paths["markdown"], case_profile=manifest["case_profile"])
            data = json.loads(render_json(result))
            facts = [evaluate_fact(data, fact) for fact in case["facts"]]
            _verify(paths, case)
            row["inputs_verified"] = True
            row["facts"] = facts
            row["status"] = "error" if any(f["status"] == "error" for f in facts) else "fail" if any(f["status"] == "fail" for f in facts) else "pass"
        except Exception as exc:
            row["error"] = str(exc)
            row["facts"] = [{"id": fact["id"], "basis": fact["basis"], "provenance": fact["provenance"],
                             "expected": fact, "status": "error", "observed": None, "error": "Case inputs or comparison could not be verified"}
                            for fact in case["facts"]]
        finally:
            result = data = None
        rows.append(row)
    return {"schema_version": "1.0", "report_type": "comparison_evaluation", "case_profile": manifest["case_profile"],
            "settings": {"comparison_schema_version": "1.0", "sequence_matching": "exact_normalized_nonoverlapping",
                         "order_anchor_matching": "exact_all_starts_unique",
                         "operation_evidence": "complete", "source_page_mapping": "explicit_physical_page"},
            "limits": "Selected facts only; not document accuracy or an upstream benchmark score.", "cases": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate explicit local comparison facts offline. No models or downloads.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path, required=True, help="New JSON report; never overwrite")
    args = parser.parse_args(argv)
    try:
        source, output = args.manifest.resolve(), args.report.absolute()
        manifest = load_manifest(source)
        protected = {source} | {_path(source.parent, case[side]["path"]) for case in manifest["cases"] for side in ("pdf", "markdown")}
        if output.resolve() in protected or os.path.lexists(si._long_path(output)):
            raise ValueError("Report exists or collides with an input")
        if not si._long_path(output.parent).is_dir():
            raise ValueError("Report parent directory must exist")
        data = evaluate(manifest, source.parent)
        with si._long_path(output).open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.write("\n")
        print(f"Evaluation report: {output}")
        return int(any(case["status"] != "pass" for case in data["cases"]))
    except Exception as exc:
        print(f"Evaluation failed: {exc}. A partial report may remain after a write failure.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
