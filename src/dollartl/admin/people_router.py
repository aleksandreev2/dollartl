from fastapi import APIRouter

from dollartl.admin.broadcast_batch import router as broadcast_router
from dollartl.admin.people_batch import router as batch_router
from dollartl.admin.people_dossier import router as dossier_router
from dollartl.admin.people_moderation import router as moderation_router
from dollartl.admin.people_selection import router as selection_router
from dollartl.admin.people_users import router as users_router

router = APIRouter(prefix="/admin/api", tags=["admin-people"])
router.include_router(users_router)
router.include_router(dossier_router)
router.include_router(selection_router)
router.include_router(batch_router)
router.include_router(moderation_router)
router.include_router(broadcast_router)
