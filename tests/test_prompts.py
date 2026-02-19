from pipeline.prompts import PROMPTS

CATEGORIES = ["meeting", "discussion", "voice_memo", "daily", "lecture", "reference"]


def test_all_categories_have_prompts():
    for cat in CATEGORIES:
        assert cat in PROMPTS, f"Missing prompt for {cat}"
        assert len(PROMPTS[cat]) > 50


def test_discussion_uses_meeting_prompt():
    assert PROMPTS["discussion"] is PROMPTS["meeting"]


def test_prompts_are_korean():
    for cat, prompt in PROMPTS.items():
        assert any(ord(c) > 0xAC00 for c in prompt), f"{cat} prompt has no Korean"
