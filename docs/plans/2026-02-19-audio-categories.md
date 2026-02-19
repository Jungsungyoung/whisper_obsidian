# 오디오 카테고리 확장 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 회의 전용이었던 MeetScribe를 6개 카테고리(회의·보이스메모·데일리·강의·프로젝트논의·레퍼런스)로 확장해 카테고리별 AI 분석 프롬프트, 노트 템플릿, Vault 저장 폴더를 자동으로 결정한다.

**Architecture:** `category` 문자열을 `/upload` → `_process()` → `analyzer` → `note_builder` → `vault_writer` 파이프라인 전체에 전달한다. `meeting`/`discussion`은 기존 NoteData 필드를 그대로 쓰고, 나머지 4개 카테고리는 `NoteData.extra: dict`에 분석 결과를 담아 카테고리별 빌더 함수로 노트를 생성한다. 기존 `.env`를 수정하지 않아도 기본값으로 동작한다.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, pytest, vanilla JS (index.html)

---

## 선행 조건

```bash
cd meetscribe
pytest tests/ -v          # 기존 테스트 전체 통과 확인
```

---

## Task 1: `pipeline/prompts.py` — 카테고리별 시스템 프롬프트

**Files:**
- Create: `meetscribe/pipeline/prompts.py`

**Step 1: 파일 생성**

```python
# meetscribe/pipeline/prompts.py
"""카테고리별 LLM 시스템 프롬프트 상수."""

MEETING_PROMPT = """당신은 회의록 분석 전문가입니다.
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

VOICE_MEMO_PROMPT = """당신은 음성 메모 분석 전문가입니다.
다음 형식으로 정확히 출력하세요.

SUMMARY: [한 줄 요약]

KEY_POINTS:
- [핵심 포인트]

ACTION_ITEMS:
- [할 일 항목]

항목이 없으면 해당 섹션은 비워두세요."""

DAILY_PROMPT = """당신은 업무 일지 분석 전문가입니다.
다음 형식으로 정확히 출력하세요.

TASKS_DONE:
- [오늘 완료한 업무]

TASKS_TOMORROW:
- [내일 할 일]

ISSUES:
- [문제나 이슈]

REFLECTION: [하루 한 줄 소감]

항목이 없으면 해당 섹션은 비워두세요."""

LECTURE_PROMPT = """당신은 강의/세미나 내용 분석 전문가입니다.
다음 형식으로 정확히 출력하세요.

SUMMARY: [강의 내용 한 줄 요약]

KEY_CONCEPTS:
- [핵심 개념]

IMPORTANT_POINTS:
- [중요 포인트]

REFERENCES:
- [참고 자료나 출처]

QUESTIONS:
- [이해가 필요한 질문이나 추가 탐구 필요 항목]

항목이 없으면 해당 섹션은 비워두세요."""

REFERENCE_PROMPT = """당신은 레퍼런스 리뷰 전문가입니다.
다음 형식으로 정확히 출력하세요.

SUMMARY: [레퍼런스 한 줄 요약]

KEY_FINDINGS:
- [핵심 발견사항]

METHODOLOGY: [연구/분석 방법론]

APPLICABILITY: [업무 적용 가능성]

CITATIONS:
- [인용 가능한 핵심 문장]

항목이 없으면 해당 섹션은 비워두세요."""

PROMPTS: dict[str, str] = {
    "meeting":    MEETING_PROMPT,
    "discussion": MEETING_PROMPT,  # 회의와 동일 프롬프트
    "voice_memo": VOICE_MEMO_PROMPT,
    "daily":      DAILY_PROMPT,
    "lecture":    LECTURE_PROMPT,
    "reference":  REFERENCE_PROMPT,
}
```

**Step 2: 테스트 작성 — `tests/test_prompts.py`**

```python
# meetscribe/tests/test_prompts.py
from pipeline.prompts import PROMPTS

CATEGORIES = ["meeting", "discussion", "voice_memo", "daily", "lecture", "reference"]

def test_all_categories_have_prompts():
    for cat in CATEGORIES:
        assert cat in PROMPTS, f"Missing prompt for {cat}"
        assert len(PROMPTS[cat]) > 50

def test_discussion_uses_meeting_prompt():
    assert PROMPTS["discussion"] is PROMPTS["meeting"]

def test_prompts_are_korean():
    for cat, prompt in PROMPTS.items():
        assert any(ord(c) > 0xAC00 for c in prompt), f"{cat} prompt has no Korean"
```

**Step 3: 테스트 실행**

```bash
cd meetscribe
pytest tests/test_prompts.py -v
```
Expected: 3 tests PASS

**Step 4: Commit**

```bash
git add meetscribe/pipeline/prompts.py meetscribe/tests/test_prompts.py
git commit -m "feat: add category-specific LLM system prompts"
```

---

## Task 2: `pipeline/analyzer.py` — 카테고리 라우팅 + 파서

**Files:**
- Modify: `meetscribe/pipeline/analyzer.py`
- Modify: `meetscribe/tests/test_analyzer.py`

**Step 1: 기존 `parse_llm_response`를 `_parse_meeting`으로 이름 변경 후 헬퍼 추가**

`analyze.py` 전체를 다음으로 교체:

```python
import os
import re
import config
from pipeline.prompts import PROMPTS


def _build_analysis_prompt(context: str, transcript_text: str) -> str:
    """회의 맥락이 있으면 프롬프트 앞에 주입."""
    ctx_line = f"[회의 맥락: {context.strip()}]\n\n" if context.strip() else ""
    return f"{ctx_line}다음 내용을 분석해주세요:\n\n{transcript_text}"


def analyze_transcript(transcript_text: str, category: str = "meeting", context: str = "") -> dict:
    """카테고리별 프롬프트 사용. Gemini 우선, 실패 시 OpenAI, 마지막은 기본 추출."""
    if config.GEMINI_API_KEY:
        try:
            return _analyze_gemini(transcript_text, context, category)
        except Exception as e:
            print(f"[Analyzer] Gemini 실패: {e}. OpenAI로 폴백.")

    if config.OPENAI_API_KEY:
        try:
            return _analyze_openai(transcript_text, context, category)
        except Exception as e:
            print(f"[Analyzer] OpenAI 실패: {e}. 기본 분석 사용.")

    return _analyze_basic(transcript_text)


def _analyze_gemini(transcript_text: str, context: str = "", category: str = "meeting") -> dict:
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    system = PROMPTS.get(category, PROMPTS["meeting"])
    user_part = _build_analysis_prompt(context, transcript_text)
    prompt = f"{system}\n\n{user_part}"
    response = client.models.generate_content(model=config.LLM_MODEL, contents=prompt)
    return parse_llm_response(response.text, category)


def _analyze_openai(transcript_text: str, context: str = "", category: str = "meeting") -> dict:
    from openai import OpenAI

    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    system = PROMPTS.get(category, PROMPTS["meeting"])
    prompt = _build_analysis_prompt(context, transcript_text)
    response = client.chat.completions.create(
        model=openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return parse_llm_response(response.choices[0].message.content, category)


def _analyze_basic(transcript_text: str) -> dict:
    """LLM 없이 기본 분석 (전사본에서 핵심 문장 추출)."""
    lines = [l.strip() for l in transcript_text.split(".") if len(l.strip()) > 10]
    return {
        "purpose": lines[0] if lines else "회의 분석 불가 (API 연결 실패)",
        "discussion": lines[1:4] if len(lines) > 1 else [],
        "decisions": [],
        "action_items": [],
        "follow_up": ["API 연결 복구 후 재분석을 권장합니다."],
    }


def parse_llm_response(response: str, category: str = "meeting") -> dict:
    """카테고리별 파서 디스패처."""
    if category in ("meeting", "discussion"):
        return _parse_meeting(response)
    elif category == "voice_memo":
        return _parse_voice_memo(response)
    elif category == "daily":
        return _parse_daily(response)
    elif category == "lecture":
        return _parse_lecture(response)
    elif category == "reference":
        return _parse_reference(response)
    return _parse_meeting(response)


# ── 공통 헬퍼 ──────────────────────────────────────────────────────────

def _extract_line(text: str, key: str) -> str:
    m = re.search(rf"{key}:\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _extract_list(text: str, key: str) -> list[str]:
    m = re.search(rf"{key}:\s*\n((?:- .+\n?)*)", text)
    if not m:
        return []
    return [item.strip() for item in re.findall(r"- (.+)", m.group(1)) if item.strip()]


# ── 카테고리별 파서 ────────────────────────────────────────────────────

def _parse_meeting(response: str) -> dict:
    sections = {
        "purpose": "",
        "discussion": [],
        "decisions": [],
        "action_items": [],
        "follow_up": [],
    }
    purpose_match = re.search(r"PURPOSE:\s*(.+)", response)
    if purpose_match:
        sections["purpose"] = purpose_match.group(1).strip()
    for section_key, dict_key in [
        ("DISCUSSION", "discussion"),
        ("DECISIONS", "decisions"),
        ("ACTION_ITEMS", "action_items"),
        ("FOLLOW_UP", "follow_up"),
    ]:
        match = re.search(rf"{section_key}:\s*\n((?:- .+\n?)*)", response)
        if match:
            sections[dict_key] = [
                item.strip()
                for item in re.findall(r"- (.+)", match.group(1))
                if item.strip()
            ]
    return sections


def _parse_voice_memo(response: str) -> dict:
    return {
        "summary": _extract_line(response, "SUMMARY"),
        "key_points": _extract_list(response, "KEY_POINTS"),
        "action_items": _extract_list(response, "ACTION_ITEMS"),
    }


def _parse_daily(response: str) -> dict:
    return {
        "tasks_done": _extract_list(response, "TASKS_DONE"),
        "tasks_tomorrow": _extract_list(response, "TASKS_TOMORROW"),
        "issues": _extract_list(response, "ISSUES"),
        "reflection": _extract_line(response, "REFLECTION"),
    }


def _parse_lecture(response: str) -> dict:
    return {
        "summary": _extract_line(response, "SUMMARY"),
        "key_concepts": _extract_list(response, "KEY_CONCEPTS"),
        "important_points": _extract_list(response, "IMPORTANT_POINTS"),
        "references": _extract_list(response, "REFERENCES"),
        "questions": _extract_list(response, "QUESTIONS"),
    }


def _parse_reference(response: str) -> dict:
    return {
        "summary": _extract_line(response, "SUMMARY"),
        "key_findings": _extract_list(response, "KEY_FINDINGS"),
        "methodology": _extract_line(response, "METHODOLOGY"),
        "applicability": _extract_line(response, "APPLICABILITY"),
        "citations": _extract_list(response, "CITATIONS"),
    }
```

