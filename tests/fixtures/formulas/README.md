# Formula fixture

`formula_equations.pdf` is an original, single-page PDF with two typeset equations
and four surrounding prose sentences. The expected mathematics is:

```latex
a^2 + b^2 = c^2
x = \frac{a+b}{c+d}
```

The superscripts use raised glyphs and the fraction uses a drawn horizontal rule;
the PDF does not contain hidden LaTeX. `generate_formula_fixture.py` uses the
existing standard-library PDF writer and standard Times fonts. Regenerate only
this fixture, without touching the earlier corpus:

```powershell
.venv\Scripts\python.exe tests\fixtures\formulas\generate_formula_fixture.py
```

The live test requires two formula items in JSON, matching display-math blocks
in Markdown, and each prose sentence exactly once in the correct position.
Only whitespace, LaTeX thin-space commands (`\,`), and optional braces around
single-digit exponents are normalized.
This is a small regression case, not a general formula-accuracy benchmark.

After caching CodeFormulaV2 and the ordinary conversion models:

The formula test pins snapshot `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`, including
engine-specific revision overrides. That exact snapshot must already be cached;
the test never falls back to a different cached `main` revision or downloads it.
Application defaults are unchanged.

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PDF_RECEIPT_RUN_FORMULA_TESTS = "1"
.venv\Scripts\python.exe -m unittest tests.integration.test_formula_conversion
```

The suite also makes the optional formula engine unavailable while converting
normally in both profiles. An explicit formula request must fail visibly and
leave its manifest incomplete.

The simulated transfer interruption is a separate, version-specific diagnostic:

```powershell
$env:PDF_RECEIPT_RUN_HUB_DIAGNOSTICS = "1"
.venv\Scripts\python.exe -m unittest tests.integration.test_hub_recovery
```

It exercises Hugging Face Hub 1.29.0's temporary-file lifecycle without HTTP
traffic or model loading. Other versions are explicitly skipped with a reason:
their download behavior must be re-evaluated instead of treating a dependency
implementation change as a formula conversion regression. No dependency pin is
added by this diagnostic.
