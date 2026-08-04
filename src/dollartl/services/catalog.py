from sqlalchemy.ext.asyncio import AsyncSession

from dollartl.services.catalog_audience import CatalogAudienceMixin
from dollartl.services.catalog_core import CatalogCoreMixin
from dollartl.services.catalog_files import CatalogFilesMixin
from dollartl.services.catalog_publication import CatalogPublicationMixin
from dollartl.services.catalog_types import (
    DeepLinkTarget,
    ReleaseFileBundle,
    generate_deep_link_token,
    normalize_title,
    slugify,
)


class CatalogService(
    CatalogCoreMixin,
    CatalogFilesMixin,
    CatalogAudienceMixin,
    CatalogPublicationMixin,
):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


__all__ = [
    "CatalogService",
    "DeepLinkTarget",
    "ReleaseFileBundle",
    "generate_deep_link_token",
    "normalize_title",
    "slugify",
]
