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
