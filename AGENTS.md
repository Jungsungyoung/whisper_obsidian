# Repository Guidelines

## Project Structure & Module Organization
- `main.py`: FastAPI entrypoint and upload/status endpoints.
- `pipeline/`: core processing modules (`transcriber.py`, `analyzer.py`, `note_builder.py`, `vault_writer.py`).
- `tests/`: unit and integration tests plus fixtures (`sample.mp3`, `generate_test_audio.py`).
- `static/`: browser UI served by FastAPI.
- `docs/plans/`: design and implementation notes.
- Runtime/output paths: `uploads/` for temporary files and the Obsidian vault path configured in `.env`.

## Build, Test, and Development Commands
Run commands from the repo root (`meetscribe/`):

```bash
pip install -r requirements.txt
Copy-Item .env.example .env   # Windows PowerShell
uvicorn main:app --host 0.0.0.0 --port 8765
```

`run.bat` starts the same server and prepends the local CUDA DLL path.

```bash
pytest tests/test_note_builder.py tests/test_vault_writer.py tests/test_analyzer.py -v
pytest tests/test_integration.py -v -s
python tests/generate_test_audio.py   # creates sample.mp3 (requires gtts)
python tests/e2e_test.py              # end-to-end transcription (requires MEETSCRIBE_E2E_AUDIO)
python tests/test_server.py           # full upload/status flow against live server
```

## Coding Style & Naming Conventions
- Python with 4-space indentation and PEP 8-aligned formatting.
- Use type hints on public functions and clear return schemas between pipeline steps.
- `snake_case` for modules/functions/variables, `PascalCase` for classes/dataclasses (for example `NoteData`, `VaultWriter`).
- Keep each pipeline module single-purpose and avoid cross-module side effects.

## Testing Guidelines
- Framework: `pytest`.
- Name tests with `test_*.py`; keep one behavior per test.
- Add/adjust unit tests for parsing, formatting, and data-shaping logic.
- Add integration coverage when changing end-to-end flow (transcription -> analysis -> note save).
- If a test needs audio input, document fixture generation in the PR.

## Commit & Pull Request Guidelines
- Follow observed Conventional Commit prefixes: `feat:`, `fix:`, `docs:`.
- Keep commits atomic and scoped to one logical change.
- PRs should include: objective, files/modules touched, config/env impact, and exact test commands run.
- Include screenshots for UI changes in `static/index.html`.

## Security & Configuration Tips
- Never commit `.env`, API keys, or local vault filesystem paths.
- Ensure `VAULT_PATH` and at least one API key (`OPENAI_API_KEY` or `GEMINI_API_KEY`) are set before starting the app.
