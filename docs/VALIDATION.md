# Validation and limits of the evidence

Development validation started on 2026-10-18. This document reports executed checks, not a claim that every personal task or file is correct.

| Check | Executed result |
|---|---|
| Windows, CPython 3.13.0 | 36 tests: 35 passed, 1 skipped because file symlink creation lacks OS privileges. The separate real directory-junction regressions ran and passed. |
| Isolated Linux, CPython 3.14.8 | 36 tests passed, no skips. Includes `/proc/self/fd` checks, symlink boundaries, CLI and real loopback HTTP. |
| Independent code review | Six reproduced P2 issues fixed; follow-up reran the existing suite and found no remaining P1/P2. This is bounded review, not an exhaustive security proof. |
| Real local history | Optional native adapter imported user/final text into a private index, without publishing it. Repeated-source and unsupported-schema behavior also have synthetic regression tests. |
| Historical retrieval sample | Ten development-informed queries found the intended task among the first five results and retained the original user item identifiers. Machine retrieval only; no human usability/accuracy study. |
| Browser on Windows | Actual local page load, Chinese note save/readback, restart persistence, original source display, inert HTML-looking source text, file hash check, and editable handoff preview. Markdown/JSON download buttons were exercised; their destination files were not independently recovered from the in-app browser. CLI exports and HTTP response bytes are verified separately. |
| Hosted CI | Workflow prepared for Windows/Linux × Python 3.12/3.13. Consult the repository's Actions page for actual hosted results; local execution is not substituted for those runs. |

Tests cover import atomicity, source immutability, idempotency, manual-edit survival, literal Chinese/Unicode search, root restrictions, directory-alias regressions, opened-file checks, stale acceptance, provenance, handoff literal blocks, backups, CLI and HTTP authentication/origin/body/download behavior. Failure logs were preserved privately, including the initial Windows test connection cleanup failure and the pre-fix review regressions.

The first hosted run passed both Linux jobs but failed the Windows jobs because runner temporary directories used a short-path spelling while file resolution produced the canonical long path. Root registration now canonicalizes and pins the target; filesystem fixtures explicitly use canonical temporary directories. A new regression verifies root registration through a directory alias. Existing root restrictions and test assertions were retained. Hosted reruns, rather than the initial local result, determine acceptance of this correction.

The historical sample was selected from a previously curated evidence set and frozen before its real-data run, **after core implementation**. It is a development regression sample, not a preregistered independent benchmark. It does not prove superiority to Obsidian, semantic completeness, task completion, file content correctness, or time saved by a human.

The review's junction test schedules a real directory change at one defined boundary. Other interleavings were not exhaustively tested. Same-user hostile processes, browser extensions, hard resource isolation, cloud history completeness and other operating systems remain outside the validated scope. macOS is not a supported file-check platform.

Private messages, real task identifiers, file inventories, screenshots and raw acceptance logs are intentionally absent from this source repository. Reproduce portable behavior with the synthetic fixtures and `python -X utf8 -m unittest discover -s tests -v`.
