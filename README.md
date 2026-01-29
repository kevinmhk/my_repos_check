# repo-check

A small CLI that scans the immediate subfolders of a target directory, detects Git repositories, and reports branch and clean/dirty status. Results are rendered in color using Git-style green/red.

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
- `--include-hidden` (include subfolders starting with `.`)
- `--no-color` (disable ANSI colors and dynamic rendering)
- `--max-workers` (parallelism for Git checks, default: CPU count)

## Output legend

- Green `clean` = no uncommitted changes
- Red `dirty` = uncommitted changes
- Yellow `not a git repo` = no Git repository detected