**Step 2: 기존 테스트가 여전히 통과하는지 확인**

```bash
cd meetscribe
pytest tests/test_analyzer.py -v
```
Expected: 기존 5개 PASS (`parse_llm_response` 시그니처에 `category` 기본값이 있으므로 기존 호출 그대로 동작)

**Step 3: 신규 테스트를 `test_analyzer.py` 끝에 추가**

```python
# ── 카테고리별 파서 테스트 ─────────────────────────────────────────

VOICE_MEMO_RESPONSE = """
SUMMARY: 프로젝트 아이디어 메모

KEY_POINTS:
- 새 API 설계 필요
- 팀원 피드백 반영

ACTION_ITEMS:
- API 설계서 초안 작성
"""

DAILY_RESPONSE = """
TASKS_DONE:
- 코드 리뷰 완료
- 단위 테스트 작성

TASKS_TOMORROW:
- 문서 작성

ISSUES:
- 빌드 오류 발생

REFLECTION: 생산적인 하루였다
"""

LECTURE_RESPONSE = """
SUMMARY: 제어 시스템 기초 강의

KEY_CONCEPTS:
- PID 제어기
- 상태 공간 표현

IMPORTANT_POINTS:
- 안정성 조건 확인 필요

REFERENCES:
- 교재 3장

QUESTIONS:
- 비선형 시스템 적용 방법?
"""

REFERENCE_RESPONSE = """
SUMMARY: USV 자율항법 논문 검토

KEY_FINDINGS:
- GPS 오류 보정 알고리즘 제안

METHODOLOGY: 시뮬레이션 기반 검증

APPLICABILITY: 현 프로젝트 항법 모듈에 직접 적용 가능

CITATIONS:
- "The proposed algorithm reduces error by 40%"
"""


def test_parse_voice_memo_summary():
    result = parse_llm_response(VOICE_MEMO_RESPONSE, "voice_memo")
    assert result["summary"] == "프로젝트 아이디어 메모"


def test_parse_voice_memo_lists():
    result = parse_llm_response(VOICE_MEMO_RESPONSE, "voice_memo")
    assert len(result["key_points"]) == 2
    assert "새 API 설계 필요" in result["key_points"]
    assert len(result["action_items"]) == 1


def test_parse_daily_tasks():
    result = parse_llm_response(DAILY_RESPONSE, "daily")
    assert result["tasks_done"] == ["코드 리뷰 완료", "단위 테스트 작성"]
    assert result["tasks_tomorrow"] == ["문서 작성"]
    assert result["issues"] == ["빌드 오류 발생"]


def test_parse_daily_reflection():
    result = parse_llm_response(DAILY_RESPONSE, "daily")
    assert result["reflection"] == "생산적인 하루였다"


def test_parse_lecture():
    result = parse_llm_response(LECTURE_RESPONSE, "lecture")
    assert result["summary"] == "제어 시스템 기초 강의"
    assert "PID 제어기" in result["key_concepts"]
    assert len(result["questions"]) == 1


def test_parse_reference():
    result = parse_llm_response(REFERENCE_RESPONSE, "reference")
    assert result["summary"] == "USV 자율항법 논문 검토"
    assert result["methodology"] == "시뮬레이션 기반 검증"
    assert len(result["citations"]) == 1


def test_unknown_category_falls_back_to_meeting():
    result = parse_llm_response(SAMPLE_RESPONSE, "unknown_cat")
    assert "purpose" in result
```

**Step 4: 테스트 실행**

```bash
cd meetscribe
pytest tests/test_analyzer.py -v
```
Expected: 전체 PASS (기존 5 + 신규 8 = 13개)

**Step 5: Commit**

```bash
git add meetscribe/pipeline/analyzer.py meetscribe/tests/test_analyzer.py
git commit -m "feat: add category-aware analyzer with per-category parsers"
```

---

## Task 3: `pipeline/note_builder.py` — NoteData + 카테고리별 빌더

**Files:**
- Modify: `meetscribe/pipeline/note_builder.py`
- Modify: `meetscribe/tests/test_note_builder.py`

**Step 1: `note_builder.py` 전체 교체**

