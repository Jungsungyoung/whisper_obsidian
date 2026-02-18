# MeetScribe

회의 녹음 파일을 업로드하면 자동으로 전사하고 AI가 분석해 Obsidian 노트를 생성합니다.

## 파이프라인

```
mp3/wav/m4a 업로드
    → Whisper 전사 (로컬 우선, OpenAI API 폴백)
    → GPT-4o-mini 분석 (목적 / 주요논의 / 결정 / 액션아이템)
    → Obsidian Vault에 [회의] + [전사] 노트 자동 생성
```

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 실제 값 입력
```

## HuggingFace 설정 (화자 분리용)

1. https://hf.co/pyannote/speaker-diarization-3.1 → Accept License
2. https://hf.co/pyannote/segmentation-3.0 → Accept License
3. https://hf.co/settings/tokens → Read 토큰 생성 → `.env`의 `HF_TOKEN`에 입력

> pyannote 없이 OpenAI API만 쓰려면 `HF_TOKEN`을 임의 값으로 설정하세요.
> 로컬 Whisper 실패 시 자동으로 OpenAI API로 폴백됩니다.

## .env 설정

```env
OPENAI_API_KEY=sk-...
HF_TOKEN=hf_...
WHISPER_MODEL=base          # tiny / base / small / medium / large
LLM_MODEL=gpt-4o-mini
VAULT_PATH=C:\Users\Admin\OneDrive\문서\Obsidian Vault
MEETINGS_FOLDER=10_Calendar/13_Meetings
```

## 실행

```bash
uvicorn main:app --port 8765
# 또는 Windows에서
run.bat
```

브라우저에서 http://localhost:8765 열기

## 테스트

```bash
# 단위 테스트 (18개)
pytest tests/test_note_builder.py tests/test_vault_writer.py tests/test_analyzer.py -v

# 통합 테스트 (오디오 파일 필요)
pip install gtts
python tests/generate_test_audio.py
pytest tests/test_integration.py -v -s
```

## 출력 노트 형식

Vault의 `10_Calendar/13_Meetings/` 에 두 파일이 생성됩니다:

- `[회의] YYYY-MM-DD 제목.md` — 기존 Meeting Note 템플릿 호환 (요약 + 액션아이템)
- `[전사] YYYY-MM-DD 제목.md` — 타임스탬프 + 화자 포함 전체 전사본
