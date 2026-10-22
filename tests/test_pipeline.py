import json
from types import SimpleNamespace

import pytest

from eft_tracker import cli, deidentify, gamify, scoring, store, transcript
from eft_tracker.dashboard import render

TRANSCRIPT = """Me: Thanks for coming in. What's been happening this week?
Jane: He just shuts down every time I bring anything up.
Me: So when it gets tense, you reach and he goes quiet.
John: I don't know what to say, so I say nothing.
Me: What happens inside right then, just before you go quiet?
John: I feel like I'm going to fail her again.
Jane: I didn't know that. Call me at 312-555-0199 or jane@example.com.
Me: Can you tell her that?
"""


def fake_analysis(rubric, **over):
    a = {
        "stage_assessment": {"step": 3, "confidence": .6, "evidence": ["I feel like I'm going to fail her again."], "rationale": "r"},
        "skills": {s["key"]: {"assessable": True, "score": 2, "confidence": .7,
                              "evidence": ["What happens inside right then"], "note": "n"} for s in rubric["skills"]},
        "cycle_naming": {"level": 1, "cycle_description": "pursue/withdraw", "evidence": ["you reach and he goes quiet"]},
        "enactments": [{"quote_of_invitation": "Can you tell her that?", "timing": "ripe",
                        "primary_emotion_accessed_before": "yes", "rationale": "r"}],
        "change_events": [], "blocks": [{"block_type": "nonsense_type", "partner": "A", "evidence": [], "confidence": .5, "suggested_move": "m"}],
        "rewrites": [], "top_strengths": ["x"], "growth_edges": ["emotional_deepening", "bogus_key"],
        "focus_for_next_session": "f", "limits_note": "l",
    }
    a.update(over)
    return a


def add(tmp_path, case="AB", date="2026-09-01", extra=()):
    f = tmp_path / "t.txt"
    f.write_text(TRANSCRIPT)
    assert cli.main(["add", case, "--file", str(f), "--date", date, "--my-step", "5",
                     "--scrub", "Jane=Partner A", "--scrub", "John=Partner B", *extra]) == 0
    return store.session_id(case, date, 1)


def test_talk_stats_and_parse():
    st = transcript.talk_stats(TRANSCRIPT)
    assert st and 0 < st["therapist_word_share"] < 1 and st["client_speakers"] == ["Jane", "John"]
    assert transcript.talk_stats("no labels here at all\njust prose") is None


def test_scrub():
    out = deidentify.scrub(TRANSCRIPT, {"Jane": "Partner A", "John": "Partner B"})
    assert "Jane" not in out and "Partner A:" in out and "[email]" in out and "[phone]" in out


def test_add_creates_pending_session_and_stage(tmp_path):
    sid = add(tmp_path)
    s = store.load_session(sid)
    assert s["status"] == "pending" and s["my_step"] == 5 and s["my_stage"] == 2
    assert store.load_cases()["AB"]["scrub"]["Jane"] == "Partner A"


def test_manual_prompt_is_scrubbed_and_import_validates(tmp_path):
    sid = add(tmp_path)
    out = tmp_path / "p.txt"
    assert cli.main(["prompt", sid, "--out", str(out)]) == 0
    text = out.read_text()
    assert "Jane" not in text and "Partner A" in text
    rub = store.load_rubric()
    reply = tmp_path / "r.json"
    reply.write_text("```json\n" + json.dumps(fake_analysis(rub)) + "\n```")
    assert cli.main(["import", sid, str(reply)]) == 0
    s = store.load_session(sid)
    assert s["status"] == "scored"
    a = s["analysis"]
    assert a["stage_assessment"]["stage"] == 1  # step 3 -> stage 1
    assert a["blocks"][0]["block_type"] == "other"  # unknown block type normalised
    assert a["growth_edges"] == ["emotional_deepening"]  # unknown skill dropped
    assert s["scoring"]["quote_check"]["verbatim_rate"] == 1.0  # all quotes appear in the scrubbed transcript


def test_import_rejects_bad_scores(tmp_path):
    sid = add(tmp_path)
    rub = store.load_rubric()
    bad = fake_analysis(rub)
    bad["skills"]["validation"]["score"] = 9
    reply = tmp_path / "r.json"
    reply.write_text(json.dumps(bad))
    assert cli.main(["import", sid, str(reply)]) == 1
    assert store.load_session(sid)["status"] == "pending"


