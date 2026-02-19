# MeetScribe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 회의 녹음 파일(mp3/wav/m4a)을 FastAPI 웹 UI로 업로드하면 Whisper로 전사하고 GPT-4o-mini로 분석해, 기존 Obsidian Vault의 13_Meetings 폴더에 [회의]/[전사] 마크다운 노트를 자동 생성한다.

**Architecture:** FastAPI 백엔드가 파일 업로드를 받아 백그라운드 태스크로 처리한다. pyannote.audio가 화자를 분리하고 Whisper(로컬 우선 → OpenAI API 폴백)가 전사한다. GPT-4o-mini가 목적/주요논의/결정사항/액션아이템을 추출하고 기존 Meeting Note 템플릿과 호환되는 마크다운을 생성해 Vault에 직접 저장한다.

**Tech Stack:** Python 3.10+, FastAPI, openai-whisper, pyannote.audio, openai, pathlib, uvicorn

---

## 사전 준비 (코드 작성 전)

### HuggingFace 토큰 설정 (화자 분리용)
1. https://huggingface.co 계정 생성
2. https://hf.co/pyannote/speaker-diarization-3.1 → Accept License
3. https://hf.co/pyannote/segmentation-3.0 → Accept License
4. https://hf.co/settings/tokens → Access Token 생성 (Read)
5. 토큰을 `.env` 파일에 저장 (Task 1에서 설정)

---

## Task 1: 프로젝트 초기 설정

**Files:**
- Create: `meetscribe/requirements.txt`
- Create: `meetscribe/.env.example`
- Create: `meetscribe/config.py`
- Create: `meetscribe/tests/__init__.py`

**Step 1: 프로젝트 디렉토리 생성**

```bash
mkdir -p meetscribe/pipeline
mkdir -p meetscribe/static
mkdir -p meetscribe/tests
mkdir -p meetscribe/uploads
```

**Step 2: `meetscribe/requirements.txt` 작성**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
openai-whisper==20240930
openai==1.40.0
pyannote.audio==3.3.2
python-dotenv==1.0.1
torch>=2.0.0
torchaudio>=2.0.0
```

**Step 3: `meetscribe/.env.example` 작성**

```
OPENAI_API_KEY=sk-...
HF_TOKEN=hf_...
WHISPER_MODEL=base
LLM_MODEL=gpt-4o-mini
VAULT_PATH=C:\Users\Admin\OneDrive\문서\Obsidian Vault
MEETINGS_FOLDER=10_Calendar/13_Meetings
```

**Step 4: `.env` 파일 생성 (실제 키 입력)**

```bash
cp meetscribe/.env.example meetscribe/.env
# .env 파일을 에디터로 열어 실제 값 입력
```

**Step 5: `meetscribe/config.py` 작성**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
HF_TOKEN: str = os.environ["HF_TOKEN"]
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
VAULT_PATH: Path = Path(os.environ["VAULT_PATH"])
MEETINGS_FOLDER: str = os.getenv("MEETINGS_FOLDER", "10_Calendar/13_Meetings")
UPLOAD_DIR: Path = Path(__file__).parent / "uploads"

def validate_config() -> None:
    """앱 시작 시 설정값 검증"""
    if not VAULT_PATH.exists():
        raise RuntimeError(f"Vault 경로를 찾을 수 없습니다: {VAULT_PATH}")
    meetings_path = VAULT_PATH / MEETINGS_FOLDER
    if not meetings_path.exists():
        meetings_path.mkdir(parents=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
```

**Step 6: `meetscribe/tests/__init__.py` 생성 (빈 파일)**

**Step 7: 의존성 설치**

```bash
cd meetscribe
pip install -r requirements.txt
```

Expected: 패키지 설치 완료 (torch 포함, 수분 소요)

**Step 8: 설정 검증 테스트**

```bash
python -c "from config import validate_config; validate_config(); print('설정 OK')"
```

Expected: `설정 OK`

**Step 9: Commit**

```bash
git init
git add requirements.txt .env.example config.py tests/ uploads/.gitkeep
echo ".env" >> .gitignore
echo "uploads/" >> .gitignore
echo "__pycache__/" >> .gitignore
git commit -m "feat: project setup - config and dependencies"
```

---

## Task 2: NoteBuilder 모듈 (TDD 선행)

NoteBuilder는 순수 함수라 테스트가 쉽다. 먼저 테스트 작성.

**Files:**
- Create: `meetscribe/tests/test_note_builder.py`
- Create: `meetscribe/pipeline/note_builder.py`

**Step 1: 테스트 작성**

`meetscribe/tests/test_note_builder.py`:

