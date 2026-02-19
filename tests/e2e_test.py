"""Run end-to-end transcription directly (without FastAPI server)."""

import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUDA_DLL_PATH = os.getenv("CUDA_DLL_PATH", r"D:\cuda_libs\dlls")
DEFAULT_AUDIO = PROJECT_ROOT / "tests" / "sample.mp3"
AUDIO = Path(os.getenv("MEETSCRIBE_E2E_AUDIO", str(DEFAULT_AUDIO)))

if Path(CUDA_DLL_PATH).exists():
    os.environ["PATH"] = f"{CUDA_DLL_PATH};" + os.environ.get("PATH", "")

# PyTorch 번들 cuDNN DLL을 PATH에 추가 (pyannote가 cuDNN을 찾을 수 있도록)
try:
    import torch
    torch_lib = Path(torch.__file__).parent / "lib"
    if torch_lib.exists():
        os.environ["PATH"] = f"{torch_lib};" + os.environ.get("PATH", "")
except Exception:
    pass

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if not AUDIO.exists():
    print(f"audio not found: {AUDIO}")
    print("set MEETSCRIBE_E2E_AUDIO to a real file path")
    raise SystemExit(1)

progress_log: list[str] = []
start_time = time.time()


def on_progress(pct: int, detail: str):
    elapsed = time.time() - start_time
    msg = f"[{elapsed:5.1f}s] {pct:3d}% {detail}"
    print(msg, flush=True)
    progress_log.append(msg)


from pipeline.transcriber import transcribe, is_cuda_available

if not is_cuda_available():
    print("[경고] GPU(CUDA)를 사용할 수 없습니다. CPU 모드로 실행하면 매우 느립니다.")
    answer = input("CPU 모드로 계속 진행하시겠습니까? [y/N] ").strip().lower()
    if answer != "y":
        print("중단합니다.")
        raise SystemExit(0)
    print("CPU 모드로 실행합니다.\n")
else:
    print("[OK] GPU(CUDA) 감지됨. GPU 모드로 실행합니다.\n")

print(f"audio: {AUDIO.name} ({AUDIO.stat().st_size // 1024 // 1024}MB)")
print("transcription start...\n")

result = transcribe(AUDIO, on_progress=on_progress)

elapsed = time.time() - start_time
print(f"\nfinished in {elapsed:.1f}s")
print(f"method: {result['method']}")
print(f"duration: {result['duration']}")
print(f"segments: {len(result['segments'])}")

speakers = {segment["speaker"] for segment in result["segments"]}
print(f"speakers: {sorted(speakers)}\n")

print("=== transcript preview (first 10) ===")
for segment in result["segments"][:10]:
    print(f"{segment['timestamp']}  {segment['speaker']:10s}  {segment['text'][:60]}")

if len(speakers) > 1:
    print("\nspeaker diarization: OK")
else:
    print("\nspeaker diarization: only 1 speaker detected")
