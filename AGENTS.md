# Repository Guidelines

## Project Structure & Module Organization
- `src/repo_check/` contains the CLI implementation and package code.
- `README.md` documents usage, flags, and output semantics.
- `docs/` is reserved for additional documentation (currently minimal).
- There is no `tests/` directory yet; add one if automated tests are introduced.

## Build, Test, and Development Commands
- `python -m repo_check.cli --path <dir>` runs the CLI directly from source.
- `repo-check --path <dir>` runs the installed console script (from `pyproject.toml`).
- `python -m pip install -e .` installs the project in editable mode for local development.
- `python -m pip install .` installs a regular build for local use.
- `uv tool install .` installs the CLI as a user-level tool (recommended).

## Coding Style & Naming Conventions
- Python 3.9+; use 4-space indentation and PEP 8 naming (`snake_case` functions, `CapWords` classes).
- Keep functions small, pure where feasible, and avoid side effects unless necessary.
- Add short, precise docstrings for public functions and modules when behavior is non-obvious.
- No formatter or linter is configured; keep code readable and consistent with existing style.

## Testing Guidelines
- No test framework is configured yet.
- If tests are added, use a `tests/` directory and name files `test_*.py`.
- Ensure any new tests are runnable via a single command (e.g., `python -m pytest`).

## Commit & Pull Request Guidelines
- Use Conventional Commits, as in recent history: `feat:`, `fix:`, `docs:`.
- Keep commit messages scoped and specific (e.g., `feat: add remote sync checks`).
- PRs should include a brief summary, testing notes (or “not run”), and any behavioral changes.

## Configuration Notes
- Git must be available on PATH; the CLI exits early with a clear error when Git is missing.
- Output auto-enables color and dynamic rendering only when `stdout` is a TTY.
- The CLI ensures `~/.config/my_repos_check/config` exists and uses it for default flag values.
