import pytest
from datetime import date
from pipeline.note_builder import (
    build_meeting_note, build_transcript_note, NoteData, get_filenames,
    get_note_filenames, build_discussion_note, build_voice_memo_note,
    build_daily_note, build_lecture_note, build_reference_note, build_note,
    build_source_note,
)

SAMPLE_DATA = NoteData(
    date=date(2026, 2, 18),
    title="스프린트 리뷰",
    audio_filename="meeting.mp3",
    duration="05:30",
    speakers=["Speaker A", "Speaker B"],
    purpose="스프린트 리뷰 및 배포 계획 논의",
    discussion=["ECS V1.2 진행률 75%", "해상 시험 일정 조정"],
    decisions=["배포일 2026-02-25 확정"],
    action_items=["배포 스크립트 준비 (Speaker A, ~02/22)"],
    follow_up=["API 타임아웃 원인 파악 필요"],
    transcript=[
        {"timestamp": "00:00:12", "speaker": "Speaker A", "text": "스프린트 리뷰 시작합니다."},
        {"timestamp": "00:01:05", "speaker": "Speaker B", "text": "로그인 기능 완료됐습니다."},
    ],
)


def test_meeting_note_has_frontmatter():
    note = build_meeting_note(SAMPLE_DATA)
    assert note.startswith("---\n")
    assert "date: 2026-02-18" in note
    assert "type: meeting" in note
    assert "ai-transcribed" in note


def test_meeting_note_has_all_sections():
    note = build_meeting_note(SAMPLE_DATA)
    assert "## 목적" in note
    assert "## 주요 논의" in note
    assert "## 결정 사항" in note
    assert "## Action Items" in note
    assert "## 후속 질문" in note


def test_meeting_note_has_backlink_to_transcript():
    note = build_meeting_note(SAMPLE_DATA)
    assert "[[전사] 2026-02-18 스프린트 리뷰]]" in note


def test_meeting_note_action_items_are_checkboxes():
    note = build_meeting_note(SAMPLE_DATA)
    assert "- [ ] 배포 스크립트 준비" in note


def test_transcript_note_has_timestamps():
    note = build_transcript_note(SAMPLE_DATA)
    assert "**[00:00:12] Speaker A:**" in note
    assert "스프린트 리뷰 시작합니다." in note


def test_transcript_note_has_backlink_to_meeting():
    note = build_transcript_note(SAMPLE_DATA)
    assert "[[회의] 2026-02-18 스프린트 리뷰]]" in note


def test_filename_convention():
    meeting_fn, transcript_fn = get_filenames(SAMPLE_DATA)
    assert meeting_fn == "[회의] 2026-02-18 스프린트 리뷰.md"
    assert transcript_fn == "[전사] 2026-02-18 스프린트 리뷰.md"


# ── 카테고리별 파일명 ───────────────────────────────────────────────────

def test_meeting_filenames():
    data = NoteData(date=date(2026,2,18), title="리뷰", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="meeting")
    main, transcript = get_note_filenames(data)
    assert main == "[회의] 2026-02-18 리뷰.md"
    assert transcript == "[전사] 2026-02-18 리뷰.md"

def test_discussion_filenames():
    data = NoteData(date=date(2026,2,18), title="설계 논의", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="discussion")
    main, transcript = get_note_filenames(data)
    assert main == "[논의] 2026-02-18 설계 논의.md"
    assert transcript == "[전사] 2026-02-18 설계 논의.md"

def test_voice_memo_filename():
    data = NoteData(date=date(2026,2,18), title="아이디어", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="voice_memo")
    fn = get_note_filenames(data)
    assert fn == "[메모] 2026-02-18 아이디어.md"

def test_daily_filename_has_no_title():
    data = NoteData(date=date(2026,2,18), title="오늘 업무", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="daily")
    fn = get_note_filenames(data)
    assert fn == "[업무일지] 2026-02-18.md"

# ── 보이스 메모 노트 ────────────────────────────────────────────────────

VOICE_MEMO_DATA = NoteData(
    date=date(2026, 2, 18), title="아이디어 메모", audio_filename="memo.m4a",
    duration="02:30", speakers=["Speaker A"],
    purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
    transcript=[],
    category="voice_memo",
    extra={"summary": "새 기능 아이디어", "key_points": ["API 개선"], "action_items": ["문서 작성"]},
)

def test_voice_memo_frontmatter():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "type: voice_memo" in note
    assert "voice-memo" in note

def test_voice_memo_sections():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "## 요약" in note
    assert "## 핵심 포인트" in note
    assert "새 기능 아이디어" in note
    assert "- API 개선" in note

def test_voice_memo_action_items_are_checkboxes():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "- [ ] 문서 작성" in note

# ── 데일리 노트 ─────────────────────────────────────────────────────────

