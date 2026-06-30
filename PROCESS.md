# How this repo is built

This is a portfolio project, but it is built like production work. The scope is
deliberately small (KISS); the *process* is not. **Minimal scope, maximal rigor**
— because at a senior level the code is table stakes and the *thinking* (the
decisions, the trade-offs, the way failure is handled) is the thing worth
showing. The process artifacts in this repo are part of what it demonstrates.

## Quality gates — every work item

Each unit of work goes through the same sequence:

1. **Architect lens + read first.** Understand the existing code and the
   constraints before writing anything. No edits before reading.
2. **Adversarial challenge (recorded).** An independent pass that tries to break
   the design — wrong invariants, dead config, missing failure modes. The author
   can't be their own witness. Findings are written down, not just fixed in
   passing.
3. **Decision record.** Any non-obvious call is captured as a short ADR-lite in
   [`docs/decisions/`](docs/decisions/) — the decision, the alternatives, and why.
4. **Tests first.** Tests are written before the implementation and fail for the
   right reason first. At least one test exercises the real artifact, not a
   re-implementation of its logic (mirror tests prove nothing about what ships).
5. **Implement.**
6. **Review cycle:** correctness review → test-coverage challenge → security
   pass → audit against the stated spec (the README arc and the ADRs).
7. **Pre-commit gate.** A final adversarial look at the committed state before it
   is staged. Staged paths are named explicitly — never `git add -A`.
8. **Branch → PR → merge.** One branch per issue, linked to a GitHub issue. CI
   (lint + type-check + tests) must be green. Nothing lands on `main` directly.

**Cross-model review (Gemini Pro)** runs at the code-quality pass and on any
high-stakes or contested call. Its output is *adjudicated, not forwarded* — a
second model optimises for its own framing of the prompt, so its advice is
weighed against the project's own strategy before anything is acted on.

## What is deliberately NOT here

This project borrows its discipline from a larger regulated-AI system but drops
the ceremony that only existed to protect a legally-consequential artifact:

- **Compliance routing / sign-off workflow** — there is no €35M penalty here.
- **Signed-PDF audit records and sub-article citation verification** — the EU AI
  Act is a *worked example* in this repo, not a live compliance product.
- **Deploy / incident apparatus** (CDN, hosted DB, release hooks) — this runs
  from a clean clone with the caller's own API keys; there is no hosted
  infrastructure. The *principle* (fail-fast config, honest degradation) is kept;
  the infrastructure is not.

Scope and process are orthogonal. Cutting scope does not mean cutting rigor.

## Commit & history conventions

- Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `build:`, `chore:`).
- History reads as a narrative — no single squashed dump of the whole project.
- The honesty spine in the README governs every claim: if something is designed
  but not running, it is labelled *DESIGNED / NEXT*, in the matching tense.
