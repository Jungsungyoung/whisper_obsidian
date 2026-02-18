import uuid
from pathlib import Path
from datetime import date
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import config
from config import validate_config
from pipeline.transcriber import transcribe
from pipeline.analyzer import analyze_transcript
from pipeline.note_builder import NoteData, build_meeting_note, build_transcript_note
from pipeline.vault_writer import VaultWriter

# in-memory job store (단일 프로세스)
job_status: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    yield


app = FastAPI(title="MeetScribe", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"지원하지 않는 파일 형식: {suffix}")

    job_id = str(uuid.uuid4())
    save_path = config.UPLOAD_DIR / f"{job_id}{suffix}"
    save_path.write_bytes(await file.read())

    effective_title = title.strip() or Path(file.filename).stem
    job_status[job_id] = {"status": "queued", "step": "", "result": None, "error": None}
    background_tasks.add_task(
        _process, job_id, save_path, effective_title, project.strip(), file.filename
    )
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    return job_status[job_id]


def _process(job_id: str, audio_path: Path, title: str, project: str, original_filename: str):
    try:
        _set(job_id, "transcribing", "전사 중...")
        transcript_result = transcribe(audio_path)

        _set(job_id, "analyzing", "AI 분석 중...")
        analysis = analyze_transcript(transcript_result["full_text"])

        _set(job_id, "building", "노트 생성 중...")
        speakers = sorted({seg["speaker"] for seg in transcript_result["segments"]})
        note_data = NoteData(
            date=date.today(),
            title=title,
            audio_filename=original_filename,
            duration=transcript_result["duration"],
            speakers=speakers,
            purpose=analysis["purpose"],
            discussion=analysis["discussion"],
            decisions=analysis["decisions"],
            action_items=analysis["action_items"],
            follow_up=analysis["follow_up"],
            transcript=transcript_result["segments"],
            project=project,
        )

        _set(job_id, "saving", "Vault에 저장 중...")
        writer = VaultWriter(config.VAULT_PATH, config.MEETINGS_FOLDER)
        result = writer.save(note_data, build_meeting_note(note_data), build_transcript_note(note_data))

        job_status[job_id] = {"status": "done", "step": "완료", "result": result, "error": None}

    except Exception as e:
        job_status[job_id] = {"status": "error", "step": "오류", "result": None, "error": str(e)}
    finally:
        if audio_path.exists():
            audio_path.unlink()


def _set(job_id: str, status: str, step: str):
    job_status[job_id] = {"status": status, "step": step, "result": None, "error": None}
