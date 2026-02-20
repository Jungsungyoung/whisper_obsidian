from datetime import date
from pathlib import Path
from pipeline.note_builder import (
    NoteData, build_meeting_note, build_transcript_note, get_filenames,
    build_voice_memo_note, build_daily_note, build_source_note,
)
from pipeline.vault_writer import VaultWriter


def _meeting_data():
    return NoteData(
        date=date(2026, 2, 18), title="테스트 회의", audio_filename="test.mp3",
        duration="01:00", speakers=["Speaker A"],
        purpose="테스트", discussion=["항목 1"], decisions=["결정 1"],
        action_items=["할 일 1 (Speaker A, ~02/20)"], follow_up=[],
        transcript=[{"timestamp": "00:00:01", "speaker": "Speaker A", "text": "안녕하세요."}],
        category="meeting",
    )


def test_saves_both_files(tmp_path):
    data = _meeting_data()
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"meeting": "Meetings"})
    meeting_fn, transcript_fn = get_filenames(data)
    writer.save(data, build_meeting_note(data), build_transcript_note(data))
    assert (tmp_path / "Meetings" / meeting_fn).exists()
    assert (tmp_path / "Meetings" / transcript_fn).exists()


def test_meeting_note_content_is_correct(tmp_path):
    data = _meeting_data()
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"meeting": "Meetings"})
    meeting_fn, _ = get_filenames(data)
    writer.save(data, build_meeting_note(data), build_transcript_note(data))
    content = (tmp_path / "Meetings" / meeting_fn).read_text(encoding="utf-8")
    assert "## 목적" in content
    assert "테스트" in content


def test_returns_obsidian_uri(tmp_path):
    data = _meeting_data()
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"meeting": "Meetings"})
    result = writer.save(data, build_meeting_note(data), build_transcript_note(data))
    assert result["meeting_uri"].startswith("obsidian://open")
    assert result["transcript_uri"].startswith("obsidian://open")
    assert result["note_uri"] == result["meeting_uri"]  # 하위 호환


def test_creates_meetings_folder_if_missing(tmp_path):
    data = _meeting_data()
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"meeting": "NewFolder/Meetings"})
    writer.save(data, build_meeting_note(data), build_transcript_note(data))
    assert (tmp_path / "NewFolder" / "Meetings").exists()


def test_voice_memo_saves_to_inbox(tmp_path):
    data = NoteData(
        date=date(2026, 2, 18), title="아이디어", audio_filename="a.m4a",
        duration="01:00", speakers=[], purpose="", discussion=[],
        decisions=[], action_items=[], follow_up=[], transcript=[],
        category="voice_memo",
        extra={"summary": "테스트 메모", "key_points": [], "action_items": []},
    )
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"voice_memo": "Inbox"})
    note = build_voice_memo_note(data)
    result = writer.save(data, note)
    assert (tmp_path / "Inbox" / "[메모] 2026-02-18 아이디어.md").exists()
    assert "note_uri" in result
    assert "transcript_uri" not in result


def test_daily_saves_to_daily_folder(tmp_path):
    data = NoteData(
        date=date(2026, 2, 18), title="", audio_filename="d.m4a",
        duration="02:00", speakers=[], purpose="", discussion=[],
        decisions=[], action_items=[], follow_up=[], transcript=[],
        category="daily",
        extra={"tasks_done": [], "tasks_tomorrow": [], "issues": [], "reflection": ""},
    )
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"daily": "Daily"})
    note = build_daily_note(data)
    writer.save(data, note)
    assert (tmp_path / "Daily" / "[업무일지] 2026-02-18.md").exists()


def test_discussion_saves_in_project_subfolder(tmp_path):
    data = NoteData(
        date=date(2026, 2, 18), title="설계 논의", audio_filename="d.mp3",
        duration="05:00", speakers=["Speaker A"],
        purpose="설계 검토", discussion=[], decisions=[], action_items=[], follow_up=[],
        transcript=[], project="MyProject",
        category="discussion",
    )
    from pipeline.note_builder import build_discussion_note
    writer = VaultWriter(vault_path=tmp_path, folder_overrides={"discussion_base": "Projects"})
    note = build_discussion_note(data)
    writer.save(data, note, "")
    assert (tmp_path / "Projects" / "MyProject" / "[논의] 2026-02-18 설계 논의.md").exists()


# ── MD 임포트 dual-note 저장 테스트 ────────────────────────────────────

def test_md_reference_saves_dual_note(tmp_path):
    """MD reference 임포트: 메인 노트 + 원문 노트 둘 다 저장되는지 확인."""
    vault = tmp_path / "Vault"
    md_data = NoteData(
        date=date(2026, 2, 20),
        title="AI 논문",
        audio_filename="ai_paper.md",
        duration="0:00",
        speakers=[],
        purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
        transcript=[],
        category="reference",
        extra={"summary": "요약", "key_findings": [], "methodology": "", "applicability": "", "citations": []},
        source_type="md",
        md_source_text="# 논문 원문\n내용",
    )
    writer = VaultWriter(vault, folder_overrides={"reference": "Resources"})
    from pipeline.note_builder import build_reference_note
    main_note = build_reference_note(md_data)
    source_note = build_source_note(md_data)
    result = writer.save(md_data, main_note, source_note)

    assert "note_path" in result
    assert "transcript_path" in result
    main_file = Path(result["note_path"])
    source_file = Path(result["transcript_path"])
    assert main_file.exists()
    assert source_file.exists()
    assert source_file.name.startswith("[원문]")
    assert "# 논문 원문" in source_file.read_text(encoding="utf-8")


def test_md_voice_memo_also_saves_dual_note(tmp_path):
    """MD voice_memo 임포트: 단일 노트 카테고리도 MD일 때 dual-note 저장."""
    vault = tmp_path / "Vault"
    md_data = NoteData(
        date=date(2026, 2, 20),
        title="아이디어 메모",
        audio_filename="idea.md",
        duration="0:00",
        speakers=[],
        purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
        transcript=[],
        category="voice_memo",
        extra={"summary": "요약", "key_points": [], "action_items": []},
        source_type="md",
        md_source_text="# 아이디어\n내용",
    )
    writer = VaultWriter(vault, folder_overrides={"voice_memo": "Inbox"})
    from pipeline.note_builder import build_voice_memo_note
    main_note = build_voice_memo_note(md_data)
    source_note = build_source_note(md_data)
    result = writer.save(md_data, main_note, source_note)

    assert Path(result["transcript_path"]).name.startswith("[원문]")
