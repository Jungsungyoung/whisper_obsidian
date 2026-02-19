"""Local script to test FastAPI upload/status flow."""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUDA_DLL_PATH = os.getenv("CUDA_DLL_PATH", r"D:\cuda_libs\dlls")
SERVER_URL = os.getenv("MEETSCRIBE_SERVER_URL", "http://localhost:8765")
DEFAULT_AUDIO = PROJECT_ROOT / "tests" / "sample.mp3"
AUDIO_FILE = Path(os.getenv("MEETSCRIBE_TEST_AUDIO", str(DEFAULT_AUDIO)))


def start_server() -> subprocess.Popen | None:
    env = dict(os.environ)
    if Path(CUDA_DLL_PATH).exists():
        env["PATH"] = f"{CUDA_DLL_PATH};" + env.get("PATH", "")

    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    print("starting server...", end="", flush=True)
    for _ in range(30):
        time.sleep(1)
        print(".", end="", flush=True)
        try:
            urllib.request.urlopen(f"{SERVER_URL}/", timeout=2)
            print(" ready")
            return proc
        except Exception:
            continue

    print(" failed")
    proc.terminate()
    return None


def upload_file(audio_path: Path) -> dict:
    boundary = b"----MeetScribeBoundary"
    body = b""
    body += b"--" + boundary + b"\r\n"
    body += b'Content-Disposition: form-data; name="file"; filename="' + audio_path.name.encode() + b'"\r\n'
    body += b"Content-Type: audio/mp4\r\n\r\n"
    body += audio_path.read_bytes()
    body += b"\r\n"
    body += b"--" + boundary + b"\r\n"
    body += b'Content-Disposition: form-data; name="title"\r\n\r\n'
    body += "test upload".encode("utf-8")
    body += b"\r\n"
    body += b"--" + boundary + b"--\r\n"

    req = urllib.request.Request(
        f"{SERVER_URL}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def poll_status(job_id: str) -> bool:
    print(f"\n[job {job_id[:8]}] polling")
    last_pct = -1
    started = time.time()

    while True:
        try:
            resp = urllib.request.urlopen(f"{SERVER_URL}/status/{job_id}", timeout=5)
            data = json.loads(resp.read())
        except Exception as exc:
            print(f"status error: {exc}")
            time.sleep(2)
            continue

        pct = data.get("progress", 0)
        detail = data.get("detail", "")
        elapsed = data.get("elapsed", 0)
        status = data.get("status", "")

        if pct != last_pct or status in ("done", "error"):
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"[{bar}] {pct:3d}% {detail} ({elapsed}s)")
            last_pct = pct

        if status == "done":
            total = int(time.time() - started)
            print(f"\ncompleted in {total}s")
            result = data.get("result", {})
            print(f"meeting note: {result.get('meeting_uri', '')}")
            print(f"transcript note: {result.get('transcript_uri', '')}")
            return True
        if status == "error":
            print(f"\nerror: {data.get('error', '')}")
            return False

        time.sleep(1.5)


if __name__ == "__main__":
    if not AUDIO_FILE.exists():
        print(f"audio not found: {AUDIO_FILE}")
        print("set MEETSCRIBE_TEST_AUDIO to a real file path")
        raise SystemExit(1)

    print(f"audio: {AUDIO_FILE.name} ({AUDIO_FILE.stat().st_size // 1024 // 1024}MB)")

    proc = start_server()
    if not proc:
        raise SystemExit(1)

    try:
        print("uploading file...")
        response = upload_file(AUDIO_FILE)
        poll_status(response["job_id"])
    finally:
        proc.terminate()
        print("\nserver stopped")
