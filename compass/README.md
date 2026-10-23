# Daily Compass

Single-file task manager published as a claude.ai Artifact for practice building, client work, content, people, joy, body and mind, and space.

- `compass.html` is the page body. Tasks, goals, plans, daily reflections, daily goals, settings and the coach log use the artifact `db` capability, with a localStorage fallback.
- Today: daily brief, 5-minute brain dump (with streak), Big 3, a "something for you" slot, calendar for the day with open windows, task load vs. capacity, daily goals (micro-workouts), weekly balance against protected hours, avoidance radar.
- Horizon: the next eight weeks of calendar load, scheduled tasks, deadlines and goal dates.
- Plan and Goals: inbox, scheduled, someday; goals show a next step or flag as stalled, and "Break it down" proposes steps.
- Coach: `sample` capability with tools to add and schedule tasks. Moderate push-back: moving a task a third time (or a hard conversation a second time) asks what you're afraid of, and you can always override with a reason.
- Calendar and email: the `mcp` capability reads Google Calendar (calendars chosen in Settings) and scans Gmail subjects and previews for tasks. Reads only; nothing is sent or created.
- Seed: Content HQ production deadlines (edit-by, film-by, script-by) were imported as content tasks on 2026-10-23.
