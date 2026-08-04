from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select

from dollartl.db.community_models import Comment, CommentRevision
from dollartl.db.models import AuditLog, UserSettings
from dollartl.services.community_base import CommunityServiceBase
from dollartl.services.moderation import ModerationService


class CommunityCommentsMixin(CommunityServiceBase):
    async def set_display_name(self, user_id: UUID, nickname: str | None) -> str:
        settings = (
            await self.session.execute(
                select(UserSettings).where(UserSettings.user_id == user_id)
            )
        ).scalar_one()
        if nickname is None:
            settings.display_name = None
            await self.session.commit()
            return ""
        candidate, nword = await ModerationService(self.session).validate_nickname(
            user_id=user_id, nickname=nickname
        )
        if nword:
            raise PermissionError(
                "Bro, you don't have the N-word pass. Pick another nickname and cut that shit out."
            )
        settings.display_name = candidate
        await self.session.commit()
        return candidate

    async def create_comment(
        self,
        *,
        user_id: UUID,
        target_type: str,
        title_id: UUID | None,
        release_id: UUID | None,
        body: str,
    ) -> Comment:
        text = body.strip()
        if not 1 <= len(text) <= 1000:
            raise ValueError("Comment must contain 1–1,000 characters.")
        if target_type not in {"title", "release"}:
            raise ValueError("Unsupported comment target.")
        _, vip = await self.display_name(user_id)
        result = await ModerationService(self.session).sanitize(
            user_id=user_id,
            text=text,
            surface="comment",
            entity_type=target_type,
            entity_id=str(title_id or release_id),
        )
        comment = Comment(
            user_id=user_id,
            target_type=target_type,
            title_id=title_id,
            release_id=release_id,
            original_body=text,
            public_body=result.text,
            replacement_count=result.replacements,
            vip_snapshot=vip,
        )
        self.session.add(comment)
        await self.session.flush()
        self.session.add(
            CommentRevision(
                comment_id=comment.id,
                original_body=text,
                public_body=result.text,
                replacement_count=result.replacements,
                editor_user_id=user_id,
            )
        )
        await self.session.commit()
        return comment

    async def list_comments(
        self,
        *,
        target_type: str,
        target_id: UUID,
        page: int,
        page_size: int = 8,
    ) -> tuple[list[tuple[Comment, str]], int]:
        condition = (
            Comment.title_id == target_id
            if target_type == "title"
            else Comment.release_id == target_id
        )
        total = int(
            (
                await self.session.execute(
                    select(func.count(Comment.id)).where(
                        Comment.target_type == target_type,
                        condition,
                        Comment.is_deleted.is_(False),
                    )
                )
            ).scalar_one()
        )
        comments = list(
            (
                await self.session.execute(
                    select(Comment)
                    .where(
                        Comment.target_type == target_type,
                        condition,
                        Comment.is_deleted.is_(False),
                    )
                    .order_by(Comment.created_at.desc())
                    .offset(max(page, 0) * page_size)
                    .limit(page_size)
                )
            ).scalars()
        )
        rendered: list[tuple[Comment, str]] = []
        for comment in comments:
            name, vip = await self.display_name(comment.user_id)
            rendered.append((comment, f"[VIP] {name}" if vip else name))
        return rendered, total

    async def list_user_comments(
        self, user_id: UUID, *, limit: int = 20
    ) -> list[Comment]:
        return list(
            (
                await self.session.execute(
                    select(Comment)
                    .where(
                        Comment.user_id == user_id,
                        Comment.is_deleted.is_(False),
                    )
                    .order_by(Comment.created_at.desc())
                    .limit(limit)
                )
            ).scalars()
        )

    async def delete_own_comment(self, comment_id: UUID, user_id: UUID) -> bool:
        comment = await self.session.get(Comment, comment_id)
        if comment is None or comment.user_id != user_id or comment.is_deleted:
            return False
        comment.is_deleted = True
        comment.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return True

    async def delete_comment(
        self, comment_id: UUID, *, admin_telegram_id: int | None = None
    ) -> bool:
        comment = await self.session.get(Comment, comment_id)
        if comment is None or comment.is_deleted:
            return False
        comment.is_deleted = True
        comment.deleted_at = datetime.now(timezone.utc)
        comment.deleted_by_admin_id = admin_telegram_id
        if admin_telegram_id is not None:
            self.session.add(
                AuditLog(
                    actor_telegram_id=admin_telegram_id,
                    action="comment.deleted",
                    entity_type="comment",
                    entity_id=str(comment.id),
                    payload={},
                )
            )
        await self.session.commit()
        return True

    async def restore_comment(self, comment_id: UUID, admin_telegram_id: int) -> bool:
        comment = await self.session.get(Comment, comment_id)
        if comment is None or not comment.is_deleted:
            return False
        comment.is_deleted = False
        comment.deleted_at = None
        comment.deleted_by_admin_id = None
        self.session.add(
            AuditLog(
                actor_telegram_id=admin_telegram_id,
                action="comment.restored",
                entity_type="comment",
                entity_id=str(comment.id),
                payload={},
            )
        )
        await self.session.commit()
        return True
