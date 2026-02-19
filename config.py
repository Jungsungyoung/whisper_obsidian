import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "").strip()
HF_TOKEN: str = os.environ.get("HF_TOKEN", "").strip()
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
LLM_MODEL: str = os.getenv("LLM_MODEL", "").strip() or "gemini-2.0-flash"
VAULT_PATH: Path = Path(os.environ.get("VAULT_PATH", "."))
MEETINGS_FOLDER: str = os.getenv("MEETINGS_FOLDER", "10_Calendar/13_Meetings")
INBOX_FOLDER: str = os.getenv("INBOX_FOLDER", "00_Inbox")
DAILY_FOLDER: str = os.getenv("DAILY_FOLDER", "10_Calendar/11_Daily")
AREAS_FOLDER: str = os.getenv("AREAS_FOLDER", "30_Areas")
PROJECTS_FOLDER: str = os.getenv("PROJECTS_FOLDER", "20_Projects")
RESOURCES_FOLDER: str = os.getenv("RESOURCES_FOLDER", "40_Resources")
UPLOAD_DIR: Path = Path(__file__).parent / "uploads"
ALLOW_CPU: bool = os.getenv("ALLOW_CPU", "false").strip().lower() == "true"
DOMAIN_VOCAB: str = os.getenv("DOMAIN_VOCAB", "함정, 선박, 전투체계, 소나, 레이더, 추진체계, 함교, 수상함, 잠수함, 어뢰, 기관실, 항법, 통신체계").strip()


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
    for folder_name in [INBOX_FOLDER, DAILY_FOLDER, AREAS_FOLDER,
                        PROJECTS_FOLDER, RESOURCES_FOLDER]:
        folder_path = vault / folder_name
        if not folder_path.exists():
            folder_path.mkdir(parents=True)
    UPLOAD_DIR.mkdir(exist_ok=True)

    # GPU 가용성 확인
    from pipeline.transcriber import is_cuda_available
    if not is_cuda_available() and not ALLOW_CPU:
        raise RuntimeError(
            "GPU(CUDA)를 사용할 수 없습니다.\n"
            "CPU 모드로 실행하려면 .env에 ALLOW_CPU=true 를 추가하세요."
        )
