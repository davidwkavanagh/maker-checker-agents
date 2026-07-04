# 0011 — The CLI: two verbs, and a pre-flight that follows the config

**Status:** Accepted

## Context

Issue #6 builds the CLI — the repo's **only** surface ([0006]: the reviewer UI is a
cut, not a deferral). It consumes `run_pipeline` ([0010]) and renders the result a
human acts on. The plan reserved three decisions for this issue: how cases are
stored, how the tool is invoked, and the entry point. Review then surfaced a fourth
that mattered more than any of them — how the pre-flight key check knows which keys
to demand.

## Decision 1 — Two verbs mirroring the honesty spine: `list` (the map) and `run` (the proof)

`mca list` prints every fictional case and its *illustrative* expected tier —
**deterministic, keyless, free**. `mca run <case-id>` sends one case live through
`run_pipeline` and prints the reviewer's-eye view: both agents' full decision, the
verdict, the routed-to-human line. Single case, **no batch / no run-all**.

*Why:* the two verbs are the honesty spine made operable. `list` is the map a
first-contact cloner runs before the key wall — it teaches the scope for free. `run`
is the costed proof. A batch/run-all verb would multiply live spend for a demo whose
point is one honest run, and invite a replay/fixture harness to make it repeatable —
which [0008] D1 forbids (live only, no mock).

## Decision 2 — Cases are Python literals in `cases.py`, not YAML

The six demo cases are `DemoCase` literals (a `Case` plus `expected_tier` and
`designed_to_diverge`), authored in code.

*Why:* "data not code" is unearned for a handful of curated fixtures that must
conform to a frozen `Case`. YAML would add a parse/validation failure surface for no
benefit, and `cases.py` doubles as the single source of truth the tests bind to
(`expected_tier` is checked against `policy.risk_tier_ids`; the out-of-scope case is
checked against the *real* scope gate, not its label). The policy that a compliance
owner edits is `policy.yaml`; the demo fixtures are the developer's, and belong in
code.

## Decision 3 — `console_scripts` `mca` primary, a delegating `__main__.py` fallback

`mca` is the entry point ([project.scripts]); `python -m maker_checker_agents` is a
three-line shim delegating to `main`. No duplicated logic.

*Why:* one command from a clean clone (the AC). The `__main__` shim is a PATH-failure
fallback, not a second implementation.

## Decision 4 — The pre-flight key check follows the config: the adapter owns which keys are needed

`mca run` must confirm the required API keys are present **before any paid call**.
The required variables are **not hardcoded** — they are derived from the configured
providers (`policy.models`) by `agents.preflight_environment`, which raises
`AdapterPreflightError` naming every missing variable. The CLI holds **zero** vendor
names, no `os` env-sniffing, no key strings.

*Why here (the adapter), and how it was chosen:* the fact "provider `google` needs
`GOOGLE_API_KEY`" is not policy data and not a CLI concern — it is an **SDK
implementation detail**: it is what the `ChatGoogleGenerativeAI` client reads.
`agents.py` is the only module that imports the vendor SDKs, so it is the only module
that should know what they need. `preflight_environment` sits beside `_make_client`
and mirrors its exhaustive `assert_never`, so a new provider is a mypy error in both
places — the key requirement and the client construction cannot drift. Because it is
derived from `policy.models`, pointing both agents at one vendor in `policy.yaml`
demands only that vendor's key ([0004]: config, not code). This was the *entry point
that quietly contradicted the config-not-code thesis*; deriving it makes the thesis
true at the one surface a user touches.

*Alternatives rejected (options walked, reviewed cross-vendor):*
- **Hardcode `(GOOGLE, ANTHROPIC)`** — the shipped bug: a policy on one vendor still
  demands the other's key. Falsifies a README "RUNS" claim.
- **A map in the CLI** — puts vendor knowledge in a file that otherwise knows nothing
  about SDKs; no exhaustiveness tie to `_make_client`.
- **A property on `Policy` (config.py)** — a layering violation: `config.py` is the
  schema layer and imports no SDK; the env-var is SDK-packaging trivia, not a
  projection of YAML data (unlike `risk_tier_ids`). *(This was the author's first
  pick; an independent Sonnet review corrected it to the adapter; a cross-vendor
  Gemini review then refined a bare-string helper into the encapsulated
  `preflight_environment`.)*
- **A `str`-returning helper in agents.py** — right layer, but leaks the env check
  back to the CLI (imports `os`, sniffs env) and assumes one variable per provider.
  `preflight_environment` returns a `set` and owns the check end to end.

## Decision 5 — Every failure renders a designed message; no failure fabricates a verdict

Two failure paths reach a designed, plain message on stderr, never a raw traceback:
**both agents fail** (`run_pipeline` raises `PipelineError` [0010] D6 → a "cannot
proceed" message, no verdict) and **an unreadable/malformed policy** (`load_policy`
raises `ConfigError`, now including read errors — a UTF-16/BOM file or a permission
fault — caught at the one call site). Citations always carry the honesty note
([0007]/[0008] D2): a once-per-run factual line that the cited articles are
illustrative and ungrounded, and how production grounds them.