```python
from dataclasses import dataclass
from datetime import date


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
    category: str = "meeting"
    extra: dict = None  # 비회의 카테고리의 분석 결과 (voice_memo, daily 등)


# ── 파일명 ────────────────────────────────────────────────────────────

def get_filenames(data: NoteData) -> tuple[str, str]:
    """하위 호환: 회의 파일명 반환."""
    date_str = data.date.strftime("%Y-%m-%d")
    return f"[회의] {date_str} {data.title}.md", f"[전사] {date_str} {data.title}.md"


def get_note_filenames(data: NoteData) -> str | tuple[str, str]:
    """카테고리별 파일명 반환. 2개 노트 카테고리는 tuple, 1개는 str."""
    date_str = data.date.strftime("%Y-%m-%d")
    cat = data.category
    if cat == "meeting":
        return f"[회의] {date_str} {data.title}.md", f"[전사] {date_str} {data.title}.md"
    elif cat == "discussion":
        return f"[논의] {date_str} {data.title}.md", f"[전사] {date_str} {data.title}.md"
    elif cat == "voice_memo":
        return f"[메모] {date_str} {data.title}.md"
    elif cat == "daily":
        return f"[업무일지] {date_str}.md"
    elif cat == "lecture":
        return f"[강의] {date_str} {data.title}.md"
    elif cat == "reference":
        return f"[레퍼런스] {date_str} {data.title}.md"
    return f"[메모] {date_str} {data.title}.md"


# ── 빌더 디스패처 ─────────────────────────────────────────────────────

def build_note(data: NoteData) -> str:
    """단일 노트 카테고리(voice_memo/daily/lecture/reference) 디스패처."""
    builders = {
        "voice_memo": build_voice_memo_note,
        "daily":      build_daily_note,
        "lecture":    build_lecture_note,
        "reference":  build_reference_note,
    }
    if data.category not in builders:
        raise ValueError(f"build_note: unsupported category '{data.category}'. Use build_meeting_note or build_discussion_note for meeting/discussion.")
    return builders[data.category](data)


# ── 회의 노트 (기존 유지) ──────────────────────────────────────────────

def build_meeting_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    _, transcript_fn = get_filenames(data)
    transcript_link = transcript_fn[:-3]

    participants_yaml = "\n".join(f"  - {s}" for s in data.speakers)
    discussion_items = "\n".join(f"- {d}" for d in data.discussion)
    decision_items = "\n".join(f"- {d}" for d in data.decisions)
    action_items = "\n".join(f"- [ ] {a}" for a in data.action_items)
    follow_up_items = "\n".join(f"- {f}" for f in data.follow_up)

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: meeting\n"
        f"project: \"{data.project}\"\n"
        f"participants:\n{participants_yaml}\n"
        f"tags:\n  - meeting\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [회의] {date_str} {data.title}\n\n"
        f"> [!note] AI 자동 생성\n"
        f"> Whisper + LLM으로 자동 생성. 전체 전사: [[{transcript_link}]]\n\n"
        f"## 목적\n{data.purpose}\n\n"
        f"## 주요 논의\n{discussion_items}\n\n"
        f"## 결정 사항\n{decision_items}\n\n"
        f"## Action Items\n{action_items}\n\n"
        f"## 후속 질문\n{follow_up_items}\n"
    )


def build_transcript_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    meeting_fn, _ = get_filenames(data) if data.category == "meeting" else get_note_filenames(data)
    meeting_link = meeting_fn[:-3]

    lines = "\n".join(
        f"**[{seg['timestamp']}] {seg['speaker']}:** {seg['text']}"
        for seg in data.transcript
    )

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: meeting-transcript\n"
        f"tags:\n  - transcript\n"
        f"---\n\n"
        f"# [전사] {date_str} {data.title}\n\n"
        f"> 요약: [[{meeting_link}]]\n\n"
        f"{lines}\n"
    )


# ── 프로젝트 논의 노트 ─────────────────────────────────────────────────

def build_discussion_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    note_fn, transcript_fn = get_note_filenames(data)
    transcript_link = transcript_fn[:-3]

    participants_yaml = "\n".join(f"  - {s}" for s in data.speakers)
    discussion_items = "\n".join(f"- {d}" for d in data.discussion)
    decision_items   = "\n".join(f"- {d}" for d in data.decisions)
    action_items     = "\n".join(f"- [ ] {a}" for a in data.action_items)
    follow_up_items  = "\n".join(f"- {f}" for f in data.follow_up)

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: discussion\n"
        f"project: \"{data.project}\"\n"
        f"participants:\n{participants_yaml}\n"
        f"status: 진행\n"
        f"tags:\n  - discussion\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [논의] {date_str} {data.title}\n\n"
        f"> [!note] AI 자동 생성\n"
        f"> Whisper + LLM으로 자동 생성. 전체 전사: [[{transcript_link}]]\n\n"
        f"## 목적\n{data.purpose}\n\n"
        f"## 주요 논의\n{discussion_items}\n\n"
        f"## 결정 사항\n{decision_items}\n\n"
        f"## Action Items\n{action_items}\n\n"
        f"## 후속 질문\n{follow_up_items}\n"
    )


# ── 보이스 메모 노트 ──────────────────────────────────────────────────

def build_voice_memo_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    extra = data.extra or {}
    key_points   = "\n".join(f"- {p}" for p in extra.get("key_points", []))
    action_items = "\n".join(f"- [ ] {a}" for a in extra.get("action_items", []))

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: voice_memo\n"
        f"tags:\n  - voice-memo\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [메모] {date_str} {data.title}\n\n"
        f"> [!note] AI 자동 생성 — Whisper + LLM\n\n"
        f"## 요약\n{extra.get('summary', '')}\n\n"
        f"## 핵심 포인트\n{key_points}\n\n"
        f"## 할 일\n{action_items}\n"
    )


# ── 데일리 업무일지 노트 ───────────────────────────────────────────────

def build_daily_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    extra = data.extra or {}
    tasks_done     = "\n".join(f"- [x] {t}" for t in extra.get("tasks_done", []))
    tasks_tomorrow = "\n".join(f"- [ ] {t}" for t in extra.get("tasks_tomorrow", []))
    issues         = "\n".join(f"- {i}" for i in extra.get("issues", []))

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: daily\n"
        f"tags:\n  - daily\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [업무일지] {date_str}\n\n"
        f"> [!note] AI 자동 생성 — Whisper + LLM\n\n"
        f"## 오늘 완료한 업무\n{tasks_done}\n\n"
        f"## 내일 할 일\n{tasks_tomorrow}\n\n"
        f"## 문제/이슈\n{issues}\n\n"
        f"## 소감\n{extra.get('reflection', '')}\n"
    )


# ── 강의/세미나 노트 ───────────────────────────────────────────────────

def build_lecture_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    extra = data.extra or {}
    key_concepts     = "\n".join(f"- {c}" for c in extra.get("key_concepts", []))
    important_points = "\n".join(f"- {p}" for p in extra.get("important_points", []))
    references       = "\n".join(f"- {r}" for r in extra.get("references", []))
    questions        = "\n".join(f"- {q}" for q in extra.get("questions", []))

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: lecture\n"
        f"tags:\n  - lecture\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [강의] {date_str} {data.title}\n\n"
        f"> [!note] AI 자동 생성 — Whisper + LLM\n\n"
        f"## 요약\n{extra.get('summary', '')}\n\n"
        f"## 핵심 개념\n{key_concepts}\n\n"
        f"## 중요 포인트\n{important_points}\n\n"
        f"## 참고 자료\n{references}\n\n"
        f"## 질문\n{questions}\n"
    )


# ── 레퍼런스 리뷰 노트 ─────────────────────────────────────────────────

def build_reference_note(data: NoteData) -> str:
    date_str = data.date.strftime("%Y-%m-%d")
    extra = data.extra or {}
    key_findings = "\n".join(f"- {f}" for f in extra.get("key_findings", []))
    citations    = "\n".join(f"- {c}" for c in extra.get("citations", []))

    return (
        f"---\n"
        f"date: {date_str}\n"
        f"type: reference\n"
        f"tags:\n  - reference\n  - ai-transcribed\n"
        f"audio: \"{data.audio_filename}\"\n"
        f"duration: \"{data.duration}\"\n"
        f"---\n\n"
        f"# [레퍼런스] {date_str} {data.title}\n\n"
        f"> [!note] AI 자동 생성 — Whisper + LLM\n\n"
        f"## 요약\n{extra.get('summary', '')}\n\n"
        f"## 핵심 발견\n{key_findings}\n\n"
        f"## 방법론\n{extra.get('methodology', '')}\n\n"
        f"## 업무 적용 가능성\n{extra.get('applicability', '')}\n\n"
        f"## 인용\n{citations}\n"
    )
```

**Step 2: 기존 테스트 통과 확인**

```bash
cd meetscribe
pytest tests/test_note_builder.py -v
```
Expected: 기존 7개 PASS

**Step 3: 신규 테스트를 `test_note_builder.py` 끝에 추가**

