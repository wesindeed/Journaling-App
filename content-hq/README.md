# Content HQ

Single-file dashboard for the Wes White Counseling YouTube channel and content business.

- `dashboard.html` is the page body (title, styles, markup, script). It is published as a claude.ai Artifact.
- Seed data (videos, channel stats, script queue, comment drafts) is a snapshot from VidIQ and Google Drive taken 2026-10-22.
- "Refresh from VidIQ" re-pulls videos, channel stats and comments through the VidIQ connector (about 15 credits).
- Production is a Kanban board plus calendar (Planned, Scripted, Filmed needs editing, Edited needs thumbnail and setup, Scheduled, Published). Card moves, dates, imports and comment status are saved with the artifact `db` capability.
- "Copy board for my chat" and "Import from chat" sync the board with a Claude planning chat by copy and paste.
- "Pull new scripts from Drive" reads the To Film folder through the Google Drive connector.
- Course sales are parsed from ThriveCart "Sale notification" emails through the Gmail connector (date, product, amount only).

Not yet connected: Kit (official connector exists, needs adding in claude.ai), Google Analytics, Squarespace forms. Descript is intentionally not used. See the Data sources tab.
