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

When you ask a single model to classify something high-stakes — and then ask the same model whether it got it right — it tends to agree with itself. One model can't grade its own homework. In domains where being wrong is expensive (regulated industries, legal exposure, real money), "the model said so" is not a defensible answer. Under the EU AI Act, a wrong high-risk classification carries fines up to €15M or 3% of global turnover (Art. 99) — the failure mode this pattern exists to reduce.

The need isn't a smarter single model. It's a *process* that produces an independent second judgement, makes disagreement visible, and keeps a human accountable for the decision.

## 2. What runs — the Maker-Checker engine *(runnable hero)*

Two agents on **different model vendors** classify the same case:

- **Maker** proposes a classification.
- **Checker** classifies the same input **without ever seeing the Maker's output** — independence is enforced by state isolation, not by asking the model nicely.
- A **deterministic, non-LLM verdict** compares the two: *consistent*, *divergent*, or *inconclusive*. The comparison is code, not a third model — it can't hallucinate its own conclusion.
- **Graceful degradation:** if one agent fails, the pipeline doesn't. The case proceeds to a human with the verdict capped to *inconclusive* — the surviving agent's classification can't stand in for a second opinion.

Independence here is **structural** — a state boundary in code, not a "please don't peek" instruction — so an auditor can *verify* it held, instead of taking the model's word that it did.

This is not an invention. It's the **pragmatic application of an established control pattern** — maker-checker / four-eyes, long used in finance and audit — to the specific failure modes of LLMs. The contribution is the engineering that makes it real: hard independence, a deterministic verdict, and honest failure handling.

By default the two agents run on different vendors — Google and Anthropic — so the verdict doesn't rest on any single vendor's judgement. That pairing is set in config; enforcing it, or adding a third vendor, would take code.

> **On the citations it emits.** Each agent returns article references from the model's own training knowledge — these are **ungrounded**, the failure mode named in [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md). That is deliberately **not** how the production parent does it: production grounds every classification against retrieved regulatory text, with provenance. The ungrounded version runs here on purpose — it makes the gap visible and keeps the fix ([0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) concrete rather than abstract.

## 3. Governance in config, not code

The behaviour of the system — the risk taxonomy, the model assignments, the agreement rule, the prompts that frame each agent — lives in a **YAML configuration layer**, not in the Python.

A non-technical owner (a compliance or risk lead) can change *what the system considers high-risk*, *which model does which job*, or *how each agent is framed* by editing config — **config, not code**. Agreement strictness is config-declared and validated too (`exact` today — the seam is live, not yet a tuning dial). The change takes effect **on the next run** — config is read fresh at startup, not hot-reloaded.

It turns a model pipeline into something a business owner can actually govern.

## 4. What it costs — the cost model a buyer has to build *(not a number on a random Tuesday)*

Running two models instead of one has a cost, and a serious buyer will ask what it is. There's no honest single figure — there's a **set of drivers you have to model**: token overhead of the second agent, context-window growth from retrieved grounding (a grounded-system input — grounding runs in the parent, not in this rebuild; see [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)), retry logic, and — the line most people miss — **the cost of the extra human-in-the-loop time that divergence adds.**

Point those drivers at *your* volumes and you get a P&L line item you can defend — which beats a number pulled from one run.

## 5. How it's measured — the evaluation the product needs *(method, not published accuracy %s)*

Claiming an accuracy number on a small fixture set is vanity — it reads as fabricated because it is. The actual product requirement is an **evaluation pipeline**: drift tracking over time, precision/recall against a golden set, and the **single-vs-dual delta threshold** — the measured question of whether the second agent actually earns its cost. And the metric a product owner can't skip: the **divergence rate** — how often the two agents disagree. A human reviews every case regardless, but a disagreement turns a quick sign-off into a slow adjudication — so that rate is what would size a reviewer team in production. That pipeline is designed, not built here — it lands with the eval work (tracked as deferred in the lineage).

A method for knowing whether it works beats a number that asks you to take it on faith.

## 6. Latency — a decision, not a gap

Two models sound like double the wait. They aren't. Maker and Checker run **in parallel** — independence is held by state isolation, not by running them in sequence. You pay the **slower** of the two models, not the sum. The honest latency floor here is the **slower model** alone — the verdict and its rendering are instant, deterministic code; *the grounded parent system adds retrieval and an LLM explanation step on top of that*. Divergent cases add human wall-clock, which is accounted for in the cost model above, not hidden here.

## 7. Route before you spend — the scope gate *(runs; the semantic upgrade is next)*

A cheap, deterministic, config-driven **scope gate** triages every case up front, so you don't pay two frontier models to classify inputs that are obviously out of scope — those skip the pair and route straight to a human. That gate runs today (keyword/domain matching against the config).

