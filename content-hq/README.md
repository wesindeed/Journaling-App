# Content HQ

Single-file dashboard for the Wes White Counseling YouTube channel and content business.

- `dashboard.html` is the page body (title, styles, markup, script). It is published as a claude.ai Artifact.
- Seed data (videos, channel stats, script queue, comment drafts) is a snapshot from VidIQ and Google Drive taken 2026-10-22.
- "Refresh from VidIQ" re-pulls videos, channel stats and comments through the VidIQ connector (about 15 credits).
- Production is a Kanban board plus calendar (Planned, Scripted, Filmed needs editing, Edited needs thumbnail and setup, Scheduled, Published). Card moves, dates, imports and comment status are saved with the artifact `db` capability.
- "Copy board for my chat" and "Import from chat" sync the board with a Claude planning chat by copy and paste.
- "Pull new scripts from Drive" reads the To Film folder through the Google Drive connector.
- Course sales are parsed from ThriveCart "Sale notification" emails through the Gmail connector (date, product, amount only).

- Waitlist tab: reads Squarespace "Join My Waitlist Form" emails from Gmail, sorts by the Illinois answer, fills editable reply templates (copy, or create a Gmail draft; never sends). Outside-Illinois requests can be added to Kit with a tag, only when they ticked the email-updates box. Request details are not stored; only replied and skipped marks are.
- Kit panel (Funnel tab): subscribers, forms, broadcasts and signup sources via the Kit connector.
- Descript sync: a project in the To Edit folder is Filmed, needs editing; a name ending _edited is Edited.
- Website card reads a Google Sheet filled by `ga4-to-sheets.gs` (Google Apps Script, free). The script has not been run against a real GA4 property.

Not yet set up: Google Analytics sheet, Search Console. See the Data sources tab.
