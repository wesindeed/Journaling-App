"""Command line interface. Run:  python -m eft_tracker --help"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from datetime import date

from . import deidentify, gamify, prompts, scoring, store, transcript
from .dashboard import render

PRIVACY_NOTICE = """\
PRIVACY: this sends the (scrubbed) transcript to the Anthropic API from your machine.
  - Names you registered with --scrub are replaced; emails/phones are masked. Review `eft_tracker prompt <id>` first if unsure.
  - Confirm that your client consent covers AI processing, and that your API plan's data terms
    (retention / BAA) are acceptable for session content. Recording consent alone may not cover this.
  - Use manual mode (`prompt` -> paste into your own Claude project -> `import`) to keep control of where it goes.
"""


def _read_text(path: str | None) -> str:
    if path and path != "-":
        return open(path, encoding="utf-8").read()
    if sys.stdin.isatty():
        print("Paste the transcript, then press Ctrl-D (Ctrl-Z, Enter on Windows):", file=sys.stderr)
    return sys.stdin.read()


def _step_to_stage(step: int) -> int:
    return 1 if step <= 4 else 2 if step <= 7 else 3


def cmd_add(a) -> int:
    case = store.slug(a.case)
    cases = store.load_cases()
    reg = cases.setdefault(case, {"scrub": {}})
    for pair in a.scrub or []:
        real, _, ph = pair.partition("=")
        if not ph:
            print(f"--scrub needs NAME=Placeholder, got {pair!r}", file=sys.stderr)
            return 2
        reg["scrub"][real.strip()] = ph.strip()
    reg["therapist_label"] = a.therapist_label or reg.get("therapist_label")
    store.save_cases(cases)
    text = _read_text(a.file)
    if not text.strip():
        print("empty transcript", file=sys.stderr)
        return 2
    header, text = transcript.split_granola_header(text)
    if header:
        print("  Granola header detected and dropped (the title usually names the clients).")
    d = a.date or transcript.parse_header_date(header.get("date")) or date.today().isoformat()
    n = store.next_number(case)
    sid = store.session_id(case, d, n)
    my_step = a.my_step
    my_stage = a.my_stage or (_step_to_stage(my_step) if my_step else None)
    sess = {"id": sid, "case": case, "date": d, "number": n, "status": "pending", "my_stage": my_stage,
            "my_step": my_step, "my_block": a.my_block, "notes": a.notes,
            "talk_stats": transcript.talk_stats(text, reg.get("therapist_label")), "supervisor": None, "analysis": None}
    store.transcript_path(sid).write_text(text, encoding="utf-8")
    store.save_session(sess)
    print(f"saved {sid}  ({len(text.split())} words)")
    if not sess["talk_stats"]:
        print("  note: couldn't identify therapist vs client speakers; talk-stats skipped. "
              "Use --therapist-label (e.g. 'Me').")
    if not (my_step or my_stage):
        print("  tip: log your own stage call BEFORE scoring (--my-step 1-9). It powers the stage-calibration chart.")
    return 0


def _transcript_seen(sess: dict) -> str:
    text = store.transcript_path(sess["id"]).read_text(encoding="utf-8")
    reg = store.load_cases().get(sess["case"], {})
    return deidentify.scrub(text, reg.get("scrub", {}))


def cmd_prompt(a) -> int:
    sess = store.load_session(a.session)
    out = prompts.SYSTEM + "\n\n---\n\n" + prompts.build_user_prompt(store.load_rubric(), _transcript_seen(sess), sess)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print(f"wrote {a.out}  -> paste into Claude, then save its JSON reply and run: import {sess['id']} reply.json")
    else:
        print(out)
    return 0


def cmd_import(a) -> int:
    sess = store.load_session(a.session)
    raw = scoring.extract_json(_read_text(a.file))
    try:
        scoring.apply_analysis(sess, raw, store.load_rubric(), _transcript_seen(sess), a.model or "manual", "manual")
    except scoring.ScoreError as e:
        print(f"rejected: {e}", file=sys.stderr)
        return 1
    store.save_session(sess)
    print(f"imported analysis for {sess['id']}  quote check: {sess['scoring']['quote_check']}")
    return 0


def cmd_score(a) -> int:
    ids = [s["id"] for s in store.all_sessions() if s["status"] == "pending"] if a.all_pending else [a.session]
    if not ids or ids == [None]:
        print("nothing to score")
        return 0
    if not a.yes:
        print(PRIVACY_NOTICE)
        if input("Send to the API? [y/N] ").strip().lower() != "y":
            return 1
    rubric, rc = store.load_rubric(), 0
    for sid in ids:
        sess = store.load_session(sid)
        try:
            scoring.score_with_api(sess, _transcript_seen(sess), rubric, a.model)
        except scoring.ScoreError as e:
            print(f"{sid}: FAILED - {e}", file=sys.stderr)
            rc = 1
            continue
        store.save_session(sess)
        qc = sess["scoring"]["quote_check"]
        print(f"{sid}: scored with {sess['scoring']['model']}  (verbatim quotes: {qc['verbatim_rate']} of {qc['checked']})")
    return rc


def cmd_supervisor(a) -> int:
    sess = store.load_session(a.session)
    skills = {}
    for pair in a.skill or []:
        k, _, v = pair.partition("=")
        if k not in {s["key"] for s in store.load_rubric()["skills"]} or not v.isdigit() or not 0 <= int(v) <= 4:
            print(f"bad --skill {pair!r}: use key=0..4", file=sys.stderr)
            return 2
        skills[k] = int(v)
    sess["supervisor"] = {"step": a.step, "stage": _step_to_stage(a.step) if a.step else a.stage, "skills": skills, "notes": a.notes}
    store.save_session(sess)
    print(f"recorded supervisor ratings for {sess['id']}")
    return 0


def _supervision_text(sess: dict, path: str | None) -> str:
    text = _read_text(path)
    reg = store.load_cases().get(sess["case"], {})
    return deidentify.scrub(text, reg.get("scrub", {}))


def cmd_supervision(a) -> int:
    """Turn a transcript of a supervision session into structured feedback on one session."""
    sess = store.load_session(a.session)
    rubric = store.load_rubric()
    text = _supervision_text(sess, a.file)
    hint = (f"Case {sess['case']}, session #{sess['number']}, dated {sess['date']}. "
            "The supervisor may call it 'the couple', by a first name, or by day of the week.")
    prompt = prompts.build_supervision_prompt(rubric, text, hint)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(prompts.SUPERVISION_SYSTEM + "\n\n---\n\n" + prompt)
        print(f"wrote {a.out}. Paste into Claude, save the JSON reply, then: supervision-import {sess['id']} reply.json")
        return 0
    if not a.yes:
        print(PRIVACY_NOTICE)
        if input("Send to the API? [y/N] ").strip().lower() != "y":
            return 1
    try:
        raw = scoring.score_supervision_with_api(prompt, a.model)
    except scoring.ScoreError as e:
        print(f"FAILED - {e}", file=sys.stderr)
        return 1
    return _store_supervision(sess, raw, rubric)


def _store_supervision(sess: dict, raw: dict, rubric: dict) -> int:
    sess["supervision"] = scoring.validate_supervision(raw, rubric)
    store.save_session(sess)
    sv = sess["supervision"]
    print(f"stored {len(sv['skill_signals'])} skill signals, {len(sv['stage_comments'])} stage comments for {sess['id']}")
    for c in sv["stage_comments"]:
        print(f"  stage comment: step={c['step']} stage={c.get('stage')}  \"{c['quote']}\"")
    if sv["stage_comments"]:
        print(f"  If the supervisor gave a step call, record it yourself: supervisor {sess['id']} --step N")
    return 0


def cmd_supervision_import(a) -> int:
    sess = store.load_session(a.session)
    return _store_supervision(sess, scoring.extract_json(_read_text(a.file)), store.load_rubric())


def cmd_practice(a) -> int:
    keys = {s["key"] for s in store.load_rubric()["skills"]}
    if a.skill not in keys:
        print(f"unknown skill {a.skill!r}. Options: {', '.join(sorted(keys))}", file=sys.stderr)
        return 2
    rec = store.log_practice(a.skill, a.minutes, a.note or "", a.date)
    print(f"logged {rec['minutes']} min on {a.skill}  (+{min(a.minutes, gamify.XP_PRACTICE_CAP_MIN) * gamify.XP_PER_PRACTICE_MIN} XP, capped daily)")
    return 0


def _data():
    return gamify.build_dashboard_data(store.all_sessions(), store.load_practice(), store.load_rubric())


def cmd_dashboard(a) -> int:
    out = a.out or str(store.data_dir() / "dashboard.html")
    open(out, "w", encoding="utf-8").write(render(_data()))
    print(f"wrote {out}")
    if a.open:
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


def cmd_status(a) -> int:
    d = _data()
    lv = d["level"]
    print(f"Level {lv['level']}: {lv['title']}   {lv['xp']} XP" + (f"  (next: {lv['next_title']} at {lv['next_at']})" if lv["next_at"] else ""))
    print(f"Sessions: {d['counts']['sessions']} logged, {d['counts']['scored']} scored   Streak: {d['streak_weeks']} wk")
    for q in d["quests"]:
        print(" -", q["name"], (f"(now {q['current']}, target {q['target']})" if q["kind"] == "skill" else f"({q['progress']}/{q['goal']})"))
    st = d["stage"]
    if st["n"]:
        print(f"Stage calls: {st['match_rate']:.0%} match reference; bias {st['bias']:+} (positive = you call it further along than reference)")
    return 0


def cmd_demo(a) -> int:
    import shutil
    os.environ["EFT_DATA_DIR"] = a.dir
    for sub in ("sessions", "transcripts"):  # demo dir is disposable: always start clean
        shutil.rmtree(os.path.join(a.dir, sub), ignore_errors=True)
    for f in ("practice.jsonl", "cases.json", "dashboard.html"):
        if os.path.exists(os.path.join(a.dir, f)):
            os.remove(os.path.join(a.dir, f))
    from . import demo
    n = demo.build()
    out = os.path.join(a.dir, "dashboard.html")
    open(out, "w", encoding="utf-8").write(render(_data()))
    print(f"wrote {n} synthetic sessions + {out}")
    if a.open:
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eft_tracker", description="Local EFT-for-couples progress tracker. Data dir: $EFT_DATA_DIR (default ./data).")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("add", help="store a transcript (paste or --file)")
    s.add_argument("case", help="client initials, e.g. AB (couples: AB+CD)")
    s.add_argument("--file", help="transcript file; omit to paste on stdin")
    s.add_argument("--date", help="YYYY-MM-DD (default today)")
    s.add_argument("--my-step", type=int, choices=range(1, 10), help="YOUR blind call, EFT step 1-9, made before scoring")
    s.add_argument("--my-stage", type=int, choices=(1, 2, 3))
    s.add_argument("--my-block", help="your hypothesis about what's blocking this couple")
    s.add_argument("--notes")
    s.add_argument("--scrub", action="append", metavar="NAME=Placeholder", help="repeatable; remembered per case")
    s.add_argument("--therapist-label", help="speaker label that is you in the transcript, e.g. Me")
    s.set_defaults(fn=cmd_add)

    s = sp.add_parser("prompt", help="manual mode: build the scoring prompt to paste into Claude")
    s.add_argument("session"); s.add_argument("--out"); s.set_defaults(fn=cmd_prompt)  # noqa: E702

    s = sp.add_parser("import", help="manual mode: import Claude's JSON reply")
    s.add_argument("session"); s.add_argument("file", nargs="?", help="JSON file; omit/'-' for stdin")  # noqa: E702
    s.add_argument("--model", help="label for which model produced it"); s.set_defaults(fn=cmd_import)  # noqa: E702

    s = sp.add_parser("score", help="API mode: score with the Anthropic API (needs ANTHROPIC_API_KEY)")
    s.add_argument("session", nargs="?"); s.add_argument("--all-pending", action="store_true")  # noqa: E702
    s.add_argument("--model"); s.add_argument("--yes", action="store_true", help="skip the privacy confirmation")  # noqa: E702
    s.set_defaults(fn=cmd_score)

    s = sp.add_parser("supervisor", help="record your supervisor's ratings for a session (calibrates the scorer)")
    s.add_argument("session"); s.add_argument("--step", type=int, choices=range(1, 10)); s.add_argument("--stage", type=int, choices=(1, 2, 3))  # noqa: E702
    s.add_argument("--skill", action="append", metavar="key=0..4"); s.add_argument("--notes"); s.set_defaults(fn=cmd_supervisor)  # noqa: E702

    s = sp.add_parser("supervision", help="extract your supervisor's feedback on a session from a supervision transcript")
    s.add_argument("session"); s.add_argument("--file", help="supervision transcript; omit for stdin")  # noqa: E702
    s.add_argument("--out", help="manual mode: write the prompt here instead of calling the API")
    s.add_argument("--model"); s.add_argument("--yes", action="store_true"); s.set_defaults(fn=cmd_supervision)  # noqa: E702
    s = sp.add_parser("supervision-import", help="manual mode: import Claude's extraction JSON")
    s.add_argument("session"); s.add_argument("file", nargs="?"); s.set_defaults(fn=cmd_supervision_import)  # noqa: E702

    s = sp.add_parser("practice", help="log a deliberate-practice rep")
    s.add_argument("skill"); s.add_argument("--minutes", type=int, default=10); s.add_argument("--note"); s.add_argument("--date")  # noqa: E702
    s.set_defaults(fn=cmd_practice)

    s = sp.add_parser("dashboard", help="render the local HTML dashboard")
    s.add_argument("--out"); s.add_argument("--open", action="store_true"); s.set_defaults(fn=cmd_dashboard)  # noqa: E702

    s = sp.add_parser("status", help="terminal summary"); s.set_defaults(fn=cmd_status)

    s = sp.add_parser("demo", help="build a synthetic-data dashboard (no real data)")
    s.add_argument("--dir", default="data-demo"); s.add_argument("--open", action="store_true"); s.set_defaults(fn=cmd_demo)  # noqa: E702

    a = p.parse_args(argv)
    if a.cmd == "score" and not (a.session or a.all_pending):
        p.error("score needs a session id or --all-pending")
    try:
        return a.fn(a)
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
