"""Exposes the plugin registry's actual state — honestly empty today. See
backend/plugins/base.py for why nothing is registered and what registering one would mean."""

from fastapi import APIRouter

from backend.plugins.base import registry

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("")
def list_plugins():
    return {
        "registered": registry.list_keys(),
        "note": ("Plugin interface only (backend/plugins/base.py). No safety-property plugins "
                 "are implemented or wired into the live verifier; the verifier still enforces "
                 "exactly the one locked, real property (angular rate)."),
    }
