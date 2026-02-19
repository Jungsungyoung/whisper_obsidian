# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `meetscribe/`:

```bash
# Install dependencies
pip install -r requirements.txt

# GPU support (optional, CUDA 12.1)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Run server
uvicorn main:app --host 0.0.0.0 --port 8765
# or on Windows:
run.bat

# Unit tests (all)
pytest tests/ -v

# Single test file
pytest tests/test_analyzer.py -v

# Single test
pytest tests/test_note_builder.py::test_function_name -v

# E2E test (requires actual audio file)
MEETSCRIBE_E2E_AUDIO="C:/path/to/audio.m4a" python tests/e2e_test.py

# Environment diagnostics
python diagnose.py
```

## Architecture

**MeetScribe** is a local FastAPI web app that transcribes meeting audio and saves Obsidian notes.

### Request lifecycle

```
POST /upload
  → background task: _process()
      → transcribe()        # pipeline/transcriber.py
      → analyze_transcript() # pipeline/analyzer.py
      → job status = "review" (waits for POST /confirm/{job_id})
      → build_meeting_note() / build_transcript_note() # pipeline/note_builder.py
      → VaultWriter.save()  # pipeline/vault_writer.py
      → job status = "done"

GET /status/{job_id}   # frontend polls this
POST /confirm/{job_id} # user submits edited analysis + speaker_map
POST /cancel/{job_id}  # sets status="cancelling"; _process() checks this
```

**Job states:** `queued → transcribing → analyzing → review → confirmed → building → saving → done` (or `error` / `cancelled`)

### Pipeline module contracts

| Module | Key function | Returns |
|--------|-------------|---------|
| `transcriber.py` | `transcribe(audio_path, on_progress, context)` | `{segments, full_text, duration, method}` |
| `analyzer.py` | `analyze_transcript(text, context)` | `{purpose, discussion, decisions, action_items, follow_up}` |
| `note_builder.py` | `build_meeting_note(NoteData)` / `build_transcript_note(NoteData)` | `str` (markdown) |
| `vault_writer.py` | `VaultWriter(vault_path, folder).save(note_data, meeting_md, transcript_md)` | `{meeting_path, transcript_path}` |

**`NoteData`** (dataclass in `note_builder.py`) is the data contract between the pipeline and note building. All fields come from `transcribe()` + `analyze_transcript()` results.

### Fallback chains

- **Transcription:** WhisperX local (GPU→CPU) → OpenAI Whisper API (`whisper-1`)
- **Analysis:** Gemini (`GEMINI_API_KEY`) → OpenAI (`OPENAI_API_KEY`) → regex extraction
- **Speaker diarization:** pyannote (requires `HF_TOKEN` + license acceptance) → all speakers labeled `Speaker A`

### Configuration (`config.py`)

`config.py` is the single source of truth for all env vars — import `config` directly rather than calling `os.getenv()` in pipeline modules. `validate_config()` runs at startup via FastAPI lifespan and raises `RuntimeError` for missing/invalid config.

Key vars: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`, `WHISPER_MODEL`, `VAULT_PATH`, `MEETINGS_FOLDER`, `ALLOW_CPU`, `DOMAIN_VOCAB`.

`ALLOW_CPU=true` is required to run without a CUDA GPU.

### `context` field

The optional `context` text from the upload form is injected in two places:
1. Whisper `initial_prompt` (alongside `DOMAIN_VOCAB`) to improve transcription accuracy
2. LLM analysis prompt prefix as `[회의 맥락: ...]`

### Projects API (`/projects`)

Scans `VAULT_PATH/20_Projects/*/` for `*Dashboard*.md` files whose YAML frontmatter has `status: 진행`. Returns display name + Obsidian `[[link]]`. Uses `pyyaml` for frontmatter parsing.

### Settings API (`/settings` GET/POST)

Reads and writes `.env` in-place. Secret keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `HF_TOKEN`) are masked as `●●●●●●●●` in GET responses. After POST, reloads `config` module via `importlib.reload(config)` without server restart.

## Conventions

- Pipeline modules import `config` at the top level; no direct `os.getenv()` calls inside pipeline.
- `on_progress(pct: int, detail: str)` callback is passed into `transcribe()` and called at key steps (0, 40, 70, 90%).
- Speaker labels are always `Speaker A`, `Speaker B`, … (alphabetical, up to 26). The `speaker_map` in `/confirm` payload lets users rename them before saving.
- Transcript segments format: `{"timestamp": "MM:SS", "speaker": "Speaker A", "text": "..."}`.
- Output filenames: `[회의] YYYY-MM-DD 제목.md` and `[전사] YYYY-MM-DD 제목.md`.
