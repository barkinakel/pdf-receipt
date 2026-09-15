from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from pdf_receipt import structural_integrity as integrity


def label(value: str) -> SimpleNamespace:
    return SimpleNamespace(value=value)


def heading(text: str, level: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        label=label("section_header"),
        text=text,
        level=level,
        hyperlink=None,
    )


def list_group() -> SimpleNamespace:
    return SimpleNamespace(label=label("list"))


def list_item(text: str, *, enumerated: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        label=label("list_item"),
        text=text,
        enumerated=enumerated,
        marker="1." if enumerated else "-",
        hyperlink=None,
    )


def text_item(text: str, hyperlink: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        label=label("text"),
        text=text,
        hyperlink=hyperlink,
    )


def table(rows: list[list[str]]) -> SimpleNamespace:
    grid = [
        [SimpleNamespace(text=value) for value in row]
        for row in rows
    ]
    return SimpleNamespace(label=label("table"), data=SimpleNamespace(grid=grid))


def picture(content_layer: str = "body") -> SimpleNamespace:
    return SimpleNamespace(
        label=label("picture"),
        content_layer=label(content_layer),
    )


def document(
    *entries: tuple[object, int],
    pictures: int = 0,
    furniture_pictures: int = 0,
) -> SimpleNamespace:
    body_pictures = tuple(picture() for _ in range(pictures))
    furniture = tuple(picture("furniture") for _ in range(furniture_pictures))
    items = tuple(entries) + tuple((item, 1) for item in body_pictures)

    def iterate_items(*, with_groups: bool = False):
        visible = (
            (item, level)
            for item, level in items
            if getattr(
                getattr(item, "content_layer", None), "value", "body"
            ) == "body"
        )
        if with_groups:
            return visible
        return iter(
            (item, level)
            for item, level in visible
            if getattr(getattr(item, "label", None), "value", None) != "list"
        )

    return SimpleNamespace(
        iterate_items=iterate_items,
        pictures=body_pictures + furniture,
    )


def save_png(path: Path, size: tuple[int, int] = (3, 2)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, format="PNG")


