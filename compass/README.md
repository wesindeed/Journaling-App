# Daily Compass

Single-file task manager published as a claude.ai Artifact for practice building, client work, content, people, joy, body and mind, and space.

- `compass.html` is the page body. Tasks, goals, plans, daily reflections, daily goals, settings and the coach log use the artifact `db` capability, with a localStorage fallback.
- Today: daily brief, 5-minute brain dump (with streak), Big 3, a "something for you" slot, calendar for the day with open windows, task load vs. capacity, daily goals (micro-workouts), weekly balance against protected hours, avoidance radar.
- Horizon: the next eight weeks of calendar load, scheduled tasks, deadlines and goal dates.
- Plan and Goals: inbox, scheduled, someday; goals show a next step or flag as stalled, and "Break it down" proposes steps.
- Coach: `sample` capability with tools to add and schedule tasks. Moderate push-back: moving a task a third time (or a hard conversation a second time) asks what you're afraid of, and you can always override with a reason.
- Calendar and email: the `mcp` capability reads Google Calendar (calendars chosen in Settings) and scans Gmail subjects and previews for tasks. Reads only; nothing is sent or created.
- Seed: Content HQ production deadlines (edit-by, film-by, script-by) were imported as content tasks on 2026-10-23.
- People tab: keep-in-touch rhythms (weekly to quarterly) with a "last connected" date and gift or life notes, plus birthdays and anniversaries. Each date gets a planning level (full for a partner, family, or light for friends) and tasks appear automatically about four weeks out, for example brainstorm, buy, book dinner, card. Deleting one of those tasks suppresses it for that year. "Import list" turns a pasted list of names into people and dates.
- Areas: Practice building, Client work, Content, People, Joy, Body & mind, Space, Home & life.
- Capacity (6.5h default) counts tasks plus calendar time. Calendar events that are all-day, marked free, under 10 minutes, or titled "reminder" are not counted. Events containing words in Settings > Ignore (default: toptal) are dropped.
- Goals are projects: phases, P1 to P3 priorities, "waits on" dependencies, later items parked as someday, and a parked flag. The next step is the first unblocked task by priority.
- Calendar writes: "Put on calendar" in a task opens a sheet to pick day, time and length. Nothing is created until "Add to calendar" is pressed.
- Imports: a document in the `imports` collection (`goals`, `tasks`, `people`, `dates`, `habits`, `days`, plus `delete`) is applied once, the next time the page opens, then marked `applied`. `imports/plan1` holds the 2026-10-23 master plan, brain dump and family list.
