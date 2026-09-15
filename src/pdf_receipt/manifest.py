"""Completion records and conservative, model-free output reuse checks."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator
from urllib.parse import unquote, urlsplit

from . import structural_integrity as integrity

if TYPE_CHECKING:
    from .converter import OutputPaths

SCHEMA_VERSION = 1
APPLICATION_VERSION = "0.1.0"


def _io(path: Path) -> Path:
    from .converter import long_path

    return long_path(path)


def manifest_path(output: OutputPaths) -> Path:
    return output.directory / f"{output.markdown.stem}_manifest.json"


def lock_path(output: OutputPaths) -> Path:
    return output.directory / f"{output.markdown.stem}_conversion.lock"


def settings(profile: str, formula: bool, image_scale: float, report: bool) -> dict[str, Any]:
    return dict(profile=profile, formula=formula, image_scale=image_scale, report=report)


def versions() -> dict[str, str]:
    # The source digest also invalidates editable/source checkouts without a release bump.
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return {"application": APPLICATION_VERSION, "application_sha256": digest.hexdigest(),
            "docling": version("docling"), "docling_core": version("docling-core")}


def fingerprint(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with _io(path).open("rb") as stream:
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed while being read: {path.name}")
    return {"size": after.st_size, "sha256": digest.hexdigest()}


def source_identity(path: Path) -> dict[str, Any]:
    before = _io(path).stat()
    result = fingerprint(path)
    after = _io(path).stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed while being read")
    return {"path": str(path.resolve()), "mtime_ns": after.st_mtime_ns, **result}


def atomic_write(output: OutputPaths, payload: dict[str, Any]) -> None:
    """Replace only the completion record, on the same filesystem, after flushing."""
    target = _io(manifest_path(output))
    fd, temporary = tempfile.mkstemp(prefix=".pdf-receipt-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def conversion_lock(output: OutputPaths) -> Iterator[None]:
    """Prevent two cooperating writers from completing mixed outputs."""
    target = _io(lock_path(output))
    try:
        stream = target.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError(
            f"Conversion lock exists: {lock_path(output)}. If no conversion is running, "
            "remove this lock file and retry."
        ) from None
    try:
        with stream:
            stream.write(f"pid={os.getpid()}\n")
        yield
    finally:
        target.unlink()


def _relative(path: Path, output: OutputPaths) -> str:
    relative = path.relative_to(output.directory)
    resolved = _io(path).resolve()
    if not resolved.is_relative_to(_io(output.directory).resolve()):
        raise ValueError(f"Output escapes its directory: {relative}")
    return relative.as_posix()


def _image_target(target: str, output: OutputPaths) -> Path:
    if urlsplit(target).scheme or "\\" in target:
        raise ValueError("Image target must be a relative forward-slash path")
    path, error = integrity._resolve_local_target(
        target, markdown_path=output.markdown, output_root=output.directory)
    if error or path is None:
        raise ValueError(f"Invalid image target: {target}")
    if not _io(path).resolve().is_relative_to(_io(output.artifacts).resolve()):
        raise ValueError("Image target is outside the artifact directory")
    # Preserve the planned root's path form (including Windows long-path handling).
    return output.directory / Path(unquote(urlsplit(target).path))


def inventory(output: OutputPaths, report: bool) -> dict[str, Any]:
    """Validate and hash required exports and every referenced image, never extra files."""
    from docling_core.types.doc import DoclingDocument

    markdown = _io(output.markdown).read_text(encoding="utf-8")
    document = json.loads(_io(output.json).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_name") != "DoclingDocument":
        raise ValueError("JSON is not a DoclingDocument")
    DoclingDocument.model_validate(document)
    parsed = integrity.parse_markdown(markdown)
    images = {_image_target(link.target, output) for link in parsed.images}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            image = value.get("image")
            if isinstance(image, dict) and "uri" in image:
                # Docling serializes relative Path values with Windows separators.
                images.add(_image_target(image["uri"].replace("\\", "/"), output))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    for path in images:
        integrity._decode_image(path)
    for link in parsed.links:
        if integrity._target_kind(link.target) == "local":
            path, error = integrity._resolve_local_target(
                link.target, markdown_path=output.markdown, output_root=output.directory)
            if error or path is None or integrity._inspect_local_link(path):
                raise ValueError(f"Broken local link: {link.target}")

    exports = {"markdown": _relative(output.markdown, output),
               "json": _relative(output.json, output),
               "report": _relative(output.report, output) if report else None,
               "artifacts": _relative(output.artifacts, output)}
    paths = [output.markdown, output.json, *sorted(images)]
    if report:
        if not _io(output.report).read_text(encoding="utf-8").strip():
            raise ValueError("Quality report is empty")
        paths.append(output.report)
    # Empty Markdown is valid for an empty or fast-profile scanned document.
    return {"paths": exports,
            "files": {_relative(path, output): fingerprint(path) for path in paths},
            "artifact_paths": sorted(_relative(path, output) for path in images)}


def complete(output: OutputPaths, source: dict[str, Any], options: dict[str, Any]) -> None:
    payload = {"manifest_version": SCHEMA_VERSION, "source": source,
               "versions": versions(), "settings": options,
               "outputs": inventory(output, options["report"]), "complete": True}
    atomic_write(output, payload)


def reusable(pdf: Path, output: OutputPaths, options: dict[str, Any]) -> bool:
    """A missing, unreadable, old or inconsistent record is always a cache miss."""
    try:
        # Hold the writer lock while checking so a concurrent conversion cannot
        # invalidate or replace files halfway through an otherwise valid check.
        with conversion_lock(output):
            payload = json.loads(_io(manifest_path(output)).read_text(encoding="utf-8"))
            return (
                payload["manifest_version"] == SCHEMA_VERSION
                and payload["complete"] is True
                and payload["settings"] == options
                and payload["versions"] == versions()
                and payload["source"] == source_identity(pdf)
                and payload["outputs"] == inventory(output, options["report"])
            )
    except Exception:
        return False
