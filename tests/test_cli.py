from __future__ import annotations

from pathlib import Path

import repo_check.cli as cli


def test_coerce_config_multiple_paths() -> None:
    defaults = {
        "paths": ["/default"],
        "exclude_hidden": "false",
        "max_workers": "4",
    }
    values = [
        ("path", "/one"),
        ("path", "/two"),
        ("exclude_hidden", "true"),
        ("max_workers", "8"),
        ("depth", "99"),
    ]

    config = cli._coerce_config(values, defaults)

    assert config["paths"] == ["/one", "/two"]
    assert config["exclude_hidden"] == "true"
    assert config["max_workers"] == "8"


def test_normalize_paths_dedup_and_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    normalized = cli._normalize_paths(["a", str(tmp_path / "b"), "a"])

    assert normalized == [str(tmp_path / "a"), str(tmp_path / "b")]


def test_build_scan_list_nested_order(tmp_path: Path) -> None:
    base = tmp_path / "a"
    nested = base / "b"
    base.mkdir()
    nested.mkdir()
    (base / "c").mkdir()
    (nested / "e").mkdir()

    names_and_paths = cli._build_scan_list(
        [str(base), str(nested)],
        include_hidden=True,
        ignore_entries=[],
    )

    names = [name for name, _ in names_and_paths]
    assert names == ["b", "└─ e", "c"]


def test_check_repo_unborn_head(monkeypatch) -> None:
    def fake_run_git(path: str, args: list[str]) -> tuple[int, str, str]:
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return 0, "true", ""
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return 128, "", "fatal: ambiguous argument 'HEAD'"
        if args == ["status", "--porcelain"]:
            return 0, "", ""
        if args == ["remote", "get-url", "origin"]:
            return 1, "", ""
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr(cli, "_run_git", fake_run_git)
    result = cli._check_repo("/tmp/repo", "repo")

    assert result.branch == cli.LABEL_NO_COMMITS
    assert result.error is None
    assert result.upstream_ref is None
    assert result.origin_url is None
    assert result.is_clean is True