```python
import pytest
from datetime import date
from pipeline.note_builder import build_meeting_note, build_transcript_note, NoteData

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
    from pipeline.note_builder import get_filenames
    meeting_fn, transcript_fn = get_filenames(SAMPLE_DATA)
    assert meeting_fn == "[회의] 2026-02-18 스프린트 리뷰.md"
    assert transcript_fn == "[전사] 2026-02-18 스프린트 리뷰.md"
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
cd meetscribe
python -m pytest tests/test_note_builder.py -v
```

Expected: FAIL — `ModuleNotFoundError: pipeline.note_builder`

**Step 3: `meetscribe/pipeline/__init__.py` 생성 (빈 파일)**

**Step 4: `meetscribe/pipeline/note_builder.py` 구현**

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class NoteData:
    date: date
    title: str
    audio_filename: str
    duration: str
    speakers: list[str]
    purpose: str
    discussion: list[str]
    decisions: list[str]
    action_items: list[str]
    follow_up: list[str]
    transcript: list[dict]  # {"timestamp": str, "speaker": str, "text": str}
    project: str = ""


def get_filenames(data: NoteData) -> tuple[str, str]:
    date_str = data.date.strftime("%Y-%m-%d")
    meeting = f"[회의] {date_str} {data.title}.md"
    transcript = f"[전사] {date_str} {data.title}.md"
    return meeting, transcript


def build_meeting_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    _, transcript_filename = get_filenames(data)
    transcript_link = transcript_filename[:-3]  # .md 제거

    participants_yaml = "\n".join(f"  - {s}" for s in data.speakers)
    discussion_items = "\n".join(f"- {d}" for d in data.discussion)
    decision_items = "\n".join(f"- {d}" for d in data.decisions)
    action_items = "\n".join(f"- [ ] {a}" for a in data.action_items)
    follow_up_items = "\n".join(f"- {f}" for f in data.follow_up)

    return f"""---
date: {date_str}
type: meeting
project: "{data.project}"
participants:
{participants_yaml}
tags:
  - meeting
  - ai-transcribed
audio: "{data.audio_filename}"
duration: "{data.duration}"
---

# [회의] {date_str} {data.title}

> [!note] AI 자동 생성
> Whisper + LLM으로 자동 생성. 전체 전사: [[{transcript_link}]]

## 목적
{data.purpose}

## 주요 논의
{discussion_items}

## 결정 사항
{decision_items}

## Action Items
{action_items}

## 후속 질문
{follow_up_items}
"""


def build_transcript_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    meeting_filename, _ = get_filenames(data)
    meeting_link = meeting_filename[:-3]

    lines = "\n".join(
        f"**[{seg['timestamp']}] {seg['speaker']}:** {seg['text']}"
        for seg in data.transcript
    )

    return f"""---
date: {date_str}
type: meeting-transcript
tags:
  - transcript
---

# [전사] {date_str} {data.title}

> 요약: [[{meeting_link}]]

{lines}
"""
```

**Step 5: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_note_builder.py -v
```

Expected: 7개 PASS

**Step 6: Commit**

```bash
git add pipeline/__init__.py pipeline/note_builder.py tests/test_note_builder.py
git commit -m "feat: note_builder - meeting and transcript markdown generation"
```

---

## Task 3: VaultWriter 모듈 (TDD 선행)

**Files:**
- Create: `meetscribe/tests/test_vault_writer.py`
- Create: `meetscribe/pipeline/vault_writer.py`

**Step 1: 테스트 작성**

`meetscribe/tests/test_vault_writer.py`:

```python
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
    meeting_note = build_meeting_note(SAMPLE_DATA)
    transcript_note = build_transcript_note(SAMPLE_DATA)
    meeting_fn, transcript_fn = get_filenames(SAMPLE_DATA)

    writer.save(SAMPLE_DATA, meeting_note, transcript_note)

    assert (tmp_path / "Meetings" / meeting_fn).exists()
    assert (tmp_path / "Meetings" / transcript_fn).exists()


def test_meeting_note_content_is_correct(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="Meetings")
    meeting_note = build_meeting_note(SAMPLE_DATA)
    transcript_note = build_transcript_note(SAMPLE_DATA)
    meeting_fn, _ = get_filenames(SAMPLE_DATA)

    writer.save(SAMPLE_DATA, meeting_note, transcript_note)

    content = (tmp_path / "Meetings" / meeting_fn).read_text(encoding="utf-8")
    assert "## 목적" in content
    assert "테스트" in content


def test_returns_obsidian_uri(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="Meetings")
    meeting_note = build_meeting_note(SAMPLE_DATA)
    transcript_note = build_transcript_note(SAMPLE_DATA)

    result = writer.save(SAMPLE_DATA, meeting_note, transcript_note)

    assert result["meeting_uri"].startswith("obsidian://open")
    assert result["transcript_uri"].startswith("obsidian://open")


def test_creates_meetings_folder_if_missing(tmp_path):
    writer = VaultWriter(vault_path=tmp_path, meetings_folder="NewFolder/Meetings")
    meeting_note = build_meeting_note(SAMPLE_DATA)
    transcript_note = build_transcript_note(SAMPLE_DATA)

    writer.save(SAMPLE_DATA, meeting_note, transcript_note)

    assert (tmp_path / "NewFolder" / "Meetings").exists()
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_vault_writer.py -v
```

