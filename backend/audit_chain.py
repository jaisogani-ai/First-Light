"""Tamper-evident audit chain — a real Merkle/blockchain-style hash chain over the
commands table. Each link's hash is a function of the previous link's hash plus the
command's own hash, signature, and sequence number, so corrupting any past command_hash
or signature changes every chain_hash computed after it. Verification recomputes the
whole chain from stored fields and compares — it does not trust any stored chain_hash
without independently reproducing it.
"""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import func, select

from backend.models import audit_chain, commands, proof_certificates

GENESIS_HASH = "0" * 64


def compute_link_hash(previous_chain_hash: str, command_hash: str, signature: str, sequence_no: int) -> str:
    payload = f"{previous_chain_hash}|{command_hash}|{signature}|{sequence_no}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def append_to_chain(conn, command_row_id: int, command_hash: str, signature: str, sequence_no: int) -> str:
    """Appends a new link for a just-persisted command. Must run in the same transaction
    as the command insert so concurrent appends can't race on `previous_chain_hash`."""
    last = conn.execute(
        select(audit_chain.c.chain_hash, audit_chain.c.sequence_index)
        .order_by(audit_chain.c.sequence_index.desc()).limit(1)
    ).fetchone()
    previous_chain_hash = last.chain_hash if last else GENESIS_HASH
    sequence_index = (last.sequence_index if last else 0) + 1

    chain_hash = compute_link_hash(previous_chain_hash, command_hash, signature, sequence_no)
    conn.execute(audit_chain.insert().values(
        command_id=command_row_id,
        sequence_index=sequence_index,
        previous_chain_hash=previous_chain_hash,
        chain_hash=chain_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    return chain_hash


def verify_chain(conn) -> dict:
    """Walks the whole chain in order, independently recomputing each chain_hash from
    the command's actual current command_hash/sequence_no and its certificate's actual
    current signature — not from the stored chain_hash. The first index where the
    recomputed hash disagrees with what's stored (or with the previous link) is where
    tampering happened."""
    rows = conn.execute(
        select(
            audit_chain.c.sequence_index, audit_chain.c.previous_chain_hash, audit_chain.c.chain_hash,
            commands.c.command_hash, commands.c.sequence_no, proof_certificates.c.signature,
        )
        .join(commands, audit_chain.c.command_id == commands.c.id)
        .join(proof_certificates, proof_certificates.c.command_id == commands.c.id)
        .order_by(audit_chain.c.sequence_index)
    ).fetchall()

    expected_previous = GENESIS_HASH
    for row in rows:
        if row.previous_chain_hash != expected_previous:
            return {"valid": False, "total_links": len(rows), "broken_at_index": row.sequence_index,
                    "reason": "stored previous_chain_hash does not match the prior link's actual chain_hash"}
        recomputed = compute_link_hash(expected_previous, row.command_hash, row.signature, row.sequence_no)
        if recomputed != row.chain_hash:
            return {"valid": False, "total_links": len(rows), "broken_at_index": row.sequence_index,
                    "reason": "recomputed hash does not match stored chain_hash — "
                              "command_hash, signature, or sequence_no was altered after chaining"}
        expected_previous = row.chain_hash

    return {"valid": True, "total_links": len(rows), "broken_at_index": None, "reason": None}