```python
from datetime import date
from pipeline.note_builder import (
    NoteData, get_note_filenames,
    build_discussion_note, build_voice_memo_note,
    build_daily_note, build_lecture_note, build_reference_note, build_note,
)

# ── 카테고리별 파일명 ───────────────────────────────────────────────────

def test_meeting_filenames():
    data = NoteData(date=date(2026,2,18), title="리뷰", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="meeting")
    main, transcript = get_note_filenames(data)
    assert main == "[회의] 2026-02-18 리뷰.md"
    assert transcript == "[전사] 2026-02-18 리뷰.md"

def test_discussion_filenames():
    data = NoteData(date=date(2026,2,18), title="설계 논의", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="discussion")
    main, transcript = get_note_filenames(data)
    assert main == "[논의] 2026-02-18 설계 논의.md"
    assert transcript == "[전사] 2026-02-18 설계 논의.md"

def test_voice_memo_filename():
    data = NoteData(date=date(2026,2,18), title="아이디어", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="voice_memo")
    fn = get_note_filenames(data)
    assert fn == "[메모] 2026-02-18 아이디어.md"

def test_daily_filename_has_no_title():
    data = NoteData(date=date(2026,2,18), title="오늘 업무", audio_filename="a.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="daily")
    fn = get_note_filenames(data)
    assert fn == "[업무일지] 2026-02-18.md"

# ── 보이스 메모 노트 ────────────────────────────────────────────────────

VOICE_MEMO_DATA = NoteData(
    date=date(2026, 2, 18), title="아이디어 메모", audio_filename="memo.m4a",
    duration="02:30", speakers=["Speaker A"],
    purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
    transcript=[],
    category="voice_memo",
    extra={"summary": "새 기능 아이디어", "key_points": ["API 개선"], "action_items": ["문서 작성"]},
)

def test_voice_memo_frontmatter():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "type: voice_memo" in note
    assert "voice-memo" in note

def test_voice_memo_sections():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "## 요약" in note
    assert "## 핵심 포인트" in note
    assert "새 기능 아이디어" in note
    assert "- API 개선" in note

def test_voice_memo_action_items_are_checkboxes():
    note = build_voice_memo_note(VOICE_MEMO_DATA)
    assert "- [ ] 문서 작성" in note

# ── 데일리 노트 ─────────────────────────────────────────────────────────

DAILY_DATA = NoteData(
    date=date(2026, 2, 18), title="", audio_filename="daily.m4a",
    duration="03:00", speakers=["Speaker A"],
    purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
    transcript=[],
    category="daily",
    extra={"tasks_done": ["코드 리뷰"], "tasks_tomorrow": ["문서 작성"], "issues": [], "reflection": "좋은 하루"},
)

def test_daily_frontmatter():
    note = build_daily_note(DAILY_DATA)
    assert "type: daily" in note
    assert "date: 2026-02-18" in note

def test_daily_completed_tasks_use_checkmark():
    note = build_daily_note(DAILY_DATA)
    assert "- [x] 코드 리뷰" in note

def test_daily_tomorrow_tasks_use_empty_checkbox():
    note = build_daily_note(DAILY_DATA)
    assert "- [ ] 문서 작성" in note

# ── 논의 노트 ────────────────────────────────────────────────────────────

DISCUSSION_DATA = NoteData(
    date=date(2026, 2, 18), title="아키텍처 논의", audio_filename="disc.mp3",
    duration="10:00", speakers=["Speaker A", "Speaker B"],
    purpose="마이크로서비스 전환 방향 결정",
    discussion=["API 분리 방안 검토"], decisions=["3월 착수 확정"],
    action_items=["PoC 구현 (Speaker A, ~03/05)"], follow_up=[],
    transcript=[], project="[[USV_ECS_개발]]",
    category="discussion",
)

def test_discussion_frontmatter():
    note = build_discussion_note(DISCUSSION_DATA)
    assert "type: discussion" in note
    assert "status: 진행" in note

def test_discussion_has_transcript_backlink():
    note = build_discussion_note(DISCUSSION_DATA)
    assert "[[전사] 2026-02-18 아키텍처 논의]]" in note

# ── build_note 디스패처 ───────────────────────────────────────────────────

def test_build_note_dispatches_voice_memo():
    note = build_note(VOICE_MEMO_DATA)
    assert "## 요약" in note

def test_build_note_raises_for_meeting():
    import pytest
    data = NoteData(date=date(2026,2,18), title="x", audio_filename="x.mp3",
                    duration="01:00", speakers=[], purpose="", discussion=[],
                    decisions=[], action_items=[], follow_up=[], transcript=[],
                    category="meeting")
    with pytest.raises(ValueError, match="unsupported category"):
        build_note(data)
```

**Step 4: 테스트 실행**

```bash
cd meetscribe
pytest tests/test_note_builder.py -v
```
Expected: 전체 PASS (기존 7 + 신규 15 = 22개)

**Step 5: Commit**

```bash
git add meetscribe/pipeline/note_builder.py meetscribe/tests/test_note_builder.py
git commit -m "feat: add NoteData.category/extra fields and per-category note builders"
```

---

## Task 4: `config.py` + `.env.example` — 신규 폴더 환경변수

**Files:**
- Modify: `meetscribe/config.py`
- Modify: `meetscribe/.env.example`

**Step 1: `config.py`에 5개 변수 추가**

`MEETINGS_FOLDER` 줄 바로 아래에 추가:

```python
MEETINGS_FOLDER: str = os.getenv("MEETINGS_FOLDER", "10_Calendar/13_Meetings")
INBOX_FOLDER: str = os.getenv("INBOX_FOLDER", "00_Inbox")
DAILY_FOLDER: str = os.getenv("DAILY_FOLDER", "10_Calendar/11_Daily")
AREAS_FOLDER: str = os.getenv("AREAS_FOLDER", "30_Areas")
PROJECTS_FOLDER: str = os.getenv("PROJECTS_FOLDER", "20_Projects")
RESOURCES_FOLDER: str = os.getenv("RESOURCES_FOLDER", "40_Resources")
```

`validate_config()` 안에서 신규 폴더들도 자동 생성:

```python
# validate_config() 안의 meetings_path 처리 이후에 추가
for folder_attr in ("INBOX_FOLDER", "DAILY_FOLDER", "AREAS_FOLDER",
                    "PROJECTS_FOLDER", "RESOURCES_FOLDER"):
    folder_path = vault / getattr(config_module, folder_attr)
    if not folder_path.exists():
        folder_path.mkdir(parents=True)
```

> 주의: `validate_config`는 모듈 레벨 변수를 직접 참조하므로 위 코드는 `validate_config` 내부에서 `import config as config_module`을 사용하거나 단순히 변수명을 직접 쓴다. 현재 코드 스타일 확인 후 맞춰 작성.

실제로는 `validate_config` 안에 아래처럼 추가:

```python
for folder_name in [INBOX_FOLDER, DAILY_FOLDER, AREAS_FOLDER,
                    PROJECTS_FOLDER, RESOURCES_FOLDER]:
    folder_path = vault / folder_name
    if not folder_path.exists():
        folder_path.mkdir(parents=True)
```

**Step 2: `.env.example`에 주석 추가**

기존 `MEETINGS_FOLDER` 줄 아래에 추가:

```env
# 카테고리별 저장 폴더 (기본값 제공 — 기존 .env 수정 불필요)
# INBOX_FOLDER=00_Inbox
# DAILY_FOLDER=10_Calendar/11_Daily
# AREAS_FOLDER=30_Areas
# PROJECTS_FOLDER=20_Projects
# RESOURCES_FOLDER=40_Resources
```

**Step 3: 기존 전체 테스트 통과 확인**

```bash
cd meetscribe
pytest tests/ -v
```
Expected: 전체 PASS

**Step 4: Commit**

```bash
git add meetscribe/config.py meetscribe/.env.example
git commit -m "feat: add per-category folder config vars with defaults"
```

---

## Task 5: `pipeline/vault_writer.py` — 카테고리별 폴더 저장

**Files:**
- Modify: `meetscribe/pipeline/vault_writer.py`
- Modify: `meetscribe/tests/test_vault_writer.py`

**Step 1: `vault_writer.py` 전체 교체**

