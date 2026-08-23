"""Tamper-evident hash-chain audit log — real Merkle/blockchain-style chaining over
the commands table. See backend/audit_chain.py for the chaining and verification logic."""

from fastapi import APIRouter
from sqlalchemy import select

from backend.audit_chain import verify_chain
from backend.db import engine
from backend.models import audit_chain, commands

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/chain")
def get_chain(limit: int = 100):
    with engine.connect() as conn:
        rows = conn.execute(
            select(audit_chain, commands.c.command_id)
            .join(commands, audit_chain.c.command_id == commands.c.id)
            .order_by(audit_chain.c.sequence_index.desc()).limit(limit)
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/verify")
def verify():
    with engine.connect() as conn:
        return verify_chain(conn)
