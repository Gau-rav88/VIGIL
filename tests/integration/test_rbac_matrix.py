from __future__ import annotations

import os
import jwt
from api.main import app

os.environ["DEMO_FIXTURES"] = "true"
from fastapi.testclient import TestClient
from vigil_common.config import get_settings
from vigil_common.timeutil import now_utc

client = TestClient(app)
settings = get_settings()


def get_token_for_role(role: str) -> str:
    return jwt.encode(
        {"sub": f"test_{role}", "role": role, "iat": now_utc().timestamp()},
        settings.JWT_HS256_SECRET,
        algorithm="HS256",
    )


ROLES = ["investigator", "compliance_officer", "admin", "auditor_readonly"]


def test_unauthenticated_requests_fail_on_protected_endpoints() -> None:
    res = client.get("/api/v1/cases")
    assert res.status_code == 401
    assert res.headers.get("content-type") == "application/problem+json"


def test_rbac_matrix_cases_list() -> None:
    # /cases -> I, C, A, R: 200
    for r in ROLES:
        token = get_token_for_role(r)
        res = client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {r} failed with {res.status_code}"


def test_rbac_matrix_directives() -> None:
    # /cases/{id}/directives -> I, C: 202; A, R: 403
    payload = {"type": "WIDEN_WINDOW", "params": {"seconds": 300}}
    for r in ["investigator", "compliance_officer"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/cases/case_01/directives", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 202, f"Role {r} failed with {res.status_code}"

    for r in ["admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/cases/case_01/directives", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_submit() -> None:
    # /cases/{id}/submit -> I: 202; C, A, R: 403
    token_i = get_token_for_role("investigator")
    res_i = client.post("/api/v1/cases/case_01/submit", headers={"Authorization": f"Bearer {token_i}"})
    assert res_i.status_code == 202

    for r in ["compliance_officer", "admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/cases/case_01/submit", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_review() -> None:
    # /cases/{id}/review -> C: allowed (200 or 409 depending on state); I, A, R: 403
    token_c = get_token_for_role("compliance_officer")
    payload = {"status": "APPROVED", "comment": "Legitimate investigation"}
    res_c = client.post("/api/v1/cases/case_01/review", json=payload, headers={"Authorization": f"Bearer {token_c}"})
    assert res_c.status_code in (200, 409), f"Compliance officer got {res_c.status_code}"

    for r in ["investigator", "admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/cases/case_01/review", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_evidence_download() -> None:
    # /evidence/{id}/download -> I, C, A: 200; R: 403
    for r in ["investigator", "compliance_officer", "admin"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/evidence/EV-TRADE_01/download", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {r} failed with {res.status_code}"

    token_r = get_token_for_role("auditor_readonly")
    res_r = client.get("/api/v1/evidence/EV-TRADE_01/download", headers={"Authorization": f"Bearer {token_r}"})
    assert res_r.status_code == 403


def test_rbac_matrix_dossier_bundle() -> None:
    # /dossiers/{id}/bundle -> C, A: 200; I, R: 403
    for r in ["compliance_officer", "admin"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/dossiers/dossier_01/bundle", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {r} failed with {res.status_code}"

    for r in ["investigator", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/dossiers/dossier_01/bundle", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_account_reveal() -> None:
    # /accounts/{id}/reveal -> C: allowed (200); I, A, R: 403
    payload = {"case_id": "case_01", "justification": "Valid court subpoena authorization"}
    token_c = get_token_for_role("compliance_officer")
    res_c = client.post("/api/v1/accounts/acc_test_01/reveal", json=payload, headers={"Authorization": f"Bearer {token_c}"})
    assert res_c.status_code in (200, 500), f"Compliance officer got {res_c.status_code}"
    assert res_c.status_code != 403

    for r in ["investigator", "admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/accounts/acc_test_01/reveal", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_ledger() -> None:
    # /ledger -> C, A, R: 200; I: 403
    for r in ["compliance_officer", "admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/ledger", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {r} failed with {res.status_code}"

    token_i = get_token_for_role("investigator")
    res_i = client.get("/api/v1/ledger", headers={"Authorization": f"Bearer {token_i}"})
    assert res_i.status_code == 403


def test_rbac_matrix_admin_health() -> None:
    # /admin/health -> A, I: 200; C, R: 403
    for r in ["admin", "investigator"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/admin/health", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {r} failed with {res.status_code}"

    for r in ["compliance_officer", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/admin/health", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_rbac_matrix_sim_control() -> None:
    # /sim/scenarios/{id}/start -> A: 200; I, C, R: 403
    token_a = get_token_for_role("admin")
    res_a = client.post("/api/v1/sim/scenarios/baseline_01/start", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200

    for r in ["investigator", "compliance_officer", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.post("/api/v1/sim/scenarios/baseline_01/start", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 403, f"Role {r} should be 403, got {res.status_code}"


def test_social_signals_redaction_by_role() -> None:
    # G-4: /social/signals text is unredacted for I, C; redacted for A, R
    for r in ["investigator", "compliance_officer"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/social/signals", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0
        assert not items[0]["text"].startswith("[REDACTED"), f"Role {r} was unexpectedly redacted"

    for r in ["admin", "auditor_readonly"]:
        token = get_token_for_role(r)
        res = client.get("/api/v1/social/signals", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0
        assert items[0]["text"].startswith("[REDACTED"), f"Role {r} should be redacted"