class StructuralIntegrityTests(unittest.TestCase):
    def evaluate(
        self,
        root: Path,
        doc: object,
        markdown: str,
    ) -> integrity.StructuralIntegrityReport:
        markdown_path = root / "document.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        return integrity.evaluate(
            doc,
            markdown,
            markdown_path=markdown_path,
            output_root=root,
            artifacts_dir=root / "document_artifacts",
        )

    def test_valid_document_records_all_structure_and_image_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            image_path = root / "document_artifacts" / "figure.png"
            save_png(image_path, (7, 5))
            doc = document(
                (heading("Structure", 1), 1),
                (list_group(), 1),
                (list_item("first"), 2),
                (list_item("second"), 2),
                (table([["Name", "Value"], ["Count", "7"]]), 1),
                (text_item("project", "https://example.com/docs"), 1),
                pictures=1,
            )
            markdown = "\n".join(
                (
                    "## Structure",
                    "",
                    "- first",
                    "- second",
                    "",
                    "| Name | Value |",
                    "|---|---:|",
                    "| Count | 7 |",
                    "",
                    "[project](https://example.com/docs)",
                    "",
                    "![Image](document_artifacts/figure.png)",
                )
            )

            report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed)
            self.assertEqual(report.headings.as_tuple(), (1, 1))
            self.assertEqual(report.lists.as_tuple(), (1, 1))
            self.assertEqual(report.list_items.as_tuple(), (2, 2))
            self.assertEqual(report.tables.as_tuple(), (1, 1))
            self.assertEqual(report.table_cells.as_tuple(), (4, 4))
            self.assertEqual(report.links.as_tuple(), (1, 1))
            self.assertEqual(report.images.as_tuple(), (1, 1))
            self.assertEqual(report.valid_image_count, 1)
            self.assertEqual(report.stale_artifact_count, 0)
            self.assertEqual(report.artifacts[0].format, "PNG")
            self.assertEqual(
                (report.artifacts[0].width, report.artifacts[0].height),
                (7, 5),
            )

    def test_lost_heading_changed_list_and_changed_table_cell_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (heading("Expected", 1), 1),
                (list_group(), 1),
                (list_item("kept as a list"), 2),
                (table([["Name", "Value"], ["Count", "7"]]), 1),
            )
            markdown = "\n".join(
                (
                    "# Expected",
                    "",
                    "kept as a paragraph",
                    "",
                    "| Name | Value |",
                    "|---|---:|",
                    "| Count | 8 |",
                )
            )

            report = self.evaluate(root, doc, markdown)
            codes = {issue.code for issue in report.issues}

            self.assertFalse(report.passed)
            self.assertIn("changed_heading", codes)
            self.assertIn("missing_list", codes)
            self.assertIn("missing_list_item", codes)
            self.assertIn("changed_table_cell", codes)
            cell_issue = next(
                issue for issue in report.issues
                if issue.code == "changed_table_cell"
            )
            self.assertEqual(cell_issue.location, "table 1, row 2, column 2")

    def test_fenced_code_does_not_create_false_structure_or_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            markdown = "\n".join(
                (
                    "```markdown",
                    "# false heading",
                    "- false list",
                    "| false | table |",
                    "|---|---|",
                    "[false](missing.txt)",
                    "![false](missing.png)",
                    "```",
                )
            )

            report = self.evaluate(root, document(), markdown)

            self.assertTrue(report.passed)
            self.assertEqual(report.headings.actual, 0)
            self.assertEqual(report.links.actual, 0)
            self.assertEqual(report.images.actual, 0)

    def test_escaped_pipe_and_merged_grid_repetition_compare_by_cell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (table([["Header", "Header"], ["A|B", "7"]]), 1),
            )
            markdown = "\n".join(
                (
                    "| Header | Header |",
                    "|---|---:|",
                    "| A&#124;B | 7 |",
                )
            )

            report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed)
            self.assertEqual(report.table_cells.as_tuple(), (4, 4))

    def test_literal_inline_markers_are_not_discarded_as_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (
                    table(
                        [
                            ["A", "B", "C", "D", "E", "F"],
                            [
                                "foo_bar",
                                "a*b",
                                "~draft~",
                                "tick`value",
                                "bold italic strike code",
                                r"\em",
                            ],
                        ]
                    ),
                    1,
                )
            )
            markdown = "\n".join(
                (
                    "| A | B | C | D | E | F |",
                    "|---|---|---|---|---|---|",
                    (
                        r"| foo\_bar | a*b | ~draft~ | tick`value | "
                        r"**bold** *italic* ~~strike~~ `code` | \\*em* |"
                    ),
                )
            )

            report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed, report.issues)

            changed = self.evaluate(
                root,
                document((table([["foobar"]]), 1)),
                "| A |\n|---|\n| foo_bar |",
            )
            self.assertIn(
                "changed_table_cell", {issue.code for issue in changed.issues}
            )

    def test_lost_table_is_reported_separately_from_cell_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document((table([["Name", "Value"], ["Count", "7"]]), 1))

            report = self.evaluate(root, doc, "No table was serialized.")

            self.assertIn("missing_table", {issue.code for issue in report.issues})
            self.assertEqual(report.tables.as_tuple(), (1, 0))
            self.assertEqual(report.table_cells.as_tuple(), (4, 0))

    def test_nested_lists_keep_group_count_depth_and_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (list_group(), 1),
                (list_item("outer", enumerated=True), 2),
                (list_group(), 3),
                (list_item("inner"), 4),
                (list_item("outer second", enumerated=True), 2),
            )
            markdown = "\n".join(
                (
                    "1. outer",
                    "    - inner",
                    "2. outer second",
                )
            )

            report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed)
            self.assertEqual(report.lists.as_tuple(), (2, 2))
            self.assertEqual(report.list_items.as_tuple(), (3, 3))

    def test_multiline_and_loose_list_item_text_is_joined(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (list_group(), 1),
                (list_item("first line\ncontinuation"), 2),
                (list_item("loose\nparagraph"), 2),
            )
            markdown = "\n".join(
                (
                    "- first line  ",
                    "continuation",
                    "- loose",
                    "",
                    "  paragraph",
                )
            )

            report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed, report.issues)
            self.assertEqual(report.lists.as_tuple(), (1, 1))

    def test_repeated_headings_lists_and_tables_are_consumed_one_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (heading("Repeated", 1), 1),
                (heading("Repeated", 1), 1),
                (list_group(), 1),
                (list_item("same"), 2),
                (list_item("same"), 2),
                (table([["same"]]), 1),
                (table([["same"]]), 1),
            )
            markdown = "\n".join(
                (
                    "## Repeated",
                    "- same",
                    "| Value |",
                    "|---|",
                    "| same |",
                )
            )

            report = self.evaluate(root, doc, markdown)
            codes = [issue.code for issue in report.issues]

            self.assertEqual(codes.count("missing_heading"), 1)
            self.assertEqual(codes.count("missing_list_item"), 1)
            self.assertEqual(codes.count("missing_table"), 1)

    def test_external_and_anchor_links_are_not_opened_as_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (text_item("web", "https://example.com/a"), 1),
                (text_item("mail", "mailto:test@example.com"), 1),
                (text_item("section", "#section"), 1),
            )
            markdown = " ".join(
                (
                    "[web](https://example.com/a)",
                    "[mail](mailto:test@example.com)",
                    "[section](#section)",
                )
            )

            with patch(
                "pdf_receipt.structural_integrity._inspect_local_link",
                side_effect=AssertionError("external targets must not be opened"),
            ):
                report = self.evaluate(root, doc, markdown)

            self.assertTrue(report.passed)

    def test_repeated_link_targets_are_matched_one_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (text_item("first", "https://example.com/repeated"), 1),
                (text_item("second", "https://example.com/repeated"), 1),
            )

            report = self.evaluate(
                root,
                doc,
                "[first](https://example.com/repeated)",
            )

            self.assertEqual(
                [issue.code for issue in report.issues].count("missing_link"),
                1,
            )

    def test_nested_bracket_link_labels_preserve_target_occurrences(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            (root / "guide.md").write_text("guide", encoding="utf-8")
            doc = document(
                (text_item("nested", "guide.md"), 1),
                (text_item("section", "guide.md"), 1),
                (text_item("escaped slash", "guide.md"), 1),
            )

            report = self.evaluate(
                root,
                doc,
                (
                    "literal` [a [nested] label](guide.md) "
                    r"[[section]](guide.md) \\[escaped slash](guide.md)"
                ),
            )

            self.assertTrue(report.passed, report.issues)
            self.assertEqual(report.links.as_tuple(), (3, 3))

    def test_indented_fence_and_false_closing_marker_hide_code_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            markdown = "\n".join(
                (
                    "    ```markdown",
                    "    - false list",
                    "    [false](missing.txt)",
                    "    ```still code",
                    "    # false heading",
                    "    ```",
                )
            )

            report = self.evaluate(root, document(), markdown)

            self.assertTrue(report.passed, report.issues)
            self.assertEqual(report.list_items.actual, 0)
            self.assertEqual(report.links.actual, 0)

    def test_broken_local_link_and_outside_root_target_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            doc = document(
                (text_item("guide", "guide.txt"), 1),
                (text_item("outside", "../outside.txt"), 1),
            )
            markdown = "\n".join(
                (
                    "[guide](guide.txt)",
                    "[outside](../outside.txt)",
                )
            )

            report = self.evaluate(root, doc, markdown)
            codes = {issue.code for issue in report.issues}

            self.assertIn("missing_local_target", codes)
            self.assertIn("outside_output_root", codes)

    def test_valid_directory_and_unreadable_local_links_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            valid = root / "guide.txt"
            valid.write_text("guide", encoding="utf-8")
            directory = root / "folder"
            directory.mkdir()
            doc = document(
                (text_item("guide", "guide.txt"), 1),
                (text_item("folder", "folder"), 1),
            )
            markdown = "[guide](guide.txt) [folder](folder)"

            report = self.evaluate(root, doc, markdown)

            self.assertEqual(
                {issue.code for issue in report.issues},
                {"local_target_not_file"},
            )

            markdown_path = root / "document.md"
            markdown_path.write_text("[guide](guide.txt)", encoding="utf-8")
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                unreadable = integrity.evaluate(
                    document((text_item("guide", "guide.txt"), 1)),
                    "[guide](guide.txt)",
                    markdown_path=markdown_path,
                    output_root=root,
                    artifacts_dir=root / "document_artifacts",
                )
            self.assertIn(
                "unreadable_local_target",
                {issue.code for issue in unreadable.issues},
            )

    @unittest.skipUnless(os.name == "nt", "extended-length paths are Windows-only")
    def test_extended_length_paths_are_normalized_for_containment_checks(self) -> None:
        path = Path(r"\\?\C:\Users\test\output\artifact.png")

        self.assertEqual(
            integrity._normal_path(path),
            Path(r"C:\Users\test\output\artifact.png"),
        )

    def test_missing_empty_invalid_and_unreadable_images_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            artifacts = root / "document_artifacts"
            artifacts.mkdir()
            (artifacts / "empty.png").write_bytes(b"")
            (artifacts / "invalid.png").write_bytes(b"not an image")
            save_png(artifacts / "unreadable.png")

            cases = (
                ("missing.png", "missing_image"),
                ("empty.png", "empty_image"),
                ("invalid.png", "invalid_image"),
            )
            for target, expected_code in cases:
                with self.subTest(target=target):
                    report = self.evaluate(
                        root,
                        document(pictures=1),
                        f"![Image](document_artifacts/{target})",
                    )
                    self.assertIn(expected_code, {issue.code for issue in report.issues})

            with patch(
                "pdf_receipt.structural_integrity._decode_image",
                side_effect=PermissionError("denied"),
            ):
                report = self.evaluate(
                    root,
                    document(pictures=1),
                    "![Image](document_artifacts/unreadable.png)",
                )
            self.assertIn("unreadable_image", {issue.code for issue in report.issues})

    def test_percent_encoded_windows_path_stale_file_and_duplicate_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            artifacts = root / "document_artifacts"
            linked = artifacts / "figure one.png"
            stale = artifacts / "old.png"
            save_png(linked)
            save_png(stale)
            markdown = "\n".join(
                (
                    "![Image](document_artifacts\\figure%20one.png)",
                    "![Image](document_artifacts/figure%20one.png)",
                )
            )

            report = self.evaluate(root, document(pictures=2), markdown)
            codes = {issue.code for issue in report.issues}

            self.assertIn("ambiguous_duplicate_image", codes)
            self.assertIn("stale_artifact", codes)
            self.assertEqual(report.stale_artifact_count, 1)

    def test_docling_local_image_target_with_literal_spaces_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            image_path = root / "document artifacts" / "figure one.png"
            save_png(image_path, (4, 6))

            report = self.evaluate(
                root,
                document(pictures=1),
                "![Image](document artifacts/figure one.png)",
            )

            self.assertTrue(report.passed)
            self.assertEqual(report.valid_image_count, 1)
            self.assertEqual(
                (report.artifacts[0].width, report.artifacts[0].height),
                (4, 6),
            )

    def test_only_body_layer_pictures_are_expected_in_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            image_path = root / "document_artifacts" / "body.png"
            save_png(image_path)

            report = self.evaluate(
                root,
                document(pictures=1, furniture_pictures=1),
                "![Image](document_artifacts/body.png)",
            )

            self.assertTrue(report.passed, report.issues)
            self.assertEqual(report.images.as_tuple(), (1, 1))

    def test_stale_entries_resolving_outside_root_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.TemporaryDirectory() as outside_dir:
                root = Path(temp_dir).resolve()
                outside = Path(outside_dir).resolve()
                artifacts = root / "document_artifacts"
                artifacts.mkdir()
                save_png(artifacts / "file-link.png")
                (artifacts / "directory-link").mkdir()

                def resolved_entry(path: Path) -> Path:
                    return outside / integrity._normal_path(path).name

                with patch(
                    "pdf_receipt.structural_integrity._resolve_artifact_entry",
                    side_effect=resolved_entry,
                ):
                    report = self.evaluate(root, document(), "")
                outside_issues = [
                    issue
                    for issue in report.issues
                    if issue.code == "artifact_target_outside_root"
                ]

                self.assertEqual(len(outside_issues), 2)
                self.assertNotIn(
                    "stale_artifact", {issue.code for issue in report.issues}
                )

    def test_stale_symlink_resolution_error_is_a_normal_integrity_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            artifacts = root / "document_artifacts"
            artifacts.mkdir()
            save_png(artifacts / "loop.png")

            with patch(
                "pdf_receipt.structural_integrity._resolve_artifact_entry",
                side_effect=RuntimeError("symlink loop"),
            ):
                report = self.evaluate(root, document(), "")

            self.assertIn(
                "artifact_scan_error", {issue.code for issue in report.issues}
            )
            self.assertEqual(report.artifacts[0].status, "unreadable")

    def test_external_image_and_image_outside_root_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            report = self.evaluate(
                root,
                document(pictures=2),
                "\n".join(
                    (
                        "![Image](https://example.com/image.png)",
                        "![Image](../outside.png)",
                    )
                ),
            )
            codes = {issue.code for issue in report.issues}

            self.assertIn("external_image", codes)
            self.assertIn("outside_output_root", codes)


if __name__ == "__main__":
    unittest.main()
