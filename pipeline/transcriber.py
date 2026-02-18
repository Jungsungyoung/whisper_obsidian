from pathlib import Path
import config


def transcribe(audio_path: Path) -> dict:
    """
    오디오 파일을 전사. 화자 분리 포함.
    로컬 Whisper + pyannote 우선, 실패 시 OpenAI API 폴백.
    Returns:
        segments: [{"timestamp": "MM:SS", "speaker": "Speaker A", "text": "..."}]
        full_text: str
        duration:  str (MM:SS 또는 HH:MM:SS)
        method:    "local" | "api"
    """
    try:
        return _transcribe_local(audio_path)
    except Exception as e:
        print(f"[Transcriber] 로컬 Whisper 실패: {e}. OpenAI API로 폴백.")
        return _transcribe_api(audio_path)


def _transcribe_local(audio_path: Path) -> dict:
    import torch
    import whisper
    from pyannote.audio import Pipeline

    model = whisper.load_model(config.WHISPER_MODEL)
    result = model.transcribe(str(audio_path), word_timestamps=True, language="ko")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=config.HF_TOKEN,
    )
    if torch.cuda.is_available():
        pipeline = pipeline.to(torch.device("cuda"))

    diarization = pipeline(str(audio_path))
    segments = _merge(result["segments"], diarization)
    full_text = " ".join(seg["text"].strip() for seg in result["segments"])

    return {
        "segments": segments,
        "full_text": full_text,
        "duration": _fmt(result.get("duration") or 0),
        "method": "local",
    }


def _transcribe_api(audio_path: Path) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            language="ko",
        )

    segments = [
        {
            "timestamp": _fmt(seg.start),
            "speaker": "Speaker A",
            "text": seg.text.strip(),
        }
        for seg in response.segments
    ]
    duration = _fmt(getattr(response, "duration", 0) or 0)

    return {
        "segments": segments,
        "full_text": response.text,
        "duration": duration,
        "method": "api",
    }


def _merge(whisper_segments: list, diarization) -> list:
    """Whisper 세그먼트에 pyannote 화자 레이블 매핑."""
    speaker_map: dict[str, str] = {}
    counter = [0]

    def label(raw: str) -> str:
        if raw not in speaker_map:
            speaker_map[raw] = f"Speaker {chr(ord('A') + counter[0])}"
            counter[0] += 1
        return speaker_map[raw]

    result = []
    for seg in whisper_segments:
        start = seg["start"]
        speaker = "Speaker A"
        for turn, _, raw_label in diarization.itertracks(yield_label=True):
            if turn.start <= start <= turn.end:
                speaker = label(raw_label)
                break
        result.append({
            "timestamp": _fmt(start),
            "speaker": speaker,
            "text": seg["text"].strip(),
        })
    return result


def _fmt(seconds: float) -> str:
    """초 → MM:SS 또는 HH:MM:SS"""
    s = int(seconds)
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
