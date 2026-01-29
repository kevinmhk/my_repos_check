# repo-check

A small CLI that scans subfolders of a target directory (depth configurable), detects Git repositories, and reports branch, clean/dirty state, and remote sync status. Results are rendered in color using Git-style green/red when output is a TTY.

## Requirements

- Python 3.9+
- Git on PATH

## Usage

```bash
python -m repo_check.cli --path ~/workspaces
# or, after installing
repo-check --path ~/workspaces
```

### Common flags

- `--path` (default: current working directory)
- `--exclude-hidden` (exclude hidden subfolders starting with `.`)
- `--max-workers` (parallelism for Git checks, default: CPU count)
- `--depth` (subfolder depth to scan, default: 1)

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
