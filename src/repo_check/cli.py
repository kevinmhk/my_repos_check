"""CLI entrypoint for repo-check."""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class RepoResult:
    name: str
    path: str
    is_repo: bool
    branch: Optional[str]
    is_clean: Optional[bool]
    origin_url: Optional[str]
    upstream_ref: Optional[str]
    ahead_count: Optional[int]
    behind_count: Optional[int]
    error: Optional[str]


ANSI_RESET = "\x1b[0m"
ANSI_RED = "\x1b[31m"
ANSI_GREEN = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_BLUE = "\x1b[34m"
ANSI_CYAN = "\x1b[36m"
ANSI_DIM = "\x1b[2m"

LABEL_PENDING = "pending"
LABEL_NOT_INIT = "not-init"
LABEL_UNKNOWN = "unknown"
LABEL_DETACHED = "detached"
LABEL_NO_COMMITS = "no-commits"
LABEL_CLEAN = "clean"
LABEL_DIRTY = "dirty"
LABEL_ORIGIN = "origin"
LABEL_NO_REMOTE = "no-remote"
LABEL_IN_SYNC = "in-sync"
LABEL_NO_UPSTREAM = "no-upstream"
LABEL_ERROR = "error"


def _color(text: str, code: str, use_color: bool) -> str:
    if not use_color:
        return text
    return f"{code}{text}{ANSI_RESET}"


