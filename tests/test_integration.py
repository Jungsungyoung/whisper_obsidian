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


def test_convert_whisperx_segments_with_speakers():
    """WhisperX 세그먼트를 {timestamp, speaker, text} 형식으로 변환."""
    from pipeline.transcriber import _convert_whisperx_segments
    wx_segs = [
        {"start": 0.0,  "end": 3.0,  "text": "안녕하세요", "speaker": "SPEAKER_00"},
        {"start": 3.5,  "end": 7.0,  "text": "반갑습니다", "speaker": "SPEAKER_01"},
        {"start": 7.5,  "end": 10.0, "text": "네 맞아요",  "speaker": "SPEAKER_00"},
    ]
    result = _convert_whisperx_segments(wx_segs)
    assert len(result) == 3
    assert result[0] == {"timestamp": "00:00", "speaker": "Speaker A", "text": "안녕하세요"}
    assert result[1] == {"timestamp": "00:03", "speaker": "Speaker B", "text": "반갑습니다"}
    assert result[2] == {"timestamp": "00:07", "speaker": "Speaker A", "text": "네 맞아요"}


def test_convert_whisperx_segments_no_speaker():
    """speaker 키 없을 때 모두 Speaker A 반환."""
    from pipeline.transcriber import _convert_whisperx_segments
    wx_segs = [
        {"start": 0.0, "end": 2.0, "text": "텍스트"},
    ]
    result = _convert_whisperx_segments(wx_segs)
    assert result[0]["speaker"] == "Speaker A"


def test_convert_whisperx_segments_empty_text_stripped():
    """text 앞뒤 공백 제거 확인."""
    from pipeline.transcriber import _convert_whisperx_segments
    wx_segs = [{"start": 0.0, "end": 1.0, "text": "  공백  ", "speaker": "SPEAKER_00"}]
    result = _convert_whisperx_segments(wx_segs)
    assert result[0]["text"] == "공백"


def test_convert_whisperx_segments_none_text():
    """text 값이 None일 때 빈 문자열 반환."""
    from pipeline.transcriber import _convert_whisperx_segments
    wx_segs = [{"start": 0.0, "end": 1.0, "text": None, "speaker": "SPEAKER_00"}]
    result = _convert_whisperx_segments(wx_segs)
    assert result[0]["text"] == ""
