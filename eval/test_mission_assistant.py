"""Mission Assistant — read-only explainer. conftest.py clears ANTHROPIC_API_KEY for the
whole suite (tests must stay offline/deterministic), so these tests exercise the
deterministic_fallback path honestly — not a mocked LLM response."""


def test_explain_uses_deterministic_fallback_without_api_key(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Assistant Target", "mission_profile_key": "earth_observation",
    }).json()

    resp = client.post(f"/api/missions/{mission['id']}/assistant/explain", json={
        "question": "What is the mission status?",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["generated_by"] == "deterministic_fallback"
    assert mission["mission_name"] in body["answer"]


def test_explain_references_real_command_counts(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Assistant Counts", "mission_profile_key": "earth_observation",
    }).json()
    client.post("/api/commands/propose", json={
        "maneuver_type": "SAFE_RCS_PULSE", "mission_profile_key": "earth_observation",
        "mission_id": mission["id"],
    })

    body = client.post(f"/api/missions/{mission['id']}/assistant/explain").json()
    assert "1 command" in body["answer"]


def test_explain_persists_as_mission_report(client):
    mission = client.post("/api/missions", json={
        "mission_name": "Assistant Report", "mission_profile_key": "earth_observation",
    }).json()
    explained = client.post(f"/api/missions/{mission['id']}/assistant/explain").json()

    reports = client.get(f"/api/missions/{mission['id']}/reports").json()
    assistant_reports = [r for r in reports if r["report_type"] == "assistant_explanation"]
    assert len(assistant_reports) == 1
    assert assistant_reports[0]["id"] == explained["report_id"]
    assert assistant_reports[0]["generated_by"] == "deterministic_fallback"


def test_explain_missing_mission_404s(client):
    resp = client.post("/api/missions/999999/assistant/explain")
    assert resp.status_code == 404
