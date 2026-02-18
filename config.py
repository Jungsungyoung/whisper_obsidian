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
