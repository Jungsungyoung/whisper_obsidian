import pytest
from pathlib import Path
from datetime import date
from pipeline.note_builder import NoteData, build_meeting_note, build_transcript_note, get_filenames
from pipeline.vault_writer import VaultWriter

SAMPLE_DATA = NoteData(
    date=date(2026, 2, 18),
    title="테스트 회의",
    audio_filename="test.mp3",
    duration="01:00",
    speakers=["Speaker A"],
    purpose="테스트",
    discussion=["항목 1"],
    decisions=["결정 1"],
    action_items=["할 일 1 (Speaker A, ~02/20)"],
    follow_up=[],
    transcript=[{"timestamp": "00:00:01", "speaker": "Speaker A", "text": "안녕하세요."}],
)


def test_saves_both_files(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="Meetings")
    meeting_fn, transcript_fn = get_filenames(SAMPLE_DATA)
    writer.save(SAMPLE_DATA, build_meeting_note(SAMPLE_DATA), build_transcript_note(SAMPLE_DATA))
    assert (tmp_path / "Meetings" / meeting_fn).exists()
    assert (tmp_path / "Meetings" / transcript_fn).exists()


def test_meeting_note_content_is_correct(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="Meetings")
    meeting_fn, _ = get_filenames(SAMPLE_DATA)
    writer.save(SAMPLE_DATA, build_meeting_note(SAMPLE_DATA), build_transcript_note(SAMPLE_DATA))
    content = (tmp_path / "Meetings" / meeting_fn).read_text(encoding="utf-8")
    assert "## 목적" in content
    assert "테스트" in content


def test_returns_obsidian_uri(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="Meetings")
    result = writer.save(SAMPLE_DATA, build_meeting_note(SAMPLE_DATA), build_transcript_note(SAMPLE_DATA))
    assert result["meeting_uri"].startswith("obsidian://open")
    assert result["transcript_uri"].startswith("obsidian://open")


def test_creates_meetings_folder_if_missing(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="NewFolder/Meetings")
    writer.save(SAMPLE_DATA, build_meeting_note(SAMPLE_DATA), build_transcript_note(SAMPLE_DATA))
    assert (tmp_path / "NewFolder" / "Meetings").exists()
