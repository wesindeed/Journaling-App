# EFT Tracker

A **local-first** tool that turns couples-therapy session transcripts into a skill-development dashboard for
Emotionally Focused Therapy (EFT) training. Everything is stored as plain files on your machine in `data/`
(git-ignored). Nothing is uploaded except, optionally, the scrubbed transcript sent to the Anthropic API when you
choose API mode.

> **Screening aid, not a competency verdict.** Scores come from an LLM applying a rubric to *text*. A transcript
> cannot show tone, tempo, silence or body language, and the scorer has **not been validated** against trained EFT
> raters. Use the Trust panel + your supervisor to calibrate. (EFT itself has strong outcome evidence; LLM-scored
> EFT fidelity has none that I'm aware of.)

## Quick start

```bash
pip install -r requirements.txt
python -m eft_tracker demo --open        # synthetic data, no real clients (writes ./data-demo)
```

## Per-session workflow (about 3 minutes of your time)

```bash
# 1. Paste the Granola transcript (Ctrl-D to finish), logging YOUR blind stage call first.
python -m eft_tracker add AB --date 2026-10-20 --my-step 4 --my-block "withdrawer not engaged" \
    --scrub "Jane=Partner A" --scrub "John=Partner B" --therapist-label Me
#    (--scrub is remembered per case. Case = client initials, e.g. AB or AB+CD.)

# 2a. API mode (sends the *scrubbed* transcript to the Anthropic API; asks you to confirm each time):
export ANTHROPIC_API_KEY=...
python -m eft_tracker score AB_2026-10-20_01
#     or score everything pending:  python -m eft_tracker score --all-pending

# 2b. Manual mode (you control where the text goes):
python -m eft_tracker prompt AB_2026-10-20_01 --out prompt.txt   # paste into your own Claude project
python -m eft_tracker import AB_2026-10-20_01 reply.json         # paste Claude's JSON reply back

# 3. Look at it
python -m eft_tracker dashboard --open
python -m eft_tracker status
```

Weekly, after supervision (this is what makes the scores trustworthy):

```bash
python -m eft_tracker supervisor AB_2026-10-20_01 --step 3 --skill emotional_deepening=2 --skill enactment_timing=1
python -m eft_tracker practice emotional_deepening --minutes 15 --note "3-Turn Stay on session 4"
```

### Supervision transcripts (no numeric ratings needed)

If your supervisor gives comments rather than scores, feed the supervision-session transcript in:

```bash
python -m eft_tracker supervision AB_2026-10-20_01 --file supervision.txt --out prompt.txt   # manual mode
python -m eft_tracker supervision-import AB_2026-10-20_01 reply.json
#   or API mode: omit --out
```

It extracts only what the supervisor actually said (quote-backed strengths, growth edges, stage comments,
assignments). The Trust panel then reports **direction agreement**: did the scorer rate as a growth edge what your
supervisor called one? That is much weaker than numeric ratings. If the supervisor gives a step call, record it with
`supervisor --step N`.

### Granola format notes

`add` strips Granola's `Meeting Title / Date / Participants / Transcript:` header (the title usually names the
clients) and uses its date if you don't pass `--date`. Granola labels you `Me` and everyone else `Them`, so **both
partners arrive merged**: the tool can measure your talk share but not per-partner airtime, and the scorer is told to
infer who is speaking from context. Speech recognition garbles names; register each variant you see
(`--scrub "Garen=Friend" --scrub "Garrett=Friend"`).

## What it tracks

- **12 EFT skills**, scored 0-4 with verbatim evidence quotes (`eft_tracker/rubric.json`).
- **Your four named sticking points**: deepening emotion before enactments, enactment timing (premature / ripe / late),
  stage diagnosis (your blind call vs. supervisor/scorer, with a lean toward calling couples further along than they are), and
  whether clients name the cycle (levels 0-4).
- **Per-couple timelines**: step trajectory, cycle-naming level, change events (withdrawer re-engagement, blamer softening),
  block hypotheses, next-session focus.
- **Practice engine**: weakest skills become quests with a drill, and the scorer rewrites your missed moments.
- **Gamification**: XP, levels, weekly streaks, badges. Session XP is capped per week on purpose: XP follows deliberate
  practice, supervisor calibration and real skill milestones, not session volume.
- **Trust panel**: scorer-vs-supervisor agreement and a "quote tripwire" (share of cited quotes that appear verbatim).

## Privacy

- Data lives in `./data` (or `$EFT_DATA_DIR`), git-ignored. The dashboard is a single offline HTML file.
- "Hide client details" on the dashboard blurs case ids and quotes for screen-sharing.
- Scrubbing is best-effort (registered names, emails, phone numbers). Review `prompt` output when in doubt.
- API mode sends session content to a third party. Confirm your client consent covers AI processing (recording consent
  may not), and that your API plan's retention/BAA terms are acceptable.
- Don't commit `data/`, and don't publish the dashboard HTML anywhere.

## Customizing the rubric

`eft_tracker/rubric.json` is a draft built from the general EFT literature. Put your ICEEFT requirements and your
supervisor's tape-review criteria in it. Copy it to `data/rubric.local.json` to keep a private version. Keep the skill
`key`s stable: renaming one orphans old scores.

## Tests

```bash
python -m pytest -q
```
