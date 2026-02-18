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
    """OpenAI 우선, 실패 시 HuggingFace Inference API 폴백."""
    try:
        return _analyze_openai(transcript_text)
    except Exception as e:
        print(f"[Analyzer] OpenAI 실패: {e}. HuggingFace API로 폴백.")
        try:
            return _analyze_hf(transcript_text)
        except Exception as e2:
            print(f"[Analyzer] HuggingFace 실패: {e2}. 기본 분석 사용.")
            return _analyze_basic(transcript_text)


def _analyze_openai(transcript_text: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 회의 내용을 분석해주세요:\n\n{transcript_text}"},
        ],
        temperature=0.3,
    )
    return parse_llm_response(response.choices[0].message.content)


def _analyze_hf(transcript_text: str) -> dict:
    """HuggingFace Inference API를 통한 분석."""
    import json
    import urllib.request

    model_id = "mistralai/Mistral-7B-Instruct-v0.3"
    prompt = (
        f"<s>[INST] {SYSTEM_PROMPT}\n\n"
        f"다음 회의 내용을 분석해주세요:\n\n{transcript_text} [/INST]"
    )

    payload = json.dumps({
        "inputs": prompt,
        "parameters": {"max_new_tokens": 512, "temperature": 0.3, "return_full_text": False},
    }).encode()

    req = urllib.request.Request(
        f"https://api-inference.huggingface.co/models/{model_id}",
        data=payload,
        headers={
            "Authorization": f"Bearer {config.HF_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        result = json.loads(r.read())

    if isinstance(result, list) and result:
        text = result[0].get("generated_text", "")
    else:
        text = str(result)

    return parse_llm_response(text)


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
