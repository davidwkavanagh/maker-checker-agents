# maker-checker-agents

**Independent dual-agent verification for high-stakes AI classification.** Two models from different vendors classify the same case without seeing each other's work; a deterministic check surfaces where they disagree; a human always makes the call. The rules that govern the AI live in configuration, not code.

---

## Why I built this

Even before AI was widely adopted, dev velocity was outpacing Governance — Compliance, Legal and Privacy. Those reviews simply didn't scale at the same rate products were being built. That mismatch turned a process that used to keep pace into a bottleneck, extending time-to-market by months, not because Governance is slow or unwilling, but because the ratio broke.

The fix I have seen is that an organization moves Governance further down the product lifecycle, only fully engaging them once products are in the build stage. In my opinion this fix was wrong. It made changes required by Governance expensive and time-consuming, and turned them into adversaries to overcome.

I believe the fix isn't pushing Governance further down the funnel, it's giving Governance a voice at the point of cheapest correction — making them partners at ideation, not adversaries at launch. Submission to Governance is mandatory, but a submitter can see their classification and understand the challenges they face before they choose to proceed. They can revise and resubmit, move forward, or decide not to — maybe they were just testing an idea.

The EU AI Act was chosen as the worked example because it represents the most immediate AI-specific regulatory challenge facing organisations in Europe. High-risk classification obligations under Annex III were originally scheduled to apply from August 2026. The Digital Omnibus deferred those specific obligations to December 2027, but August 2026 remains a live date for transparency obligations.

That deferral is the window: organisations that get governance right now will be ready. Those that don't will face the same reactive scramble GDPR triggered in 2018. It's the worked example, not the limit. The same pattern extends to GDPR, DORA and ISO 42001 as the engine grows.

