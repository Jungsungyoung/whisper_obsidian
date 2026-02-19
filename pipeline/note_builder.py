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
    filenames = get_note_filenames(data)
    if isinstance(filenames, tuple):
        meeting_fn = filenames[0]
    else:
        meeting_fn = filenames
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
