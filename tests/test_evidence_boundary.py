from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_model_card_keeps_synthetic_decision_evidence_boundary() -> None:
    text = _read("reports/model_card.md")

    assert "proof of concept" in text.lower()
    assert "synthetic data" in text.lower()
    assert "not benchmarks for any real clinic" in text.lower()
    assert "real-world deployment **as-is**" in text.lower()


def test_roadmap_keeps_nhs_gpad_claim_scope_narrow() -> None:
    text = _read("ROADMAP.md")

    assert "observed attended appointment activity" in text
    assert "does **not** identify latent demand" in text
    assert "does not validate the synthetic latent-demand or staffing-policy layer" in text


def test_roadmap_keeps_operational_evidence_work_blocked() -> None:
    text = _read("ROADMAP.md")

    assert "## Blocked by operational data" in text
    assert "governed demand-attempt dataset" in text
    assert "defensible patient-facing capacity measure" in text
    assert "real staffing-policy validation design" in text


def test_readiness_boundary_rejects_deployment_equivalence() -> None:
    text = _read("docs/production_readiness.md")

    assert "Production-shaped code is not, by itself, evidence of production readiness." in text
    assert "not a clinically governed production deployment" in text
    assert "A real deployment should not promote this repository directly." in text


def test_readiness_matrix_uses_only_canonical_statuses() -> None:
    text = _read("docs/production_readiness.md")
    canonical = {
        "Implemented in this portfolio",
        "Requires deployment integration",
        "Requires governed clinical evidence",
    }

    statuses = {
        match.strip("*")
        for match in re.findall(
            r"\| \*\*(.*?)\*\* \|",
            text,
        )
    }
    unexpected = statuses - canonical

    assert canonical <= statuses
    assert not unexpected, f"Unexpected readiness status labels: {sorted(unexpected)}"


def test_readiness_boundary_keeps_real_staffing_claims_evidence_gated() -> None:
    text = _read("docs/production_readiness.md").lower()

    required_phrases = (
        "real latent-demand/capacity staffing benefit",
        "Requires governed clinical evidence",
        "Governed operational outcomes and prospective validation",
        "real capacity censoring",
        "realised hybrid-switch precision/recall",
    )
    for phrase in required_phrases:
        assert phrase.lower() in text
