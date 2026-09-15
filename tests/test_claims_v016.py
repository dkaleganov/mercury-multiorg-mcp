"""v0.1.6: README.md and the project brief make no claim about how Mercury's MCP server scopes organizations (no runtime changes).

Both state only that a Mercury API token is created from inside a single
organization, which is what Mercury's token setup docs show. CLAUDE.md is not
shipped in the sdist, so its check needs a checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOKEN_SENTENCE = "A Mercury API token is created from inside a single organization"


def _hyphenated(*words: str) -> str:
    """Join at runtime so the removed claim's literal stays out of tracked and shipped files."""
    return "-".join(words)


SCOPE_CLAIMS = (_hyphenated("single", "organization"), "per connection", "hosted MCP")

needs_checkout = pytest.mark.skipif(not (ROOT / "CLAUDE.md").is_file(), reason="CLAUDE.md not present (sdist)")


def _flat(name: str) -> str:
    return " ".join((ROOT / name).read_text(encoding="utf-8").split())


def _assert_no_scope_claim(text: str) -> None:
    for phrase in SCOPE_CLAIMS:
        assert phrase not in text, phrase
    assert TOKEN_SENTENCE in text


def test_readme_makes_no_claim_about_mercury_mcp_organization_scope():
    _assert_no_scope_claim(_flat("README.md"))


@needs_checkout
def test_brief_makes_no_claim_about_mercury_mcp_organization_scope():
    _assert_no_scope_claim(_flat("CLAUDE.md"))
