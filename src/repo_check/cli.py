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
    error: Optional[str]


ANSI_RESET = "\x1b[0m"
ANSI_RED = "\x1b[31m"
ANSI_GREEN = "\x1b[32m"
ANSI_YELLOW = "\x1b[33m"
ANSI_BLUE = "\x1b[34m"
ANSI_DIM = "\x1b[2m"


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


def _check_repo(path: str, name: str) -> RepoResult:
    code, _, _ = _run_git(path, ["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        return RepoResult(name=name, path=path, is_repo=False, branch=None, is_clean=None, error=None)

    code, branch, err = _run_git(path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if code != 0:
        return RepoResult(name=name, path=path, is_repo=True, branch=None, is_clean=None, error=err or None)

    code, status, err = _run_git(path, ["status", "--porcelain"])
    if code != 0:
        return RepoResult(name=name, path=path, is_repo=True, branch=branch, is_clean=None, error=err or None)

    is_clean = status == ""
    return RepoResult(name=name, path=path, is_repo=True, branch=branch, is_clean=is_clean, error=None)


def _list_subfolders(base_path: str, include_hidden: bool) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    with os.scandir(base_path) as it:
        for entry in it:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if not include_hidden and entry.name.startswith("."):
                continue
            entries.append((entry.name, entry.path))
    entries.sort(key=lambda item: item[0].lower())
    return entries


def _render_lines(
    names: List[str],
    results: List[Optional[RepoResult]],
    use_color: bool,
) -> List[str]:
    lines: List[str] = []
    for idx, name in enumerate(names):
        result = results[idx]
        if result is None:
            status = _color("pending", ANSI_DIM, use_color)
            lines.append(f"{name}  {status}")
            continue

        if not result.is_repo:
            status = _color("not a git repo", ANSI_YELLOW, use_color)
            lines.append(f"{name}  {status}")
            continue

        branch = result.branch or "unknown"
        if branch == "HEAD":
            branch_label = _color("detached", ANSI_BLUE, use_color)
        else:
            branch_label = _color(branch, ANSI_BLUE, use_color)

        if result.is_clean is True:
            clean_label = _color("clean", ANSI_GREEN, use_color)
        elif result.is_clean is False:
            clean_label = _color("dirty", ANSI_RED, use_color)
        else:
            clean_label = _color("unknown", ANSI_YELLOW, use_color)

        if result.error:
            err_label = _color("error", ANSI_RED, use_color)
            lines.append(f"{name}  {branch_label}  {clean_label}  {err_label}")
        else:
            lines.append(f"{name}  {branch_label}  {clean_label}")

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
            _print_block(_render_lines(names, results, use_color))

    if allow_dynamic:
        _print_block(_render_lines(names, results, use_color))

    tasks = [run_one(idx, name, path) for idx, (name, path) in enumerate(names_and_paths)]
    await asyncio.gather(*tasks)

    if not allow_dynamic:
        _print_block(_render_lines(names, results, use_color))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check immediate subfolders for Git status (branch + clean/dirty)."
        )
    )
    parser.add_argument(
        "--path",
        default=os.getcwd(),
        help="Target directory to scan (default: current working directory).",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden subfolders starting with a dot.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors and dynamic rendering.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Maximum parallel Git checks (default: CPU count).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    base_path = os.path.abspath(os.path.expanduser(args.path))
    if not os.path.isdir(base_path):
        parser.error(f"Not a directory: {base_path}")

    names_and_paths = _list_subfolders(base_path, args.include_hidden)
    if not names_and_paths:
        print("No subfolders found.")
        return

    use_color = sys.stdout.isatty() and not args.no_color
    allow_dynamic = use_color and sys.stdout.isatty() and not args.no_color

    try:
        asyncio.run(_run_checks(names_and_paths, use_color, allow_dynamic, args.max_workers))
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
