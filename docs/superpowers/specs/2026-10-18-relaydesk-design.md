# RelayDesk design

Approved scope: a personal, local task and deliverable continuity desk. The owner approved implementation and GitHub publication on 2026-10-18; a later instruction explicitly requests a public repository. No personal history or filesystem inventory is publishable.

Python 3.12+ standard library only; SQLite data outside the source tree; Chinese browser UI on 127.0.0.1, CLI, offline operation. Import original user messages and assistant final answers, never reasoning or tool bodies. Each conversation becomes one task unless the user explicitly associates conversations. Preserve source identifiers, dates, and redacted text. Import is transactional, repeatable, and must not overwrite manual edits. Unknown source schemas fail without modifying the index. Codex's local database format is an optional, version-sensitive adapter, not an official public API.

Search supports literal Chinese/Unicode substrings and multiple AND terms. Show original sources and corrections as evidence, not inferred truth. User edits task goal, corrections, open items, next step, category, and status. Assistant claims, file existence/hash, manually linked verification notes, and user acceptance are distinct. No background agent orchestration or historical authorization replay.

Extract candidate file references, checking only explicitly permitted local roots. Refuse UNC/device paths, traversal outside roots, symlink escapes and nonregular files. Bounded hashing; no execution or recursive disk scan. User acceptance attaches to a checked hash and becomes stale if bytes change. Missing/oversized/unapproved files cannot be accepted as a checked version. User-classified source/full/revision/print artifacts support course organization without claiming complete source coverage.

Export editable Markdown and JSON handoff cards with task notes, original references, limitations and current artifact checks. Back up the private index with SQLite's backup API. Never upload this data. The GitHub repository contains source, synthetic fixtures, documentation and CI only.

HTTP API uses a random session bearer token, loopback binding, strict Host/Origin validation, no CORS, bounded bodies, and inert rendering of untrusted text. No arbitrary shell commands or server-side file opening. File downloads are limited to checked, allowed document types and sent as attachments. Static resources use a restrictive CSP and no external assets.

Acceptance: unit/integration tests exercise persistence, idempotency, Chinese search, stale acceptance, path boundaries, backup/restore, CLI, and real HTTP security. A separately frozen private pilot uses ten historical tasks to verify source retrieval, evidence anchors and non-fabricated completion. Automated retrieval timing is not a human usability result. Browser verification uses clearly synthetic fixtures; real-history results stay outside Git.
