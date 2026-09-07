"""Test package.

Puts `src` on the import path so the suite runs without installing the
project: `python -m unittest discover -s tests -t .` is enough.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
