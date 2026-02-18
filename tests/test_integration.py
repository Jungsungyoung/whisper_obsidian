"""
통합 테스트: 실제 오디오 파일로 전체 파이프라인 검증
실행: pytest tests/test_integration.py -v -s

sample.mp3가 없으면 SKIP됩니다:
  python tests/generate_test_audio.py  (requires: pip install gtts)
"""
import pytest
from pathlib import Path
from datetime import date

SAMPLE_AUDIO = Path(__file__).parent / "sample.mp3"


@pytest.fixture
def tmp_vault(tmp_path):
    (tmp_path / "10_Calendar" / "13_Meetings").mkdir(parents=True)
    return tmp_path


@pytest.mark.skipif(not SAMPLE_AUDIO.exists(), reason="sample.mp3 없음 — generate_test_audio.py 실행 필요")
def test_full_pipeline(tmp_vault, monkeypatch):
    import config
    monkeypatch.setattr(config, "VAULT_PATH", tmp_vault)
    monkeypatch.setattr(config, "MEETINGS_FOLDER", "10_Calendar/13_Meetings")

    from pipeline.transcriber import transcribe
    from pipeline.analyzer import analyze_transcript
    from pipeline.note_builder import NoteData, build_meeting_note, build_transcript_note
    from pipeline.vault_writer import VaultWriter

    # 1. 전사
    t = transcribe(SAMPLE_AUDIO)
    assert t["segments"], "전사 세그먼트가 비어있음"
    assert t["duration"], "duration이 비어있음"

    # 2. 분석
    a = analyze_transcript(t["full_text"])
    assert isinstance(a["purpose"], str)

    # 3. 노트 생성
    nd = NoteData(
        date=date.today(),
        title="통합 테스트",
        audio_filename="sample.mp3",
        duration=t["duration"],
        speakers=sorted({s["speaker"] for s in t["segments"]}),
        purpose=a["purpose"],
        discussion=a["discussion"],
        decisions=a["decisions"],
        action_items=a["action_items"],
        follow_up=a["follow_up"],
        transcript=t["segments"],
    )

    # 4. 저장
    res = VaultWriter(tmp_vault, "10_Calendar/13_Meetings").save(
        nd, build_meeting_note(nd), build_transcript_note(nd)
    )
    assert Path(res["meeting_path"]).exists()
    assert Path(res["transcript_path"]).exists()
    assert res["meeting_uri"].startswith("obsidian://open")

    print("\n=== 생성된 회의 노트 ===")
    print(Path(res["meeting_path"]).read_text(encoding="utf-8"))
