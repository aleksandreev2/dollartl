from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from dollartl.admin.people_common import Admin, iso
from dollartl.config import get_settings
from dollartl.db.boosty_models import BoostyAccessEvent, BoostyAccessPeriod, BoostyLink
from dollartl.db.community_models import Comment, Report, TranslationRating
from dollartl.db.models import (
    AuditLog,
    Ban,
    BanHistory,
    DownloadEvent,
    NotificationPreference,
    Release,
    Title,
    User,
    UserConsent,
    UserSettings,
    UserTitleFollow,
)
from dollartl.db.session import SessionFactory
from dollartl.db.suggestion_models import TitleSuggestion
from dollartl.services.access import ADULT_CONSENT_TYPE

router = APIRouter()


@router.get("/users/{user_id}/dossier")
async def user_dossier(user_id: UUID, admin: Admin) -> dict[str, Any]:
    del admin
    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with SessionFactory() as session:
        row = (
            await session.execute(
                select(User, UserSettings, NotificationPreference, BoostyLink)
                .outerjoin(UserSettings, UserSettings.user_id == User.id)
                .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id)
                .outerjoin(BoostyLink, BoostyLink.user_id == User.id)
                .where(User.id == user_id)
            )
        ).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user, preferences, notification, link = row

        consent = (
            await session.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user.id,
                    UserConsent.consent_type == ADULT_CONSENT_TYPE,
                    UserConsent.version == settings.adult_consent_version,
                )
            )
        ).scalar_one_or_none()
        bans = list(
            (
                await session.execute(
                    select(Ban)
                    .where(Ban.user_id == user.id)
                    .order_by(Ban.created_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
        ban_ids = [item.id for item in bans]
        ban_history = list(
            (
                await session.execute(
                    select(BanHistory)
                    .where(BanHistory.ban_id.in_(ban_ids) if ban_ids else False)
                    .order_by(BanHistory.created_at.desc())
                    .limit(60)
                )
            ).scalars()
        )
        periods = list(
            (
                await session.execute(
                    select(BoostyAccessPeriod)
                    .where(BoostyAccessPeriod.user_id == user.id)
                    .order_by(BoostyAccessPeriod.starts_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
        access_events = list(
            (
                await session.execute(
                    select(BoostyAccessEvent)
                    .where(BoostyAccessEvent.user_id == user.id)
                    .order_by(BoostyAccessEvent.created_at.desc())
                    .limit(40)
                )
            ).scalars()
        )
        comments = list(
            (
                await session.execute(
                    select(Comment)
                    .where(Comment.user_id == user.id)
                    .order_by(Comment.created_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
        ratings = (
            await session.execute(
                select(TranslationRating, Release, Title)
                .join(Release, Release.id == TranslationRating.release_id)
                .join(Title, Title.id == Release.title_id)
                .where(TranslationRating.user_id == user.id)
                .order_by(TranslationRating.created_at.desc())
                .limit(30)
            )
        ).all()
        reports = list(
            (
                await session.execute(
                    select(Report)
                    .where(Report.user_id == user.id)
                    .order_by(Report.created_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
        suggestions = list(
            (
                await session.execute(
                    select(TitleSuggestion)
                    .where(
                        TitleSuggestion.user_id == user.id,
                        TitleSuggestion.status != "draft",
                    )
                    .order_by(TitleSuggestion.created_at.desc())
                    .limit(30)
                )
            ).scalars()
        )
        downloads = (
            await session.execute(
                select(DownloadEvent, Release, Title)
                .join(Release, Release.id == DownloadEvent.release_id)
                .join(Title, Title.id == Release.title_id)
                .where(DownloadEvent.user_id == user.id)
                .order_by(DownloadEvent.created_at.desc())
                .limit(40)
            )
        ).all()
        follows = (
            await session.execute(
                select(UserTitleFollow, Title)
                .join(Title, Title.id == UserTitleFollow.title_id)
                .where(UserTitleFollow.user_id == user.id)
                .order_by(UserTitleFollow.created_at.desc())
                .limit(100)
            )
        ).all()
        audits = list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_type == "user",
                        AuditLog.entity_id == str(user.id),
                    )
                    .order_by(AuditLog.created_at.desc())
                    .limit(50)
                )
            ).scalars()
        )
        counts = {
            "comments": int(
                (
                    await session.execute(
                        select(func.count(Comment.id)).where(Comment.user_id == user.id)
                    )
                ).scalar_one()
            ),
            "ratings": int(
                (
                    await session.execute(
                        select(func.count(TranslationRating.id)).where(
                            TranslationRating.user_id == user.id
                        )
                    )
                ).scalar_one()
            ),
            "reports": int(
                (
                    await session.execute(
                        select(func.count(Report.id)).where(Report.user_id == user.id)
                    )
                ).scalar_one()
            ),
            "suggestions": int(
                (
                    await session.execute(
                        select(func.count(TitleSuggestion.id)).where(
                            TitleSuggestion.user_id == user.id,
                            TitleSuggestion.status != "draft",
                        )
                    )
                ).scalar_one()
            ),
            "downloads": int(
                (
                    await session.execute(
                        select(func.count(DownloadEvent.id)).where(
                            DownloadEvent.user_id == user.id
                        )
                    )
                ).scalar_one()
            ),
            "follows": int(
                (
                    await session.execute(
                        select(func.count(UserTitleFollow.id)).where(
                            UserTitleFollow.user_id == user.id
                        )
                    )
                ).scalar_one()
            ),
            "bans": int(
                (
                    await session.execute(
                        select(func.count(Ban.id)).where(Ban.user_id == user.id)
                    )
                ).scalar_one()
            ),
        }

    active_ban = next(
        (
            item
            for item in bans
            if item.is_active
            and (
                item.ban_type == "permanent"
                or item.expires_at is None
                or item.expires_at > now
            )
        ),
        None,
    )
    return {
        "user": {
            "id": str(user.id),
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "telegram_first_name": user.telegram_first_name,
            "telegram_last_name": user.telegram_last_name,
            "anonymous_id": user.anonymous_id,
            "display_name": preferences.display_name if preferences else None,
            "locale": preferences.locale if preferences else "en",
            "is_active": user.is_active,
            "manual_download_access": user.manual_download_access,
            "boosty_status": link.status if link else "unverified",
            "last_seen_at": iso(user.last_seen_at),
            "created_at": iso(user.created_at),
            "updated_at": iso(user.updated_at),
        },
        "access": {
            "adult_consent": bool(consent),
            "adult_consent_at": iso(consent.accepted_at) if consent else None,
            "blocked": active_ban is not None,
            "effective_download_access": bool(
                user.manual_download_access
                or (
                    link
                    and (
                        link.status == "active_vip"
                        or (
                            link.status == "grace_period"
                            and link.grace_ends_at is not None
                            and link.grace_ends_at > now
                        )
                    )
                )
            ),
            "notifications": {
                "new_titles": (
                    notification.new_title_announcements if notification else True
                ),
                "service": notification.service_notifications if notification else True,
            },
            "boosty": (
                {
                    "id": str(link.id),
                    "status": link.status,
                    "username": link.boosty_username,
                    "user_id": link.boosty_user_id,
                    "tier_name": link.tier_name,
                    "verified_at": iso(link.verified_at),
                    "last_checked_at": iso(link.last_checked_at),
                    "membership_expires_at": iso(link.membership_expires_at),
                    "grace_ends_at": iso(link.grace_ends_at),
                    "last_error_code": link.last_error_code,
                    "last_error_message": link.last_error_message,
                }
                if link
                else None
            ),
        },
        "counts": counts,
        "bans": [
            {
                "id": str(item.id),
                "type": item.ban_type,
                "is_active": item.is_active,
                "public_reason": item.public_reason,
                "internal_note": item.internal_note,
                "starts_at": iso(item.starts_at),
                "expires_at": iso(item.expires_at),
                "unbanned_at": iso(item.unbanned_at),
                "created_at": iso(item.created_at),
            }
            for item in bans
        ],
        "ban_history": [
            {
                "id": str(item.id),
                "ban_id": str(item.ban_id),
                "action": item.action,
                "actor_telegram_id": item.actor_telegram_id,
                "details": item.details,
                "created_at": iso(item.created_at),
            }
            for item in ban_history
        ],
        "boosty_periods": [
            {
                "id": str(item.id),
                "status": item.status,
                "reason": item.reason,
                "starts_at": iso(item.starts_at),
                "ends_at": iso(item.ends_at),
            }
            for item in periods
        ],
        "boosty_events": [
            {
                "id": str(item.id),
                "event_type": item.event_type,
                "payload": item.payload,
                "sent_at": iso(item.sent_at),
                "last_error": item.last_error,
                "created_at": iso(item.created_at),
            }
            for item in access_events
        ],
        "comments": [
            {
                "id": str(item.id),
                "target_type": item.target_type,
                "body": item.public_body,
                "is_deleted": item.is_deleted,
                "created_at": iso(item.created_at),
            }
            for item in comments
        ],
        "ratings": [
            {
                "id": str(item.id),
                "score": item.score,
                "feedback": item.feedback,
                "status": item.status,
                "release": release.chapter_label,
                "title": title.english_title,
                "created_at": iso(item.created_at),
            }
            for item, release, title in ratings
        ],
        "reports": [
            {
                "id": str(item.id),
                "category": item.category,
                "status": item.status,
                "description": item.description,
                "created_at": iso(item.created_at),
            }
            for item in reports
        ],
        "suggestions": [
            {
                "id": str(item.id),
                "title": item.original_title,
                "status": item.status,
                "chapter_count": item.chapter_count,
                "submitted_at": iso(item.submitted_at),
            }
            for item in suggestions
        ],
        "downloads": [
            {
                "id": str(item.id),
                "title": title.english_title,
                "release": release.chapter_label,
                "method": item.delivery_method,
                "status": item.status,
                "created_at": iso(item.created_at),
            }
            for item, release, title in downloads
        ],
        "follows": [
            {
                "title_id": str(title.id),
                "title": title.english_title,
                "created_at": iso(follow.created_at),
            }
            for follow, title in follows
        ],
        "audit": [
            {
                "id": str(item.id),
                "actor_telegram_id": item.actor_telegram_id,
                "action": item.action,
                "payload": item.payload,
                "correlation_id": item.correlation_id,
                "created_at": iso(item.created_at),
            }
            for item in audits
        ],
    }
