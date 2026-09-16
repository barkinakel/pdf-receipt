"""Version-specific Hub diagnostics; no network traffic or model loading."""

from __future__ import annotations

import os
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("PDF_RECEIPT_RUN_HUB_DIAGNOSTICS") == "1",
    "set PDF_RECEIPT_RUN_HUB_DIAGNOSTICS=1 for version-specific download diagnostics",
)
class Hub129RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        installed = version("huggingface-hub")
        if installed != "1.29.0":
            raise unittest.SkipTest(
                f"Recovery diagnostic covers huggingface-hub 1.29.0; installed {installed}. "
                "Re-evaluate download behavior before adapting this diagnostic."
            )

    def test_interrupted_hub_transfer_recovers_by_restarting(self) -> None:
        """Exercise the installed Hub client's file lifecycle without network I/O."""
        from huggingface_hub import file_download

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "model.bin"
            partial = root / "model.bin.incomplete"
            calls = []

            def transfer(url, stream, **kwargs):
                calls.append((stream.tell(), kwargs.get("resume_size", 0)))
                stream.write(b"abc")
                if len(calls) == 1:
                    raise KeyboardInterrupt()
                stream.write(b"def")

            kwargs = dict(incomplete_path=partial, destination_path=destination,
                          url_to_download="https://unused.invalid/model", headers={},
                          expected_size=6, filename="model.bin", force_download=False,
                          etag=None, xet_file_data=None)
            with patch.object(file_download, "http_get", side_effect=transfer):
                with self.assertRaises(KeyboardInterrupt):
                    file_download._download_to_tmp_and_move(**kwargs)
                self.assertFalse(destination.exists())
                self.assertEqual(list(root.glob("*.incomplete")), [])
                file_download._download_to_tmp_and_move(**kwargs)
            self.assertEqual(calls, [(0, 0), (0, 0)])
            self.assertEqual(destination.read_bytes(), b"abcdef")


if __name__ == "__main__":
    unittest.main()
