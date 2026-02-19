from pathlib import Path
import config


def _build_initial_prompt(domain_vocab: str, context: str) -> str:
    """DOMAIN_VOCAB + 회의 맥락을 합성해 Whisper initial_prompt 생성."""
    parts = [p for p in [domain_vocab.strip(), context.strip()] if p]
    return ". ".join(parts)


def transcribe(audio_path: Path, on_progress=None, context: str = "") -> dict:
    """
    오디오 파일을 전사. 화자 분리 포함.
    로컬 Whisper + pyannote 우선, 실패 시 OpenAI API 폴백.
    Returns:
        segments: [{"timestamp": "MM:SS", "speaker": "Speaker A", "text": "..."}]
        full_text: str
        duration:  str (MM:SS 또는 HH:MM:SS)
        method:    "local" | "api"
    """
    initial_prompt = _build_initial_prompt(config.DOMAIN_VOCAB, context)
    try:
        return _transcribe_local(audio_path, on_progress, initial_prompt)
    except RuntimeError:
        raise  # 다운로드 실패 등 치명적 오류는 폴백 없이 즉시 전파
    except Exception as e:
        print(f"[Transcriber] 로컬 Whisper 실패: {e}. OpenAI API로 폴백.")
        return _transcribe_api(audio_path)


def is_cuda_available() -> bool:
    """CUDA 사용 가능 여부 확인."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _detect_device() -> tuple[str, str]:
    """CUDA 사용 가능 여부를 확인해 (device, compute_type) 반환."""
    if is_cuda_available():
        return "cuda", "float16"
    return "cpu", "int8"


def _transcribe_local(audio_path: Path, on_progress=None, initial_prompt: str = "") -> dict:
    import whisperx
    import whisperx.audio

    device, compute_type = _detect_device()
    model_name = config.WHISPER_MODEL
    if on_progress:
        on_progress(0, f"모델 로딩 중... ({device.upper()}, {model_name})")
    print(f"[Transcriber] WhisperX device={device}, compute_type={compute_type}, model={model_name}")

    # batch_size: GPU는 16, CPU는 4 (메모리 절약)
    batch_size = 16 if device == "cuda" else 4

    # 1. 전사
    try:
        model = whisperx.load_model(
            model_name, device,
            compute_type=compute_type, language="ko"
        )
    except Exception as e:
        err_msg = str(e)
        if "Connection" in err_msg or "download" in err_msg.lower() or "HTTP" in err_msg:
            raise RuntimeError(
                f"'{model_name}' 모델 다운로드 실패 (인터넷 연결 필요): {e}\n"
                "설정에서 더 작은 모델(base/small)을 선택하거나 네트워크를 확인하세요."
            )
        if "out of memory" in err_msg.lower() and device == "cuda":
            print(f"[Transcriber] CUDA OOM ({compute_type}), int8로 재시도...")
            if on_progress:
                on_progress(5, f"VRAM 부족 — int8 모드로 재시도 중... ({model_name})")
            compute_type = "int8"
            model = whisperx.load_model(
                model_name, device,
                compute_type=compute_type, language="ko"
            )
        else:
            raise
    audio = whisperx.load_audio(str(audio_path))
    transcribe_kwargs = {"batch_size": batch_size}
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt
    try:
        result = model.transcribe(audio, **transcribe_kwargs)
    except TypeError as e:
        if "initial_prompt" in str(e):
            print(f"[Transcriber] 이 WhisperX 버전은 initial_prompt 미지원 — 프롬프트 없이 재시도")
            transcribe_kwargs.pop("initial_prompt")
            result = model.transcribe(audio, **transcribe_kwargs)
        else:
            raise
    if on_progress:
        on_progress(40, "전사 완료, 단어 정렬 중...")

    # 2. 단어 단위 정렬 (speaker 매핑 정확도 향상)
    try:
        align_model, metadata = whisperx.load_align_model(
            language_code="ko", device=device
        )
        result = whisperx.align(
            result["segments"], align_model, metadata, audio, device,
            return_char_alignments=False
        )
        if on_progress:
            on_progress(70, "화자 분리 중...")
    except Exception as e:
        print(f"[Transcriber] 단어 정렬 생략: {e}")
        if on_progress:
            on_progress(70, "화자 분리 중...")

    # 3. 화자 분리 (HF 토큰 필요 - 실패해도 계속)
    try:
        from whisperx.diarize import DiarizationPipeline as _DiarizationPipeline
        diarize_model = _DiarizationPipeline(
            token=config.HF_TOKEN, device=device
        )
        diarize_segments = diarize_model(str(audio_path))
        result = whisperx.assign_word_speakers(diarize_segments, result)
        if on_progress:
            on_progress(90, "변환 중...")
    except Exception as e:
        print(f"[Transcriber] 화자 분리 생략: {e}")
        if on_progress:
            on_progress(90, "변환 중...")

    # 4. 기존 인터페이스로 변환
    segments = _convert_whisperx_segments(result["segments"])
    full_text = " ".join(s["text"] for s in segments if s["text"])
    duration_sec = len(audio) / whisperx.audio.SAMPLE_RATE

    return {
        "segments": segments,
        "full_text": full_text,
        "duration": _fmt(duration_sec),
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


def _convert_whisperx_segments(wx_segments: list) -> list:
    """WhisperX 세그먼트를 기존 {timestamp, speaker, text} 형식으로 변환."""
    speaker_map: dict[str, str] = {}
    counter = [0]

    def label(raw: str) -> str:
        if raw not in speaker_map:
            if counter[0] >= 26:
                raise ValueError(f"Speaker count exceeds 26; cannot assign label for '{raw}'")
            speaker_map[raw] = f"Speaker {chr(ord('A') + counter[0])}"
            counter[0] += 1
        return speaker_map[raw]

    result = []
    for seg in wx_segments:
        raw_speaker = seg.get("speaker", "SPEAKER_00")
        result.append({
            "timestamp": _fmt(seg.get("start", 0)),
            "speaker": label(raw_speaker),
            "text": (seg.get("text") or "").strip(),
        })
    return result


def _fmt(seconds: float) -> str:
    """초 → MM:SS 또는 HH:MM:SS"""
    s = int(seconds)
    h, m = divmod(s, 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
