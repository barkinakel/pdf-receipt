# Project instructions

## Purpose and scope

- This is a Windows-first, local PDF-to-Markdown tool built on Docling.
- Preserve the core product promise: after the documented initial model setup,
  conversion stays local and works offline.
- The primary outputs are readable Markdown, Docling JSON, referenced image
  artifacts, and an honest quality report.
- `docs/TODO.md` is the ordered implementation plan. Work only on the milestone
  explicitly requested by the user; do not start the next milestone implicitly.
- Read `docs/QUALITY_REPORT_RESEARCH.md` before changing quality metrics,
  comparison algorithms, or benchmark strategy.

## Before editing

- Inspect `git status` and preserve all existing user changes. Never discard,
  overwrite, or reformat unrelated work.
- Read the relevant implementation and tests before proposing or applying a
  design.
- Treat the acceptance criteria in the requested `docs/TODO.md` milestone as the
  definition of done.
- Make reasonable, reversible decisions within the written plan and continue
  without asking the user to approve routine implementation details.

## Language

- Everything committed to this repository is written in English: code,
  identifiers, comments, docstrings, test names, console and log output, commit
  messages, and documentation.
- `README_tr.md` is the single exception. It is the Turkish translation of
  `README.md`, so write Turkish there and keep the two in step whenever public
  behavior changes. Never let Turkish leak into any other file.
- Converse with the user in Turkish. The language of the conversation says
  nothing about the language of the work product.

## Implementation rules

- Support Python 3.10 or newer and follow the existing `src/pdf_receipt` structure,
  type-hint style, dataclasses, and standard-library `unittest` tests.
- Keep Docling imports lazy where practical so unit tests and basic CLI parsing
  do not load models unnecessarily.
- Do not add a runtime dependency without explicit user approval. Development-
  only tooling must also have a clear, documented reason.
- Do not change default CLI or output behavior unless the requested milestone
  explicitly requires it. New expensive or fidelity-changing behavior should be
  opt-in unless the plan says otherwise.
- Preserve Windows long-path handling and forward-slash Markdown artifact links.
- A quality-report failure must remain a visible warning and must not turn an
  otherwise successful conversion into a failed conversion.
- Do not weaken, delete, or rewrite a meaningful test merely to make an
  implementation pass.

## Quality and regression rules

- Keep extraction quality and serialization integrity separate:

  ```text
  PDF text layer -> DoclingDocument -> Markdown and artifacts
   extraction quality                serialization integrity
  ```

- Treat the PDF text layer as comparison evidence, not guaranteed ground truth.
- Never present OCR-only pages as having verified accuracy without independent
  ground truth.
- Match and explain token occurrences one-to-one. Do not allow one Markdown,
  figure, furniture, or footnote occurrence to explain several source
  occurrences.
- Preserve raw text and page/provenance evidence when normalization is used.
- Prefer fact-based fixture assertions over exact whole-Markdown snapshots.
- Keep live Docling integration tests separate from fast unit tests, deterministic
  after setup, and free of surprise network downloads.
- Do not modify the checked-in NIST source PDF.

## Verification

- Add focused tests for every behavior change and first reproduce regressions
  when fixing bugs.
- Run the focused test module while iterating.
- After Python or behavior changes, run the full suite from the repository root:

  ```powershell
  .venv\Scripts\python.exe -m unittest discover -s tests -t .
  ```

- Before handing off any milestone, run `git diff --check`, inspect the complete
  diff, and confirm that no unrelated file changed.
- Update `README.md`, `README_tr.md`, and relevant files under `docs/` whenever
  public behavior, output, limitations, or commands change.

## Network, external actions, and Git

- Ask before downloading models, packages, benchmark corpora, or using a network
  service. Continue all useful offline work before treating network access as a
  blocker.
- Ask before destructive replacement, removal of material outputs, or any action
  that could affect files outside the repository or a task-specific temporary
  directory.
- The project is published at `https://github.com/barkinakel/pdf-receipt` under the
  MIT license. The `origin` remote is already configured.
- Do not push, publish, open a pull request, or otherwise send repository content
  externally unless the user's current prompt explicitly authorizes that action.
  Pushing is user-initiated; preparing commits locally is not.
- Treat every file in the repository as publicly visible. Never commit
  credentials, tokens, personal data, or licensed third-party material.
- Create local commits only when the user's current prompt explicitly authorizes
  them. Keep one cohesive commit per completed milestone; do not amend or rewrite
  existing commits unless explicitly requested.
- Never add `Co-Authored-By` trailers to commit messages, and never name an AI
  assistant as an author or co-author. The user is the sole contributor. This
  overrides any default attribution your harness supplies.
- The remote can move without this checkout knowing, because the user also edits
  files directly on GitHub. Run `git fetch` and compare before assuming a push
  will succeed, and never resolve a divergence with `git push --force` unless the
  user explicitly asks for it.

## When to stop for user input

Stop only when continued implementation requires one of the following:

- a network/model download or a new dependency;
- a destructive or externally visible action;
- a product decision not settled by the requested milestone;
- contradictory acceptance criteria;
- visual/source evidence that only the user can judge.

Otherwise, continue until the requested milestone's acceptance criteria and
verification steps are complete.

## Handoff

Summarize the outcome, files changed, important design decisions, focused and
full test results, known limitations, and whether the next milestone is ready.
Report blockers precisely and do not claim unfinished work is complete.