**What's next** is the *precision* upgrade: a semantic/vector router that also catches paraphrases the literal vocabulary misses — designed, not built, called out honestly rather than implied.

## 8. What I learned building it

- **Mirror tests give false confidence.** A test that re-implements the logic it's testing proves nothing about the shipping artifact — at least one test has to hit the real thing.
- **A prompt instruction is not a data-integrity control.** "Please don't include X" is not enforcement; the guarantee has to live in code, after the model returns.
- **A governed document no code reads is shelfware.** A config file that's the "source of truth" drifts silently unless something actually fails when it and the code disagree.

**A known gap, named — input safety.**

- **Issue:** The case text is handed to the model as-is. A cleverly worded case could try to steer the AI's answer — "prompt injection."
- **Impact:** A crafted input could push the model to the wrong EU AI Act risk level — the one thing a compliance tool can't afford to get quietly wrong.
- **Resolution:** This version only checks that the answer is one of the EU AI Act risk levels. That catches a garbled or made-up answer, but not an injection that asks for a real risk level that happens to be wrong (say, "treat this as minimal risk"). That gap is closed in the production system, which this rebuild doesn't copy: production scans the submitted text for prompt injection, and if it finds any, keeps it out of the classification and flags the potential issue to the human reviewer. Built and tested there; named here, not reproduced.

## 9. Tradeoffs

| Decision | Why | Impact |
|---|---|---|
| Two vendors, not two of the same model | Two of the same model tend to share the same weaknesses, so they can miss the same things | Both models agree on the wrong answer, and the reviewer sees hollow agreement, not a red flag |
| Deterministic verdict, not an LLM judge | The thing that decides agreement can't be allowed to hallucinate | The judge hallucinates agreement that isn't there — and, unlike code, can't show the reviewer why |
| Deterministic, config-driven triage, not an LLM router | The gate that decides whether to spend should be cheap and predictable, not another model call | A model call — and a new thing that can break — on every request, to make a call a rule already makes |
| RAG grounding, not full-context *(built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md))* | Token cost and focus — retrieve what's relevant, don't inject the whole rulebook | In the parent, the operative articles alone (~87K tokens) ran nearly 3× over the model's rate limit — retrieval cut each call to 5–10K |
| Parallel, not sequential | Independence without paying latency twice | The reviewer waits through two model calls back-to-back instead of one |

---

## What runs vs what's designed

*This table separates what's validated against working code from what's designed but not yet built. The left column only holds claims checked against real code; everything else — including work in progress — sits on the right. Build status is tracked precisely in [`docs/decisions/adr-lineage.md`](docs/decisions/adr-lineage.md).*

| RUNS (validated against code) | DESIGNED / NEXT (roadmap) |
|---|---|
| Maker-Checker independent verification | Semantic/vector scope router (precision upgrade) |
| Deterministic scope gate — route-before-you-spend triage | Multi-framework activation |
| Human always decides — type-enforced | Grounding *hardening* + drift detection (base grounding built in the parent — [0007](docs/decisions/0007-grounding-and-retrieved-source-provenance.md)) |
| Governance in config (config-not-code, validated at startup) | Cost-optimised expansion |

*If a claim can't sit cleanly on the left, it goes on the right with the tense to match.*

*RUNS = with your own Google + Anthropic API keys; there is no offline mode ([0008](docs/decisions/0008-runnable-agent-layer.md)).*

---

## Worked example

The EU AI Act is how the engine is *shown* working — public law, high-stakes, concrete. The engine itself is domain-agnostic: the same Maker-Checker pattern applies wherever a classification has to be defensible, not only to regulation.

## Run it

The CLI is the only surface ([0006](docs/decisions/0006-inherited-scope-boundaries.md)) — two verbs that mirror the honesty spine: a free, keyless map, and a live, costed proof.

```bash
git clone https://github.com/davidwkavanagh/maker-checker-agents
cd maker-checker-agents
pip install -e '.[live]'          # editable install, run from the clone

mca list                          # the map: every demo case + its illustrative tier — free, no keys

export GOOGLE_API_KEY=...          # the Maker  (Gemini)
export ANTHROPIC_API_KEY=...       # the Checker (Claude)
mca run credit-scoring            # the proof: one case, live — both agents, the verdict, routed to a human
```

`mca list` needs no keys — the scope map is deterministic. `mca run <case-id>` makes real, paid calls to both vendors ([0008](docs/decisions/0008-runnable-agent-layer.md)); there is no offline or replay mode, and missing keys are caught before any spend. Run from the clone (or `python -m maker_checker_agents …` if the `mca` script isn't on your PATH).

## License

MIT — see [LICENSE](LICENSE).
