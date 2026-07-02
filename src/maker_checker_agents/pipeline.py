"""The runner — composes the four stages into one end-to-end pipeline (issue #5).

    scope gate → (maker ‖ checker, concurrent) → verdict → human

This module only *composes* the stages; every piece of stage logic lives in its
own already-tested function (``scope_gate``, ``agents``, ``verdict``). That is
deliberate ([0010]): the composition is exactly the shape a LangGraph
``StateGraph`` would declare — four nodes, a fan-out from the gate to the two
agents, a fan-in to the verdict — so moving to a framework is a mechanical wrap,
not a rewrite. Sandra runs this on LangGraph because it needs durable
interrupt/resume and multi-framework routing; this proof deliberately cuts both,
so the orchestration is plain stdlib: one ``ThreadPoolExecutor`` at the single
fan-out point.

A human initiates every run synchronously (the CLI, #6). That single fact shapes
the failure model:

* **Out of scope skips the spend, never the human.** ``proceed=False`` → the
  expensive pair is not called at all, ``verdict`` is ``None``, the case still
  routes to a human ("route before you spend"). A gate that failed *open* returns
  ``proceed=True, degraded=True`` — the pair runs and the verdict caps ([0009]).
* **One agent fails, the run continues.** The other still classified → INCONCLUSIVE,
  routed to the human with the one result ([0009]): graceful degradation.
* **Both agents fail, the run cannot proceed.** There is nothing to classify or
  review, so ``run_pipeline`` raises ``PipelineError`` — the human who started the
  run gets an error and retries. This is the FAILED state [0009] deferred to the
  runner; it is a *run failure*, not a verdict value.
* **Parallel, not sequential.** Maker and Checker are independent ([0008]) so they
  run concurrently; the calls are blocking network I/O (GIL released), so threads
  give real wall-clock parallelism: pay the slower of the two, not the sum.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait

from .agents import run_checker, run_maker
from .config import Policy
from .models import AgentOutput, Case, PipelineResult
from .scope_gate import run_scope_gate
from .verdict import run_verdict

# A single classification call returns a small JSON verdict in seconds; 60s is a
# generous ceiling that will not false-trip a legitimately slow call. Past it the
# vendor call is treated as hung: the agent degrades to ``None`` — the same failure
# path as any other agent error ([0008]) — so one stalled model cannot stall the run.
# (This bounds the *pipeline*; a client-side request timeout that also reaps the
# abandoned worker thread is a service-hardening follow-up — see the security review.)
_AGENT_TIMEOUT_SECONDS = 60.0


class PipelineError(Exception):
    """A run produced no result: both agents failed to classify the case.

    Distinct from a *single* agent failing (that still yields one classification →
    INCONCLUSIVE, routed for human review). Both failing means both models were
    unavailable — an infrastructure failure, not a case to adjudicate — so the run
    cannot proceed. A human initiates every run, so this surfaces to them directly.
    """


def run_pipeline(case: Case, policy: Policy) -> PipelineResult:
    """Run one case end to end: scope gate → agents → verdict → human.

    Out of scope (``proceed=False``) short-circuits before the agents and returns a
    result with ``verdict=None``; the case still routes to a human. If both agents
    fail there is nothing to review, so this raises ``PipelineError`` rather than
    returning a result. A degraded fail-open gate has ``proceed=True``, so the pair
    runs and the ``degraded`` flag is forwarded to the verdict, which caps it.
    """
    scope = run_scope_gate(case, policy)
    if not scope.proceed:
        # Out of scope: skip the expensive pair, still route to the human.
        return PipelineResult(case_id=case.case_id, scope=scope, verdict=None)

    maker, checker = _classify_concurrently(case, policy)
    if maker is None and checker is None:
        # Both models failed — no classification exists to review. Cannot proceed.
        raise PipelineError(
            f"both agents failed to classify case {case.case_id!r} — cannot proceed"
        )

    verdict = run_verdict(
        case_id=case.case_id,
        maker=maker,
        checker=checker,
        degraded=scope.degraded,
        policy=policy,
    )
    return PipelineResult(case_id=case.case_id, scope=scope, verdict=verdict)


def _classify_concurrently(
    case: Case, policy: Policy
) -> tuple[AgentOutput | None, AgentOutput | None]:
    """Run Maker and Checker at the same time — the fan-out.

    Independence is guaranteed upstream ([0008]: neither agent can see the other's
    output), so concurrency changes only timing, never the result. Two blocking
    network calls → two threads → wall-clock is the slower of the two, not the sum.

    The wait is bounded: an agent still running past ``_AGENT_TIMEOUT_SECONDS`` is
    treated as a failure (``None``), so a hung vendor call cannot stall the pipeline.
    ``shutdown(wait=False)`` means we do not block on the abandoned worker — for a
    one-shot CLI it dies with the process; reaping it in a long-lived service is the
    client-side-timeout follow-up.
    """
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        maker_future = pool.submit(run_maker, case, policy)
        checker_future = pool.submit(run_checker, case, policy)
        wait([maker_future, checker_future], timeout=_AGENT_TIMEOUT_SECONDS)
        maker = maker_future.result() if maker_future.done() else None
        checker = checker_future.result() if checker_future.done() else None
        return maker, checker
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
