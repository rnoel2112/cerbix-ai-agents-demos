"""Shared harness for the clientAI scenarios.

Each scenario is a small "client AI agent" running the **real SDK enforcement
engine**. The harness builds a genuine ``cerbix.CerbixRuntime`` and drives its
real request/response hooks (identity → cascade → DLP → PIP →
``raise_if_blocked``) — the exact decision code a live call hits — so every
ALLOW / BLOCK / REDACT is a genuine product decision, rendered deterministically
with no server, network, or API keys.

What's real vs simulated, to be precise:
  • REAL: the SDK package, the runtime, the policy cascade + structured
    conditions, DLP/PIP, and the block/redact decisions.
  • SIMULATED: the LLM/tool call itself. Instead of patching the network and
    making a real request, the harness drives the hooks directly — which keeps
    the demos deterministic AND lets scenarios exercise paths the httpcore
    catch-all doesn't carry (structured attributes, streaming response bodies,
    non-AI egress hosts — all transport/proxy-plane concerns).

For the FULLY faithful path — ``cerbix.init()`` monkey-patching a real
``httpx`` call that gets blocked before the network — see
``scenario_00_real_interception.py`` (and ``tests/sdk/test_enforcement_integration.py``).

In production the policy rules are synced from the control plane; here we load
them directly into the agent so each scenario is self-contained.
"""

from __future__ import annotations

import os
import sys

# Make the in-repo SDK importable without `pip install` (demo convenience).
_SDK = os.path.join(os.path.dirname(__file__), "..", "cerbix", "sdk")
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

import logging  # noqa: E402

# Silence the SDK's internal warning lines so only the scenario narration
# shows. (The decisions themselves are what we render below.)
logging.getLogger("cerbix").setLevel(logging.ERROR)

import cerbix  # noqa: E402
from cerbix import CerbixBlockedError, CerbixConfig  # noqa: E402
from cerbix.config import DLPConfig, PIPConfig  # noqa: E402
from cerbix.interceptors.base import (  # noqa: E402
    RequestContext,
    ResponseContext,
    raise_if_blocked,
    raise_if_response_blocked,
)

GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


class ClientAgent:
    """A Cerbix-protected AI agent for demonstrations."""

    def __init__(
        self,
        name: str,
        *,
        department: str = "",
        rules: list | None = None,
        lists: dict | None = None,
        dlp: bool = False,
        pip: bool = False,
        shadow: bool = False,
    ) -> None:
        self.name = name
        config = CerbixConfig(
            org_id="clientai-demo",
            agent_id=name,
            department=department,
            audit_enabled=False,
            shadow_mode=shadow,
            dlp=DLPConfig(enabled=dlp, mode="enforce"),
            pip=PIPConfig(enabled=pip),
        )
        # Construct the runtime (wires the real hooks) without starting
        # background threads / network — we drive the hooks directly.
        self.runtime = cerbix.CerbixRuntime(config)
        self.runtime.token_manager = None
        self.runtime.transport = None
        if self.runtime.policy_sync is not None:
            self.runtime.policy_sync._rules = rules or []
            self.runtime.policy_sync._lists = lists or {}

    # ── Agentic actions ──────────────────────────────────────

    def act(self, action: str, resource: str, body=None, attributes=None) -> bool:
        """Take an outbound action (tool/LLM call). Returns True if allowed.

        `attributes` carries structured fields (amount, counterparty, hour…)
        for condition-based rules.
        """
        ctx = RequestContext(method=action, url=resource, body=body)
        if attributes:
            ctx.metadata["attributes"] = attributes
        for hook in self.runtime.registry._request_hooks:
            ctx = hook(ctx) or ctx
        try:
            raise_if_blocked(ctx)
            print(f"   {GREEN}✓ ALLOWED{RESET}  {action} {resource}")
            return True
        except CerbixBlockedError as exc:
            print(f"   {RED}✗ BLOCKED{RESET}  {action} {resource}")
            print(f"             {DIM}{exc.reason}{RESET}")
            return False

    def receive(self, response_body: str):
        """Receive an inbound response (e.g. LLM output). Returns it, or None
        if Cerbix blocked it (e.g. it leaked PII)."""
        req = RequestContext(
            method="POST", url="https://api.openai.com/v1/chat/completions"
        )
        res = ResponseContext(body=response_body)
        for hook in self.runtime.registry._response_hooks:
            hook(req, res)
        try:
            raise_if_response_blocked(res)
            preview = response_body[:60] + ("…" if len(response_body) > 60 else "")
            print(f'   {GREEN}✓ RESPONSE delivered{RESET}  "{preview}"')
            return response_body
        except CerbixBlockedError as exc:
            print(f"   {RED}✗ RESPONSE blocked{RESET}")
            print(f"             {DIM}{exc.reason}{RESET}")
            return None


# ── Rule builders (mirror compiled control-plane rules) ──────


def rule(scope, target, action, text, *, department=None, agent_id=None):
    return {
        "id": f"{scope}-{target}-{abs(hash(text)) % 10000}",
        "scope": scope,
        "target": target,
        "action": action,
        "rule_text": text,
        "department": department,
        "agent_id": agent_id,
    }


def banner(title: str, subtitle: str = "") -> None:
    print()
    print(f"{BOLD}━━━ {title} ━━━{RESET}")
    if subtitle:
        print(f"{DIM}{subtitle}{RESET}")
