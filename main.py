import os
import uuid
import time
from pathlib import Path
from datetime import date
from contextlib import asynccontextmanager

# PyTorch 번들 cuDNN DLL을 PATH에 추가 (pyannote가 cuDNN을 찾을 수 있도록)
try:
    import torch as _torch
    _torch_lib = str(Path(_torch.__file__).parent / "lib")
    os.environ["PATH"] = _torch_lib + ";" + os.environ.get("PATH", "")
    del _torch, _torch_lib
except Exception:
    pass

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

import config
from config import validate_config
from pipeline.transcriber import transcribe
from pipeline.analyzer import analyze_transcript
from pipeline.note_builder import (
    NoteData, build_meeting_note, build_transcript_note,
    build_discussion_note, build_note,
)
from pipeline.vault_writer import VaultWriter

# in-memory job store (단일 프로세스)
job_status: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    yield


app = FastAPI(title="MeetScribe", lifespan=lifespan)

# ── PIN AUTH MIDDLEWARE (SessionMiddleware보다 먼저 선언 → 내부에서 실행됨) ──
@app.middleware("http")
async def pin_auth_middleware(request: Request, call_next):
    if not config.ACCESS_PIN:
        return await call_next(request)
    path = request.url.path
    if path == "/login" or path.startswith("/static"):
        return await call_next(request)
    if request.session.get("authenticated"):
        return await call_next(request)
    return RedirectResponse(url="/login", status_code=302)


# ── SESSION MIDDLEWARE (나중에 추가 = outermost = 먼저 실행됨) ──
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=86400,  # 24시간
    https_only=False,  # Cloudflare Tunnel은 HTTPS이지만 내부는 HTTP
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


_LOGIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MeetScribe — 로그인</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f4f4f2; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: #fff; border-radius: 12px; padding: 32px 28px;
            width: 100%; max-width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
    h1 { font-size: 1.1rem; font-weight: 700; margin-bottom: 4px; }
    p  { font-size: 0.82rem; color: #666; margin-bottom: 24px; }
    label { display: block; font-size: 0.78rem; font-weight: 500;
            color: #555; margin-bottom: 6px; }
    input[type=password] { width: 100%; padding: 10px 12px; border: 1px solid #ddd;
                           border-radius: 8px; font-size: 1rem; outline: none;
                           transition: border-color .15s; }
    input[type=password]:focus { border-color: #2563eb; }
    button { width: 100%; padding: 11px; margin-top: 14px;
             background: #2563eb; color: #fff; border: none; border-radius: 8px;
             font-size: 0.9rem; font-weight: 600; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    .err { color: #dc2626; font-size: 0.8rem; margin-top: 10px; display: none; }
  </style>
</head>
<body>
  <div class="card">
    <h1>MeetScribe</h1>
    <p>접속 PIN을 입력하세요.</p>
    <form method="post" action="/login">
      <label for="pin">PIN</label>
      <input type="password" id="pin" name="pin" autocomplete="current-password"
             inputmode="numeric" placeholder="••••" autofocus>
      <button type="submit">확인</button>
    </form>
    {error}
  </div>
</body>
</html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(_LOGIN_HTML.replace("{error}", ""))


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, pin: str = Form("")):
    if pin == config.ACCESS_PIN:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    err = '<p class="err" style="display:block">PIN이 올바르지 않습니다.</p>'
    return HTMLResponse(_LOGIN_HTML.replace("{error}", err), status_code=401)


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
    context: str = Form(""),
    category: str = Form("meeting"),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"지원하지 않는 파일 형식: {suffix}")

    job_id = str(uuid.uuid4())
    save_path = config.UPLOAD_DIR / f"{job_id}{suffix}"
    save_path.write_bytes(await file.read())

    effective_title = title.strip() or Path(file.filename).stem
    job_status[job_id] = {"status": "queued", "step": "", "progress": 0, "detail": "", "elapsed": 0, "result": None, "error": None, "logs": []}
    background_tasks.add_task(
        _process, job_id, save_path, effective_title,
        project.strip(), file.filename, context.strip(), category.strip()
    )
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    return job_status[job_id]


_ENV_PATH = Path(__file__).parent / ".env"
_MASK = "●●●●●●●●"
_SECRET_KEYS = {"GEMINI_API_KEY", "OPENAI_API_KEY", "HF_TOKEN"}


def _read_env() -> dict[str, str]:
    result = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _write_env(data: dict[str, str]) -> None:
    lines = []
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.partition("=")[0].strip()
                if k in data:
                    continue
            lines.append(line)
    for k, v in data.items():
        lines.append(f"{k}={v}")
    _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _scan_projects(vault_path: Path) -> list[dict]:
    """Vault의 20_Projects/ 폴더에서 status: 진행 Dashboard 파일 수집."""
    import yaml
    projects_dir = vault_path / config.PROJECTS_FOLDER
    if not projects_dir.exists():
        return []
    result = []
    try:
        for folder in sorted(projects_dir.iterdir()):
            if not folder.is_dir():
                continue
            for md_file in folder.glob("*Dashboard*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    if text.startswith("---"):
                        end = text.index("---", 3)
                        fm = yaml.safe_load(text[3:end])
                        if isinstance(fm, dict) and fm.get("status") == "진행":
                            raw = folder.name
                            display = "_".join(raw.split("_")[1:]).replace("_", " ")
                            link = f"[[{md_file.stem}]]"
                            result.append({"display": display, "link": link})
                except Exception:
                    continue
    except Exception:
        return []
    return result


@app.get("/projects")
def get_projects():
    return _scan_projects(config.VAULT_PATH)


@app.post("/cancel/{job_id}")
def cancel_job(job_id: str):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    if job_status[job_id]["status"] not in ("done", "error", "cancelled"):
        job_status[job_id]["status"] = "cancelling"
    return {"ok": True}


@app.get("/settings")
def get_settings():
    env = _read_env()
    masked = {}
    for k in [
        "WHISPER_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY", "HF_TOKEN",
        "VAULT_PATH", "MEETINGS_FOLDER", "INBOX_FOLDER", "DAILY_FOLDER",
        "AREAS_FOLDER", "PROJECTS_FOLDER", "RESOURCES_FOLDER", "DOMAIN_VOCAB",
    ]:
        v = env.get(k, "")
        masked[k] = _MASK if k in _SECRET_KEYS and v else v
    return masked


class ConfirmPayload(BaseModel):
    analysis: dict = {}        # 카테고리 분석 결과 (category-generic)
    speaker_map: dict[str, str] = {}
    # 하위 호환: 기존 회의 필드 (analysis가 비어있을 때 폴백)
    purpose: str = ""
    discussion: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    follow_up: list[str] = []


def _apply_speaker_map(segments: list[dict], speaker_map: dict[str, str]) -> list[dict]:
    """segments의 speaker 필드를 speaker_map으로 치환. 빈 값이면 원래 이름 유지."""
    for seg in segments:
        mapped = speaker_map.get(seg["speaker"], "")
        if mapped:
            seg["speaker"] = mapped
    return segments


@app.post("/confirm/{job_id}")
def confirm_job(job_id: str, payload: ConfirmPayload):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    if job_status[job_id].get("status") != "review":
        raise HTTPException(400, "Job is not in review state")

    edited = payload.model_dump()
    # analysis가 비어있으면 기존 개별 필드를 analysis에 합침 (하위 호환)
    if not edited.get("analysis"):
        legacy = {k: edited[k] for k in ("purpose", "discussion", "decisions", "action_items", "follow_up") if edited.get(k)}
        if legacy:
            edited["analysis"] = legacy
    job_status[job_id]["analysis_edited"] = edited
    job_status[job_id]["status"] = "confirmed"
    return {"ok": True}


class SettingsPayload(BaseModel):
    WHISPER_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HF_TOKEN: str = ""
    VAULT_PATH: str = ""
    MEETINGS_FOLDER: str = ""
    INBOX_FOLDER: str = ""
    DAILY_FOLDER: str = ""
    AREAS_FOLDER: str = ""
    PROJECTS_FOLDER: str = ""
    RESOURCES_FOLDER: str = ""
    DOMAIN_VOCAB: str = ""


@app.post("/settings")
def save_settings(payload: SettingsPayload):
    updates = {}
    for k, v in payload.model_dump().items():
        if v and v != _MASK:
            updates[k] = v
    _write_env(updates)
    # config 리로드
    import importlib
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH, override=True)
    importlib.reload(config)
    return {"ok": True}


def _process(job_id: str, audio_path: Path, title: str, project: str, original_filename: str, context: str = "", category: str = "meeting"):
    start_time = time.time()

    def _log(detail: str):
        elapsed = int(time.time() - start_time)
        m, s = divmod(elapsed, 60)
        job_status[job_id]["logs"].append(f"[{m:02d}:{s:02d}] {detail}")

    def update(status: str, step: str, progress: int = 0, detail: str = ""):
        job_status[job_id].update({
            "status": status, "step": step,
            "progress": progress, "detail": detail,
            "elapsed": int(time.time() - start_time),
        })
        if detail:
            _log(detail)

    def on_transcribe_progress(pct: int, detail: str):
        job_status[job_id].update({
            "progress": pct, "detail": detail,
            "elapsed": int(time.time() - start_time),
        })
        if detail:
            _log(detail)

    def is_cancelled() -> bool:
        return job_status[job_id].get("status") == "cancelling"

    def mark_cancelled():
        _log("사용자에 의해 취소됨")
        job_status[job_id].update({
            "status": "cancelled", "step": "취소됨", "progress": 0,
            "detail": "취소됨", "elapsed": int(time.time() - start_time),
        })

    try:
        update("transcribing", "전사 중...", 0, "모델 준비 중...")
        transcript_result = transcribe(audio_path, on_progress=on_transcribe_progress, context=context)

        if is_cancelled():
            mark_cancelled()
            return

        update("analyzing", "AI 분석 중...", 96, "Gemini 분석 중...")
        analysis = analyze_transcript(transcript_result["full_text"], category=category, context=context)

        if is_cancelled():
            mark_cancelled()
            return

        # 사용자 검토 대기 (speakers는 review panel 표시용으로 미리 계산)
        review_speakers = sorted({seg["speaker"] for seg in transcript_result["segments"]})
        _log("AI 분석 완료. 결과를 확인하고 저장 버튼을 클릭하세요.")
        job_status[job_id].update({
            "status": "review", "step": "검토 중...", "progress": 97,
            "detail": "분석 결과를 확인하고 저장 버튼을 클릭하세요.",
            "analysis": analysis,
            "category": category,
            "speakers": review_speakers,
            "elapsed": int(time.time() - start_time),
        })

        while True:
            time.sleep(0.5)
            cur = job_status[job_id].get("status")
            if cur == "confirmed":
                edited = job_status[job_id].get("analysis_edited") or {}
                speaker_map = edited.pop("speaker_map", {})
                # 신규: generic analysis dict 우선
                if edited.get("analysis"):
                    analysis = edited["analysis"]
                elif any(k in edited for k in ("purpose", "discussion", "decisions")):
                    # 하위 호환: 기존 개별 필드
                    edited.pop("analysis", None)
                    analysis = edited
                if speaker_map:
                    _apply_speaker_map(transcript_result["segments"], speaker_map)
                break
            if cur == "cancelling":
                mark_cancelled()
                return

        update("building", "노트 생성 중...", 98, "노트 빌드 중...")
        speakers = sorted({seg["speaker"] for seg in transcript_result["segments"]})

        if category in ("meeting", "discussion"):
            note_data = NoteData(
                date=date.today(),
                title=title,
                audio_filename=original_filename,
                duration=transcript_result["duration"],
                speakers=speakers,
                purpose=analysis.get("purpose", ""),
                discussion=analysis.get("discussion", []),
                decisions=analysis.get("decisions", []),
                action_items=analysis.get("action_items", []),
                follow_up=analysis.get("follow_up", []),
                transcript=transcript_result["segments"],
                project=project,
                category=category,
            )
            main_note = build_discussion_note(note_data) if category == "discussion" else build_meeting_note(note_data)
            transcript_note = build_transcript_note(note_data)
        else:
            note_data = NoteData(
                date=date.today(),
                title=title,
                audio_filename=original_filename,
                duration=transcript_result["duration"],
                speakers=speakers,
                purpose="", discussion=[], decisions=[], action_items=[], follow_up=[],
                transcript=transcript_result["segments"],
                project=project,
                category=category,
                extra=analysis,
            )
            main_note = build_note(note_data)
            transcript_note = None

        update("saving", "Vault에 저장 중...", 99, "파일 저장 중...")
        writer = VaultWriter(config.VAULT_PATH)
        result = writer.save(note_data, main_note, transcript_note)

        done_msg = f"완료 — 총 {int(time.time() - start_time)}초 소요"
        _log(done_msg)
        job_status[job_id].update({
            "status": "done", "step": "완료", "progress": 100,
            "detail": done_msg,
            "elapsed": int(time.time() - start_time), "result": result, "error": None,
            "category": category,
        })

    except Exception as e:
        _log(f"오류: {e}")
        job_status[job_id].update({
            "status": "error", "step": "오류", "progress": 0,
            "detail": str(e), "result": None, "error": str(e),
        })
    finally:
        if audio_path.exists():
            audio_path.unlink()


