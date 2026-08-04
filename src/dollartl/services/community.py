from dollartl.services.community_base import CommunityServiceBase
from dollartl.services.community_comments import CommunityCommentsMixin
from dollartl.services.community_ratings import CommunityRatingsMixin
from dollartl.services.community_reports import CommunityReportsMixin


class CommunityService(
    CommunityCommentsMixin,
    CommunityRatingsMixin,
    CommunityReportsMixin,
    CommunityServiceBase,
):
    pass


__all__ = ["CommunityService"]
