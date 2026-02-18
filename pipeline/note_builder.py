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


def get_filenames(data: NoteData) -> tuple[str, str]:
    date_str = data.date.strftime("%Y-%m-%d")
    return f"[회의] {date_str} {data.title}.md", f"[전사] {date_str} {data.title}.md"


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
    meeting_fn, _ = get_filenames(data)
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
