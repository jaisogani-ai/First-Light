"""Builds a real dependency graph from a run's actual persisted pipeline steps — edges
are derived by checking whether a value in one step's outputs actually reappears in the
next step's inputs, not from a fixed hand-drawn diagram. A "data" edge means the two
steps share an equal value for some field; a "control" edge means the steps ran in
sequence with no shared field (the later step still only ran because the earlier one
completed, e.g. Safety Agent passing gates the Proof Generator running at all)."""


def build_pipeline_graph(steps: list[dict]) -> dict:
    nodes = [
        {
            "id": f"step-{s['step_order']}",
            "label": s["agent_name"],
            "type": "agent",
            "status": s["status"],
            "confidence": s["confidence"],
            "latency_ms": s["latency_ms"],
        }
        for s in steps
    ]

    edges = []
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        shared_fields = [
            k for k, v in a["outputs"].items()
            if k in b["inputs"] and b["inputs"][k] == v
        ]
        edges.append({
            "source": f"step-{a['step_order']}",
            "target": f"step-{b['step_order']}",
            "kind": "data" if shared_fields else "control",
            "shared_fields": shared_fields,
        })

    # The verifier is real (backend/verifier.py) but not itself a pipeline_steps row —
    # this edge documents which fields of the final certificate it actually reads.
    if steps and steps[-1]["status"] == "COMPLETED":
        last = steps[-1]
        nodes.append({
            "id": "verifier", "label": "Independent Verifier", "type": "verifier",
            "status": "PENDING", "confidence": None, "latency_ms": None,
        })
        edges.append({
            "source": f"step-{last['step_order']}", "target": "verifier",
            "kind": "data",
            "shared_fields": ["command_hash", "signature", "multipliers", "constraints", "sequence_no"],
        })

    return {"nodes": nodes, "edges": edges}
