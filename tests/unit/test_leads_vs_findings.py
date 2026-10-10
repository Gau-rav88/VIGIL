from __future__ import annotations

from attribution.community import CommunityDetector
from attribution.confidence import is_finding_link
from attribution.models import AccountPairLink, LinkMethod, MethodScore


def test_confidence_threshold_classification() -> None:
    # Strict PRD Guardrail G-2: conf < 0.60 is INFERRED-LOW lead, excluded from findings
    assert not is_finding_link(0.0)
    assert not is_finding_link(0.35)
    assert not is_finding_link(0.59)
    assert not is_finding_link(0.5999)

    assert is_finding_link(0.60)
    assert is_finding_link(0.75)
    assert is_finding_link(0.99)
    assert is_finding_link(1.0)


def test_leads_never_appear_in_findings_links() -> None:
    cd = CommunityDetector()

    high_conf_link = AccountPairLink(
        source_account="A",
        target_account="B",
        confidence=0.82,
        methods=[LinkMethod.SHARED_DEVICE],
        method_scores=[MethodScore(method=LinkMethod.SHARED_DEVICE, weight=0.90, strength=0.8)],
        is_finding=True,
    )

    lead_link_1 = AccountPairLink(
        source_account="B",
        target_account="C",
        confidence=0.48,
        methods=[LinkMethod.BROKER_PATHWAY],
        method_scores=[MethodScore(method=LinkMethod.BROKER_PATHWAY, weight=0.40, strength=0.6)],
        is_finding=False,
    )

    lead_link_2 = AccountPairLink(
        source_account="A",
        target_account="D",
        confidence=0.55,
        methods=[LinkMethod.LATENCY_SIGNATURE],
        method_scores=[MethodScore(method=LinkMethod.LATENCY_SIGNATURE, weight=0.50, strength=0.7)],
        is_finding=False,
    )

    clusters = cd.resolve_entities(
        links=[high_conf_link, lead_link_1, lead_link_2],
        account_volumes={"A": 100, "B": 100, "C": 50, "D": 50},
        total_symbol_volume=1000,
    )

    assert len(clusters) == 1
    cluster = clusters[0]

    # Findings MUST ONLY contain links with confidence >= 0.60
    assert len(cluster.findings_links) == 1
    assert cluster.findings_links[0].confidence >= 0.60
    assert cluster.findings_links[0].source_account == "A"
    assert cluster.findings_links[0].target_account == "B"

    # Leads MUST contain links with confidence < 0.60
    assert len(cluster.leads_links) == 2
    for lead in cluster.leads_links:
        assert lead.confidence < 0.60
        assert not lead.is_finding
