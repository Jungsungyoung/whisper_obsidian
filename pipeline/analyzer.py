import re
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
    """Gemini 우선, 실패 시 OpenAI, 마지막은 기본 추출."""
    if config.GEMINI_API_KEY:
        try:
            return _analyze_gemini(transcript_text)
        except Exception as e:
            print(f"[Analyzer] Gemini 실패: {e}. OpenAI로 폴백.")

    if config.OPENAI_API_KEY:
        try:
            return _analyze_openai(transcript_text)
        except Exception as e:
            print(f"[Analyzer] OpenAI 실패: {e}. 기본 분석 사용.")

    return _analyze_basic(transcript_text)


def _analyze_gemini(transcript_text: str) -> dict:
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = f"{SYSTEM_PROMPT}\n\n다음 회의 내용을 분석해주세요:\n\n{transcript_text}"
    response = client.models.generate_content(
        model=config.LLM_MODEL,
        contents=prompt,
    )
    return parse_llm_response(response.text)


def _analyze_openai(transcript_text: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 회의 내용을 분석해주세요:\n\n{transcript_text}"},
        ],
        temperature=0.3,
    )
    return parse_llm_response(response.choices[0].message.content)


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


def parse_llm_response(response: str) -> dict:
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
