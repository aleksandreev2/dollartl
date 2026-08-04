# Title suggestions

## Rules and quotas

Before the first submission, a user accepts versioned prohibited-content rules. Standard accounts can submit one suggestion per calendar month; active VIP and valid grace-period accounts can submit five. Drafts do not consume quota.

Standard suggestions may describe works longer than 200 chapters, but requested translation scope is capped at chapters 1–200. VIP submissions preserve the full current chapter count.

## Required data

A submitted suggestion must contain:

1. original-language title;
2. at least one source URL;
3. current chapter count and publication status;
4. **one valid raw source file**;
5. optional official cover.

Accepted raw formats are EPUB, TXT, ZIP, DOCX and PDF, up to 20 MB. The raw step cannot be skipped. Submission is rejected when the raw file is missing or its validation status is not `valid`.

The requirement is enforced twice:

- in the Telegram wizard before review and submission;
- by a PostgreSQL trigger when a draft first leaves `draft` status.

The database trigger is limited to the initial submission transition so historical v0.6 records can still be moderated.

## File checks

Raw files receive signature checks, SHA-256, archive path-traversal protection, entry and unpacked-size limits, suspicious compression detection and an optional antivirus command. Raw files remain private in S3 and are visible only through authenticated administration tools.

## Duplicate review

Submission records exact matches by normalized title, source URL and uploaded-file checksum. Matching a published title also creates a duplicate candidate. Duplicates are flagged for owner review rather than silently rejected.

## Statuses

- `under_review`
- `accepted`
- `translated`
- `rejected`

`translated` requires a linked published Title UUID. Rejection requires a public reason. Internal notes are never shown to the user. Every transition is retained and the applicant is notified.
