"""Paper Review, Algorithm Review, and Scientific Comparison agents — all grounded on real
uploaded document text. ANTHROPIC_API_KEY is cleared for the whole suite (eval/conftest.py),
so these exercise the real 'evidence exists, Claude unavailable' deterministic_fallback
path — never a mock — plus the real refusal path when there's no usable text at all."""

import pytest


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Scientific Review Target", "mission_profile_key": "earth_observation",
    }).json()


def _upload_text(client, mission_id, filename, text, doc_type="RESEARCH_PAPER"):
    return client.post(f"/api/missions/{mission_id}/documents", params={"doc_type": doc_type},
                        files={"file": (filename, text, "text/plain")}).json()


def test_paper_review_grounds_on_real_document_and_falls_back_honestly(client, mission):
    doc = _upload_text(client, mission["id"], "paper.txt",
                        "This paper studies angular rate safety verification for spacecraft using Farkas certificates.")
    resp = client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/paper")
    body = resp.json()
    assert body["status"] == "OK"
    assert body["reviewed"] is False  # Claude unavailable in test suite
    assert body["generated_by"] == "deterministic_fallback"
    assert body["document_id"] == doc["document_id"]
    assert body["filename"] == "paper.txt"


def test_paper_review_refuses_when_document_has_no_extracted_text(client, mission):
    doc = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "IMAGE"},
                       files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfakepixels", "image/png")}).json()
    resp = client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/paper")
    body = resp.json()
    assert body["reviewed"] is False
    assert body["generated_by"] == "deterministic_refusal"
    assert "cannot find" in body["reason"].lower()


def test_paper_review_missing_document_reports_not_found(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/documents/999999/review/paper")
    body = resp.json()
    assert body["reviewed"] is False
    assert "not found" in body["reason"].lower()


def test_paper_review_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/documents/1/review/paper")
    assert resp.status_code == 404


def test_algorithm_review_grounds_on_real_document(client, mission):
    doc = _upload_text(client, mission["id"], "algo.py",
                        "def desaturate(rw_momentum):\n    return rw_momentum * 0.95\n",
                        doc_type="ALGORITHM_DESCRIPTION")
    resp = client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/algorithm")
    body = resp.json()
    assert body["status"] == "OK"
    assert body["generated_by"] == "deterministic_fallback"
    assert body["filename"] == "algo.py"


def test_algorithm_review_refuses_without_evidence(client, mission):
    doc = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "OTHER"},
                       files={"file": ("mystery.xyz", b"binary junk", "application/octet-stream")}).json()
    resp = client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/algorithm")
    body = resp.json()
    assert body["generated_by"] == "deterministic_refusal"


def test_comparison_requires_both_documents_real(client, mission):
    doc_a = _upload_text(client, mission["id"], "paper_a.txt", "Paper A discusses Farkas certificates.")
    resp = client.post(f"/api/missions/{mission['id']}/documents/compare",
                        json={"document_id_a": doc_a["document_id"], "document_id_b": 999999})
    body = resp.json()
    assert body["compared"] is False
    assert "999999" in body["reason"]


def test_comparison_grounds_on_both_real_documents(client, mission):
    doc_a = _upload_text(client, mission["id"], "paper_a.txt", "Paper A proposes Farkas-certificate-based verification.")
    doc_b = _upload_text(client, mission["id"], "paper_b.txt", "Paper B proposes a Lyapunov-based stability approach.")
    resp = client.post(f"/api/missions/{mission['id']}/documents/compare",
                        json={"document_id_a": doc_a["document_id"], "document_id_b": doc_b["document_id"]})
    body = resp.json()
    assert body["status"] == "OK"
    assert body["generated_by"] == "deterministic_fallback"
    assert body["document_a"]["filename"] == "paper_a.txt"
    assert body["document_b"]["filename"] == "paper_b.txt"


def test_comparison_refuses_when_either_document_lacks_text(client, mission):
    doc_a = _upload_text(client, mission["id"], "paper_a.txt", "Real text here.")
    doc_b = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "IMAGE"},
                         files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfakepixels", "image/png")}).json()
    resp = client.post(f"/api/missions/{mission['id']}/documents/compare",
                        json={"document_id_a": doc_a["document_id"], "document_id_b": doc_b["document_id"]})
    body = resp.json()
    assert body["compared"] is False
    assert body["generated_by"] == "deterministic_refusal"


def test_comparison_missing_body_fields_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/documents/compare", json={"document_id_a": 1})
    assert resp.status_code == 400


def test_all_three_agents_persist_to_audit_trail_with_real_latency(client, mission):
    doc = _upload_text(client, mission["id"], "paper.txt", "Farkas certificates for angular rate safety.")
    client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/paper")
    client.post(f"/api/missions/{mission['id']}/documents/{doc['document_id']}/review/algorithm")

    doc_b = _upload_text(client, mission["id"], "paper2.txt", "Lyapunov stability methods.")
    client.post(f"/api/missions/{mission['id']}/documents/compare",
                json={"document_id_a": doc["document_id"], "document_id_b": doc_b["document_id"]})

    runs = client.get(f"/api/missions/{mission['id']}/agent-runs").json()
    agent_names = {r["agent_name"] for r in runs}
    assert {"paper_review_agent", "algorithm_review_agent", "scientific_comparison_agent"} <= agent_names
    for r in runs:
        if r["agent_name"] in ("paper_review_agent", "algorithm_review_agent", "scientific_comparison_agent"):
            assert r["status"] == "OK"
            assert r["latency_ms"] >= 0
            assert r["mission_id"] == mission["id"]
