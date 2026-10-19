# Maintainer handoff

RelayDesk 1.0.0 implements the bounded design in `docs/superpowers/specs/2026-10-18-relaydesk-design.md`. The owner approved development and public source publication. All personal imports, actual task cards, raw validation, screenshots and backups live outside this checkout and must never be committed.

Entry: `python -m relaydesk serve`. Tests: `python -X utf8 -W error::ResourceWarning -m unittest discover -s tests -v`. No runtime dependencies. `demo` uses explicitly fictional data; real imports require the user's local history and current schema compatibility.

Read README, `docs/SECURITY.md` and `docs/VALIDATION.md` before modifying import, path or confirmation behavior. Preserve imported provenance and manual notes; never classify assistant claims as acceptance. Do not broaden roots, remove a test assertion, replay historical permissions or upload private indexes to solve a failure.

The public repository is source only. Publication metadata, exact commit/tree checks, public file hashes and raw test evidence are maintained outside the repository so they cannot accidentally include themselves or personal data. GitHub Actions provides hosted test results. No PyPI package, installer, hosted service or official Release is required.
