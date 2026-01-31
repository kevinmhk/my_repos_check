# repo-check

A small CLI that scans immediate subfolders of one or more target directories, detects Git repositories, and reports branch, clean/dirty state, and remote sync status. Results are rendered in color using Git-style green/red when output is a TTY.

## Requirements

- Python 3.9+
- Git on PATH
- uv (recommended for installation)

## Installation (Recommended)

Use uv to install the CLI as a user-level tool:

```bash
git clone https://github.com/kevinmhk/repo-check.git
cd repo-check
uv tool install .
```

This installs an isolated tool environment under `~/.local/share/uv/tools` and exposes the `repo-check`
command via your user PATH (typically `~/.local/bin`).

Alternatively, install directly from GitHub:

```bash
uv tool install git+https://github.com/kevinmhk/repo-check.git
```

To pin a specific tag or commit:

```bash
uv tool install git+https://github.com/kevinmhk/repo-check.git@v1.0.0
```

## Usage

```bash
repo-check --path ~/workspaces
```

Scan multiple roots (repeat `--path`):

```bash
repo-check --path ~/a --path ~/a/b
```

## Execution and Installation in Development Mode

Run the local source directly without installing:

```bash
python -m repo_check.cli --path ~/workspaces
```

Reinstall the tool from local source and bypass the cache:

```bash
uv tool install . --reinstall --no-cache
```

## Development Workflows

Install dev tools:

```bash
uv pip install -e ".[dev]"
```

Lint:

```bash
ruff check .
```

Format:

```bash
ruff format .
```

Type check:

```bash
ty check
```

Tests:

```bash
python -m pytest
```

### Common flags

- `--path` (repeatable; defaults to config values)
- `--exclude-hidden` / `--no-exclude-hidden` (toggle hidden subfolders)
- `--max-workers` (parallelism for Git checks, default: config value)

## Configuration

On startup, the CLI ensures a config file exists at `~/.config/repo-check/config`. The file uses simple `key=value` pairs for flag defaults, for example:

```
path=/Users/you/workspaces
path=/Users/you/workspaces/personal
exclude_hidden=false
max_workers=8
```

CLI flags always override config values for that run.
Repeat the `path=` line to configure multiple scan roots.

You can also create an ignore file at `~/.config/repo-check/ignore` to skip folders. Each line is a folder
path; absolute paths are used as-is, and relative paths are resolved against each `--path` scan root.
Blank lines and lines starting with `#` are ignored.

## Output legend

- Green `clean` = no uncommitted changes
- Red `dirty` = uncommitted changes
- Yellow `not-init` = no Git repository detected (shown in branch column)
- Yellow `no-commits` = Git repo with no commits yet (unborn HEAD)
- Dim `pending` = check in progress (shown in branch column)
- Cyan `origin` = remote origin configured
- Red `no-remote` = no remote origin configured
- Green `in-sync` = local matches upstream
- Yellow `ahead N` = local has commits not pushed
- Red `behind N` = upstream has commits not pulled
- `└─` prefix = entry nested under another target path

## Example output

```
apps              not-init
└─ web            main       dirty   origin    ahead 2
docs              not-init
infra/terraform   detached   clean   no-remote no-upstream
tools             pending
```
