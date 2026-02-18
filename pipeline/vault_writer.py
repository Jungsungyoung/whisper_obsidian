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
        return {
            "meeting_path": str(meeting_path),
            "transcript_path": str(transcript_path),
            "meeting_uri": self._obsidian_uri(vault_name, meeting_fn),
            "transcript_uri": self._obsidian_uri(vault_name, transcript_fn),
        }

    def _obsidian_uri(self, vault_name: str, filename: str) -> str:
        return (
            f"obsidian://open"
            f"?vault={quote(vault_name)}"
            f"&file={quote(filename[:-3])}"
        )