This README describes the product as it's designed to work, not necessarily as it fully runs today — what's marked as working is checked against running code, and nothing's claimed as done until it's built. The pattern comes from [Sandra](https://prileco.com), a live EU AI Act governance system I built.

## 1. The problem

When you ask a single model to classify something high-stakes — and then ask the same model whether it got it right — it tends to agree with itself. One model can't grade its own homework. In domains where being wrong is expensive (regulated industries, legal exposure, real money), "the model said so" is not a defensible answer.

The need isn't a smarter single model. It's a *process* that produces an independent second judgement, makes disagreement visible, and keeps a human accountable for the decision.

## 2. What runs — the Maker-Checker engine *(runnable hero)*

Two agents on **different model vendors** classify the same case:

- **Maker** proposes a classification.
- **Checker** classifies the same input **without ever seeing the Maker's output** — independence is enforced by state isolation, not by asking the model nicely.
- A **deterministic, non-LLM verdict** compares the two: *consistent*, *divergent*, or *inconclusive*. The comparison is code, not a third model — it can't hallucinate its own conclusion.
- **Graceful degradation:** if one agent fails, the pipeline doesn't. The case proceeds to a human with the verdict marked degraded.

This is not an invention. It's the **pragmatic application of an established control pattern** — maker-checker / four-eyes, long used in finance and audit — to the specific failure modes of LLMs. The contribution is the engineering that makes it real: hard independence, a deterministic verdict, and honest failure handling.

> **On the citations it emits.** Each agent returns article references from the model's own training knowledge — these are **ungrounded**, the failure mode named in [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md). That is deliberately **not** how the production parent does it: production grounds every classification against retrieved regulatory text, with provenance. The ungrounded version runs here on purpose — it makes the gap visible and keeps the fix ([0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) concrete rather than abstract.

> _[visual: demo GIF — Maker-Checker running on a sample case, terminal output]_

## 3. The digital-enablement layer — governance in config, not code

The behaviour of the system — the risk taxonomy, the model assignments, the thresholds, the prompts that frame each agent — lives in a **YAML configuration layer**, not in the Python.

A non-technical owner (a compliance or risk lead) can change *what the system considers high-risk*, *which model does which job*, or *how strict the agreement threshold is* by editing config — **config, not code**. The change takes effect **on the next deploy** (not live, not zero-deploy).

It turns a model pipeline into something a business owner can actually govern.

> _[visual: clip — edit a YAML value, behaviour changes]_

## 4. What it costs — a TCO method *(not a number on a random Tuesday)*

Running two models instead of one has a cost, and a serious buyer will ask what it is. This section is a **costing method**, not a hardcoded figure: token overhead of the second agent, context-window growth from retrieved grounding (a grounded-system input — grounding runs in the parent, not in this rebuild; see [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)), retry logic, and — the line most people miss — **the cost of the human-in-the-loop cycles that divergence triggers.**

The output is a model you can point at *your* volumes to project a P&L line item at scale.

## 5. How it's measured — an evaluation framework *(method, not published accuracy %s)*

Claiming an accuracy number on a small set looks fabricated. Instead this describes the **evaluation pipeline architecture**: drift tracking over time, precision/recall against a golden set, and the **single-vs-dual delta threshold** — the measured question of whether the second agent actually earns its cost.

A method for knowing whether it works beats a number that asks you to take it on faith.

## 6. Latency — a decision, not a gap

Two models sound like double the wait. They aren't. Maker and Checker run **in parallel** — independence is held by state isolation, not by running them in sequence. You pay the **slower** of the two models, not the sum. The honest latency floor is *(slower model + the explanation step; add retrieval in the grounded parent system)*; divergent cases add human wall-clock, which is accounted for in the TCO method above, not hidden here.

## 7. What's next — route before you spend *(designed, not shipped — labelled)*

A cheap, config-driven router that triages cases up front, so you don't pay two frontier models to classify inputs that obviously don't apply. **Designed, not built** — it's on the roadmap, called out honestly rather than implied.

## 8. What I learned building it

- **Mirror tests give false confidence.** A test that re-implements the logic it's testing proves nothing about the shipping artifact — at least one test has to hit the real thing.
- **A prompt instruction is not a data-integrity control.** "Please don't include X" is not enforcement; the guarantee has to live in code, after the model returns.
- **A governed document no code reads is shelfware.** A config file that's the "source of truth" drifts silently unless something actually fails when it and the code disagree.

**A known gap, named — input safety.**

- **Issue:** The case text is handed to the model as-is. A cleverly worded case could try to steer the AI's answer — "prompt injection."
- **Impact:** A crafted input could push the model to the wrong EU AI Act risk level — the one thing a compliance tool can't afford to get quietly wrong.
- **Resolution:** This version only checks that the answer is one of the EU AI Act risk levels. That catches a garbled or made-up answer, but not an injection that asks for a real risk level that happens to be wrong (say, "treat this as minimal risk"). That gap is closed in the production system, which this rebuild doesn't copy: production scans the submitted text for prompt injection, and if it finds any, keeps it out of the classification and flags the potential issue to the human reviewer. Built and tested there; named here, not reproduced.

## 9. Tradeoffs

| Decision | Why |
|---|---|
| Two vendors, not two of the same model | Correlated errors defeat the point of a second opinion |
| Deterministic verdict, not an LLM judge | The thing that decides agreement can't be allowed to hallucinate |
| Config-driven router (next), not an LLM router | Triage should be cheap and predictable |
| RAG grounding, not full-context *(built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md))* | Cost and focus — retrieve what's relevant, don't pay for the whole corpus |
| Parallel, not sequential | Independence without paying latency twice |

---

## What runs vs what's designed

*This table separates what's validated against working code from what's designed but not yet built. The left column only holds claims checked against real code; everything else — including work in progress — sits on the right. Build status is tracked precisely in [`docs/decisions/adr-lineage.md`](docs/decisions/adr-lineage.md).*

| RUNS (validated against code) | DESIGNED / NEXT (roadmap) |
|---|---|
| Maker-Checker independent verification | Route-before-you-spend router |
| Human always decides — type-enforced | Multi-framework activation |
| Governance in config (config-not-code, validated at startup) | Grounding *hardening* + drift detection (base grounding built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) |
| | Cost-optimised expansion |

*If a claim can't sit cleanly on the left, it goes on the right with the tense to match.*

*RUNS = with your own Google + Anthropic API keys; there is no offline mode ([0008](docs/decisions/0008-runnable-agent-layer.md)).*

---

## Worked example

The EU AI Act is how the engine is *shown* working — public law, high-stakes, concrete. The engine itself is domain-agnostic: the same Maker-Checker pattern applies wherever a classification has to be defensible, not only to regulation.

## Run it

> _Quickstart lands here once the CLI is built — one command, runs with your own Google + Anthropic API keys (no offline mode)._

## License

MIT — see [LICENSE](LICENSE).