```python
from pathlib import Path
from urllib.parse import quote
import config as _cfg
from pipeline.note_builder import NoteData, get_filenames, get_note_filenames


class VaultWriter:
    def __init__(self, vault_path: Path, folder_overrides: dict | None = None):
        """
        folder_overrides: 테스트용 폴더 경로 오버라이드.
        예: {"meeting": "Meetings", "voice_memo": "Inbox"}
        """
        self.vault_path = Path(vault_path)
        self._overrides = folder_overrides or {}

    def _get_folder(self, data: NoteData) -> Path:
        """카테고리에 따라 저장 폴더 결정."""
        defaults = {
            "meeting":    _cfg.MEETINGS_FOLDER,
            "voice_memo": _cfg.INBOX_FOLDER,
            "daily":      _cfg.DAILY_FOLDER,
            "lecture":    _cfg.AREAS_FOLDER,
            "reference":  _cfg.RESOURCES_FOLDER,
        }
        if data.category == "discussion":
            base = self._overrides.get("discussion_base", _cfg.PROJECTS_FOLDER)
            project_name = (data.project or "기타").strip("[]").split("|")[0].strip()
            return self.vault_path / base / project_name
        folder = self._overrides.get(data.category) or defaults.get(data.category, _cfg.MEETINGS_FOLDER)
        return self.vault_path / folder

    def save(self, data: NoteData, main_note: str, transcript_note: str = None) -> dict:
        folder = self._get_folder(data)
        folder.mkdir(parents=True, exist_ok=True)

        filenames = get_note_filenames(data)
        vault_name = self.vault_path.name
        result: dict = {}

        if isinstance(filenames, tuple):
            main_fn, transcript_fn = filenames
            (folder / main_fn).write_text(main_note, encoding="utf-8")
            if transcript_note:
                (folder / transcript_fn).write_text(transcript_note, encoding="utf-8")
            result["note_uri"]        = self._obsidian_uri(vault_name, main_fn)
            result["note_path"]       = str(folder / main_fn)
            result["transcript_uri"]  = self._obsidian_uri(vault_name, transcript_fn)
            result["transcript_path"] = str(folder / transcript_fn)
            # 하위 호환 키
            result["meeting_uri"]  = result["note_uri"]
            result["meeting_path"] = result["note_path"]
        else:
            note_fn = filenames
            (folder / note_fn).write_text(main_note, encoding="utf-8")
            result["note_uri"]  = self._obsidian_uri(vault_name, note_fn)
            result["note_path"] = str(folder / note_fn)

        print(f"[VaultWriter] saved: {folder}")
        return result

    def _obsidian_uri(self, vault_name: str, filename: str) -> str:
        return (
            f"obsidian://open"
            f"?vault={quote(vault_name)}"
            f"&file={quote(filename[:-3])}"
        )
```

**Step 2: `test_vault_writer.py` 업데이트 (기존 테스트 수정 + 신규 추가)**

```python
import pytest
from pathlib import Path
from datetime import date
from pipeline.note_builder import (
    NoteData, build_meeting_note, build_transcript_note, get_filenames,
    build_voice_memo_note, build_daily_note,
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
```

**Step 3: 테스트 실행**

```bash
cd meetscribe
pytest tests/test_vault_writer.py -v
```
Expected: 전체 PASS (기존 4 → 신규 7개로 업데이트)

**Step 4: 전체 테스트 회귀 확인**

```bash
cd meetscribe
pytest tests/ -v
```
Expected: 전체 PASS

**Step 5: Commit**

```bash
git add meetscribe/pipeline/vault_writer.py meetscribe/tests/test_vault_writer.py
git commit -m "feat: category-aware VaultWriter with per-category folder routing"
```

---

## Task 6: `main.py` — 카테고리 플러밍

**Files:**
- Modify: `meetscribe/main.py`
- Modify: `meetscribe/tests/test_confirm_api.py` (있으면)
- Add test: `meetscribe/tests/test_upload_category.py`

**Step 1: import 추가 및 `ConfirmPayload` 변경**

`main.py` 상단 import에 추가:

```python
from pipeline.note_builder import (
    NoteData, build_meeting_note, build_transcript_note,
    build_discussion_note, build_note,
)
```

`ConfirmPayload` 교체:

```python
class ConfirmPayload(BaseModel):
    analysis: dict = {}        # 카테고리 분석 결과 (category-generic)
    speaker_map: dict[str, str] = {}
    # 하위 호환: 기존 회의 필드 (analysis가 비어있을 때 폴백)
    purpose: str = ""
    discussion: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    follow_up: list[str] = []
```

**Step 2: `/upload` 엔드포인트에 `category` 필드 추가**

```python
@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
    context: str = Form(""),
    category: str = Form("meeting"),   # 신규
):
    ...
    background_tasks.add_task(
        _process, job_id, save_path, effective_title,
        project.strip(), file.filename, context.strip(), category.strip()
    )
    return {"job_id": job_id}
```

**Step 3: `_process()` 시그니처 + 카테고리 라우팅**

```python
def _process(
    job_id: str, audio_path: Path, title: str, project: str,
    original_filename: str, context: str = "", category: str = "meeting"
):
    ...
    # analyze_transcript 호출 수정
    analysis = analyze_transcript(transcript_result["full_text"], category=category, context=context)

    # review 상태에 category 포함
    job_status[job_id].update({
        "status": "review", "step": "검토 중...", "progress": 97,
        "detail": "분석 결과를 확인하고 저장 버튼을 클릭하세요.",
        "analysis": analysis,
        "category": category,          # 신규
        "speakers": review_speakers,
        "elapsed": int(time.time() - start_time),
    })

    # confirm 후 분석 데이터 읽기 수정
    while True:
        time.sleep(0.5)
        cur = job_status[job_id].get("status")
        if cur == "confirmed":
            edited = job_status[job_id].get("analysis_edited") or {}
            speaker_map = edited.pop("speaker_map", {})
            # 신규: generic analysis dict 우선
            if edited.get("analysis"):
                analysis = edited["analysis"]
            elif any(k in edited for k in ("purpose", "discussion", "decisions")):
                # 하위 호환: 기존 개별 필드
                edited.pop("analysis", None)
                analysis = edited
            break
        ...

    # NoteData 생성 + 노트 빌드 (카테고리 분기)
    update("building", "노트 생성 중...", 98, "노트 빌드 중...")
    speakers = sorted({seg["speaker"] for seg in transcript_result["segments"]})

    if category in ("meeting", "discussion"):
        note_data = NoteData(
            date=date.today(),
            title=title,
            audio_filename=original_filename,
            duration=transcript_result["duration"],
            speakers=speakers,
            purpose=analysis.get("purpose", ""),
            discussion=analysis.get("discussion", []),
            decisions=analysis.get("decisions", []),
            action_items=analysis.get("action_items", []),
            follow_up=analysis.get("follow_up", []),
            transcript=transcript_result["segments"],
            project=project,
            category=category,
        )
        main_note = build_discussion_note(note_data) if category == "discussion" else build_meeting_note(note_data)
        transcript_note = build_transcript_note(note_data)
    else:
        note_data = NoteData(
            date=date.today(),
            title=title,
            audio_filename=original_filename,
            duration=transcript_result["duration"],
            speakers=speakers,
            purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
            transcript=transcript_result["segments"],
            project=project,
            category=category,
            extra=analysis,
        )
        main_note = build_note(note_data)
        transcript_note = None

    update("saving", "Vault에 저장 중...", 99, "파일 저장 중...")
    writer = VaultWriter(config.VAULT_PATH)
    result = writer.save(note_data, main_note, transcript_note)
    ...
```

**Step 4: `/settings` GET에 신규 폴더 변수 추가**

```python
@app.get("/settings")
def get_settings():
    env = _read_env()
    masked = {}
    for k in [
        "WHISPER_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY", "HF_TOKEN",
        "VAULT_PATH", "MEETINGS_FOLDER", "INBOX_FOLDER", "DAILY_FOLDER",
        "AREAS_FOLDER", "PROJECTS_FOLDER", "RESOURCES_FOLDER", "DOMAIN_VOCAB",
    ]:
        v = env.get(k, "")
        masked[k] = _MASK if k in _SECRET_KEYS and v else v
    return masked
```

