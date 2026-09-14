"""v0.1.4: the package moved to its own repository (metadata, links, docs; no runtime changes).

Pins (a) that README.md, docs/, pyproject.toml, and server.json name the old
monorepo only inside README's repository-history note, as a link or as plain
text, (b) that git installs use this repository with no ``#subdirectory=``,
(c) that the history note records the move and the tag rename, and (d) that
the agent briefs use standalone framing and link here. Every file read here is
inside this repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/dkaleganov/mercury-multiorg-mcp"
OLD = "personal-ai-systems"
OLD_REPO = "https://github.com/dkaleganov/personal-ai-systems"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
README = (ROOT / "README.md").read_text(encoding="utf-8")
HISTORY_MARKER = "**Repository history.**"
URL = re.compile(r"""(?:git\+)?https?://[^\s)'"<>\]`]+""")

# server.json and CLAUDE.md are tracked in git but not shipped in the sdist.
needs_checkout = pytest.mark.skipif(not (ROOT / "CLAUDE.md").is_file(), reason="CLAUDE.md not present (sdist)")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _history_note() -> str:
    notes = [p for p in re.split(r"\n\s*\n", README) if p.lstrip().startswith(HISTORY_MARKER)]
    assert len(notes) == 1, notes
    return notes[0]


def _checked_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "pyproject.toml", *sorted((ROOT / "docs").glob("*.md"))]
    if (ROOT / "server.json").is_file():
        files.append(ROOT / "server.json")
    return files


@needs_checkout
def test_the_checked_file_set_is_complete_in_a_checkout():
    names = {p.relative_to(ROOT).as_posix() for p in _checked_files()}
    assert {"README.md", "pyproject.toml", "server.json", "docs/tools.md", "docs/keepalive.md"} <= names


def test_no_link_or_mention_of_the_monorepo_outside_the_history_note():
    for path in _checked_files():
        text = path.read_text(encoding="utf-8")
        if path.name == "README.md":
            text = text.replace(_history_note(), "")
        assert [u for u in URL.findall(text) if OLD in u] == [], path.name
        assert OLD not in text, path.name  # not even as plain text


def test_history_note_records_the_move_and_the_tag_rename():
    note = _flat(_history_note())
    assert "through v0.1.3" in note and "moved to this repository at v0.1.4" in note and "history preserved" in note
    assert "`mercury-v0.1.x`" in note and "`v0.1.x`" in note and "`vX.Y.Z` from now on" in note
    assert "SHAs differ" in note
    old_links = [u for u in URL.findall(note) if OLD in u]
    assert old_links == [OLD_REPO], old_links  # the monorepo root only: never a tag, path, or install source in it


def test_readme_outside_the_history_note_has_no_monorepo_packaging():
    rest = README.replace(_history_note(), "")
    assert "monorepo" not in rest and "mercury-v" not in rest


def test_git_installs_use_this_repository_without_subdirectory():
    for path in (ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))):
        text = path.read_text(encoding="utf-8")
        assert "#subdirectory" not in text, path.name
        for source in re.findall(r"git\+https?://[^\s'\"`]+", text):
            assert source == f"git+{REPO}@<FULL_COMMIT_SHA>", (path.name, source)
    assert f"git clone {REPO}.git" in README and "\ncd mercury-multiorg-mcp\n" in README
    assert f"git ls-remote --tags {REPO} 'v{VERSION}^{{}}'" in README
    keepalive = (ROOT / "docs" / "keepalive.md").read_text(encoding="utf-8")
    assert f"uvx --from 'git+{REPO}@<FULL_COMMIT_SHA>' \\\n  mercury-multiorg-mcp-keepalive --entities" in keepalive


def test_agents_md_links_here_and_runs_gitleaks_from_this_root():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert [u for u in URL.findall(agents) if OLD in u] == []
    assert f"[CLAUDE.md]({REPO}/blob/main/CLAUDE.md)" in agents
    assert "gitleaks git --no-banner --redact ." in agents and "from this repository's root" in _flat(agents)
    assert "monorepo" not in agents


@needs_checkout
def test_brief_uses_standalone_framing_and_records_the_move():
    brief = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    flat = _flat(brief)
    assert [u for u in URL.findall(brief) if OLD in u] == []
    assert "#subdirectory" not in brief and "sibling folders" not in brief
    assert "## Monorepo packaging rules" not in brief and "## Packaging rules" in brief
    assert "public monorepo" not in brief and "clone the monorepo" not in brief
    assert "gitleaks git --no-banner --redact ." in brief and "this repository's root so its `.gitleaks.toml` applies" in flat
    assert "Release tags are `vX.Y.Z`" in flat
    assert "moved to a dedicated repository at v0.1.4 so the server can have its own listings (Glama, awesome lists) and a focused home" in flat
