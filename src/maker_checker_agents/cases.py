"""The fictional demo case set — the ``list`` map and the ``run`` inputs (issue #6).

These are *illustrative fictions*, not real filings. Each ``DemoCase`` pairs a
``Case`` (the pipeline input) with two demo-only fields:

* ``expected_tier`` — an illustrative label for orientation. It is ``None`` for a
  case the scope gate genuinely skips (out of scope carries no tier). It is never
  a promise about what the live agents will say — that is the whole point of the
  proof.
* ``designed_to_diverge`` — marks a case that sits on a real EU AI Act fault line,
  where the two independent agents can legitimately disagree. Divergence is not a
  bug to suppress; it is the signal that routes a case to a human.

The set is authored to span the taxonomy and to be *bound to the real gate*: the
tests run the actual ``run_scope_gate`` over these cases, so an out-of-scope case
here is one the shipped gate skips — not a case merely labelled that way.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models import Case


class DemoCase(BaseModel):
    """One fictional case plus its illustrative, demo-only metadata."""

    model_config = ConfigDict(frozen=True)

    case: Case
    expected_tier: str | None
    designed_to_diverge: bool = False


# Three finance cases and three pharma cases — an even split for a regulated-
# enterprise audience. Together they span high / unacceptable / limited, include
# one genuinely out-of-scope case (the gate skips it) and one divergence case.
DEMO_CASES: list[DemoCase] = [
    # ---- Finance ---------------------------------------------------------- #
    DemoCase(
        case=Case(
            case_id="credit-scoring",
            system_name="CreditGauge",
            purpose=(
                "Automated credit scoring that assesses applicant creditworthiness "
                "to approve or decline personal loans."
            ),
            domain="finance",
            data_subjects=["loan applicants"],
            data_types=["financial history", "income records"],
            description=(
                "A credit scoring model used by a retail bank to rank consumer loan "
                "applications."
            ),
        ),
        expected_tier="high",
    ),
    DemoCase(
        case=Case(
            case_id="customer-social-scoring",
            system_name="TrustLens",
            purpose=(
                "A social scoring system that rates retail-banking customers' general "
                "trustworthiness from social-media activity and their wider social graph."
            ),
            domain="finance",
            data_subjects=["bank customers"],
            data_types=["social media activity", "behavioural history"],
            description=(
                "Uses a general social scoring signal to grant or deny access to services "
                "unrelated to the data's original purpose."
            ),
        ),
        expected_tier="unacceptable",
    ),
    DemoCase(
        case=Case(
            case_id="bank-meeting-summariser",
            system_name="MinuteMaker",
            purpose=(
                "Summarises internal staff meeting notes into action points for a retail "
                "bank's operations team."
            ),
            domain="corporate-operations",
            data_subjects=["employees"],
            data_types=["meeting notes"],
            description=(
                "An internal productivity tool. Processes no customer data and makes no "
                "automated decision about any person."
            ),
        ),
        expected_tier=None,  # the real gate matches no framework — genuinely out of scope
    ),
    # ---- Pharma ----------------------------------------------------------- #
    DemoCase(
        case=Case(
            case_id="patient-triage",
            system_name="TriageAssist",
            purpose=(
                "Triages incoming patient symptoms to prioritise care and support a "
                "clinician's diagnosis in a hospital."
            ),
            domain="healthcare",
            data_subjects=["patients"],
            data_types=["symptoms", "health records"],
            description="A clinical decision-support tool used in an emergency department.",
        ),
        expected_tier="high",
    ),
    DemoCase(
        case=Case(
            case_id="clinical-trial-chatbot",
            system_name="TrialMate",
            purpose=(
                "A patient-facing chatbot that answers questions about an ongoing clinical "
                "trial and discloses that it is an AI assistant, not a clinician."
            ),
            domain="healthcare",
            data_subjects=["trial participants"],
            data_types=["participant questions"],
            description="Provides transparency information; does not diagnose or decide.",
        ),
        expected_tier="limited",
    ),
    DemoCase(
        case=Case(
            case_id="staff-wellbeing-emotion",
            system_name="MoodMonitor",
            purpose=(
                "Runs emotion recognition on laboratory and hospital staff during their "
                "shifts to monitor stress and wellbeing."
            ),
            domain="healthcare",
            data_subjects=["staff"],
            data_types=["voice recordings", "stress inferences"],
            description="Continuous workplace emotion recognition of employees.",
        ),
        # The taxonomy files emotion recognition as 'limited' (transparency), but
        # workplace emotion recognition is prohibited under Art 5 — the two agents
        # can legitimately split. Illustrative ground truth: unacceptable.
        expected_tier="unacceptable",
        designed_to_diverge=True,
    ),
]


def get_demo_case(case_id: str) -> DemoCase | None:
    """Return the demo case with ``case_id``, or ``None`` if there is no such case."""
    for demo in DEMO_CASES:
        if demo.case.case_id == case_id:
            return demo
    return None
