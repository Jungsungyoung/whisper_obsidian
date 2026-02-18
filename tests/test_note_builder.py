import pytest
from datetime import date
from pipeline.note_builder import build_meeting_note, build_transcript_note, NoteData, get_filenames

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
