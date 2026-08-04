# Title suggestions

## Rules and consent

The first suggestion requires a versioned consent. The prohibited categories are guro or extreme sexualized gore, scat or feces-related sexual content, and sexual content involving minors. Changing `SUGGESTION_RULES_VERSION` asks every user to accept the revised rules again.

## Monthly quotas

- Standard users: 1 submitted suggestion per calendar month.
- Active VIP and valid grace-period users: 5 submitted suggestions per calendar month.
- Drafts do not consume quota.
- A membership change modifies the current monthly ceiling; it does not create a second quota pool.
- The owner can restore a consumed slot with `/suggestion_restore_slot`.

Standard users may suggest works longer than 200 chapters, but the requested translation scope is stored as chapters 1–200. VIP suggestions keep the full current chapter count as scope.

## Wizard

1. Original-language title.
2. One or more original source URLs.
3. Current chapter count and publication status.
4. Optional EPUB, TXT, ZIP, DOCX or PDF raw file up to 20 MB.
5. Optional official JPG, PNG or WebP cover.
6. Review and submit.

Raw files and covers are private S3 objects. Upload validation checks signatures, archive paths, entry count, unpacked size, suspicious compression ratios and SHA-256. `SUGGESTION_ANTIVIRUS_COMMAND` may point to an external scanner; use `{file}` as a placeholder or the temporary path is appended automatically.

## Duplicate review

Submission records exact matches by normalized title, source URL and uploaded-file checksum. Matching a published title also creates a duplicate candidate. Duplicate detection does not silently reject a suggestion; it flags it for the owner. A rejected duplicate may have its monthly slot restored.

## Statuses

- `under_review`
- `accepted`
- `translated`
- `rejected`

`translated` requires a linked published Title UUID. Rejection requires a public reason. Internal notes are never shown to the user. Every transition is retained in status history and sent to the applicant.

## Temporary owner commands

```text
/suggestion_list [under_review|accepted|translated|rejected|all]
/suggestion_show <uuid>
/suggestion_status <uuid> <accepted|rejected|translated> [linked_title_uuid] | public reason | internal note
/suggestion_restore_slot <uuid> [reason]
```
