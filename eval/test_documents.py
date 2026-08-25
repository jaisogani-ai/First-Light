"""Mission Files — upload/storage/real extraction (PDF via PyMuPDF, notebook, plain text),
version history, checksums, keyword search, and the Mission Intake Agent's real findings
(duplicates/corrupt/unsupported/missing fields) plus the agent_runs audit trail."""

import json

import fitz
import pytest


def _make_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture
def mission(client):
    return client.post("/api/missions", json={
        "mission_name": "Document Pipeline Target", "mission_profile_key": "earth_observation",
    }).json()


def test_pdf_upload_extracts_real_text(client, mission):
    pdf_bytes = _make_pdf_bytes("The angular rate safety bound is derived via Farkas certificates.")
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "RESEARCH_PAPER"},
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_status"] == "OK"
    assert body["extraction_metadata"]["page_count"] == 1

    doc = client.get(f"/api/missions/{mission['id']}/documents/{body['document_id']}").json()
    assert "Farkas certificates" in doc["extracted_text"]
    assert doc["checksum"].startswith("sha256:")
    assert doc["version_no"] == 1


def test_corrupt_pdf_is_honestly_flagged_not_silently_accepted(client, mission):
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "RESEARCH_PAPER"},
        files={"file": ("broken.pdf", b"this is not a real pdf file", "application/pdf")},
    )
    body = resp.json()
    assert body["extraction_status"] == "CORRUPT"

    doc = client.get(f"/api/missions/{mission['id']}/documents/{body['document_id']}").json()
    assert doc["extracted_text"] is None


def test_unsupported_extension_is_honestly_flagged(client, mission):
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "OTHER"},
        files={"file": ("data.xyz", b"whatever", "application/octet-stream")},
    )
    assert resp.json()["extraction_status"] == "UNSUPPORTED"


def test_image_marked_not_applicable_no_fake_ocr(client, mission):
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "IMAGE"},
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"fakepixels", "image/png")},
    )
    body = resp.json()
    assert body["extraction_status"] == "NOT_APPLICABLE"
    assert body["extraction_metadata"]["reason"]


def test_notebook_extraction_reads_real_cell_source(client, mission):
    notebook = json.dumps({
        "cells": [
            {"cell_type": "markdown", "source": ["# Orbit propagation notebook"]},
            {"cell_type": "code", "source": ["def propagate(tle):\n", "    return sgp4(tle)\n"]},
        ],
        "metadata": {"kernelspec": {"name": "python3"}},
    })
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "NOTEBOOK"},
        files={"file": ("orbit.ipynb", notebook, "application/json")},
    )
    body = resp.json()
    assert body["extraction_status"] == "OK"
    assert body["extraction_metadata"]["cell_count"] == 2

    doc = client.get(f"/api/missions/{mission['id']}/documents/{body['document_id']}").json()
    assert "def propagate(tle)" in doc["extracted_text"]


def test_matlab_script_extracted_as_plain_text(client, mission):
    script = "function y = safety_margin(omega)\n  y = 0.05 - omega;\nend\n"
    resp = client.post(
        f"/api/missions/{mission['id']}/documents",
        params={"doc_type": "MATLAB_SCRIPT"},
        files={"file": ("safety_margin.m", script, "text/plain")},
    )
    body = resp.json()
    assert body["extraction_status"] == "OK"
    doc = client.get(f"/api/missions/{mission['id']}/documents/{body['document_id']}").json()
    assert doc["extracted_text"] == script


def test_reupload_same_filename_increments_version_and_keeps_history(client, mission):
    r1 = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "ENGINEERING_NOTES"},
                      files={"file": ("notes.txt", "v1 notes", "text/plain")})
    r2 = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "ENGINEERING_NOTES"},
                      files={"file": ("notes.txt", "v2 notes, revised", "text/plain")})
    assert r1.json()["version_no"] == 1
    assert r2.json()["version_no"] == 2

    listing = client.get(f"/api/missions/{mission['id']}/documents").json()
    versions = sorted(d["version_no"] for d in listing if d["filename"] == "notes.txt")
    assert versions == [1, 2]  # both preserved, original never overwritten


