# Copyright (c) 2024-2026 Alain Prasquier - Supervaize.com. All rights reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, you can obtain one at
# https://mozilla.org/MPL/2.0/.

"""Tests for the link and brace rewriting of tools/gen_model_docs.py."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "gen_model_docs.py"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_model_docs", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_tool()
GITHUB = gen.GITHUB_REPO_URL


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository root with two copied docs, one other file and one folder."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("")
    (tmp_path / "docs" / "b.md").write_text("")
    (tmp_path / "README.md").write_text("")
    (tmp_path / "SECURITY.md").write_text("")
    (tmp_path / "rfc").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _rewrite(repo: Path, text: str, source: str = "docs/a.md") -> str:
    copied = {(repo / "docs" / "a.md").resolve(), (repo / "docs" / "b.md").resolve()}
    copied.add((repo / "README.md").resolve())
    return gen.rewrite_links(text, repo / source, copied)


def test_link_to_copied_file_becomes_sibling_link(repo: Path) -> None:
    assert _rewrite(repo, "[b](b.md)") == "[b](b.md)"
    assert _rewrite(repo, "[r](../README.md)") == "[r](README.md)"


def test_sibling_link_keeps_anchor(repo: Path) -> None:
    assert _rewrite(repo, "[r](../README.md#install)") == "[r](README.md#install)"


def test_link_to_other_repository_file_becomes_github_blob_link(repo: Path) -> None:
    assert (
        _rewrite(repo, "[s](../SECURITY.md#report)")
        == f"[s]({GITHUB}/blob/main/SECURITY.md#report)"
    )


def test_link_to_repository_folder_becomes_github_tree_link(repo: Path) -> None:
    assert _rewrite(repo, "[rfc](../rfc)") == f"[rfc]({GITHUB}/tree/main/rfc)"


def test_link_to_missing_repository_path_still_becomes_github_link(repo: Path) -> None:
    assert (
        _rewrite(repo, "[x](../src/missing.py)")
        == f"[x]({GITHUB}/blob/main/src/missing.py)"
    )


@pytest.mark.parametrize(
    "link",
    [
        "[a](#section)",
        "[a](https://example.com/x)",
        "[a](mailto:me@example.com)",
        "[a](/absolute/path)",
    ],
)
def test_anchor_url_and_absolute_links_are_unchanged(repo: Path, link: str) -> None:
    assert _rewrite(repo, link) == link


def test_link_outside_repository_is_unchanged(repo: Path) -> None:
    assert _rewrite(repo, "[o](../../outside.md)") == "[o](../../outside.md)"


def test_every_link_in_a_text_is_rewritten(repo: Path) -> None:
    text = "[b](b.md) and [s](../SECURITY.md) and [u](https://e.com)"
    assert _rewrite(repo, text) == (
        f"[b](b.md) and [s]({GITHUB}/blob/main/SECURITY.md) and [u](https://e.com)"
    )


def test_escape_mdx_braces_escapes_bare_braces() -> None:
    assert gen.escape_mdx_braces("path /jobs/{slug}") == "path /jobs/\\{slug\\}"


def test_escape_mdx_braces_leaves_inline_code_alone() -> None:
    assert gen.escape_mdx_braces("use `{slug}` or {id}") == "use `{slug}` or \\{id\\}"


def test_escape_mdx_braces_without_braces_is_unchanged() -> None:
    assert gen.escape_mdx_braces("plain `code` text") == "plain `code` text"
