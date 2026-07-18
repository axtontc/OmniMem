# Project Context Ledger — OmniMem

## [1.0.0] — 2026-07-18
- **Relicensed to Apache 2.0**: Formally relicensed the project from PolyForm Noncommercial / MIT to Apache 2.0 with copyright assigned to Axton Carroll (Rule 8).
- **Ruff Style Enforcement**: Fixed style issues (E722 bare excepts, E701 colons, I001 sorting imports, F841 unused variables) and added Ruff E501 ignore setting for long database query statements.
- **Type safety upgrades**: Annotated variables (e.g. `sanitized: Dict[str, Any]` in memory router, `_queue` and `_seen_txids` in WAL) and imported missing `Field`, `Optional`, `Type`, and `TypeVar` to pass strict mypy validation.
- **None validation safety**: Checked database and model instance non-null guarantees in FastAPI `/search` and `/search_graph` endpoints to prevent runtime exceptions.
- **Unified CI Pipeline**: Integrated setup-uv environment sync actions, checking ruff format/lint bounds, and running pytest suites under Python 3.11 and 3.12 versions.
- **Custom Social Banner**: Generated the `omnimem_social_preview.png` graphic.
- **README Overhaul**: Formatted premium landing page document featuring Shields.io badges, system architecture flow diagram, CLI reference guide, subsystems grid, API signatures reference, and related projects cross-linking.
- **GitHub API Automation**: Enabled Discussions, set repository homepage URL, and created the v1.0.0 stable release.
