from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from dollartl.db.community_models import (
    Report,
    ReportAttachment,
    ReportMessage,
)
from dollartl.services.community_base import CommunityServiceBase
from dollartl.services.moderation import ModerationService

REPORT_CATEGORIES = {
    "broken_pdf",
    "broken_epub",
    "missing_chapters",
    "wrong_order",
    "metadata",
    "boosty_access",
    "other",
}
REPORT_STATUSES = {"open", "in_progress", "resolved", "rejected"}


class CommunityReportsMixin(CommunityServiceBase):
    async def create_report(
        self,
        *,
        user_id: UUID,
        target_type: str,
        title_id: UUID | None,
        release_id: UUID | None,
        category: str,
        description: str,
        attachment: dict[str, object] | None = None,
    ) -> Report:
        if category not in REPORT_CATEGORIES:
            raise ValueError("Unknown report category.")
        if not 10 <= len(description.strip()) <= 2000:
            raise ValueError("Report description must contain 10–2,000 characters.")
        sanitized = await ModerationService(self.session).sanitize(
            user_id=user_id,
            text=description.strip(),
            surface="report",
            entity_type=target_type,
            entity_id=str(title_id or release_id),
        )
        report = Report(
            user_id=user_id,
            target_type=target_type,
            title_id=title_id,
            release_id=release_id,
            category=category,
            description=sanitized.text,
        )
        self.session.add(report)
        await self.session.flush()
        message = ReportMessage(
            report_id=report.id,
            sender_type="user",
            sender_user_id=user_id,
            body=sanitized.text,
        )
        self.session.add(message)
        await self.session.flush()
        if attachment is not None:
            size = int(attachment.get("size_bytes") or 0)
            if size > self.settings.user_upload_max_bytes:
                raise ValueError("Attachment exceeds the 20 MB limit.")
            self.session.add(
                ReportAttachment(
                    report_id=report.id,
                    report_message_id=message.id,
                    telegram_file_id=str(attachment["telegram_file_id"]),
                    telegram_file_unique_id=(
                        str(attachment["telegram_file_unique_id"])
                        if attachment.get("telegram_file_unique_id")
                        else None
                    ),
                    filename=(
                        str(attachment["filename"])
                        if attachment.get("filename")
                        else None
                    ),
                    content_type=(
                        str(attachment["content_type"])
                        if attachment.get("content_type")
                        else None
                    ),
                    size_bytes=size,
                )
            )
        await self.session.commit()
        return report

    async def reply_report(
        self, report_id: UUID, *, admin_telegram_id: int, body: str
    ) -> Report | None:
        report = await self.session.get(Report, report_id)
        if report is None:
            return None
        self.session.add(
            ReportMessage(
                report_id=report.id,
                sender_type="admin",
                sender_admin_id=admin_telegram_id,
                body=body.strip(),
            )
        )
        await self.session.commit()
        return report

    async def set_report_status(
        self, report_id: UUID, *, status: str, admin_telegram_id: int
    ) -> Report | None:
        if status not in REPORT_STATUSES:
            raise ValueError("Unknown report status.")
        report = await self.session.get(Report, report_id)
        if report is None:
            return None
        report.status = status
        report.assigned_admin_id = admin_telegram_id
        await self.session.commit()
        return report

    async def report_counts(self) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(Report.status, func.count(Report.id)).group_by(Report.status)
            )
        ).all()
        return {status: int(count) for status, count in rows}
