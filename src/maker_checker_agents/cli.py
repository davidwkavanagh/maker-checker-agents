"""The CLI — the repo's only surface, two verbs that mirror the honesty spine (issue #6).

* ``mca list`` — the map. Prints the fictional cases and their *illustrative* expected
  tier. Free, deterministic, and runnable with **no API keys**: a first-contact
  cloner's first command succeeds and teaches the scope before the key wall.
* ``mca run <case-id>`` — the proof. Sends one case through ``run_pipeline`` (live
  Maker ‖ Checker) and prints the reviewer's-eye view: the *full* decision of both
  agents (tier, rationale, cited articles), the verdict, and the routed-to-human
  line. This engine hands the whole picture to a human and stops.

Locked constraints ([0005]/[0007]/[0008]):

* Live calls, own keys, no mock. A pre-flight key check (a config guard, not a
  replay harness) fires before any spend.
* Citation honesty. Where citations render, a factual note says they are
  illustrative/ungrounded and points at how production grounds them ([0007]).
* Unconditional HITL. Every returned result routes to a human. The one non-routed
  path is both-agents-fail, which ``run_pipeline`` raises as ``PipelineError`` — the
  CLI renders that as a designed message, never a traceback, and never a verdict.
* No secret leaks. No API-key *value* is ever printed — only the variable names.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .agents import AdapterPreflightError, preflight_environment
from .cases import DEMO_CASES, get_demo_case
from .config import ConfigError, Policy, load_policy
from .models import AgentOutput, PipelineResult
from .pipeline import PipelineError, run_pipeline

# The policy lives in the repo root; the CLI is run from a clone ([0008]).
_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "policy.yaml"

_CITATION_NOTE = (
    "Note on citations: the articles above are illustrative and ungrounded — each "
    "agent cites from parametric knowledge, not a verified source. Production grounds "
    "every citation via retrieval over the actual legal text, with provenance (see 0007)."
)

_USAGE = (
    "usage: mca <command>\n"
    "  list            list the fictional demo cases (no API keys needed)\n"
    "  run <case-id>   run one case live through the maker-checker pipeline\n"
)


# --------------------------------------------------------------------------- #
# Rendering — pure, no live calls
# --------------------------------------------------------------------------- #
def _render_agent(label: str, agent: AgentOutput | None) -> str:
    # `rationale` and `articles_cited` are live model output, printed verbatim — so
    # the untrusted channel is the model's *response*, not the (trusted) demo case: a
    # model can emit C0/ANSI control bytes to visually spoof the verdict line no matter
    # how static the input is. With no attacker-controlled model deployment here that
    # spoof is out of scope; a deployment rendering untrusted model output should strip
    # control chars first. Documented boundary, not hardened — proof, not platform (0011).
    if agent is None:
        return f"{label}: (no classification returned — this agent did not respond)"
    articles = ", ".join(agent.articles_cited) if agent.articles_cited else "(none cited)"
    return (
        f"{label}:\n"
        f"  Risk tier:      {agent.risk_tier}\n"
        f"  Rationale:      {agent.rationale}\n"
        f"  Articles cited: {articles}"
    )


def render_result(result: PipelineResult, policy: Policy) -> str:
    """Render a completed pipeline result as the reviewer's-eye view.

    Agent labels are derived from ``policy.models`` — the record names the model that
    actually classified, so reconfiguring the vendor in ``policy.yaml`` re-labels the
    output (config, not code). The CLI hardcodes no vendor name.
    """
    lines: list[str] = [f"Case: {result.case_id}", ""]

    if result.verdict is None:
        # Out of scope: the gate matched no governed framework, so the expensive
        # pair was skipped. Not classified — but still routed to a human.
        lines.append("Scope:   OUT OF SCOPE — no governed framework matched.")
        if result.scope.sensitive:
            lines.append("Sensitive: FLAGGED — brief matched the policy's sensitivity keywords.")
        lines.append("The maker-checker pair was skipped; this case was not classified.")
        lines.append("Routed to a human for confirmation.")
        return "\n".join(lines)

    vr = result.verdict
    scope = result.scope
    matched = ", ".join(scope.applicable_frameworks) or "none"
    lines.append(f"Scope:   in scope — matched: {matched}")
    if scope.sensitive:
        # 0006: the sensitivity flag is a retained reduction that MUST surface here —
        # the CLI is the only surface, so an unsurfaced flag is shelfware.
        lines.append("Sensitive: FLAGGED — brief matched the policy's sensitivity keywords.")
    lines.append("")
    lines.append(_render_agent(f"Maker ({policy.models.maker.model})", vr.maker))
    lines.append("")
    lines.append(_render_agent(f"Checker ({policy.models.checker.model})", vr.checker))
    lines.append("")
    lines.append(f"Verdict: {vr.verdict.value.upper()}")
    if vr.notes:
        lines.append(f"Note:    {vr.notes}")
    lines.append("Routed to a human — the human decides; this engine stops here.")
    lines.append("")
    lines.append(_CITATION_NOTE)
    return "\n".join(lines)


def render_pipeline_error() -> str:
    """Render the both-agents-fail path as a designed message, never a traceback."""
    return (
        "Cannot proceed: both agents failed to classify this case.\n"
        "Both models were unavailable, so there is nothing to review and no verdict "
        "was produced. This is a run failure, not a classification — please try again."
    )


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def _cmd_list() -> int:
    print("Fictional EU AI Act demo cases (illustrative — not real filings).")
    print("The 'expected tier' is an illustrative label for orientation, not a")
    print("grounded classification. Run one live with: mca run <case-id>")
    print()
    for demo in DEMO_CASES:
        tier = demo.expected_tier if demo.expected_tier is not None else "out of scope"
        diverge = "  (designed to diverge)" if demo.designed_to_diverge else ""
        print(f"  {demo.case.case_id:<26}  {tier:<13}  {demo.case.system_name}{diverge}")
    return 0


def _cmd_run(case_id: str) -> int:
    # Load the policy first: it names which vendors run, so the pre-flight can
    # demand exactly their keys. A malformed policy fails here with a clear
    # message, never a raw traceback.
    try:
        policy = _load_policy()
    except ConfigError as exc:
        print(f"Cannot run: {exc}", file=sys.stderr)
        return 1

    # Validate the case id first — it is free and deterministic, so an unknown id
    # fails cheaply without first sending the user to the key wall.
    demo = get_demo_case(case_id)
    if demo is None:
        print(f"Unknown case id: {case_id!r}. See available cases with: mca list", file=sys.stderr)
        return 1

    # Pre-flight: the adapter owns which secrets the selected models need. A config
    # guard before any spend, not a mock ([0008]). The CLI stays vendor-agnostic.
    try:
        preflight_environment(policy.models)
    except AdapterPreflightError as exc:
        print(f"Cannot run: {exc}", file=sys.stderr)
        print("No API calls were made.", file=sys.stderr)
        return 1

    try:
        result = run_pipeline(demo.case, policy)
    except PipelineError:
        print(render_pipeline_error(), file=sys.stderr)
        return 1

    print(render_result(result, policy))
    return 0


def _load_policy() -> Policy:
    return load_policy(_POLICY_PATH)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 success, non-zero failure)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2

    command, *rest = args
    if command == "list":
        return _cmd_list()
    if command == "run":
        if len(rest) != 1:
            print("usage: mca run <case-id>", file=sys.stderr)
            return 2
        return _cmd_run(rest[0])

    print(f"Unknown command: {command!r}", file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2
