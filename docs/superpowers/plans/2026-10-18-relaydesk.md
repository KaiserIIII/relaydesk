# RelayDesk Implementation Plan

> **For agentic workers:** Use executing-plans inline, then requesting-code-review for an independent review. No implementation delegation is needed.

**Goal:** Deliver a local Chinese task/history/artifact desk and publish sanitized source.

**Architecture:** Import adapters produce normalized message records. A transactional SQLite Store owns task edits and provenance. File checks and handoff exports consume the Store; a loopback HTTP interface and CLI share the same application operations.

**Tech Stack:** Python 3.12+ standard library, SQLite, vanilla HTML/CSS/JavaScript, unittest. No runtime or build dependency installation.

## Global constraints

- Public repository contains no real history, home paths, private indexes or raw experiment evidence.
- Data defaults outside checkout; imports never alter source databases.
- No API keys, external embedding, arbitrary command execution or autonomous task execution.
- Hash equality is not semantic correctness; assistant claims are never user acceptance.
- Only user-designated roots may be checked. No recursive inventory.

## Task 1: Private import and task store

Files: `relaydesk/privacy.py`, `relaydesk/store.py`, `relaydesk/importers.py`, `tests/test_store.py`.

Interfaces: `Store(path)`, `import_records(records) -> dict`, `search(query) -> list`, `detail(task_id) -> dict`, `edit(task_id, values) -> dict`. Records carry `thread_id,item_id,role,text,time,title`.

- [ ] Write tests: importing two messages twice leaves two records; Chinese query finds the expected thread; editing a goal survives import; malformed batch rolls back; tokens are redacted before persistence.
- [ ] Run `python -m unittest discover -s tests -v` and retain failing output.
- [ ] Implement normalization, bounded record validation, transactional upserts, parameterized literal search and explicit manual task fields.
- [ ] Run the same tests and commit the passing slice.

```python
s.import_records([{'thread_id':'course','item_id':'u1','role':'user','text':'中文公式'}])
assert s.search('中文')[0]['thread_id'] == 'course'
assert len(s.detail(s.search('中文')[0]['id'])['messages']) == 1
```

## Task 2: Artifacts and handoff

Files: `relaydesk/files.py`, `relaydesk/handoff.py`, `tests/test_artifacts.py`.

Interfaces: `check_file(path, roots) -> dict`; `Store.add_artifact(task_id,path,source_id,kind)`; `check_artifacts(task_id)`; `accept_artifact(id)`; `export_handoff(store,task_id) -> dict`.

- [ ] Test safe file hashing, missing files, root escape, symlink escape, oversized files, acceptance invalidation after mutation, and handoff source identifiers.
- [ ] Run tests before implementing; retain failures.
- [ ] Implement bounded checks and acceptance tied to a SHA256. Keep manually written notes separate from imported history.
- [ ] Run all tests and commit.

```python
p.write_text('old',encoding='utf8')
s.accept_artifact(a['id'])
p.write_text('new',encoding='utf8')
assert s.check_artifacts(task_id)[0]['acceptance'] == 'stale'
```

## Task 3: Codex adapter and CLI

Files: `relaydesk/codex.py`, `relaydesk/__main__.py`, `relaydesk/demo.py`, `tests/test_import_cli.py`.

- [ ] Build a tiny independent Codex-schema fixture; assert only human/legacy user messages and final answers import, sources stay byte-identical, and unsupported schema fails without index loss.
- [ ] Test CLI import/search/handoff/backup/roots/doctor in subprocesses and restore an index from a backup.
- [ ] Implement schema capability checks and read-only SQLite URIs, bounded JSONL input and explicit commands. Use no auth/config files.
- [ ] Run all tests; commit.

```console
python -m relaydesk --data-dir /tmp/relaydesk-demo demo
python -m relaydesk --data-dir /tmp/relaydesk-demo search 中文
python -m relaydesk --data-dir /tmp/relaydesk-demo doctor
```

## Task 4: Authenticated local web desk

Files: `relaydesk/server.py`, `relaydesk/web/index.html`, `relaydesk/web/app.js`, `relaydesk/web/style.css`, `tests/test_http.py`.

- [ ] Write real HTTP tests: wrong token/Host/Origin rejected; GET cannot mutate; oversized/invalid bodies rejected; task edits persist; download cannot escape allowed roots.
- [ ] Run failing tests before implementing server routes.
- [ ] Implement a Chinese responsive interface: search/filter, source timeline, editable task card, artifact checks, and Markdown/JSON downloads. Render source text through `textContent` only.
- [ ] Run HTTP tests and verify browser interactions against synthetic data. Commit.

## Task 5: Acceptance, documentation and publication

Files: `README.md`, `docs/USAGE_ZH.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/VALIDATION.md`, `LICENSE`, `.github/workflows/test.yml`, launch scripts.

- [ ] Run private ten-task historical pilot fixed before implementation, preserve results outside checkout, distinguish machine retrieval from human acceptance.
- [ ] Run fresh Windows environment and isolated Linux, CLI, backup/restore and browser flow; retain failures.
- [ ] Independent code review, reproduce actionable findings and fix with regression tests.
- [ ] Audit every tracked path and all Git history; produce a public manifest externally, source ZIP and Git Bundle. Verify a clean checkout.
- [ ] Create public `KaiserIIII/relaydesk`, push reviewed commits, compare remote tree/paths and verify CI. Never upload private validation data.

## Execution record

2026-10-18: design approved; new independent directory, implementation branch, no existing project modified. GitHub identity checked against an existing associated commit. Context7 lookup attempted but monthly quota exhausted; Python official documentation used instead. Runtime dependencies: none. Local tests will precede implementation in each slice.
