from pathlib import Path
from urllib.parse import quote
import config as _cfg
from pipeline.note_builder import NoteData, get_note_filenames


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
