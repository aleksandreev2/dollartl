from fastapi import APIRouter

from dollartl.admin.catalog_ops_files import router as files_router
from dollartl.admin.catalog_ops_releases import router as releases_router
from dollartl.admin.catalog_ops_titles import router as titles_router
from dollartl.admin.catalog_ops_upload import router as upload_router

router = APIRouter(prefix="/admin/api/catalog", tags=["admin-catalog"])
router.include_router(titles_router)
router.include_router(upload_router)
router.include_router(releases_router)
router.include_router(files_router)