DAILY_DATA = NoteData(
    date=date(2026, 2, 18), title="", audio_filename="daily.m4a",
    duration="03:00", speakers=["Speaker A"],
    purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
    transcript=[],
    category="daily",
    extra={"tasks_done": ["코드 리뷰"], "tasks_tomorrow": ["문서 작성"], "issues": [], "reflection": "좋은 하루"},
)

def test_daily_frontmatter():
    note = build_daily_note(DAILY_DATA)
    assert "type: daily" in note
    assert "date: 2026-02-18" in note

def test_daily_completed_tasks_use_checkmark():
    note = build_daily_note(DAILY_DATA)
    assert "- [x] 코드 리뷰" in note

def test_daily_tomorrow_tasks_use_empty_checkbox():
    note = build_daily_note(DAILY_DATA)
    assert "- [ ] 문서 작성" in note

# ── 논의 노트 ────────────────────────────────────────────────────────────

DISCUSSION_DATA = NoteData(
    date=date(2026, 2, 18), title="아키텍처 논의", audio_filename="disc.mp3",
    duration="10:00", speakers=["Speaker A", "Speaker B"],
    purpose="마이크로서비스 전환 방향 결정",
    discussion=["API 분리 방안 검토"], decisions=["3월 착수 확정"],
    action_items=["PoC 구현 (Speaker A, ~03/05)"], follow_up=[],
    transcript=[], project="[[USV_ECS_개발]]",
    category="discussion",
)

def test_discussion_frontmatter():
    note = build_discussion_note(DISCUSSION_DATA)
    assert "type: discussion" in note
    assert "status: 진행" in note

def test_discussion_has_transcript_backlink():
    note = build_discussion_note(DISCUSSION_DATA)
    assert "[[전사] 2026-02-18 아키텍처 논의]]" in note

# ── build_note 디스패처 ───────────────────────────────────────────────────

def test_build_note_dispatches_voice_memo():
    note = build_note(VOICE_MEMO_DATA)
    assert "## 요약" in note

def test_build_note_raises_for_meeting():
    data = NoteData(date=date(2026,2,18), title="x", audio_filename="x.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="meeting")
    with pytest.raises(ValueError, match="unsupported category"):
        build_note(data)


# ── MD 임포트 테스트 ─────────────────────────────────────────────────────

MD_IMPORT_DATA = NoteData(
    date=date(2026, 2, 20),
    title="AI 논문 정리",
    audio_filename="ai_paper.md",
    duration="0:00",
    speakers=[],
    purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
    transcript=[],
    category="reference",
    source_type="md",
    md_source_text="# 논문 제목\n\n본문 내용입니다.",
)


def test_md_get_note_filenames_returns_tuple():
    result = get_note_filenames(MD_IMPORT_DATA)
    assert isinstance(result, tuple), "MD 임포트는 항상 dual-note(tuple) 반환"


def test_md_source_filename_has_correct_prefix():
    _, source_fn = get_note_filenames(MD_IMPORT_DATA)
    assert source_fn.startswith("[원문]")
    assert source_fn.endswith(".md")


def test_audio_reference_still_returns_str():
    """source_type='audio'인 reference 카테고리는 기존처럼 단일 노트(str)."""
    audio_ref = NoteData(
        date=date(2026, 2, 20), title="테스트",
        audio_filename="test.mp3", duration="1:00",
        speakers=[], purpose="", discussion=[], decisions=[],
        action_items=[], follow_up=[], transcript=[],
        category="reference",
    )
    assert isinstance(get_note_filenames(audio_ref), str)


def test_build_source_note_has_frontmatter():
    note = build_source_note(MD_IMPORT_DATA)
    assert note.startswith("---\n")
    assert "type: md-source" in note
    assert "category: reference" in note


def test_build_source_note_contains_original_text():
    note = build_source_note(MD_IMPORT_DATA)
    assert "# 논문 제목" in note
    assert "본문 내용입니다." in note


def test_build_source_note_has_backlink_to_main():
    note = build_source_note(MD_IMPORT_DATA)
    assert "[[" in note  # 메인 노트 링크 존재


def test_meeting_note_with_md_links_to_source_not_transcript():
    """MD 회의 임포트: build_meeting_note가 [원문] 파일을 링크해야 함."""
    md_meeting = NoteData(
        date=date(2026, 2, 20), title="회의 메모",
        audio_filename="meeting_notes.md", duration="0:00",
        speakers=[], purpose="목적", discussion=[], decisions=[],
        action_items=[], follow_up=[], transcript=[],
        category="meeting", source_type="md",
        md_source_text="# 회의 내용",
    )
    note = build_meeting_note(md_meeting)
    assert "[원문]" in note
    assert "[전사]" not in note
