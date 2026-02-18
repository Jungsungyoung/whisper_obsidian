import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "").strip()
HF_TOKEN: str = os.environ.get("HF_TOKEN", "").strip()
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
VAULT_PATH: Path = Path(os.environ.get("VAULT_PATH", "."))
MEETINGS_FOLDER: str = os.getenv("MEETINGS_FOLDER", "10_Calendar/13_Meetings")
UPLOAD_DIR: Path = Path(__file__).parent / "uploads"


def validate_config() -> None:
    """앱 시작 시 설정값 검증 - FastAPI lifespan에서 호출"""
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        raise RuntimeError(
            "LLM API 키 누락: OPENAI_API_KEY 또는 GEMINI_API_KEY 중 하나는 필요합니다.\n"
            ".env 파일을 확인하세요."
        )
    if not os.environ.get("VAULT_PATH"):
        raise RuntimeError(
            "필수 환경변수 누락: VAULT_PATH\n.env 파일을 확인하세요."
        )
    vault = Path(os.environ["VAULT_PATH"])
    if not vault.exists():
        raise RuntimeError(f"Vault 경로를 찾을 수 없습니다: {vault}")
    meetings_path = vault / MEETINGS_FOLDER
    if not meetings_path.exists():
        meetings_path.mkdir(parents=True)
    UPLOAD_DIR.mkdir(exist_ok=True)
