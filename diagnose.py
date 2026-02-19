"""Quick local diagnostics for WhisperX/CUDA setup."""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CUDA_DLL_PATH = os.getenv("CUDA_DLL_PATH", r"D:\cuda_libs\dlls")

if Path(CUDA_DLL_PATH).exists():
    os.environ["PATH"] = f"{CUDA_DLL_PATH};" + os.environ.get("PATH", "")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _step(title: str):
    print(title)
    print("-" * len(title))


print("=" * 50)
_step("1) torch")
try:
    import torch

    print(f"version: {torch.__version__}")
    print(f"cuda_available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")
except Exception as exc:
    print(f"error: {exc}")

_step("2) ctranslate2")
try:
    import ctranslate2

    print(f"cuda_device_count: {ctranslate2.get_cuda_device_count()}")
except Exception as exc:
    print(f"error: {exc}")

_step("3) whisperx import")
try:
    import whisperx
    import whisperx.audio

    print(f"ok (sample_rate={whisperx.audio.SAMPLE_RATE})")
except Exception as exc:
    print(f"error: {exc}")

_step("4) transcriber._detect_device")
try:
    from pipeline.transcriber import _detect_device

    device, compute_type = _detect_device()
    print(f"device={device}, compute_type={compute_type}")
except Exception as exc:
    print(f"error: {exc}")

_step("5) whisperx.load_model")
try:
    import whisperx
    import config
    from pipeline.transcriber import _detect_device

    device, compute_type = _detect_device()
    print(f"loading model={config.WHISPER_MODEL} device={device} compute_type={compute_type}")
    whisperx.load_model(config.WHISPER_MODEL, device, compute_type=compute_type, language="ko")
    print("model_load_ok")
except Exception as exc:
    import traceback

    print(f"error: {exc}")
    traceback.print_exc()

print("=" * 50)
