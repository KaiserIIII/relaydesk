# RelayDesk

**A local desk for picking up unfinished work and finding the files it produced.**

RelayDesk connects conversation history, editable task notes and concrete deliverable files. Search an old request, check which version is on disk, and export a handoff card for the next conversation. The interface is in Chinese, with course preparation as the first use case.

[中文使用说明](docs/USAGE_ZH.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md) · [Validation](docs/VALIDATION.md)

## What you can do

- Search Chinese and Unicode text across original user messages, assistant final answers and your notes.
- Keep goals, corrections, unknowns, verification notes and the next step on one task card.
- Explicitly associate conversations without merging them by fuzzy similarity.
- Find file references in messages; classify source material, full notes, revision notes, print copies and evidence.
- Check permitted files and SHA256 hashes. Confirmation belongs to a specific byte version; changed or missing files invalidate that snapshot.
- Preview and edit a Markdown handoff; export JSON with original source identifiers.
- Import again without losing manual notes; back up and restore the private SQLite index.

An assistant saying “done,” a file existing, a recorded test and your own acceptance are separate evidence. A file hash does not establish content correctness. RelayDesk does not execute historical requests or run other agents.

## Start in two minutes

Requires **Python 3.12 or later on Windows or Linux**. No pip packages, Node installation, cloud API or subscription is needed.

```console
git clone https://github.com/KaiserIIII/relaydesk.git
cd relaydesk
python -m relaydesk demo
python -m relaydesk serve
```

On Linux, use `python3` if `python` is unavailable. On Windows, `start.cmd` opens the desk; `demo.cmd` imports clearly fictional examples first. The server opens a local browser tab. Keep the terminal open; press Ctrl+C to stop it.

The demo creates three fictional tasks and a sample Markdown file in the **data directory**, not in the source checkout. It is not real course material or an acceptance record. Repeating `demo` does not reset edited task notes.

## Use your history

```console
python -m relaydesk import-codex
python -m relaydesk serve
```

Or click **只读同步 Codex** in the UI and confirm the local import. This optional adapter reads only two known local Codex database projections, using read-only SQLite connections. It excludes subagent/delegated threads, reasoning, tool bodies and authentication files. This is a version-sensitive local adapter, **not an official stable Codex API**. An unknown schema stops the import and preserves the old index. Deleted, unsynced, other-device and attachment-only content may be unavailable.

For portable data, use UTF-8 JSONL:

```console
python -m relaydesk import-jsonl examples/messages.jsonl
python -m relaydesk search 中文
```

Each line contains `thread_id`, `item_id`, `role` (`user` or `assistant_final`) and `text`; optional fields are `title`, ISO time in `time`, and integer `ordinal`. The example file is fictional. An invalid record rolls back its entire import batch. The same item cannot silently acquire different source text.

## Authorize document checks

File references remain unchecked until you explicitly allow a directory:

```console
python -m relaydesk allow-root "D:\My Courses"
```

Then choose **成果文件 → 从对话提取文件引用 → 重新检查文件与版本**. This checks specific references; it does not scan the directory recursively. Document downloads require an allowed root and an allowed file type. Network/device paths, credential directories, excluded targets and oversized files are refused. Windows uses the actual opened file handle path; Linux requires `/proc/self/fd` for file checks.

## Data, exports and backup

Default data location: `%LOCALAPPDATA%\RelayDesk` on Windows; `~/.local/share/RelayDesk` on Linux. Use the same `--data-dir` **before** every command to choose another location outside the checkout:

```console
python -m relaydesk --data-dir "D:\RelayDeskData" import-codex
python -m relaydesk --data-dir "D:\RelayDeskData" serve
python -m relaydesk --data-dir "D:\RelayDeskData" backup "D:\Backups\relaydesk.sqlite"
```

Backup refuses to overwrite an existing file. To restore, stop RelayDesk and copy a chosen backup to `index.sqlite` inside an empty data directory, then run `doctor` and `serve` with that directory. Keep the original backup.

```console
python -m relaydesk doctor
python -m relaydesk handoff TASK_ID --output handoff.md
python -m relaydesk handoff TASK_ID --format json --output handoff.json
```

**Your index, backups, handoffs, screenshots and imported messages are private.** Credential masking is best effort, not complete anonymization. These files are unencrypted and must not be uploaded with the source. The application has no telemetry or external API calls; ordinary browser extensions, sync clients and account access are outside its protection.

## Limits

- Task grouping, correction notes and completion labels are editable human decisions. There is no automatic semantic judge, autonomous continuation or guarantee of complete course coverage.
- Search is normalized literal substring search with up to eight AND terms. It is not semantic retrieval; results are capped at 200 in the UI.
- Message bodies are preserved after best-effort redaction. Historical attachments and tool evidence are not reconstructed.
- File checks hash at most 25 MiB per file. Imports are bounded by record, text and request limits; there is no hard memory quota or sandbox against a hostile process running as the same OS user.
- The web server binds only to `127.0.0.1`. Its session URL contains a temporary token; do not share it, forward the port or expose it to the internet.
- Source retrieval checks are not a human usability study or proof that historical deliverables are correct.

## Development

```console
python -X utf8 -m unittest discover -s tests -v
```

CI runs the same dependency-free tests and CLI smoke flow on Windows/Linux with Python 3.12/3.13. It contains no personal history. Browser acceptance and local historical retrieval are documented separately in [Validation](docs/VALIDATION.md).

MIT licensed. This is a personal workflow tool, with no claim of a new research algorithm.
