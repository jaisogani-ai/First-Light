"""Proves the sequence-freshness check is race-free under real concurrency, not just
correct in the single-threaded case. Fires many threads at the same valid certificate
simultaneously — a read-then-write TOCTOU race would let more than one through."""

import copy
from concurrent.futures import ThreadPoolExecutor

N_CONCURRENT = 25


def test_concurrent_replay_of_the_same_certificate_accepts_exactly_once(client, valid_command):
    body = {
        "command_row_id": valid_command["command_row_id"],
        "proof": valid_command["proof"],
        "submitted_command_id": valid_command["command_id"],
        "submitted_u_cmd": valid_command["u_cmd"],
        "mission_profile_key": "earth_observation",
    }

    def fire(_):
        return client.post("/api/commands/verify", json=copy.deepcopy(body)).json()

    with ThreadPoolExecutor(max_workers=N_CONCURRENT) as pool:
        results = list(pool.map(fire, range(N_CONCURRENT)))

    verdicts = [r["verdict"] for r in results]
    assert verdicts.count("VERIFIED") == 1, (
        f"expected exactly 1 acceptance out of {N_CONCURRENT} concurrent identical requests, "
        f"got {verdicts.count('VERIFIED')} — the sequence check has a race condition"
    )
    assert verdicts.count("REJECTED") == N_CONCURRENT - 1