def test_quote_check_flags_invented_quotes(tmp_path):
    rub = store.load_rubric()
    a = scoring.validate(fake_analysis(rub), rub)
    a["skills"]["validation"]["evidence"] = ["a quote nobody ever said in this session"]
    assert scoring.quote_check(a, TRANSCRIPT)["verbatim_rate"] < 1


class FakeStream:
    def __init__(self, text, stop="end_turn"):
        self.msg = SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


def fake_client(*texts):
    calls = []
    it = iter(texts)

    def stream(**kw):
        calls.append(kw)
        return FakeStream(next(it))
    return SimpleNamespace(messages=SimpleNamespace(stream=stream)), calls


def test_api_mode_retries_once_on_invalid_output(tmp_path):
    sid = add(tmp_path)
    rub = store.load_rubric()
    client, calls = fake_client("not json at all", json.dumps(fake_analysis(rub)))
    sess = store.load_session(sid)
    scoring.score_with_api(sess, cli._transcript_seen(sess), rub, client=client)
    assert sess["status"] == "scored" and len(calls) == 2
    assert calls[0]["model"] == "claude-opus-5-5" and calls[0]["output_config"] == {"effort": "high"}
    assert "thinking" not in calls[0] and "temperature" not in calls[0]
    assert "Jane" not in calls[0]["messages"][0]["content"]  # scrubbed before leaving the machine
    assert "rejected" in calls[1]["messages"][0]["content"]


def test_api_mode_gives_up_after_retries(tmp_path):
    sid = add(tmp_path)
    client, _ = fake_client("nope", "still nope")
    sess = store.load_session(sid)
    with pytest.raises(scoring.ScoreError):
        scoring.score_with_api(sess, "x", store.load_rubric(), client=client)


def test_refusal_is_reported(tmp_path):
    client = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: FakeStream("", "refusal")))
    with pytest.raises(scoring.ScoreError, match="declined"):
        scoring.call_model("p", client=client)


def test_gamify_stage_bias_and_trust(tmp_path):
    rub = store.load_rubric()
    for i, (mine, model_step, sup) in enumerate([(2, 3, None), (2, 3, 2), (1, 2, None)]):
        d = f"2026-09-{i + 1:02d}"
        sid = add(tmp_path, "AB", d) if i == 0 else None
        if sid is None:
            f = tmp_path / f"t{i}.txt"
            f.write_text(TRANSCRIPT)
            cli.main(["add", "AB", "--file", str(f), "--date", d, "--my-stage", str(mine)])
            sid = store.session_id("AB", d, i + 1)
        s = store.load_session(sid)
        s["my_stage"] = mine
        s["analysis"] = scoring.validate(fake_analysis(rub, stage_assessment={"step": model_step, "confidence": .5}), rub)
        s["status"] = "scored"
        if sup:
            s["supervisor"] = {"step": sup, "stage": 1, "skills": {"validation": 3}, "notes": None}
        store.save_session(s)
    data = gamify.build_dashboard_data(store.all_sessions(), [], rub)
    assert data["stage"]["n"] == 3
    # supervisor (stage 1) overrides model for session 2; mine=2 there -> over-advanced
    assert data["stage"]["bias"] > 0
    assert data["trust"]["calibrated_sessions"] == 1 and data["trust"]["mae"] == 1  # scorer 2 vs supervisor 3 on validation


def test_streak_and_levels():
    from datetime import date
    days = {date(2026, 10, 5), date(2026, 10, 14), date(2026, 10, 21)}  # three consecutive ISO weeks
    assert gamify.streak_weeks(days, date(2026, 10, 22)) == 3
    assert gamify.streak_weeks(set(), date(2026, 10, 22)) == 0
    assert gamify.level_for(0)["level"] == 1 and gamify.level_for(10**6)["next_at"] is None


def test_session_xp_is_capped_per_week():
    rub = store.load_rubric()
    sessions = [{"id": f"X{i}", "case": "X", "date": "2026-10-20", "number": i, "status": "pending"} for i in range(20)]
    led = gamify.xp_ledger(sessions, [], gamify.skill_summary(sessions, rub))
    assert led["parts"]["sessions_logged"] == gamify.XP_LOGGED * gamify.XP_SESSION_WEEKLY_CAP


def test_dashboard_embeds_data_safely(tmp_path):
    rub = store.load_rubric()
    data = gamify.build_dashboard_data([], [], rub)
    data["cases"] = [{"case": "</script><script>alert(1)</script>"}]
    html = render(data)
    assert "</script><script>alert(1)" not in html and "/*__DATA__*/" not in html


