"""v0.1.5: tool descriptions carry usage guidance and parameter semantics (no runtime changes).

Every check runs over both registrations: the shared 26-tool server (document
tools enabled) and a 24-tool server built the same way with the default
``allow_documents=False``.

The contract snapshot is release-scoped. ``tests/fixtures/tool_contract_v014.json``
and ``tests/fixtures/tool_results_v014.json`` were generated from the v0.1.4
code and pin that names, annotations, description-stripped input schemas, and
live tool results did not move in this wording-only release. A later release
that changes runtime behaviour replaces them on purpose; they are not a
permanent freeze of the tool surface.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from mcp import Client

from mercury_multiorg_mcp import server as server_mod
from mercury_multiorg_mcp.registry import Registry
from mercury_multiorg_mcp.server import build_server

from .conftest import FAKE_API_BASE, KNOWN_ACCOUNT_ID, KNOWN_TREASURY_ID, FakeMercury, load_fixture
from .test_external_review_v012 import _CALLS
from .test_tools import DEFAULT_TOOLS, DOCUMENT_TOOLS, EXPECTED_TOOLS, _error_text, _payload

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

ALL26 = frozenset(EXPECTED_TOOLS)
assert len(ALL26) == 26 and len(DEFAULT_TOOLS) == 24

# Case-sensitive whole words: no AI model or client vendor name may appear in
# any tool description, Field description, or the server instructions.
_VENDOR_RE = re.compile(
    r"(?<![A-Za-z0-9_])(Claude|Anthropic|OpenAI|ChatGPT|GPT|Codex|Cursor|Windsurf|Gemini|Copilot)(?![A-Za-z0-9_])"
)

# Writing rule 6: these four tools keep the exact phrase and keep "newest
# first" out of their first line.
_DESC_ORDER_TOOLS = ("list_transactions", "list_statements", "list_treasury_transactions", "list_events")
_DESC_ORDER_PHRASE = "Mercury API `desc` order"

_LENGTH_LIMIT = 900
_LENGTH_LIMITS = {"reportable_totals": 3300}
_FIRST_LINE_LIMIT = 120


def flat(text: str) -> str:
    return " ".join(inspect.cleandoc(text).split())


def _strip_descriptions(obj):
    if isinstance(obj, dict):
        return {k: _strip_descriptions(v) for k, v in obj.items() if k != "description"}
    if isinstance(obj, list):
        return [_strip_descriptions(v) for v in obj]
    return obj


@pytest.fixture
def default_server(registry: Registry, make_client, env_tokens: None):
    """The 24-tool registration: allow_documents defaults to False."""
    return build_server(registry, api_base=FAKE_API_BASE, client_factory=make_client)


@pytest.fixture
async def default_client(default_server):
    async with Client(default_server) as client:
        yield client


async def _tools(client: Client) -> dict:
    return {t.name: t for t in (await client.list_tools()).tools}


def _field_descriptions(tool) -> dict[str, str]:
    out = {}
    for name, prop in (tool.input_schema.get("properties") or {}).items():
        description = prop.get("description")
        if isinstance(description, str):
            out[name] = description
    return out


# ---------------------------------------------------------------------------
# a. every description routes to a sibling
# ---------------------------------------------------------------------------


def _usage_match(name: str, description: str, registered: frozenset[str]):
    siblings = "|".join(sorted(registered - {name}, key=len, reverse=True))
    pattern = r"(?:^|[.;:]\s)Use this\b(?:[^`.]|`[^`]*`|e\.g\.|\.(?!\s))*?`(%s)`" % siblings
    return re.search(pattern, flat(description))


async def test_a_every_description_has_a_usage_sentence_naming_a_sibling(mcp_client: Client, default_client: Client):
    for client, expected in ((mcp_client, ALL26), (default_client, frozenset(DEFAULT_TOOLS))):
        tools = await _tools(client)
        assert set(tools) == expected
        registered = frozenset(tools)
        for name, tool in sorted(tools.items()):
            match = _usage_match(name, tool.description, registered)
            assert match is not None, (len(registered), name, flat(tool.description))
            assert match.group(1) in registered, (name, match.group(1))


# ---------------------------------------------------------------------------
# b. every tool name mentioned is registered
# ---------------------------------------------------------------------------


async def test_b_no_description_names_an_unregistered_tool(mcp_client: Client, default_client: Client):
    name_re = re.compile(r"(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])" % "|".join(sorted(ALL26, key=len, reverse=True)))
    for client in (mcp_client, default_client):
        tools = await _tools(client)
        registered = frozenset(tools)
        for name, tool in sorted(tools.items()):
            texts = {"description": tool.description, **_field_descriptions(tool)}
            for where, raw in texts.items():
                text = flat(raw)
                for m in name_re.finditer(text):
                    mentioned = m.group(1)
                    if mentioned in registered:
                        continue
                    assert mentioned in DOCUMENT_TOOLS, (name, where, mentioned)
                    # A default tool may name a document tool only as "(when enabled)".
                    assert re.match(r"`?\s*\(when enabled\)", text[m.end():]), (name, where, mentioned, text[m.end():][:40])


# ---------------------------------------------------------------------------
# c. client neutrality
# ---------------------------------------------------------------------------


async def test_c_no_ai_model_or_client_vendor_names(mcp_client: Client, default_client: Client):
    assert _VENDOR_RE.search(server_mod.INSTRUCTIONS) is None
    for client in (mcp_client, default_client):
        for name, tool in sorted((await _tools(client)).items()):
            for where, raw in {"description": tool.description, **_field_descriptions(tool)}.items():
                found = _VENDOR_RE.search(raw)
                assert found is None, (name, where, found.group(0))
    # the pattern is whole-word and case-sensitive: lowercase "cursor"
    # (pagination) is allowed and really occurs in the shipped text
    pagination = flat((await _tools(mcp_client))["list_transactions"].description)
    assert "cursor pagination" in pagination and _VENDOR_RE.search(pagination) is None


# ---------------------------------------------------------------------------
# d. required phrases
# ---------------------------------------------------------------------------


async def test_d_required_phrases_survive(mcp_client: Client, default_client: Client):
    source = " ".join(inspect.getsource(server_mod).split())
    assert "classification table in docs/tools.md" in source
    assert "for nonemployee services and certain MISC payments" in source
    for client in (mcp_client, default_client):
        tools = await _tools(client)
        for name in _DESC_ORDER_TOOLS:
            description = inspect.cleandoc(tools[name].description)
            assert _DESC_ORDER_PHRASE in description, name
            assert "newest first" not in description.split("\n")[0], name


# ---------------------------------------------------------------------------
# e. length budget
# ---------------------------------------------------------------------------


async def test_e_length_budget(mcp_client: Client, default_client: Client):
    for client in (mcp_client, default_client):
        for name, tool in sorted((await _tools(client)).items()):
            description = inspect.cleandoc(tool.description)
            first_line = description.split("\n")[0]
            assert len(first_line) <= _FIRST_LINE_LIMIT, (name, len(first_line))
            limit = _LENGTH_LIMITS.get(name, _LENGTH_LIMIT)
            assert len(description) <= limit, (name, len(description), limit)


# ---------------------------------------------------------------------------
# f. every id argument names its source tool
# ---------------------------------------------------------------------------


async def test_f_every_id_argument_names_a_source_tool(mcp_client: Client, default_client: Client):
    for client in (mcp_client, default_client):
        tools = await _tools(client)
        registered = frozenset(tools)
        checked = 0
        for name, tool in sorted(tools.items()):
            for arg, description in _field_descriptions(tool).items():
                if not arg.endswith("_id"):
                    continue
                checked += 1
                text = flat(description)
                sources = re.findall(r"from `([a-z_]+)`", text)
                assert sources, (name, arg, text)
                ok = False
                for source in sources:
                    if source in registered:
                        ok = True
                    elif source in DOCUMENT_TOOLS:
                        marker = f"from `{source}`"
                        ok = ok or bool(re.match(r"`?\s*\(when enabled\)", text[text.index(marker) + len(marker):]))
                assert ok, (name, arg, sources, sorted(registered))
        assert checked >= 8, checked


# ---------------------------------------------------------------------------
# g. no behaviour change against the committed v0.1.4 snapshot
# ---------------------------------------------------------------------------


def _hints_only(annotations: dict | None) -> dict | None:
    """Annotations without ``title``. v0.1.7 added a title to every tool
    (pinned in tests/test_titles_v017.py); every hint still equals the v0.1.4 snapshot."""
    if annotations is None:
        return None
    return {k: v for k, v in annotations.items() if k != "title"}


async def test_g_tool_contract_matches_the_v014_snapshot(mcp_client: Client, default_client: Client):
    expected = json.loads((FIXTURES / "tool_contract_v014.json").read_text(encoding="utf-8"))
    for client, label in ((default_client, "default_24"), (mcp_client, "documents_26")):
        tools = sorted((await _tools(client)).values(), key=lambda t: t.name)
        actual = [
            {
                "name": t.name,
                "annotations": _hints_only(t.annotations.model_dump(mode="json", by_alias=True) if t.annotations else None),
                "input_schema": _strip_descriptions(t.input_schema),
            }
            for t in tools
        ]
        snapshot = [{**t, "annotations": _hints_only(t["annotations"])} for t in expected[label]]
        assert actual == snapshot, label


async def test_g_tool_results_match_the_v014_snapshot(mcp_client: Client, fake_api: FakeMercury):
    expected = json.loads((FIXTURES / "tool_results_v014.json").read_text(encoding="utf-8"))
    assert set(expected) == set(_CALLS)
    for tool, args in _CALLS.items():
        if tool == "reportable_totals":
            fake_api.transactions = load_fixture("transactions_1099_2026.json")["transactions"]
        else:
            fake_api.transactions = None
        res = await mcp_client.call_tool(tool, {"entity": "acme_main", **args})
        assert not res.is_error, (tool, _error_text(res))
        assert _payload(res) == expected[tool], tool


def test_g_snapshot_ids_are_the_ones_the_calls_use():
    """Guard against a vacuous snapshot: the fixtures really carry the ids under test."""
    contract = json.loads((FIXTURES / "tool_contract_v014.json").read_text(encoding="utf-8"))
    assert [t["name"] for t in contract["default_24"]] == sorted(DEFAULT_TOOLS)
    assert [t["name"] for t in contract["documents_26"]] == sorted(EXPECTED_TOOLS)
    results = json.loads((FIXTURES / "tool_results_v014.json").read_text(encoding="utf-8"))
    assert results["list_statements"]["account_id"] == KNOWN_ACCOUNT_ID
    assert results["list_treasury_transactions"]["treasury_id"] == KNOWN_TREASURY_ID
    assert results["reportable_totals"]["totals"]["reportable_payment_count"] > 0


# ---------------------------------------------------------------------------
# h. docs/tools.md routing table
# ---------------------------------------------------------------------------


def test_h_docs_choosing_a_tool_lists_every_tool_once():
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    heading = "## Choosing a tool\n"
    assert text.count(heading) == 1
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `([a-z_]+)` \|", section, re.M)
    assert sorted(rows) == sorted(ALL26), sorted(set(rows) ^ ALL26)
    assert len(rows) == len(set(rows)) == 26


def test_h_the_table_routes_only_to_real_tools():
    """Every snake_case backticked name in the "Use instead" column is a registered tool."""
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    section = text.split("## Choosing a tool\n", 1)[1].split("\n## ", 1)[0]
    referenced = set()
    for row in re.findall(r"^\| `[a-z_]+` \| [^|]* \| ([^|]*) \|$", section, re.M):
        referenced |= set(re.findall(r"`([a-z][a-z_]*_[a-z_]+)`", row))
    assert referenced, section[:200]
    assert referenced <= ALL26, sorted(referenced - ALL26)


# ---------------------------------------------------------------------------
# fix-up: qualified claims (no runtime changes)
# ---------------------------------------------------------------------------

# A bare request-count claim ("one request", "one unpaginated `GET /credit`
# request") is not literally true: the client retries eligible failures. A
# sentence may count requests only if it also mentions retries.
COUNT_RE = re.compile(
    r"\b(?:one|single)\s+(?:unpaginated\s+)?(?:`[^`]*`\s*)?(?:request|GET)\b|\b(?:one|single)\s+(?:unpaginated\s+)?`GET\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=\.)\s+", flat(text))


def _docs_choosing_rows() -> list[str]:
    text = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    section = text.split("## Choosing a tool\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `[a-z_]+` \|.*\|$", section, re.M)
    assert len(rows) == 26, len(rows)
    return rows


async def test_i_no_unconditional_categorydata_presence_claim(mcp_client: Client, default_client: Client):
    qualified = re.compile(r"when present|absent|null")
    texts = list(_docs_choosing_rows())
    for client in (mcp_client, default_client):
        for name, tool in sorted((await _tools(client)).items()):
            assert "already carries" not in flat(tool.description), name
            texts.append(tool.description)
    checked = 0
    for text in texts:
        for sentence in _sentences(text):
            if "categoryData" in sentence:
                checked += 1
                assert qualified.search(sentence), sentence
    assert checked >= 2, checked  # the list_categories description and its docs row


async def test_ii_no_bare_request_count_claim(mcp_client: Client, default_client: Client):
    texts = [(ROOT / "docs" / "tools.md").read_text(encoding="utf-8")]
    for client in (mcp_client, default_client):
        for name, tool in sorted((await _tools(client)).items()):
            texts.append(tool.description)
            texts.extend(_field_descriptions(tool).values())
    for text in texts:
        for sentence in _sentences(text):
            if COUNT_RE.search(sentence):
                assert "retr" in sentence, sentence
    # the pattern really catches the wording this fix-up removed
    assert COUNT_RE.search("Takes only `entity`; one `GET /organization` request.")
    assert COUNT_RE.search("one unpaginated `GET /credit` request returns every credit account.")
    assert COUNT_RE.search("One unpaginated request; every attachment on the invoice is returned.")
    assert COUNT_RE.search("Unpaginated `GET /credit`; every credit account is returned.") is None