Expected: FAIL — `ModuleNotFoundError: pipeline.vault_writer`

**Step 3: `meetscribe/pipeline/vault_writer.py` 구현**

```python
from pathlib import Path
from urllib.parse import quote
from pipeline.note_builder import NoteData, get_filenames


class VaultWriter:
    def __init__(self, vault_path: Path, meetings_folder: str):
        self.vault_path = Path(vault_path)
        self.meetings_path = self.vault_path / meetings_folder

    def save(self, data: NoteData, meeting_note: str, transcript_note: str) -> dict:
        self.meetings_path.mkdir(parents=True, exist_ok=True)

        meeting_fn, transcript_fn = get_filenames(data)
        meeting_path = self.meetings_path / meeting_fn
        transcript_path = self.meetings_path / transcript_fn

        meeting_path.write_text(meeting_note, encoding="utf-8")
        transcript_path.write_text(transcript_note, encoding="utf-8")

        vault_name = self.vault_path.name
        meeting_uri = self._obsidian_uri(vault_name, meeting_fn)
        transcript_uri = self._obsidian_uri(vault_name, transcript_fn)

        return {
            "meeting_path": str(meeting_path),
            "transcript_path": str(transcript_path),
            "meeting_uri": meeting_uri,
            "transcript_uri": transcript_uri,
        }

    def _obsidian_uri(self, vault_name: str, filename: str) -> str:
        encoded_vault = quote(vault_name)
        encoded_file = quote(filename.replace(".md", ""))
        return f"obsidian://open?vault={encoded_vault}&file={encoded_file}"
```

**Step 4: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_vault_writer.py -v
```

Expected: 4개 PASS

**Step 5: Commit**

```bash
git add pipeline/vault_writer.py tests/test_vault_writer.py
git commit -m "feat: vault_writer - save notes and return obsidian URIs"
```

---

## Task 4: Analyzer 모듈 (LLM 분석)

**Files:**
- Create: `meetscribe/tests/test_analyzer.py`
- Create: `meetscribe/pipeline/analyzer.py`

**Step 1: 테스트 작성 (파싱 로직만 단위 테스트)**

`meetscribe/tests/test_analyzer.py`:

```python
import pytest
from pipeline.analyzer import parse_llm_response


SAMPLE_RESPONSE = """
PURPOSE: 스프린트 리뷰 및 3월 배포 계획 논의

DISCUSSION:
- ECS V1.2 개발 진행률 75% 완료
- 해상 시험 일정 조정 논의 (3/15 → 3/20)
- Autopilot 알고리즘 파라미터 튜닝 필요

DECISIONS:
- 해상 시험 3월 20일 확정
- 추가 문서화 마감: 3월 5일

ACTION_ITEMS:
- ECS V1.2 코드 유닛 테스트 완료 (Speaker B, ~02/25)
- 추가 문서화 작성 시작 (Speaker A, ~02/28)

FOLLOW_UP:
- Autopilot 시뮬레이션 파라미터 최적화 방법 조사
"""


def test_parses_purpose():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert result["purpose"] == "스프린트 리뷰 및 3월 배포 계획 논의"


def test_parses_discussion_items():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["discussion"]) == 3
    assert "ECS V1.2 개발 진행률 75% 완료" in result["discussion"]


def test_parses_decisions():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["decisions"]) == 2


def test_parses_action_items():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["action_items"]) == 2
    assert "ECS V1.2 코드 유닛 테스트 완료 (Speaker B, ~02/25)" in result["action_items"]


def test_parses_follow_up():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["follow_up"]) == 1


def test_handles_empty_sections():
    minimal = """
PURPOSE: 간단한 미팅

DISCUSSION:
- 항목 하나

DECISIONS:

ACTION_ITEMS:

FOLLOW_UP:
"""
    result = parse_llm_response(minimal)
    assert result["purpose"] == "간단한 미팅"
    assert result["decisions"] == []
    assert result["action_items"] == []
```

**Step 2: 테스트 실행 (실패 확인)**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: FAIL

**Step 3: `meetscribe/pipeline/analyzer.py` 구현**

```python
import re
from openai import OpenAI
import config