def test_empty_dashboard_renders(tmp_path):
    assert cli.main(["dashboard", "--out", str(tmp_path / "d.html")]) == 0
    assert (tmp_path / "d.html").read_text().startswith("<!doctype html>")


GRANOLA = """Meeting Title: Relationship stuff with Alex and Jo
Date: Oct 21
Meeting participants: Wes White

Transcript:
Them: Hi. How's it going? Good.
Me: Good, good. How were the last two weeks?
Them: Busy. We both traveled. Alex was gone, then Jo was.
Me: Mm-hmm.
Them: And then we had a tense moment about dinner yesterday.
Me: What was that like for you?
Them: Hard. I felt shut out.
Me: Yeah.
"""


def test_granola_header_is_split_and_not_parsed_as_speakers():
    hdr, body = transcript.split_granola_header(GRANOLA)
    assert hdr["date"] == "Oct 21" and "Meeting Title" not in body and body.startswith("Them: Hi")
    st = transcript.talk_stats(body)
    assert st["client_speakers"] == ["Them"] and st["partner_attribution"] == "merged"
    assert transcript.split_granola_header("Me: hi\nThem: yo") == ({}, "Me: hi\nThem: yo")


def test_header_date_parsing_never_lands_in_future():
    from datetime import date
    today = date(2026, 10, 22)
    assert transcript.parse_header_date("Oct 21", today) == "2026-10-21"
    assert transcript.parse_header_date("Dec 30", today) == "2025-12-30"
    assert transcript.parse_header_date("2026-09-01", today) == "2026-09-01"
    assert transcript.parse_header_date("someday", today) is None


def test_add_drops_granola_title_uses_its_date_and_flags_merged_speakers(tmp_path):
    f = tmp_path / "g.txt"
    f.write_text(GRANOLA)
    assert cli.main(["add", "AB", "--file", str(f), "--therapist-label", "Me"]) == 0
    sid = [s["id"] for s in store.all_sessions()][0]
    sess = store.load_session(sid)
    assert sess["date"].endswith("-10-21")
    assert "Alex and Jo" not in store.transcript_path(sid).read_text()
    from eft_tracker import prompts
    p = prompts.build_user_prompt(store.load_rubric(), "x", sess)
    assert "merged under one label" in p


def test_supervision_extraction_is_validated_and_direction_agreement_computed(tmp_path):
    rub = store.load_rubric()
    sid = add(tmp_path)
    s = store.load_session(sid)
    s["analysis"] = scoring.validate(fake_analysis(rub), rub)
    s["analysis"]["skills"]["validation"]["score"] = 3
    s["analysis"]["skills"]["emotional_deepening"]["score"] = 2
    s["analysis"]["skills"]["heightening"]["score"] = 3
    s["analysis"]["growth_edges"] = []
    s["status"] = "scored"
    store.save_session(s)
    reply = tmp_path / "sv.json"
    reply.write_text(json.dumps({
        "scope_note": "clear",
        "skill_signals": [
            {"skill": "validation", "signal": "strength", "quote": "your validation was lovely"},
            {"skill": "emotional_deepening", "signal": "growth_edge", "quote": "stay with it longer"},
            {"skill": "heightening", "signal": "growth_edge", "quote": "you could have heightened more"},
            {"skill": "not_a_skill", "signal": "strength", "quote": "x"},
            {"skill": "validation", "signal": "strength", "quote": ""},
        ],
        "stage_comments": [{"step": 11, "quote": "I'd call it stage two"}],
        "assignments": ["three-turn stay"]}))
    assert cli.main(["supervision-import", sid, str(reply)]) == 0
    s = store.load_session(sid)
    assert len(s["supervision"]["skill_signals"]) == 3  # unknown skill and quote-less item dropped
    assert s["supervision"]["stage_comments"][0]["step"] is None  # out-of-range step discarded
    d = gamify.direction_agreement(store.all_sessions())
    assert d["n"] == 3 and d["agree"] == 2  # heightening scored 3, so a 'growth edge' comment disagrees


def test_supervision_manual_prompt_is_scrubbed(tmp_path):
    sid = add(tmp_path)
    f = tmp_path / "sup.txt"
    f.write_text("Me: I'm stuck with Jane and John.\nSupervisor: Stay with it longer.")
    out = tmp_path / "p.txt"
    assert cli.main(["supervision", sid, "--file", str(f), "--out", str(out)]) == 0
    text = out.read_text()
    assert "Jane" not in text and "Partner A" in text
