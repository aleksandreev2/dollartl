from dollartl.services.boosty_admin import BoostyAdminMixin
from dollartl.services.boosty_base import BoostyServiceBase, BoostyStatus
from dollartl.services.boosty_sync import BoostySyncMixin
from dollartl.services.boosty_verification import BoostyVerificationMixin


class BoostyService(
    BoostyVerificationMixin,
    BoostySyncMixin,
    BoostyAdminMixin,
    BoostyServiceBase,
):
    pass


__all__ = ["BoostyService", "BoostyStatus"]
