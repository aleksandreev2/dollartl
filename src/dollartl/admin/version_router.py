from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from dollartl import __version__
from dollartl.admin.auth import AdminPrincipal, require_admin

Admin = Annotated[AdminPrincipal, Depends(require_admin)]
router = APIRouter(prefix="/admin/api", tags=["admin-version"])


@router.get("/session")
async def current_session(admin: Admin) -> dict[str, Any]:
    return {
        "telegram_id": admin.telegram_id,
        "username": admin.username,
        "first_name": admin.first_name,
        "version": __version__,
    }