SYSTEM_PROMPT = """당신은 회의록 분석 전문가입니다.
주어진 회의 전사본을 분석해서 다음 형식으로 정확히 출력하세요.
각 섹션의 항목은 '- '로 시작하는 bullet point로 작성하세요.

PURPOSE: [회의 목적 한 줄]

DISCUSSION:
- [주요 논의 항목 1]
- [주요 논의 항목 2]

DECISIONS:
- [결정 사항 1]

ACTION_ITEMS:
- [할 일 내용 (담당자, ~마감일)]

FOLLOW_UP:
- [후속 질문이나 확인 필요 사항]

항목이 없으면 해당 섹션은 비워두세요."""


def analyze_transcript(transcript_text: str) -> dict:
    """LLM으로 전사 텍스트 분석. config에서 API 키와 모델 로드."""
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 회의 내용을 분석해주세요:\n\n{transcript_text}"},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    return parse_llm_response(raw)


def parse_llm_response(response: str) -> dict:
    """LLM 응답 텍스트를 파싱해 구조화된 딕셔너리로 변환."""
    sections = {
        "purpose": "",
        "discussion": [],
        "decisions": [],
        "action_items": [],
        "follow_up": [],
    }

    # PURPOSE (단일 라인)
    purpose_match = re.search(r"PURPOSE:\s*(.+)", response)
    if purpose_match:
        sections["purpose"] = purpose_match.group(1).strip()

    # 섹션별 bullet 파싱
    section_map = {
        "DISCUSSION": "discussion",
        "DECISIONS": "decisions",
        "ACTION_ITEMS": "action_items",
        "FOLLOW_UP": "follow_up",
    }

    for section_key, dict_key in section_map.items():
        pattern = rf"{section_key}:\s*\n((?:- .+\n?)*)"
        match = re.search(pattern, response)
        if match:
            items = re.findall(r"- (.+)", match.group(1))
            sections[dict_key] = [item.strip() for item in items if item.strip()]

    return sections
```

**Step 4: 테스트 재실행 (통과 확인)**

```bash
python -m pytest tests/test_analyzer.py -v
```

Expected: 7개 PASS

**Step 5: Commit**

```bash
git add pipeline/analyzer.py tests/test_analyzer.py
git commit -m "feat: analyzer - LLM transcript analysis and response parsing"
```

---

## Task 5: Transcriber 모듈

> 참고: Whisper와 pyannote는 실제 오디오 파일이 필요해 단위 테스트가 어렵다. 이 태스크는 구현 후 수동 통합 테스트.

**Files:**
- Create: `meetscribe/pipeline/transcriber.py`

**Step 1: `meetscribe/pipeline/transcriber.py` 구현**

```python
import os
import tempfile
from pathlib import Path
from typing import Optional
import torch

import config


def transcribe(audio_path: Path) -> dict:
    """
    오디오 파일을 전사. 화자 분리 포함.
    Returns: {
        "segments": [{"timestamp": "HH:MM:SS", "speaker": "Speaker A", "text": "..."}],
        "full_text": str,
        "duration": str,
        "method": "local" | "api"
    }
    """
    try:
        return _transcribe_local(audio_path)
    except Exception as e:
        print(f"[Transcriber] 로컬 Whisper 실패: {e}. OpenAI API로 폴백.")
        return _transcribe_api(audio_path)


def _transcribe_local(audio_path: Path) -> dict:
    """로컬 Whisper + pyannote 화자 분리"""
    import whisper
    from pyannote.audio import Pipeline

    # 1. Whisper 전사 (word-level timestamps)
    model = whisper.load_model(config.WHISPER_MODEL)
    result = model.transcribe(str(audio_path), word_timestamps=True, language="ko")

    # 2. pyannote 화자 분리
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=config.HF_TOKEN
    )
    if torch.cuda.is_available():
        pipeline = pipeline.to(torch.device("cuda"))

    diarization = pipeline(str(audio_path))

    # 3. Whisper 세그먼트 + 화자 매핑
    segments = _merge_transcript_with_diarization(
        result["segments"], diarization
    )

    duration = _format_duration(result.get("duration", 0))
    full_text = " ".join(seg["text"] for seg in result["segments"])

    return {
        "segments": segments,
        "full_text": full_text,
        "duration": duration,
        "method": "local",
    }


def _transcribe_api(audio_path: Path) -> dict:
    """OpenAI Whisper API 폴백 (화자 분리 없음, Speaker A만 사용)"""
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

    segments = []
    for seg in response.segments:
        ts = _format_duration(seg.start)
        segments.append({
            "timestamp": ts,
            "speaker": "Speaker A",
            "text": seg.text.strip(),
        })

    full_text = response.text
    duration = _format_duration(response.duration if hasattr(response, "duration") else 0)

    return {
        "segments": segments,
        "full_text": full_text,
        "duration": duration,
        "method": "api",
    }