def _run_git(path: str, args: List[str]) -> Tuple[int, str, str]:
    completed = subprocess.run(
        ["git", "-C", path, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _config_file_path() -> str:
    return os.path.expanduser("~/.config/repo-check/config")


def _legacy_config_file_path() -> str:
    return os.path.expanduser("~/.config/my_repos_check/config")


def _ignore_file_path() -> str:
    return os.path.expanduser("~/.config/repo-check/ignore")


def _default_config() -> dict:
    return {
        "paths": [os.getcwd()],
        "exclude_hidden": "false",
        "max_workers": str(os.cpu_count() or 4),
    }


def _parse_bool(value: str) -> Optional[bool]:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _load_config(path: str) -> List[Tuple[str, str]]:
    values: List[Tuple[str, str]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                values.append((key.strip(), value.strip()))
    except FileNotFoundError:
        return []
    return values


def _write_config(path: str, values: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for entry in values.get("paths", []):
            handle.write(f"path={entry}\n")
        handle.write(f"exclude_hidden={values['exclude_hidden']}\n")
        handle.write(f"max_workers={values['max_workers']}\n")


def _coerce_config(values: List[Tuple[str, str]], defaults: dict) -> dict:
    config = defaults.copy()
    config["paths"] = []
    for key, value in values:
        if key == "path" and value:
            config["paths"].append(value)
        elif key == "exclude_hidden":
            parsed = _parse_bool(value)
            if parsed is not None:
                config["exclude_hidden"] = "true" if parsed else "false"
        elif key == "max_workers":
            if value.isdigit() and int(value) > 0:
                config["max_workers"] = value
    if not config["paths"]:
        config["paths"] = defaults["paths"]
    return config


def _load_ignore_entries() -> List[str]:
    """Load ignore entries from the ignore file."""
    ignore_path = _ignore_file_path()
    ignored: List[str] = []
    try:
        with open(ignore_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                ignored.append(stripped)
    except FileNotFoundError:
        return []
    return ignored


def _resolve_ignore_paths(base_path: str, entries: List[str]) -> List[str]:
    ignored: List[str] = []
    for entry in entries:
        expanded = os.path.expanduser(entry)
        if os.path.isabs(expanded):
            abs_path = os.path.abspath(os.path.normpath(expanded))
        else:
            abs_path = os.path.abspath(
                os.path.normpath(os.path.join(base_path, expanded))
            )
        ignored.append(abs_path)
    return ignored


def _is_ignored(path: str, ignored_paths: List[str]) -> bool:
    """Return True when path is the same as or under any ignored path."""
    if not ignored_paths:
        return False
    for ignored in ignored_paths:
        try:
            common = os.path.commonpath([path, ignored])
        except ValueError:
            continue
        if common == ignored:
            return True
    return False


def _ensure_config() -> dict:
    defaults = _default_config()
    config_path = _config_file_path()
    legacy_path = _legacy_config_file_path()
    if not os.path.exists(config_path):
        if os.path.exists(legacy_path):
            legacy = _load_config(legacy_path)
            _write_config(config_path, _coerce_config(legacy, defaults))
        else:
            _write_config(config_path, defaults)
    raw = _load_config(config_path)
    return _coerce_config(raw, defaults)


def _check_repo(path: str, name: str) -> RepoResult:
    code, _, _ = _run_git(path, ["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        return RepoResult(
            name=name,
            path=path,
            is_repo=False,
            branch=None,
            is_clean=None,
            origin_url=None,
            upstream_ref=None,
            ahead_count=None,
            behind_count=None,
            error=None,
        )

    code, branch, err = _run_git(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    unborn_head = False
    if code != 0:
        lowered = (err or "").lower()
        if "unknown revision" in lowered or "ambiguous argument 'head'" in lowered:
            unborn_head = True
            branch = LABEL_NO_COMMITS
        else:
            return RepoResult(
                name=name,
                path=path,
                is_repo=True,
                branch=None,
                is_clean=None,
                origin_url=None,
                upstream_ref=None,
                ahead_count=None,
                behind_count=None,
                error=err or None,
            )

    code, status, err = _run_git(path, ["status", "--porcelain"])
    if code != 0:
        return RepoResult(
            name=name,
            path=path,
            is_repo=True,
            branch=branch,
            is_clean=None,
            origin_url=None,
            upstream_ref=None,
            ahead_count=None,
            behind_count=None,
            error=err or None,
        )

    code, origin, _ = _run_git(path, ["remote", "get-url", "origin"])
    origin_url = origin if code == 0 and origin else None

    if unborn_head:
        upstream_ref = None
        behind_count = None
        ahead_count = None
    else:
        code, upstream, _ = _run_git(
            path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
        )
        if code == 0 and upstream:
            code, counts, _ = _run_git(
                path, ["rev-list", "--left-right", "--count", "HEAD...@{u}"]
            )
            if code == 0 and counts:
                parts = counts.split()
                if len(parts) == 2 and all(p.isdigit() for p in parts):
                    behind_count = int(parts[0])
                    ahead_count = int(parts[1])
                else:
                    behind_count = None
                    ahead_count = None
            else:
                behind_count = None
                ahead_count = None
            upstream_ref = upstream
        else:
            upstream_ref = None
            behind_count = None
            ahead_count = None

    is_clean = status == ""
    return RepoResult(
        name=name,
        path=path,
        is_repo=True,
        branch=branch,
        is_clean=is_clean,
        origin_url=origin_url,
        upstream_ref=upstream_ref,
        ahead_count=ahead_count,
        behind_count=behind_count,
        error=None,
    )


def _list_subfolders(
    base_path: str,
    include_hidden: bool,
    ignored_paths: List[str],
) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []

    with os.scandir(base_path) as it:
        for entry in it:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if _is_ignored(entry.path, ignored_paths):
                continue
            if not include_hidden and entry.name.startswith("."):
                continue
            rel_path = os.path.relpath(entry.path, base_path)
            entries.append((rel_path, entry.path))

    entries.sort(key=lambda item: item[0].lower())
    return entries


def _normalize_paths(paths: List[str]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    for path in paths:
        if not path:
            continue
        expanded = os.path.abspath(os.path.expanduser(path))
        if expanded in seen:
            continue
        seen.add(expanded)
        normalized.append(expanded)
    return normalized


def _has_ancestor(path: str, candidates: set[str]) -> bool:
    for other in candidates:
        if other == path:
            continue
        try:
            common = os.path.commonpath([path, other])
        except ValueError:
            continue
        if common == other:
            return True
    return False


def _build_scan_list(
    target_paths: List[str],
    include_hidden: bool,
    ignore_entries: List[str],
) -> List[Tuple[str, str]]:
    names_and_paths: List[Tuple[str, str]] = []
    target_set = set(target_paths)
    root_targets = [
        path for path in target_paths if not _has_ancestor(path, target_set)
    ]

    def add_for_base(base_path: str, prefix: str) -> None:
        ignored_paths = _resolve_ignore_paths(base_path, ignore_entries)
        entries = _list_subfolders(base_path, include_hidden, ignored_paths)
        for name, path in entries:
            display = f"{prefix}{name}"
            names_and_paths.append((display, path))
            if path in target_set:
                add_for_base(path, f"{prefix}└─ ")

    for base_path in root_targets:
        add_for_base(base_path, "")

    return names_and_paths


def _render_lines(
    names: List[str],
    results: List[Optional[RepoResult]],
    use_color: bool,
    show_remote: bool,
) -> List[str]:
    def format_cell(raw: str, colored: str, width: int) -> str:
        pad = " " * max(0, width - len(raw))
        return f"{colored}{pad}"

    max_name = max(len(name) for name in names)
    max_branch = max(len(LABEL_DETACHED), len(LABEL_UNKNOWN), len(LABEL_NO_COMMITS))
    max_clean = max(
        len(LABEL_CLEAN),
        len(LABEL_DIRTY),
        len(LABEL_UNKNOWN),
        len(LABEL_NOT_INIT),
        len(LABEL_PENDING),
    )
    max_remote = max(len(LABEL_ORIGIN), len(LABEL_NO_REMOTE))
    max_sync = max(len(LABEL_IN_SYNC), len(LABEL_NO_UPSTREAM), len(LABEL_ERROR))

    for result in results:
        if not result or not result.is_repo:
            continue
        if result.branch:
            max_branch = max(max_branch, len(result.branch))
        if (
            show_remote
            and result.upstream_ref
            and result.ahead_count is not None
            and result.behind_count is not None
        ):
            parts: List[str] = []
            if result.ahead_count > 0:
                parts.append(f"ahead {result.ahead_count}")
            if result.behind_count > 0:
                parts.append(f"behind {result.behind_count}")
            label = ", ".join(parts) if parts else LABEL_IN_SYNC
            max_sync = max(max_sync, len(label))

    lines: List[str] = []
    for idx, name in enumerate(names):
        result = results[idx]
        if result is None:
            branch_raw = LABEL_PENDING
            branch_colored = _color(branch_raw, ANSI_DIM, use_color)
            if show_remote:
                line = (
                    f"{format_cell(name, name, max_name)}  "
                    f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                    f"{format_cell('', '', max_clean)}  "
                    f"{format_cell('', '', max_remote)}  "
                    f"{format_cell('', '', max_sync)}"
                )
            else:
                line = (
                    f"{format_cell(name, name, max_name)}  "
                    f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                    f"{format_cell('', '', max_clean)}"
                )
            lines.append(line)
            continue

        if not result.is_repo:
            branch_raw = LABEL_NOT_INIT
            branch_colored = _color(branch_raw, ANSI_YELLOW, use_color)
            if show_remote:
                line = (
                    f"{format_cell(name, name, max_name)}  "
                    f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                    f"{format_cell('', '', max_clean)}  "
                    f"{format_cell('', '', max_remote)}  "
                    f"{format_cell('', '', max_sync)}"
                )
            else:
                line = (
                    f"{format_cell(name, name, max_name)}  "
                    f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                    f"{format_cell('', '', max_clean)}"
                )
            lines.append(line)
            continue

        branch = result.branch or LABEL_UNKNOWN
        if branch == "HEAD":
            branch_raw = LABEL_DETACHED
            branch_colored = _color(branch_raw, ANSI_BLUE, use_color)
        elif branch == LABEL_NO_COMMITS:
            branch_raw = LABEL_NO_COMMITS
            branch_colored = _color(branch_raw, ANSI_YELLOW, use_color)
        else:
            branch_raw = branch
            branch_colored = _color(branch_raw, ANSI_BLUE, use_color)

        if result.is_clean is True:
            clean_raw = LABEL_CLEAN
            clean_colored = _color(clean_raw, ANSI_GREEN, use_color)
        elif result.is_clean is False:
            clean_raw = LABEL_DIRTY
            clean_colored = _color(clean_raw, ANSI_RED, use_color)
        else:
            clean_raw = LABEL_UNKNOWN
            clean_colored = _color(clean_raw, ANSI_YELLOW, use_color)

        remote_raw = ""
        remote_colored = ""
        sync_raw = ""
        sync_colored = ""
        if show_remote:
            if result.origin_url:
                remote_raw = LABEL_ORIGIN
                remote_colored = _color(remote_raw, ANSI_CYAN, use_color)
            else:
                remote_raw = LABEL_NO_REMOTE
                remote_colored = _color(remote_raw, ANSI_RED, use_color)
            if (
                result.upstream_ref
                and result.ahead_count is not None
                and result.behind_count is not None
            ):
                if result.behind_count == 0 and result.ahead_count == 0:
                    sync_raw = LABEL_IN_SYNC
                    sync_colored = _color(sync_raw, ANSI_GREEN, use_color)
                else:
                    parts = []
                    if result.ahead_count > 0:
                        parts.append(f"ahead {result.ahead_count}")
                    if result.behind_count > 0:
                        parts.append(f"behind {result.behind_count}")
                    label = ", ".join(parts) if parts else "out-of-sync"
                    color = ANSI_RED if result.behind_count > 0 else ANSI_YELLOW
                    sync_raw = label
                    sync_colored = _color(sync_raw, color, use_color)
            else:
                sync_raw = LABEL_NO_UPSTREAM
                sync_colored = _color(sync_raw, ANSI_YELLOW, use_color)

        if result.error:
            sync_raw = LABEL_ERROR
            sync_colored = _color(sync_raw, ANSI_RED, use_color)

        if show_remote:
            line = (
                f"{format_cell(name, name, max_name)}  "
                f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                f"{format_cell(clean_raw, clean_colored, max_clean)}  "
                f"{format_cell(remote_raw, remote_colored, max_remote)}  "
                f"{format_cell(sync_raw, sync_colored, max_sync)}"
            )
        else:
            line = (
                f"{format_cell(name, name, max_name)}  "
                f"{format_cell(branch_raw, branch_colored, max_branch)}  "
                f"{format_cell(clean_raw, clean_colored, max_clean)}"
            )

        lines.append(line)

    return lines


def _clear_lines(line_count: int) -> None:
    if line_count <= 0:
        return
    sys.stdout.write(f"\x1b[{line_count}A")
    for _ in range(line_count):
        sys.stdout.write("\x1b[2K\r\n")
    sys.stdout.write(f"\x1b[{line_count}A")


def _print_block(lines: Iterable[str]) -> None:
    for line in lines:
        sys.stdout.write(line + "\n")
    sys.stdout.flush()


async def _run_checks(
    names_and_paths: List[Tuple[str, str]],
    use_color: bool,
    allow_dynamic: bool,
    max_workers: int,
    show_remote: bool,
) -> None:
    names = [name for name, _ in names_and_paths]
    results: List[Optional[RepoResult]] = [None] * len(names)

    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max_workers)

    async def run_one(idx: int, name: str, path: str) -> None:
        async with semaphore:
            result = await loop.run_in_executor(None, _check_repo, path, name)
        results[idx] = result
        if allow_dynamic:
            _clear_lines(len(names))
            _print_block(_render_lines(names, results, use_color, show_remote))

    if allow_dynamic:
        _print_block(_render_lines(names, results, use_color, show_remote))

    tasks = [
        run_one(idx, name, path) for idx, (name, path) in enumerate(names_and_paths)
    ]
    await asyncio.gather(*tasks)

    if not allow_dynamic:
        _print_block(_render_lines(names, results, use_color, show_remote))


def build_parser(defaults: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check immediate subfolders for Git status (branch + clean/dirty)."
        )
    )
    parser.add_argument(
        "--path",
        action="append",
        default=None,
        help="Target directory to scan (repeatable; defaults to configured paths).",
    )
    parser.add_argument(
        "--exclude-hidden",
        action=argparse.BooleanOptionalAction,
        default=defaults["exclude_hidden"] == "true",
        help="Exclude hidden subfolders starting with a dot.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=int(defaults["max_workers"]),
        help="Maximum parallel Git checks (default: configured value).",
    )
    return parser


def main() -> None:
    defaults = _ensure_config()
    parser = build_parser(defaults)
    args = parser.parse_args()

    git_code, _, _ = _run_git(os.getcwd(), ["--version"])
    if git_code != 0:
        print("Error: git is not available on PATH. Please install Git and try again.")
        sys.exit(1)

    include_hidden = not args.exclude_hidden
    raw_paths = args.path if args.path else defaults["paths"]
    target_paths = _normalize_paths(raw_paths)
    if not target_paths:
        parser.error("At least one --path must be provided.")
    for path in target_paths:
        if not os.path.isdir(path):
            parser.error(f"Not a directory: {path}")

    ignore_entries = _load_ignore_entries()
    names_and_paths = _build_scan_list(target_paths, include_hidden, ignore_entries)
    if not names_and_paths:
        print("No subfolders found.")
        return

    use_color = sys.stdout.isatty()
    allow_dynamic = use_color

    try:
        asyncio.run(
            _run_checks(
                names_and_paths,
                use_color,
                allow_dynamic,
                args.max_workers,
                show_remote=True,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
