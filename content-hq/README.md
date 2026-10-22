# Content HQ

Single-file dashboard for the Wes White Counseling YouTube channel and content business.

- `dashboard.html` is the page body (title, styles, markup, script). It is published as a claude.ai Artifact.
- Seed data (videos, channel stats, script queue, comment drafts) is a snapshot from VidIQ and Google Drive taken 2026-10-22.
- "Refresh from VidIQ" re-pulls videos, channel stats and comments through the VidIQ connector (about 15 credits).
- Stage, date and comment status changes are saved with the artifact `db` capability.

Not yet connected: Google Analytics, Kit, ThriveCart, Squarespace forms, Claude project chats. See the Data sources tab.
