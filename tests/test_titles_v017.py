"""v0.1.7: every tool has a short human-readable title (no runtime changes).

The title is set both on the tool and in its annotations, the two places MCP
clients read it from. Every check runs over both registrations: the 26-tool
server with document tools and the default 24-tool server. Hints are pinned
by test g in tests/test_descriptions_v015.py against the v0.1.4 snapshot.
"""

from __future__ import annotations

from mcp import Client

from .test_descriptions_v015 import _tools, default_client, default_server  # noqa: F401  (fixtures)
from .test_tools import DEFAULT_TOOLS, EXPECTED_TOOLS

TITLES = {
    "list_entities": "List Mercury organizations",
    "list_accounts": "List accounts and balances",
    "list_transactions": "List transactions",
    "reportable_totals": "Payment totals for a 1099 cross-check",
    "list_recipients": "List payment recipients",
    "list_tax_docs": "List recipient tax forms on file",
    "get_org": "Get the organization profile",
    "list_statements": "List account statements",
    "get_statement_pdf": "Get an account statement PDF",
    "list_treasury": "List treasury accounts",
    "list_treasury_transactions": "List treasury transactions",
    "list_treasury_statements": "List treasury statements and tax forms",
    "list_credit_accounts": "List credit accounts",
    "list_cards": "List cards",
    "get_card": "Get one card",
    "list_categories": "List expense categories",
    "list_merchants": "List merchants for card locks",
    "list_customers": "List invoice customers",
    "list_invoices": "List invoices",
    "get_invoice": "Get one invoice with line items",
    "get_invoice_pdf": "Get an invoice PDF",
    "list_invoice_attachments": "List an invoice's attachments",
    "list_users": "List organization users",
    "list_events": "List change events",
    "list_webhooks": "List webhooks",
    "server_info": "Server information",
}


def test_the_title_table_covers_every_tool():
    assert set(TITLES) == EXPECTED_TOOLS
    assert len(set(TITLES.values())) == len(TITLES)


async def test_every_tool_carries_its_title_twice(mcp_client: Client, default_client: Client):
    for client, expected in ((mcp_client, EXPECTED_TOOLS), (default_client, DEFAULT_TOOLS)):
        tools = await _tools(client)
        assert set(tools) == expected
        for name, tool in tools.items():
            assert tool.title == TITLES[name], name
            assert tool.annotations is not None, name
            assert tool.annotations.title == TITLES[name], name


async def test_titles_are_short_and_names_fit_64_characters(mcp_client: Client):
    for name, tool in (await _tools(mcp_client)).items():
        assert 0 < len(tool.title) <= 40, (name, tool.title)
        assert len(name) <= 64, name
