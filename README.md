# repo-check

A small CLI that scans subfolders of a target directory (depth configurable), detects Git repositories, and reports branch, clean/dirty state, and remote sync status. Results are rendered in color using Git-style green/red when output is a TTY.

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

### Common flags

- `--path` (default: config value or current working directory on first run)
- `--exclude-hidden` / `--no-exclude-hidden` (toggle hidden subfolders)
- `--max-workers` (parallelism for Git checks, default: config value)
- `--depth` (subfolder depth to scan, default: config value)

## Configuration

On startup, the CLI ensures a config file exists at `~/.config/repo-check/config`. The file uses simple `key=value` pairs for flag defaults, for example:

```
path=/Users/you/workspaces
exclude_hidden=false
max_workers=8
depth=2
```

CLI flags always override config values for that run.

## Output legend

- Green `clean` = no uncommitted changes
- Red `dirty` = uncommitted changes
- Yellow `not-init` = no Git repository detected (shown in branch column)
- Dim `pending` = check in progress (shown in branch column)
- Cyan `origin` = remote origin configured
- Red `no-remote` = no remote origin configured
- Green `in-sync` = local matches upstream
- Yellow `ahead N` = local has commits not pushed
- Red `behind N` = upstream has commits not pulled

## Example output

```
apps/api          main       clean   origin    in-sync
apps/web          main       dirty   origin    ahead 2
docs              not-init
infra/terraform   detached   clean   no-remote no-upstream
tools             pending
```