**Step 5: `SettingsPayload`에 신규 폴더 변수 추가**

```python
class SettingsPayload(BaseModel):
    WHISPER_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HF_TOKEN: str = ""
    VAULT_PATH: str = ""
    MEETINGS_FOLDER: str = ""
    INBOX_FOLDER: str = ""
    DAILY_FOLDER: str = ""
    AREAS_FOLDER: str = ""
    PROJECTS_FOLDER: str = ""
    RESOURCES_FOLDER: str = ""
    DOMAIN_VOCAB: str = ""
```

**Step 6: `_scan_projects`에서 하드코딩된 `"20_Projects"` 교체**

```python
def _scan_projects(vault_path: Path) -> list[dict]:
    projects_dir = vault_path / config.PROJECTS_FOLDER  # "20_Projects" → config
    ...
```

**Step 7: `/confirm` 엔드포인트 업데이트 — analysis 저장 방식 변경**

```python
@app.post("/confirm/{job_id}")
def confirm_job(job_id: str, payload: ConfirmPayload):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    if job_status[job_id].get("status") != "review":
        raise HTTPException(400, "Job is not in review state")

    edited = payload.model_dump()
    # analysis가 비어있으면 기존 개별 필드를 analysis에 합침 (하위 호환)
    if not edited.get("analysis"):
        legacy = {k: edited[k] for k in ("purpose", "discussion", "decisions", "action_items", "follow_up") if edited.get(k)}
        if legacy:
            edited["analysis"] = legacy
    job_status[job_id]["analysis_edited"] = edited
    job_status[job_id]["status"] = "confirmed"
    return {"ok": True}
```

**Step 8: 테스트 작성 — `tests/test_upload_category.py`**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
import io

# config 설정 전에 환경변수 패치
import os
os.environ.setdefault("VAULT_PATH", "/tmp/test_vault")
os.environ.setdefault("GEMINI_API_KEY", "fake")
os.environ.setdefault("ALLOW_CPU", "true")


@pytest.fixture
def client(tmp_path):
    os.environ["VAULT_PATH"] = str(tmp_path)
    (tmp_path / "10_Calendar" / "13_Meetings").mkdir(parents=True)
    with patch("pipeline.transcriber.is_cuda_available", return_value=False):
        from main import app
        with TestClient(app) as c:
            yield c