def test_invalid_doc_type_rejected(client, mission):
    resp = client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "NOT_A_TYPE"},
                        files={"file": ("x.txt", "hi", "text/plain")})
    assert resp.status_code == 400


def test_upload_against_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/documents", params={"doc_type": "OTHER"},
                        files={"file": ("x.txt", "hi", "text/plain")})
    assert resp.status_code == 404


def test_keyword_search_finds_and_cites_real_document(client, mission):
    client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "ENGINEERING_NOTES"},
                files={"file": ("notes.txt", "The reaction wheel saturation limit is 0.02 Nms.", "text/plain")})
    client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "ENGINEERING_NOTES"},
                files={"file": ("unrelated.txt", "Completely unrelated content about lunch.", "text/plain")})

    resp = client.get(f"/api/missions/{mission['id']}/documents/search", params={"q": "reaction wheel saturation"})
    body = resp.json()
    assert body["search_type"] == "keyword"
    assert len(body["results"]) == 1
    assert body["results"][0]["filename"] == "notes.txt"
    assert "reaction wheel" in body["results"][0]["snippet"].lower()


def test_keyword_search_no_match_returns_empty_not_fabricated(client, mission):
    client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "ENGINEERING_NOTES"},
                files={"file": ("notes.txt", "Thermal margin analysis.", "text/plain")})
    resp = client.get(f"/api/missions/{mission['id']}/documents/search", params={"q": "quantum teleportation"})
    assert resp.json()["results"] == []


def test_mission_intake_agent_detects_duplicate_uploads(client, mission):
    client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "OTHER"},
                files={"file": ("a.txt", "identical content", "text/plain")})
    client.post(f"/api/missions/{mission['id']}/documents", params={"doc_type": "OTHER"},
                files={"file": ("b.txt", "identical content", "text/plain")})

    result = client.post(f"/api/missions/{mission['id']}/intake/run").json()
    assert result["status"] == "OK"
    assert len(result["duplicate_uploads"]) == 1
    assert set(result["duplicate_uploads"][0]["filenames"]) == {"a.txt", "b.txt"}


def test_mission_intake_agent_reports_missing_fields(client, mission):
    result = client.post(f"/api/missions/{mission['id']}/intake/run").json()
    assert "No TLE imported" in " ".join(result["missing_fields"])
    assert "No spacecraft profile" in " ".join(result["missing_fields"])
    assert result["clean"] is False


def test_mission_intake_agent_clean_when_nothing_wrong(client, mission):
    client.post(f"/api/missions/{mission['id']}/imports/tle", json={
        "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9009",
        "line2": "2 25544  51.6416 339.9700 0007133  92.8340 267.3805 15.49560792 27004",
    })
    client.post(f"/api/missions/{mission['id']}/imports/spacecraft-profile", json={
        "name": "Sat-1", "inertia_ixx": 0.02, "inertia_iyy": 0.02, "inertia_izz": 0.01,
    })
    csv_text = ("omega_x,omega_y,omega_z,reaction_wheel_momentum,battery_soc_pct,"
                "temperature_c,power_draw_w,comm_delay_ms,sensor_latency_ms\n"
                "0.001,0.001,0.001,0.02,90.0,20.0,24.5,250.0,8.0\n")
    client.post(f"/api/missions/{mission['id']}/imports/csv-telemetry", files={"file": ("t.csv", csv_text, "text/csv")})

    result = client.post(f"/api/missions/{mission['id']}/intake/run").json()
    assert result["clean"] is True
    assert result["missing_fields"] == []


def test_agent_runs_are_persisted_with_real_latency(client, mission):
    client.post(f"/api/missions/{mission['id']}/intake/run")
    runs = client.get(f"/api/missions/{mission['id']}/agent-runs").json()
    assert len(runs) >= 1
    assert runs[0]["agent_name"] == "mission_intake"
    assert runs[0]["status"] == "OK"
    assert runs[0]["latency_ms"] >= 0
    assert "document_count" in runs[0]["output"]
    assert runs[0]["output"]["agent_version"] == "1.0.0"


def test_agent_runs_missing_mission_404s(client):
    resp = client.get("/api/missions/999999/agent-runs")
    assert resp.status_code == 404
