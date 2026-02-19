# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the repo root (`meetscribe/`):

```bash
# Install dependencies
pip install -r requirements.txt

# GPU support (optional, CUDA 12.1)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Run server
uvicorn main:app --host 0.0.0.0 --port 8765
# or on Windows (includes CUDA path + cloudflared auto-start):
run.bat

# Unit tests (all)
pytest tests/ -v

# Single test file
pytest tests/test_analyzer.py -v

# Single test
pytest tests/test_note_builder.py::test_function_name -v

# E2E test (requires actual audio file)
MEETSCRIBE_E2E_AUDIO="C:/path/to/audio.m4a" python tests/e2e_test.py

# Server flow test (starts server, uploads, polls)
python tests/test_server.py

# Environment diagnostics
python diagnose.py
```

## Architecture

**MeetScribe** is a local FastAPI web app that transcribes audio and saves categorised Obsidian notes.

### Request lifecycle

```
POST /upload?category=meeting
  → background task: _process()
      → transcribe()           # pipeline/transcriber.py
      → analyze_transcript()   # pipeline/analyzer.py
      → job status = "review"  (waits for POST /confirm/{job_id})
      → build_meeting_note() / build_discussion_note() / build_note()  # pipeline/note_builder.py
      → VaultWriter.save()     # pipeline/vault_writer.py
      → job status = "done"

GET  /status/{job_id}   # frontend polls; returns segments array in "review" state
POST /confirm/{job_id}  # user submits edited analysis + speaker_map
POST /cancel/{job_id}   # sets status="cancelling"; _process() checks this
GET  /projects          # scans VAULT_PATH/20_Projects/*/
GET  /settings          # masked env vars
POST /settings          # writes .env in-place, importlib.reload(config)
```

**Job states:** `queued → transcribing → analyzing → review → confirmed → building → saving → done` (or `error` / `cancelled`)

### Pipeline module contracts

| Module | Key function | Signature | Returns |
|--------|-------------|-----------|---------|
| `transcriber.py` | `transcribe` | `(audio_path, on_progress, context)` | `{segments, full_text, duration, method}` |
| `analyzer.py` | `analyze_transcript` | `(text, category="meeting", context="")` | `{purpose, discussion, decisions, action_items, follow_up}` |
| `note_builder.py` | `build_meeting_note` / `build_discussion_note` | `(NoteData)` | `str` (markdown) |
| `note_builder.py` | `build_note` | `(NoteData)` | `str` — dispatcher for non-meeting categories |
| `vault_writer.py` | `VaultWriter.save` | `(data, main_note, transcript_note=None)` | `{note_path, note_uri, …}` |

**`VaultWriter` constructor:** `VaultWriter(vault_path, folder_overrides: dict | None = None)`
- `folder_overrides` keys: `"meeting"`, `"voice_memo"`, `"daily"`, `"lecture"`, `"reference"`, `"discussion_base"`

### Category system

6 categories, each with its own LLM prompt, note builder, and Vault folder:

| Category | Note output | Builder | Vault folder var |
|----------|-------------|---------|-----------------|
| `meeting` | dual (main + transcript) | `build_meeting_note` + `build_transcript_note` | `MEETINGS_FOLDER` |
| `discussion` | dual (main + transcript) | `build_discussion_note` + `build_transcript_note` | `PROJECTS_FOLDER/<project>` |
| `voice_memo` | single | `build_voice_memo_note` | `INBOX_FOLDER` |
| `daily` | single | `build_daily_note` | `DAILY_FOLDER` |
| `lecture` | single | `build_lecture_note` | `AREAS_FOLDER` |
| `reference` | single | `build_reference_note` | `RESOURCES_FOLDER` |

`NoteData.extra` holds category-specific LLM fields (e.g. `key_points`, `tasks_done`, `key_concepts`).

### Fallback chains

- **Transcription:** WhisperX local (GPU→CPU) → OpenAI Whisper API (`whisper-1`)
- **Analysis:** Gemini (`GEMINI_API_KEY`) → OpenAI (`OPENAI_API_KEY`) → regex extraction
- **Speaker diarization:** pyannote (requires `HF_TOKEN` + license) → all speakers `Speaker A`

### Configuration (`config.py`)

Single source of truth for all env vars. Import `config` directly — no `os.getenv()` inside pipeline modules. `validate_config()` runs at startup via FastAPI lifespan.

Key vars:

| Var | Default | Purpose |
|-----|---------|---------|
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | — | LLM (one required) |
| `HF_TOKEN` | — | Speaker diarization |
| `VAULT_PATH` | — | Required |
| `WHISPER_MODEL` | `base` | `tiny`/`base`/`small`/`medium`/`large` |
| `LLM_MODEL` | `gemini-2.0-flash` | |
| `ALLOW_CPU` | `false` | Required if no CUDA GPU |
| `DOMAIN_VOCAB` | *(navy vocab)* | Comma-separated terms for Whisper prompt |
| `ACCESS_PIN` | `""` | PIN auth (empty = no auth) |
| `SECRET_KEY` | random | Session signing key (set fixed value to persist sessions across restarts) |
| `MEETINGS_FOLDER` … `RESOURCES_FOLDER` | see config.py | Per-category Vault paths |

### `context` field

Upload form `context` text is injected into:
1. Whisper `initial_prompt` (alongside `DOMAIN_VOCAB`) for transcription accuracy
2. LLM prompt prefix as `[회의 맥락: ...]`

## Conventions

- Pipeline modules import `config` at top level; never call `os.getenv()` inside pipeline.
- `on_progress(pct: int, detail: str)` callback passed into `transcribe()`; called at 0, 40, 70, 90%.
- Speaker labels: `Speaker A`, `Speaker B`, … (alphabetical, max 26). `speaker_map` in `/confirm` payload renames them before saving.
- Transcript segment format: `{"timestamp": "MM:SS", "speaker": "Speaker A", "text": "..."}`.
- `TestClient` (httpx) cannot be used — incompatible with starlette 0.35.1. Tests call functions directly.
- `get_filenames()` in `note_builder.py` is a legacy alias (meeting only). Use `get_note_filenames()` for all categories.
