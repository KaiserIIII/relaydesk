# Dependency provenance

Runtime and tests use the Python standard library only. No third-party Python or JavaScript package is bundled or installed. Python is distributed under the PSF license; use an official maintained interpreter. Browser assets are original project source and use system fonts.

CI actions were resolved from official repositories on 2026-10-18 and pinned to commit identifiers:

| Action | Source | License | Pinned commit |
|---|---|---|---|
| checkout v4 | https://github.com/actions/checkout | MIT | `11d5960a326750d5838078e36cf38b85af677262` |
| setup-python v5 | https://github.com/actions/setup-python | MIT | `a26af69be951a213d495a4c3e4e4022e16d87065` |

These are official workflow dependencies, not copied application code. The Python version is recorded by each CI job; no package resolver is invoked. Local API documentation lookup attempted Context7, whose quota was unavailable; official Python and Microsoft documentation was consulted instead. No private source/history was sent in documentation queries.