def test_upload_accepts_category_field(client, tmp_path):
    """category 필드를 포함한 업로드 요청이 200을 반환한다."""
    audio_bytes = b"fake audio data"
    response = client.post(
        "/upload",
        data={"title": "테스트", "category": "voice_memo"},
        files={"file": ("test.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert response.status_code == 200
    assert "job_id" in response.json()


def test_upload_defaults_to_meeting_category(client):
    """category 없이 업로드하면 기본값 meeting으로 처리된다."""
    audio_bytes = b"fake audio data"
    response = client.post(
        "/upload",
        data={"title": "회의"},
        files={"file": ("test.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert response.status_code == 200


def test_settings_returns_folder_vars(client):
    """GET /settings가 신규 폴더 변수를 포함해 반환한다."""
    response = client.get("/settings")
    assert response.status_code == 200
    data = response.json()
    assert "INBOX_FOLDER" in data
    assert "DAILY_FOLDER" in data
    assert "AREAS_FOLDER" in data
```

**Step 9: 테스트 실행**

```bash
cd meetscribe
pytest tests/test_upload_category.py -v
pytest tests/test_confirm_api.py -v
```
Expected: PASS

**Step 10: 전체 테스트 회귀**

```bash
cd meetscribe
pytest tests/ -v
```
Expected: 전체 PASS

**Step 11: Commit**

```bash
git add meetscribe/main.py meetscribe/tests/test_upload_category.py
git commit -m "feat: add category field to upload endpoint and route pipeline accordingly"
```

---

## Task 7: `static/index.html` — 카테고리 UI

**Files:**
- Modify: `meetscribe/static/index.html`

이 태스크는 HTML/CSS/JS 수정이므로 기능별로 세분화한다. 기존 JS 로직(폴링·녹음·설정)은 건드리지 않는다.

### 7-A: CSS 추가 — 카테고리 탭

`<style>` 블록 안 기존 스타일 끝에 추가:

```css
/* ── CATEGORY TABS ── */
.category-tabs {
  display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 14px;
}
.cat-tab {
  padding: 5px 12px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--surface-2); color: var(--text-2);
  font-family: var(--font); font-size: 0.78rem; cursor: pointer;
  transition: all .15s;
}
.cat-tab:hover { border-color: var(--border-strong); color: var(--text); }
.cat-tab.active {
  background: var(--accent); border-color: var(--accent); color: #fff;
}
/* ── CATEGORY FORM GROUPS ── */
.cat-fields { display: none; }
.cat-fields.visible { display: block; }
```

### 7-B: HTML 수정 — 카테고리 탭 + 동적 폼

기존 `.fields-start` div를 아래로 교체:

```html
<!-- 카테고리 선택 -->
<div class="category-tabs">
  <button class="cat-tab active" data-cat="meeting">회의</button>
  <button class="cat-tab" data-cat="voice_memo">보이스 메모</button>
  <button class="cat-tab" data-cat="daily">데일리</button>
  <button class="cat-tab" data-cat="lecture">강의/세미나</button>
  <button class="cat-tab" data-cat="discussion">프로젝트 논의</button>
  <button class="cat-tab" data-cat="reference">레퍼런스</button>
</div>

<!-- 회의 / 프로젝트 논의 공통 필드 -->
<div class="cat-fields visible" id="fields-meeting-like">
  <div class="field">
    <label for="title" id="title-label">회의 제목</label>
    <input type="text" id="title" placeholder="비워두면 파일명 사용">
  </div>
  <div class="field" id="project-field">
    <label for="project">프로젝트</label>
    <select id="project"><option value="">선택 안 함</option></select>
  </div>
  <div class="field" id="context-field">
    <label for="context" id="context-label">회의 맥락 <span class="opt">(전사·분석 정확도 향상)</span></label>
    <textarea id="context" rows="2" placeholder="예: 레이더 시스템 설계 검토, 전투체계 통합 일정 논의"></textarea>
  </div>
</div>

<!-- 보이스 메모 필드 -->
<div class="cat-fields" id="fields-voice-memo">
  <div class="field">
    <label for="vm-title">메모 제목</label>
    <input type="text" id="vm-title" placeholder="비워두면 파일명 사용">
  </div>
  <div class="field">
    <label for="vm-context">메모 맥락 <span class="opt">(선택)</span></label>
    <textarea id="vm-context" rows="2" placeholder="예: 퇴근길 아이디어 메모"></textarea>
  </div>
</div>

<!-- 데일리 업무일지 필드 -->
<div class="cat-fields" id="fields-daily">
  <div class="field">
    <label for="daily-context">추가 메모 <span class="opt">(선택)</span></label>
    <textarea id="daily-context" rows="2" placeholder="예: 오전 미팅 내용 포함됨"></textarea>
  </div>
</div>

<!-- 강의/세미나 필드 -->
<div class="cat-fields" id="fields-lecture">
  <div class="field">
    <label for="lec-title">강의 제목</label>
    <input type="text" id="lec-title" placeholder="강의명 또는 주제">
  </div>
  <div class="field">
    <label for="lec-source">강사/출처 <span class="opt">(선택)</span></label>
    <input type="text" id="lec-source" placeholder="예: 김철수 교수, Coursera">
  </div>
  <div class="field">
    <label for="lec-context">학습 맥락 <span class="opt">(선택)</span></label>
    <textarea id="lec-context" rows="2" placeholder="예: 제어 시스템 스터디 3주차"></textarea>
  </div>
</div>

<!-- 레퍼런스 리뷰 필드 -->
<div class="cat-fields" id="fields-reference">
  <div class="field">
    <label for="ref-title">레퍼런스 제목</label>
    <input type="text" id="ref-title" placeholder="논문명 또는 문서명">
  </div>
  <div class="field">
    <label for="ref-source">출처 <span class="opt">(선택)</span></label>
    <input type="text" id="ref-source" placeholder="예: IEEE, 사내 기술 문서">
  </div>
  <div class="field">
    <label for="ref-context">검토 목적 <span class="opt">(선택)</span></label>
    <textarea id="ref-context" rows="2" placeholder="예: USV 항법 알고리즘 개선 참고용"></textarea>
  </div>
</div>
```

버튼 위의 레이블을 `회의 분석 시작`에서 카테고리별로 바꾸지 않고 `분석 시작`으로 통일.

### 7-C: HTML 수정 — 검토 패널 (카테고리별 필드)

기존 `<div id="review-panel">` 내 `.review-body` 교체:

```html
<div class="review-body">
  <!-- 공통: 화자 이름 -->
  <div class="rv-field">
    <label>화자 이름 지정 <span class="opt">(선택)</span></label>
    <div id="rv-speakers"></div>
  </div>
  <!-- 카테고리별 분석 필드 (JS로 렌더링) -->
  <div id="rv-analysis-fields"></div>
  <div class="rv-actions">
    <button id="rv-save-btn">Vault에 저장</button>
    <button id="rv-cancel-btn">취소</button>
  </div>
</div>
```

### 7-D: HTML 수정 — 결과 섹션 (단일/이중 노트 대응)

기존 `<div id="result">` 교체:

```html
<div id="result">
  <div class="result-card">
    <div class="result-header">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      처리 완료
    </div>
    <div class="result-body">
      <p class="result-hint">Obsidian에서 바로 열기</p>
      <a id="lnk-note" class="obs-btn" href="#">
        <span class="obs-btn-icon">📝</span><span id="lnk-note-label">노트 열기</span>
      </a>
      <a id="lnk-transcript" class="obs-btn" href="#" style="display:none">
        <span class="obs-btn-icon">📄</span>전사 노트 열기
      </a>
    </div>
  </div>
</div>
```

### 7-E: HTML 수정 — 설정 모달 (폴더 설정 섹션 추가)

기존 "Obsidian Vault" 섹션 안 `s-folder` 필드 아래에 추가:

```html
<div class="modal-section">
  <div class="modal-section-title">카테고리별 저장 폴더</div>
  <div class="modal-field">
    <label for="s-inbox-folder">보이스 메모 폴더</label>
    <input type="text" id="s-inbox-folder" placeholder="00_Inbox">
  </div>
  <div class="modal-field">
    <label for="s-daily-folder">데일리 폴더</label>
    <input type="text" id="s-daily-folder" placeholder="10_Calendar/11_Daily">
  </div>
  <div class="modal-field">
    <label for="s-areas-folder">강의/레퍼런스 폴더</label>
    <input type="text" id="s-areas-folder" placeholder="30_Areas">
  </div>
  <div class="modal-field">
    <label for="s-projects-folder">프로젝트 논의 기본 폴더</label>
    <input type="text" id="s-projects-folder" placeholder="20_Projects">
  </div>
  <div class="modal-field">
    <label for="s-resources-folder">레퍼런스 폴더</label>
    <input type="text" id="s-resources-folder" placeholder="40_Resources">
  </div>
</div>
```

### 7-F: JS 추가 — 카테고리 탭 로직

`<script>` 안 기존 변수 선언 이후에 추가:

```javascript
// ── 카테고리 탭 ────────────────────────────────────────────────────────
let currentCategory = 'meeting';

const CAT_FIELDS = {
  meeting:    'fields-meeting-like',
  voice_memo: 'fields-voice-memo',
  daily:      'fields-daily',
  lecture:    'fields-lecture',
  discussion: 'fields-meeting-like',  // 공유
  reference:  'fields-reference',
};

const CAT_LABELS = {
  meeting:    '회의',
  voice_memo: '보이스 메모',
  daily:      '데일리',
  lecture:    '강의/세미나',
  discussion: '프로젝트 논의',
  reference:  '레퍼런스',
};

document.querySelectorAll('.cat-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentCategory = btn.dataset.cat;
    switchCategoryFields(currentCategory);
  });
});

function switchCategoryFields(cat) {
  // 모든 필드 그룹 숨기기
  const shown = new Set();
  document.querySelectorAll('.cat-fields').forEach(el => el.classList.remove('visible'));
  // 해당 카테고리 필드만 표시 (discussion은 meeting-like 공유)
  const fieldId = CAT_FIELDS[cat] || 'fields-meeting-like';
  if (!shown.has(fieldId)) {
    document.getElementById(fieldId).classList.add('visible');
    shown.add(fieldId);
  }
  // project 드롭다운: meeting과 discussion만 표시
  const projectField = document.getElementById('project-field');
  if (projectField) {
    projectField.style.display = (cat === 'meeting' || cat === 'discussion') ? 'block' : 'none';
  }
  // 레이블 업데이트
  const titleLabel = document.getElementById('title-label');
  if (titleLabel) titleLabel.textContent = CAT_LABELS[cat] + ' 제목';
  const contextLabel = document.getElementById('context-label');
  if (contextLabel) contextLabel.innerHTML = CAT_LABELS[cat] + ' 맥락 <span class="opt">(전사·분석 정확도 향상)</span>';
}
```

### 7-G: JS 수정 — 업로드 폼 데이터에 category + 동적 title/context 포함

기존 `btn.addEventListener('click', ...)` 안의 FormData 구성 교체:

```javascript
// 카테고리에 따라 title/context 값 읽기
function getFormValues() {
  const cat = currentCategory;
  let titleVal = '', contextVal = '';
  if (cat === 'meeting' || cat === 'discussion') {
    titleVal   = document.getElementById('title').value;
    contextVal = document.getElementById('context').value;
  } else if (cat === 'voice_memo') {
    titleVal   = document.getElementById('vm-title').value;
    contextVal = document.getElementById('vm-context').value;
  } else if (cat === 'daily') {
    titleVal   = '';
    contextVal = document.getElementById('daily-context').value;
  } else if (cat === 'lecture') {
    titleVal   = document.getElementById('lec-title').value;
    contextVal = document.getElementById('lec-context').value;
  } else if (cat === 'reference') {
    titleVal   = document.getElementById('ref-title').value;
    contextVal = document.getElementById('ref-context').value;
  }
  return { titleVal, contextVal };
}

// FormData 구성 (기존 코드를 아래로 교체)
const { titleVal, contextVal } = getFormValues();
const fd = new FormData();
fd.append('file', file);
fd.append('title', titleVal);
fd.append('project', document.getElementById('project').value || '');
fd.append('context', contextVal);
fd.append('category', currentCategory);
```

### 7-H: JS 수정 — 검토 패널 카테고리별 렌더링

**CATEGORY_REVIEW_FIELDS 정의 추가:**

```javascript
const CATEGORY_REVIEW_FIELDS = {
  meeting: [
    { id: 'purpose', label: '회의 목적', rows: 2, isList: false },
    { id: 'discussion', label: '주요 논의', rows: 3, isList: true },
    { id: 'decisions', label: '결정 사항', rows: 2, isList: true },
    { id: 'action_items', label: '액션 아이템', rows: 3, isList: true },
    { id: 'follow_up', label: '후속 과제', rows: 2, isList: true },
  ],
  discussion: [  // meeting과 동일
    { id: 'purpose', label: '목적', rows: 2, isList: false },
    { id: 'discussion', label: '주요 논의', rows: 3, isList: true },
    { id: 'decisions', label: '결정 사항', rows: 2, isList: true },
    { id: 'action_items', label: '액션 아이템', rows: 3, isList: true },
    { id: 'follow_up', label: '후속 질문', rows: 2, isList: true },
  ],
  voice_memo: [
    { id: 'summary', label: '요약', rows: 2, isList: false },
    { id: 'key_points', label: '핵심 포인트', rows: 3, isList: true },
    { id: 'action_items', label: '할 일', rows: 2, isList: true },
  ],
  daily: [
    { id: 'tasks_done', label: '완료 업무', rows: 3, isList: true },
    { id: 'tasks_tomorrow', label: '내일 할 일', rows: 3, isList: true },
    { id: 'issues', label: '문제/이슈', rows: 2, isList: true },
    { id: 'reflection', label: '소감', rows: 2, isList: false },
  ],
  lecture: [
    { id: 'summary', label: '강의 요약', rows: 2, isList: false },
    { id: 'key_concepts', label: '핵심 개념', rows: 3, isList: true },
    { id: 'important_points', label: '중요 포인트', rows: 3, isList: true },
    { id: 'references', label: '참고 자료', rows: 2, isList: true },
    { id: 'questions', label: '질문', rows: 2, isList: true },
  ],
  reference: [
    { id: 'summary', label: '요약', rows: 2, isList: false },
    { id: 'key_findings', label: '핵심 발견', rows: 3, isList: true },
    { id: 'methodology', label: '방법론', rows: 2, isList: false },
    { id: 'applicability', label: '업무 적용 가능성', rows: 2, isList: false },
    { id: 'citations', label: '인용', rows: 2, isList: true },
  ],
};
```

**`showReviewPanel` 교체:**

```javascript
function showReviewPanel(analysis, speakers, category) {
  if (!analysis) return;
  document.getElementById('right-placeholder').style.display = 'none';

  // 화자 매핑
  const speakerSection = document.getElementById('rv-speakers');
  speakerSection.innerHTML = '';
  (speakers || []).forEach(sp => {
    const row = document.createElement('div');
    row.className = 'rv-speaker-row';
    row.innerHTML = `<span class="rv-speaker-label">${sp}</span><span class="rv-speaker-arrow">→</span><input type="text" class="rv-speaker-input" data-speaker="${sp}" placeholder="실명 (비워두면 ${sp})">`;
    speakerSection.appendChild(row);
  });

  // 카테고리별 분석 필드 렌더링
  const fields = CATEGORY_REVIEW_FIELDS[category] || CATEGORY_REVIEW_FIELDS['meeting'];
  const container = document.getElementById('rv-analysis-fields');
  container.innerHTML = '';
  fields.forEach(f => {
    const div = document.createElement('div');
    div.className = 'rv-field';
    const val = analysis[f.id];
    const displayVal = f.isList ? (val || []).join('\n') : (val || '');
    div.innerHTML = `<label>${f.label}${f.isList ? ' <span class="opt">(줄바꿈으로 구분)</span>' : ''}</label><textarea id="rv-${f.id}" rows="${f.rows}">${displayVal}</textarea>`;
    container.appendChild(div);
  });

  document.getElementById('review-panel').style.display = 'block';
  cancelBtn.style.display = 'none';
  const rvSave = document.getElementById('rv-save-btn');
  rvSave.disabled = false; rvSave.textContent = 'Vault에 저장';
}
```

**`poll()` 안 review 처리 수정:**

```javascript
if (d.status === 'review') {
  setStep('s-ai', 'done');
  setProgress(97, '분석 완료 — 내용을 확인하고 저장하세요.');
  appendLogs(d.logs);
  showReviewPanel(d.analysis, d.speakers, d.category || 'meeting');  // category 추가
  return;
}
```

**`rv-save-btn` 클릭 핸들러 교체:**

```javascript
document.getElementById('rv-save-btn').addEventListener('click', async () => {
  const saveBtn = document.getElementById('rv-save-btn');
  saveBtn.disabled = true; saveBtn.textContent = '저장 중...';

  const speakerMap = {};
  document.querySelectorAll('.rv-speaker-input').forEach(input => {
    const val = input.value.trim(); if (val) speakerMap[input.dataset.speaker] = val;
  });

  // 현재 렌더링된 모든 rv-* textarea 값 수집 → analysis dict
  const analysis = {};
  const cat = document.querySelector('.cat-tab.active')?.dataset.cat || 'meeting';
  const fields = CATEGORY_REVIEW_FIELDS[cat] || CATEGORY_REVIEW_FIELDS['meeting'];
  fields.forEach(f => {
    const el = document.getElementById(`rv-${f.id}`);
    if (!el) return;
    analysis[f.id] = f.isList
      ? el.value.split('\n').map(l => l.trim()).filter(Boolean)
      : el.value.trim();
  });

  const payload = { speaker_map: speakerMap, analysis };
  try {
    const r = await fetch(`/confirm/${currentJobId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    hide('review-panel'); setStep('s-save', 'active');
  } catch (e) {
    saveBtn.disabled = false; saveBtn.textContent = 'Vault에 저장';
    showErr('저장 요청 실패: ' + e.message);
  }
});
```

### 7-I: JS 수정 — 결과 섹션 (단일/이중 노트)

기존 `done` 처리 부분 교체:

```javascript
} else if (d.status === 'done') {
  clearInterval(t); setStep('s-save', 'done');
  setProgress(100, d.detail || '완료'); stopElapsedTimer();
  appendLogs(d.logs); removeCursor(); cancelBtn.style.display = 'none';
  document.getElementById('right-placeholder').style.display = 'none';
  // note_uri (primary) 처리
  const noteLink = document.getElementById('lnk-note');
  const noteLabel = document.getElementById('lnk-note-label');
  noteLink.href = d.result.note_uri || d.result.meeting_uri || '#';
  noteLabel.textContent = d.category === 'meeting' ? '회의 노트 열기'
    : d.category === 'discussion' ? '논의 노트 열기'
    : d.category === 'daily' ? '업무일지 열기'
    : d.category === 'lecture' ? '강의 노트 열기'
    : d.category === 'reference' ? '레퍼런스 노트 열기'
    : '노트 열기';
  // transcript_uri (선택적)
  const transcriptLink = document.getElementById('lnk-transcript');
  if (d.result.transcript_uri) {
    transcriptLink.href = d.result.transcript_uri;
    transcriptLink.style.display = 'flex';
  } else {
    transcriptLink.style.display = 'none';
  }
  show('result'); btn.disabled = false; return;
}
```

### 7-J: JS 수정 — 설정 모달 폴더 필드 로드/저장

`openSettings()` 함수 안에 추가:

```javascript
document.getElementById('s-inbox-folder').value    = s.INBOX_FOLDER    || '';
document.getElementById('s-daily-folder').value    = s.DAILY_FOLDER    || '';
document.getElementById('s-areas-folder').value    = s.AREAS_FOLDER    || '';
document.getElementById('s-projects-folder').value = s.PROJECTS_FOLDER || '';
document.getElementById('s-resources-folder').value = s.RESOURCES_FOLDER || '';
```

`save-btn` 클릭 핸들러의 `payload` 객체에 추가:

```javascript
INBOX_FOLDER:     document.getElementById('s-inbox-folder').value,
DAILY_FOLDER:     document.getElementById('s-daily-folder').value,
AREAS_FOLDER:     document.getElementById('s-areas-folder').value,
PROJECTS_FOLDER:  document.getElementById('s-projects-folder').value,
RESOURCES_FOLDER: document.getElementById('s-resources-folder').value,
```

**Step (최종): 브라우저 수동 테스트**

1. `run.bat` (또는 `uvicorn main:app --host 0.0.0.0 --port 8765`) 실행
2. `http://localhost:8765` 접속
3. 카테고리 탭 클릭 — 폼 필드 전환 확인
4. 파일 업로드 후 분석 결과 검토 패널에 카테고리별 필드 표시 확인
5. 설정 모달 — 새 폴더 필드 표시 확인

**Step (최종-2): 전체 테스트**

```bash
cd meetscribe
pytest tests/ -v
```
Expected: 전체 PASS

**Step (최종-3): Commit**

```bash
git add meetscribe/static/index.html
git commit -m "feat: add category tabs, dynamic forms, and category-aware review panel"
```

---

## 완료 기준

- [ ] `pytest tests/ -v` 전체 PASS
- [ ] 6개 카테고리 탭 클릭 → 폼 필드 전환 동작
- [ ] 각 카테고리 파일 업로드 → 분석 완료 → 리뷰 패널에 올바른 필드 표시
- [ ] Vault에 올바른 폴더에 올바른 파일명으로 저장
- [ ] 기존 `.env` 수정 없이 회의 카테고리 기존 동작 유지
