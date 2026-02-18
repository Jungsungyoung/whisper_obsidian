# WhisperX 화자 분리 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `pipeline/transcriber.py`의 `_transcribe_local()`을 WhisperX로 교체해 화자 분리가 실제로 동작하도록 한다.

**Architecture:** `_transcribe_local()` 내부를 whisperx 3단계(전사 → 단어정렬 → 화자분리)로 교체. 출력 인터페이스(`segments` 리스트의 `timestamp/speaker/text`)는 그대로 유지해 다른 모듈 무변경. `_convert_whisperx_segments()` 헬퍼 함수 추가. 사용하지 않는 `_merge_fw()`, `_merge()` 제거.

**Tech Stack:** whisperx 3.8.x, pyannote.audio (whisperx 의존성), ctranslate2 (기존 CUDA 지원), HuggingFace token (`.env`의 `HF_TOKEN`)

---

## 사전 조건 확인

- `D:\cuda_libs\dlls`의 cuBLAS DLL 설치 완료 ✅
- `.env`에 `HF_TOKEN` 설정됨 ✅
- **필수**: HuggingFace에서 pyannote 모델 라이선스 수락 (미완료 시 화자분리 실패하지만 전사는 동작)
  - https://hf.co/pyannote/speaker-diarization-3.1 → "Agree and access repository"
  - https://hf.co/pyannote/segmentation-3.0 → "Agree and access repository"

---

### Task 1: whisperx 설치 및 import 검증

**Files:**
- 변경 없음 (설치 확인만)

**Step 1: whisperx 설치**

```bash
pip install whisperx
```

**Step 2: import 검증**

```bash
python -c "import whisperx; print(whisperx.__version__)"
```
Expected: `3.8.x` 버전 출력 (오류 없음)

**Step 3: whisperx audio API 확인**

```bash
python -c "import whisperx; print(whisperx.audio.SAMPLE_RATE)"
```
Expected: `16000`

**Step 4: commit (설치 기록용 requirements 업데이트)**

`requirements.txt` 파일 끝에 추가:
```
whisperx==3.8.1
```

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Idea\meetscribe
git add requirements.txt
git commit -m "feat: add whisperx dependency"
```

---

### Task 2: `_convert_whisperx_segments()` TDD

**Files:**
- Modify: `tests/test_integration.py` (새 테스트 추가)
- Modify: `pipeline/transcriber.py` (헬퍼 함수 추가)

**Step 1: 실패하는 테스트 작성**

`tests/test_integration.py` 파일 상단 import 아래에 추가:

```python
# tests/test_integration.py 하단에 추가

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
```

**Step 2: 실패 확인**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Idea\meetscribe
python -m pytest tests/test_integration.py::test_convert_whisperx_segments_with_speakers -v
```
Expected: `FAILED` — `ImportError: cannot import name '_convert_whisperx_segments'`

**Step 3: `_convert_whisperx_segments()` 구현**

`pipeline/transcriber.py`의 `_merge()` 함수 바로 위에 추가:

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

**Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_integration.py::test_convert_whisperx_segments_with_speakers tests/test_integration.py::test_convert_whisperx_segments_no_speaker tests/test_integration.py::test_convert_whisperx_segments_empty_text_stripped -v
```
Expected: `3 passed`

**Step 5: 기존 18개 테스트도 여전히 통과 확인**

```bash
python -m pytest tests/ -v --ignore=tests/test_integration.py
```
Expected: `17 passed` (note_builder 8 + vault_writer 4 + analyzer 6 — test_full_pipeline은 sample.mp3 필요)

**Step 6: commit**

```bash
git add pipeline/transcriber.py tests/test_integration.py
git commit -m "feat: add _convert_whisperx_segments helper + 3 unit tests"
```

---

### Task 3: `_transcribe_local()` WhisperX로 교체

**Files:**
- Modify: `pipeline/transcriber.py:33-80` (함수 전체 교체)

**Step 1: 현재 `_transcribe_local()` 전체를 아래로 교체**

`pipeline/transcriber.py`의 `_transcribe_local()` 함수를 다음으로 교체:

```python
def _transcribe_local(audio_path: Path, on_progress=None) -> dict:
    import whisperx

    device, compute_type = _detect_device()
    if on_progress:
        on_progress(0, f"모델 로딩 중... ({device.upper()})")
    print(f"[Transcriber] WhisperX device={device}, compute_type={compute_type}")

    # batch_size: GPU는 16, CPU는 4 (메모리 절약)
    batch_size = 16 if device == "cuda" else 4

    # 1. 전사
    model = whisperx.load_model(
        config.WHISPER_MODEL, device,
        compute_type=compute_type, language="ko"
    )
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=batch_size)
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
        diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=config.HF_TOKEN, device=device
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
```

**Step 2: 사용하지 않는 코드 제거**

`pipeline/transcriber.py`에서 다음 함수들 삭제:
- `_merge_fw()` (line 114-138): 더 이상 사용 안 함
- `_merge()` (line 141-165): 더 이상 사용 안 함

**Step 3: 파일 상태 최종 확인**

교체 후 `pipeline/transcriber.py`의 함수 목록:
- `transcribe()` — 퍼블릭 엔트리포인트 (무변경)
- `_detect_device()` — CUDA 감지 (무변경)
- `_transcribe_local()` — ★ WhisperX로 교체
- `_transcribe_api()` — OpenAI API 폴백 (무변경)
- `_convert_whisperx_segments()` — ★ 새로 추가
- `_fmt()` — 시간 포맷터 (무변경)

**Step 4: 단위 테스트 전체 재실행**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Idea\meetscribe
python -m pytest tests/test_note_builder.py tests/test_vault_writer.py tests/test_analyzer.py tests/test_integration.py::test_convert_whisperx_segments_with_speakers tests/test_integration.py::test_convert_whisperx_segments_no_speaker tests/test_integration.py::test_convert_whisperx_segments_empty_text_stripped -v
```
Expected: `21 passed`

**Step 5: commit**

```bash
git add pipeline/transcriber.py
git commit -m "feat: replace _transcribe_local with WhisperX (transcription + alignment + diarization)"
```

---

### Task 4: 통합 테스트 — 실제 파일로 화자 분리 확인

**Files:**
- 변경 없음 (수동 검증)

**Step 1: 서버 실행**

```bash
run.bat
```
브라우저에서 http://localhost:8765 열기

**Step 2: 실제 회의 파일 업로드**

파일: `C:\Users\Admin\OneDrive\문서\Obsidian Vault\00_Inbox\음성 250703_095450.m4a`

기대 동작:
- 진행률: 모델 로딩(0%) → 전사 완료(40%) → 단어 정렬(70%) → 화자 분리(90%) → 완료(100%)
- 생성된 노트에서 Speaker A / Speaker B 구분이 실제로 나타남

**Step 3: pyannote 권한 실패 시 체크리스트**

서버 로그에 `화자 분리 생략: 403` 또는 `gated repo` 오류가 나오면:
1. https://hf.co/pyannote/speaker-diarization-3.1 접속 → 로그인 → "Agree and access repository" 클릭
2. https://hf.co/pyannote/segmentation-3.0 접속 → 동일하게 수락
3. `.env`의 `HF_TOKEN`이 해당 HuggingFace 계정의 토큰인지 확인
4. 서버 재시작 후 재시도

**Step 4: 성공 확인**

생성된 `[전사] 2026-02-18 *.md` 파일 열어서:
```markdown
| 00:00 | Speaker A | 안녕하세요... |
| 00:15 | Speaker B | 네, 그렇습니다... |
| 00:30 | Speaker A | ...
```
Speaker A와 B가 교차 등장하면 화자 분리 성공.

**Step 5: final commit**

```bash
git add .
git commit -m "feat: WhisperX integration complete - speaker diarization working"
```

---

## 예상 결과

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 화자 분리 | 항상 Speaker A | Speaker A / B / C 구분 |
| 타임스탬프 정확도 | 세그먼트 단위 | 단어 단위 |
| 전사 속도 (GPU) | 37초/17분 | 비슷 (whisperx도 faster-whisper 기반) |
| 단위 테스트 | 18개 통과 | 21개 통과 |
