# Contributing to OmniMem

We welcome bug reports, feature requests, documentation improvements, and code changes!

## Development Setup

We use `uv` as our Python package and dependency manager.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/axtontc/OmniMem.git
   cd OmniMem
   ```

2. **Sync dependencies**:
   ```bash
   uv sync
   ```

3. **Verify tests pass**:
   ```bash
   uv run python -m pytest tests/ -v
   ```

## Code Style & Formatting

We use `ruff` to enforce formatting and lint checks. Before submitting a pull request, please format your code:

```bash
uv run ruff format .
uv run ruff check . --fix
```

## Pull Request Guidelines

1. **Create a branch**: Create a descriptive branch name (e.g., `feat/add-neo4j-index` or `fix/pgvector-leak`).
2. **Write tests**: Ensure your changes are backed by unit tests inside the `tests/` directory.
3. **Keep it atomic**: Make clean, focused commits.
4. **Pass CI**: Ensure the GitHub Actions lint and test suites pass successfully.