*Why:* the honesty spine's make-or-break is first contact. A traceback leaking paths
and internals on the most likely misconfiguration (a wrong key, a bad policy file)
would undercut the whole pitch — and a fabricated verdict on failure would be the
exact anti-pattern [0010] D6 forbids. No `Verdict` is built on any failure path.

## Decision 6 — The render shows the whole reviewer's-eye picture, including the retained sensitivity flag

`render_result` shows both agents' tier + rationale + cited articles, the verdict,
the scope context (matched framework), and — on both the in-scope and out-of-scope
paths — the **sensitivity flag** when set. Routed-to-human is on every path. Each
agent is labelled with the model that classified it, read from `policy.models` — the
record names the actual classifier, so reconfiguring the vendor in `policy.yaml`
re-labels the output. This is what makes Decision 4's "zero vendor names in the CLI"
literally true: no vendor string is hardcoded anywhere, not even in the render.

*Why the sensitivity flag specifically:* [0006] keeps the sensitivity flag as a
**retained reduction — "it surfaces, it does not tokenise"**. The CLI is the only
surface, so a computed-but-unrendered flag would be exactly the shelfware a governance
artifact becomes when nothing reads it. Surfacing it is what makes the record true.

*Documented boundary, not hardened (F2, security review):* the agents' `rationale`
and `articles_cited` are **live model output**, printed verbatim — so the untrusted
channel is the model's *response*, not the (trusted) demo case. A model can emit
C0/ANSI control bytes to visually spoof the verdict line regardless of how static the
input case is; with no attacker-controlled model deployment here that spoof is out of
scope, and a deployment rendering untrusted model output should strip control
characters first. This is called out at the render site and left un-hardened deliberately —
building the defence for a threat this artifact's shape cannot present would be the
gold-plating this repo argues against (proof, not platform). A precise, scoped note
is the stronger signal.

## Note — the `minimal` tier is unrepresented in the fixtures *by design*

The six cases span **unacceptable / high / limited**, plus a genuinely gate-skipped
out-of-scope case and a divergence-designed case. No fixture is labelled `minimal`:
the scope gate triggers only on *regulated* concepts, so a case benign enough to
warrant `minimal` typically matches no keyword or domain and is **gate-skipped as out
of scope** before an agent runs — a fixture authored to elicit `minimal` would usually
be one the real gate skips. (`minimal` remains a valid tier the agents *can* assign to
an in-scope case; no demo case is written to elicit it.) The out-of-scope case
(`bank-meeting-summariser`) is the benign end of the taxonomy.

## Consequences

- The runnable hero is complete and usable: #4 + #5 + #6 run from a clean clone.
- **README doc-debt closed** ([0008]): the quickstart is filled (`mca list` keyless,
  `mca run` live with your own keys, no offline mode).
- **`adr-lineage.md`:** the CLI-only surface ([0006]) is now realised in code.
- Cases are an even finance/pharma split for the regulated-enterprise audience;
  `credit-scoring` (high, legal) vs `customer-social-scoring` (unacceptable,
  prohibited) shows the line the Act draws.

## Evidence

- `src/maker_checker_agents/cli.py` — `main`, `_cmd_list`, `_cmd_run`,
  `render_result`, `render_pipeline_error`.
- `src/maker_checker_agents/cases.py` — `DemoCase`, `DEMO_CASES`, `get_demo_case`.
- `src/maker_checker_agents/__main__.py` — the `python -m` shim.
- `src/maker_checker_agents/agents.py` — `AdapterPreflightError`,
  `preflight_environment`, `_required_env_vars` (exhaustive, beside `_make_client`).
- `src/maker_checker_agents/config.py` — `load_policy` read-error guard.
- `tests/test_cli.py`, `tests/test_agents.py`, `tests/test_config.py` — case-set
  binding (real gate, tier span, divergence), keyless `list`, pre-flight ordering +
  same-vendor derivation + partial keys, designed both-fail/ConfigError messages,
  consistent-verdict and sensitivity-flag renders, the `python -m` shim end to end.

## Lineage

Realises the CLI-only surface of **[0006]**; renders `PipelineResult` from **[0010]**;
carries the always-human floor via **[0005]**, the citation-honesty contrast via
**[0007]**, and live/no-mock via **[0008]**. See [`adr-lineage.md`](adr-lineage.md).

[0004]: 0004-config-as-governance.md
[0005]: 0005-type-enforced-hitl.md
[0006]: 0006-inherited-scope-boundaries.md
[0007]: 0007-grounding-and-retrieved-source-provenance.md
[0008]: 0008-runnable-agent-layer.md
[0010]: 0010-pipeline-orchestration.md
