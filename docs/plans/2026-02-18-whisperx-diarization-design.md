# WhisperX 화자 분리 개선 Design

**Goal:** faster-whisper + 실패하는 pyannote 조합을 WhisperX 단일 패키지로 교체해 화자 분리가 실제로 동작하도록 한다.

**Architecture:** WhisperX는 전사(faster-whisper 기반) + 단어 정렬(wav2vec2) + 화자 분리(pyannote) 세 단계를 통합한다. 단어 단위 타임스탬프를 기반으로 화자를 할당하므로 기존 세그먼트 단위보다 매핑 정확도가 높다.

**Tech Stack:** whisperx 3.8.x, pyannote.audio (whisperx 의존성), cuBLAS DLL (기존 설치), HuggingFace token (기존 .env)

---

## 변경 범위

- **수정**: `pipeline/transcriber.py` — `_transcribe_local()` 및 관련 헬퍼 교체
- **무변경**: `main.py`, `pipeline/analyzer.py`, `pipeline/note_builder.py`, `pipeline/vault_writer.py`, `static/index.html`, `config.py`
- **출력 인터페이스 유지**: `segments` 리스트의 `timestamp / speaker / text` 키 그대로

## 사전 준비 (1회)

1. HuggingFace 라이선스 수락:
   - https://hf.co/pyannote/speaker-diarization-3.1 → Agree and access repository
   - https://hf.co/pyannote/segmentation-3.0 → Agree and access repository
2. 패키지 설치: `pip install whisperx`

## 구현 설계

### `_transcribe_local()` 교체

```python
def _transcribe_local(audio_path: Path, on_progress=None) -> dict:
    import whisperx

    device, compute_type = _detect_device()
    if on_progress:
        on_progress(0, f"모델 로딩 중... ({device.upper()})")

    # 1. 전사
    model = whisperx.load_model(
        config.WHISPER_MODEL, device,
        compute_type=compute_type, language="ko"
    )
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=16)
    # progress ~40%

    # 2. 단어 단위 정렬
    if on_progress:
        on_progress(50, "단어 정렬 중...")
    align_model, metadata = whisperx.load_align_model(language_code="ko", device=device)
    result = whisperx.align(result["segments"], align_model, metadata, audio, device)
    # progress ~70%

    # 3. 화자 분리 (선택적 - 실패해도 계속)
    diarize_segments = None
    try:
        if on_progress:
            on_progress(80, "화자 분리 중...")
        diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=config.HF_TOKEN, device=device
        )
        diarize_segments = diarize_model(audio_path)
        result = whisperx.assign_word_speakers(diarize_segments, result)
    except Exception as e:
        print(f"[Transcriber] 화자 분리 생략: {e}")

    # 4. segments 변환 (기존 인터페이스 유지)
    segments = _convert_whisperx_segments(result["segments"])
    full_text = " ".join(s["text"] for s in segments)
    duration_sec = audio.shape[-1] / whisperx.audio.SAMPLE_RATE

    return {
        "segments": segments,
        "full_text": full_text,
        "duration": _fmt(duration_sec),
        "method": "local",
    }
```

### `_convert_whisperx_segments()` 헬퍼

```python
def _convert_whisperx_segments(wx_segments: list) -> list:
    """WhisperX 세그먼트를 기존 {timestamp, speaker, text} 형식으로 변환."""
    speaker_map: dict[str, str] = {}
    counter = [0]

    def label(raw: str) -> str:
        if raw not in speaker_map:
            speaker_map[raw] = f"Speaker {chr(ord('A') + counter[0])}"
            counter[0] += 1
        return speaker_map[raw]

    result = []
    for seg in wx_segments:
        raw_speaker = seg.get("speaker", "SPEAKER_00")
        result.append({
            "timestamp": _fmt(seg.get("start", 0)),
            "speaker": label(raw_speaker),
            "text": seg.get("text", "").strip(),
        })
    return result
```

## 에러 처리

| 단계 | 실패 시 동작 |
|------|------------|
| whisperx 미설치 | OpenAI API 폴백 (기존과 동일) |
| 단어 정렬 실패 | 정렬 없이 세그먼트 단위로 계속 |
| 화자 분리 실패 | 모두 Speaker A로 계속 (현재와 동일) |

## 진행률 매핑

| 단계 | progress |
|------|---------|
| 모델 로딩 | 0% |
| 전사 완료 | 40% |
| 단어 정렬 | 50→70% |
| 화자 분리 | 80→90% |
| 완료 | 95% |

## 테스트 계획

- 기존 18개 단위 테스트: 인터페이스 유지이므로 **무변경 통과** 목표
- 수동 테스트: 실제 회의 파일로 Speaker A/B 분리 확인