def _merge_transcript_with_diarization(whisper_segments: list, diarization) -> list:
    """Whisper 세그먼트와 pyannote 화자 레이블 매핑"""
    # pyannote 화자 ID를 Speaker A, B, ... 로 정규화
    speaker_map = {}
    label_counter = [0]

    def get_speaker_label(raw_label: str) -> str:
        if raw_label not in speaker_map:
            letter = chr(ord("A") + label_counter[0])
            speaker_map[raw_label] = f"Speaker {letter}"
            label_counter[0] += 1
        return speaker_map[raw_label]

    segments = []
    for seg in whisper_segments:
        start = seg["start"]
        # 해당 타임스탬프에서 발화 중인 화자 찾기
        speaker = "Speaker A"
        for turn, _, label in diarization.itertracks(yield_label=True):
            if turn.start <= start <= turn.end:
                speaker = get_speaker_label(label)
                break

        segments.append({
            "timestamp": _format_duration(start),
            "speaker": speaker,
            "text": seg["text"].strip(),
        })

    return segments


def _format_duration(seconds: float) -> str:
    """초 → HH:MM:SS 형식"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
```

**Step 2: 수동 테스트 (짧은 오디오 파일로)**

```bash
python -c "
from pathlib import Path
from pipeline.transcriber import transcribe
result = transcribe(Path('tests/sample.mp3'))  # 짧은 테스트 파일 필요
print('방법:', result['method'])
print('길이:', result['duration'])
print('세그먼트:', result['segments'][:2])
"
```

> 참고: `tests/sample.mp3` 파일이 없으면 짧은 한국어 음성 파일을 준비하거나 이 단계를 Task 8 통합 테스트로 미룸

**Step 3: Commit**

```bash
git add pipeline/transcriber.py
git commit -m "feat: transcriber - whisper local with pyannote diarization, API fallback"
```

---

## Task 6: FastAPI 백엔드

**Files:**
- Create: `meetscribe/main.py`

**Step 1: `meetscribe/main.py` 구현**

```python
import uuid
from pathlib import Path
from datetime import date
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import config
from config import validate_config
from pipeline.transcriber import transcribe
from pipeline.analyzer import analyze_transcript
from pipeline.note_builder import NoteData, build_meeting_note, build_transcript_note
from pipeline.vault_writer import VaultWriter

# 진행 상황 저장 (in-memory, 단일 프로세스용)
job_status: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    yield


app = FastAPI(title="MeetScribe", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
):
    allowed = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"지원하지 않는 파일 형식: {suffix}")

    job_id = str(uuid.uuid4())
    save_path = config.UPLOAD_DIR / f"{job_id}{suffix}"

    # 파일 저장
    content = await file.read()
    save_path.write_bytes(content)

    # 제목이 없으면 파일명 사용
    if not title:
        title = Path(file.filename).stem

    job_status[job_id] = {"status": "queued", "step": "", "result": None, "error": None}
    background_tasks.add_task(process_audio, job_id, save_path, title, project, file.filename)

    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    return job_status[job_id]


def process_audio(job_id: str, audio_path: Path, title: str, project: str, original_filename: str):
    """백그라운드 처리 파이프라인"""
    try:
        # 1. 전사
        _update_status(job_id, "transcribing", "전사 중...")
        transcript_result = transcribe(audio_path)

        # 2. 분석
        _update_status(job_id, "analyzing", "AI 분석 중...")
        analysis = analyze_transcript(transcript_result["full_text"])

        # 3. 노트 생성
        _update_status(job_id, "building", "노트 생성 중...")
        today = date.today()
        speakers = list({seg["speaker"] for seg in transcript_result["segments"]})
        speakers.sort()

        note_data = NoteData(
            date=today,
            title=title,
            audio_filename=original_filename,
            duration=transcript_result["duration"],
            speakers=speakers,
            purpose=analysis["purpose"],
            discussion=analysis["discussion"],
            decisions=analysis["decisions"],
            action_items=analysis["action_items"],
            follow_up=analysis["follow_up"],
            transcript=transcript_result["segments"],
            project=project,
        )

        meeting_note = build_meeting_note(note_data)
        transcript_note = build_transcript_note(note_data)

        # 4. Vault 저장
        _update_status(job_id, "saving", "Vault에 저장 중...")
        writer = VaultWriter(
            vault_path=config.VAULT_PATH,
            meetings_folder=config.MEETINGS_FOLDER,
        )
        result = writer.save(note_data, meeting_note, transcript_note)

        # 완료
        job_status[job_id] = {
            "status": "done",
            "step": "완료",
            "result": result,
            "error": None,
        }

    except Exception as e:
        job_status[job_id] = {
            "status": "error",
            "step": "오류 발생",
            "result": None,
            "error": str(e),
        }
    finally:
        # 업로드 파일 정리
        if audio_path.exists():
            audio_path.unlink()


def _update_status(job_id: str, status: str, step: str):
    job_status[job_id] = {
        "status": status,
        "step": step,
        "result": None,
        "error": None,
    }
```

**Step 2: 앱 기동 테스트**

```bash
cd meetscribe
uvicorn main:app --reload --port 8765
```

Expected: `INFO: Application startup complete.` (에러 없이)

**Step 3: API 헬스체크**

```bash
curl http://localhost:8765/
```

Expected: HTML 응답 (index.html이 아직 없으면 404 → Task 7 후 다시 확인)

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: fastapi backend - upload, status polling, background processing pipeline"
```

---

## Task 7: 웹 프론트엔드

**Files:**
- Create: `meetscribe/static/index.html`

**Step 1: `meetscribe/static/index.html` 구현**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MeetScribe</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .container {
      width: 480px;
      background: #16213e;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    h1 { font-size: 1.6rem; margin-bottom: 8px; color: #7c83fd; }
    .subtitle { font-size: 0.85rem; color: #888; margin-bottom: 24px; }
    #drop-zone {
      border: 2px dashed #7c83fd44;
      border-radius: 12px;
      padding: 32px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s;
      margin-bottom: 20px;
    }
    #drop-zone.dragover {
      border-color: #7c83fd;
      background: #7c83fd11;
    }
    #drop-zone .icon { font-size: 2rem; margin-bottom: 8px; }
    #drop-zone .hint { font-size: 0.8rem; color: #888; margin-top: 4px; }
    #file-name { font-size: 0.85rem; color: #7c83fd; margin-top: 8px; }
    input[type="file"] { display: none; }
    .field { margin-bottom: 16px; }
    label { display: block; font-size: 0.8rem; color: #aaa; margin-bottom: 6px; }
    input[type="text"] {
      width: 100%;
      padding: 10px 14px;
      background: #0f3460;
      border: 1px solid #ffffff11;
      border-radius: 8px;
      color: #e0e0e0;
      font-size: 0.9rem;
      outline: none;
    }
    input[type="text"]:focus { border-color: #7c83fd; }
    button#submit {
      width: 100%;
      padding: 14px;
      background: #7c83fd;
      color: white;
      border: none;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
      margin-top: 4px;
    }
    button#submit:hover { background: #6a71e0; }
    button#submit:disabled { background: #444; cursor: not-allowed; }
    #progress { margin-top: 24px; display: none; }
    .step {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 0;
      font-size: 0.9rem;
      color: #888;
    }
    .step.done { color: #4caf50; }
    .step.active { color: #7c83fd; }
    .step-icon { width: 20px; text-align: center; }
    #result { margin-top: 20px; display: none; }
    .result-card {
      background: #0f3460;
      border-radius: 10px;
      padding: 16px;
    }
    .result-card h3 { font-size: 0.9rem; color: #aaa; margin-bottom: 10px; }
    .obsidian-btn {
      display: block;
      width: 100%;
      padding: 10px;
      background: #7c3aed;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 0.9rem;
      cursor: pointer;
      text-align: center;
      text-decoration: none;
      margin-bottom: 8px;
      transition: background 0.2s;
    }
    .obsidian-btn:hover { background: #6d28d9; }
    #error-msg {
      background: #3f0000;
      border: 1px solid #ff4444;
      border-radius: 8px;
      padding: 12px;
      margin-top: 16px;
      font-size: 0.85rem;
      color: #ff8080;
      display: none;
    }
  </style>
</head>
<body>
<div class="container">
  <h1>MeetScribe</h1>
  <p class="subtitle">회의 녹음 → 자동 전사 → Obsidian 노트</p>

  <div id="drop-zone" onclick="document.getElementById('file-input').click()">
    <div class="icon">🎙️</div>
    <div>파일을 여기에 드래그하거나 클릭하세요</div>
    <div class="hint">mp3 / wav / m4a / mp4</div>
    <div id="file-name"></div>
  </div>
  <input type="file" id="file-input" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">

  <div class="field">
    <label>회의 제목</label>
    <input type="text" id="title" placeholder="자동으로 파일명 사용">
  </div>
  <div class="field">
    <label>프로젝트 (선택)</label>
    <input type="text" id="project" placeholder="예: [[USV Project Dashboard]]">
  </div>

  <button id="submit" disabled>분석 시작</button>

  <div id="progress">
    <div class="step" id="step-upload"><span class="step-icon">⬜</span>업로드</div>
    <div class="step" id="step-transcribe"><span class="step-icon">⬜</span>전사 (시간이 걸릴 수 있습니다)</div>
    <div class="step" id="step-analyze"><span class="step-icon">⬜</span>AI 분석</div>
    <div class="step" id="step-save"><span class="step-icon">⬜</span>Vault 저장</div>
  </div>

  <div id="error-msg"></div>

  <div id="result">
    <div class="result-card">
      <h3>✅ 완료! Obsidian에서 열기:</h3>
      <a id="open-meeting" class="obsidian-btn" href="#">📝 회의 노트 열기</a>
      <a id="open-transcript" class="obsidian-btn" href="#">📄 전사 노트 열기</a>
    </div>
  </div>
</div>

<script>
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const submitBtn = document.getElementById('submit');
  const fileNameEl = document.getElementById('file-name');
  let selectedFile = null;

  // 드래그앤드롭
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) setFile(file);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });

  function setFile(file) {
    selectedFile = file;
    fileNameEl.textContent = file.name;
    submitBtn.disabled = false;
  }

  // 업로드 & 폴링
  submitBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    submitBtn.disabled = true;
    document.getElementById('progress').style.display = 'block';
    document.getElementById('result').style.display = 'none';
    document.getElementById('error-msg').style.display = 'none';

    setStep('step-upload', 'active');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('title', document.getElementById('title').value);
    formData.append('project', document.getElementById('project').value);

    let jobId;
    try {
      const res = await fetch('/upload', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || '업로드 실패');
      jobId = data.job_id;
    } catch (e) {
      showError(e.message);
      submitBtn.disabled = false;
      return;
    }

    setStep('step-upload', 'done');
    pollStatus(jobId);
  });

  async function pollStatus(jobId) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/status/${jobId}`);
        const data = await res.json();

        if (data.status === 'transcribing') {
          setStep('step-transcribe', 'active');
        } else if (data.status === 'analyzing') {
          setStep('step-transcribe', 'done');
          setStep('step-analyze', 'active');
        } else if (data.status === 'saving' || data.status === 'building') {
          setStep('step-analyze', 'done');
          setStep('step-save', 'active');
        } else if (data.status === 'done') {
          clearInterval(interval);
          setStep('step-save', 'done');
          showResult(data.result);
          submitBtn.disabled = false;
        } else if (data.status === 'error') {
          clearInterval(interval);
          showError(data.error);
          submitBtn.disabled = false;
        }
      } catch (e) {
        clearInterval(interval);
        showError('상태 확인 중 오류: ' + e.message);
        submitBtn.disabled = false;
      }
    }, 2000);
  }

  function setStep(id, state) {
    const el = document.getElementById(id);
    el.className = `step ${state}`;
    const icon = el.querySelector('.step-icon');
    icon.textContent = state === 'done' ? '✅' : state === 'active' ? '⏳' : '⬜';
  }

  function showResult(result) {
    document.getElementById('result').style.display = 'block';
    document.getElementById('open-meeting').href = result.meeting_uri;
    document.getElementById('open-transcript').href = result.transcript_uri;
  }

  function showError(msg) {
    const el = document.getElementById('error-msg');
    el.textContent = '오류: ' + msg;
    el.style.display = 'block';
  }
</script>
</body>
</html>
```

**Step 2: 기동 후 UI 확인**

```bash
uvicorn main:app --reload --port 8765
```

브라우저에서 `http://localhost:8765` 열어서:
- [ ] 드래그앤드롭 영역 표시
- [ ] 파일 선택 시 버튼 활성화
- [ ] 진행 단계 표시

**Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: web UI - drag and drop upload with progress polling and obsidian URIs"
```

---

## Task 8: 통합 테스트

**Files:**
- Create: `meetscribe/tests/test_integration.py`
- Create: `meetscribe/tests/generate_test_audio.py`

**Step 1: 테스트용 짧은 오디오 생성 스크립트**

`meetscribe/tests/generate_test_audio.py`:

```python
"""
테스트용 짧은 오디오 파일 생성 (gTTS 사용)
pip install gtts
"""
from pathlib import Path

def generate():
    try:
        from gtts import gTTS
        text = "안녕하세요. 오늘 회의를 시작하겠습니다. 첫 번째 안건은 프로젝트 진행 상황입니다. 네, 잘 진행되고 있습니다."
        tts = gTTS(text=text, lang='ko')
        out = Path(__file__).parent / "sample.mp3"
        tts.save(str(out))
        print(f"생성됨: {out}")
        return out
    except ImportError:
        print("pip install gtts 실행 후 다시 시도")
        return None

if __name__ == "__main__":
    generate()
```

**Step 2: 테스트 오디오 생성**

```bash
pip install gtts
python tests/generate_test_audio.py
```

Expected: `tests/sample.mp3` 생성

**Step 3: `meetscribe/tests/test_integration.py` 작성**

```python
"""
통합 테스트: 실제 오디오 파일로 전체 파이프라인 테스트
실행: pytest tests/test_integration.py -v -s
"""
import pytest
from pathlib import Path
import tempfile

SAMPLE_AUDIO = Path(__file__).parent / "sample.mp3"


@pytest.fixture
def tmp_vault(tmp_path):
    meetings = tmp_path / "10_Calendar" / "13_Meetings"
    meetings.mkdir(parents=True)
    return tmp_path


@pytest.mark.skipif(not SAMPLE_AUDIO.exists(), reason="sample.mp3 없음")
def test_full_pipeline(tmp_vault, monkeypatch):
    """전체 파이프라인 통합 테스트"""
    import config
    monkeypatch.setattr(config, "VAULT_PATH", tmp_vault)
    monkeypatch.setattr(config, "MEETINGS_FOLDER", "10_Calendar/13_Meetings")

    from pipeline.transcriber import transcribe
    from pipeline.analyzer import analyze_transcript
    from pipeline.note_builder import NoteData, build_meeting_note, build_transcript_note
    from pipeline.vault_writer import VaultWriter
    from datetime import date

    # 전사
    result = transcribe(SAMPLE_AUDIO)
    assert result["segments"]
    assert result["duration"]

    # 분석
    analysis = analyze_transcript(result["full_text"])
    assert isinstance(analysis["purpose"], str)

    # 노트 생성
    note_data = NoteData(
        date=date.today(),
        title="통합 테스트",
        audio_filename="sample.mp3",
        duration=result["duration"],
        speakers=list({s["speaker"] for s in result["segments"]}),
        purpose=analysis["purpose"],
        discussion=analysis["discussion"],
        decisions=analysis["decisions"],
        action_items=analysis["action_items"],
        follow_up=analysis["follow_up"],
        transcript=result["segments"],
    )

    meeting_note = build_meeting_note(note_data)
    transcript_note = build_transcript_note(note_data)

    # 저장
    writer = VaultWriter(tmp_vault, "10_Calendar/13_Meetings")
    save_result = writer.save(note_data, meeting_note, transcript_note)

    assert Path(save_result["meeting_path"]).exists()
    assert Path(save_result["transcript_path"]).exists()
    assert "obsidian://open" in save_result["meeting_uri"]

    print("\n=== 생성된 회의 노트 ===")
    print(Path(save_result["meeting_path"]).read_text(encoding="utf-8"))
```

**Step 4: 단위 테스트 전체 실행**

```bash
python -m pytest tests/test_note_builder.py tests/test_vault_writer.py tests/test_analyzer.py -v
```

Expected: 18개 PASS

**Step 5: 통합 테스트 실행**

```bash
python -m pytest tests/test_integration.py -v -s
```

Expected: PASS (인터넷 연결 필요, Whisper 모델 다운로드 포함)

**Step 6: 최종 Commit**

```bash
git add tests/test_integration.py tests/generate_test_audio.py tests/sample.mp3
git commit -m "test: integration test for full pipeline with sample audio"
```

---

## Task 9: 실행 스크립트 & README

**Files:**
- Create: `meetscribe/run.bat` (Windows)
- Create: `meetscribe/README.md`

**Step 1: `meetscribe/run.bat` 작성**

```bat
@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
uvicorn main:app --host 0.0.0.0 --port 8765
```

**Step 2: `meetscribe/README.md` 작성**

````markdown
# MeetScribe

회의 녹음 → Whisper 전사 → GPT 분석 → Obsidian 노트 자동 생성

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 API 키 입력
```

## HuggingFace 설정 (화자 분리용)
1. https://hf.co/pyannote/speaker-diarization-3.1 Accept
2. https://hf.co/pyannote/segmentation-3.0 Accept
3. https://hf.co/settings/tokens 에서 토큰 생성 → .env에 HF_TOKEN 입력

## 실행

```bash
uvicorn main:app --port 8765
# 또는
run.bat
```

브라우저에서 http://localhost:8765 열기

## 테스트

```bash
pytest tests/ -v
```
````

**Step 3: 최종 Commit**

```bash
git add run.bat README.md
git commit -m "docs: add run script and README"
```

---

## 완료 체크리스트

- [ ] `python -m pytest tests/ -v` — 18개 단위 테스트 PASS
- [ ] `uvicorn main:app --port 8765` — 앱 정상 기동
- [ ] 브라우저에서 파일 업로드 → 진행 상황 표시 → Obsidian 열기 버튼
- [ ] Obsidian Vault `10_Calendar/13_Meetings/` 에 [회의]/[전사] 파일 생성 확인
- [ ] 기존 Meeting Note 템플릿과 형식 호환 확인
