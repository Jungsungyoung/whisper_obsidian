# MeetScribe 개발 기여 가이드

> 소스 기준: `requirements.txt`, `config.py`
> 최종 업데이트: 2026-02-20 (MD 임포트 기능 반영)

---

## 목차

1. [개발 환경 설정](#1-개발-환경-설정)
2. [환경변수 설정](#2-환경변수-설정)
3. [실행 명령어](#3-실행-명령어)
4. [테스트](#4-테스트)
5. [디렉토리 구조](#5-디렉토리-구조)
6. [기여 워크플로우](#6-기여-워크플로우)

---

## 1. 개발 환경 설정

### 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.10+ (3.12 권장) |
| pip | 최신 버전 |
| CUDA (선택) | 11.x / 12.x |

### 패키지 설치

```bash
cd meetscribe
pip install -r requirements.txt
```

#### GPU(CUDA) 지원 설치 (선택)

```bash
# CUDA 12.1 기준
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 주요 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `fastapi` | 0.115.0 | 웹 서버 프레임워크 |
| `uvicorn[standard]` | 0.30.0 | ASGI 서버 |
| `itsdangerous` | ≥ 2.1 | PIN 인증 세션 서명 |
| `qrcode` | ≥ 7.0 | 모바일 접속 QR 코드 생성 |
| `openai-whisper` | 20240930 | 음성 전사 (폴백용) |
| `whisperx` | 3.8.1 | 로컬 음성 전사 (주 엔진) |
| `pyannote.audio` | 3.3.2 | 화자 분리 |
| `openai` | 1.40.0 | OpenAI API 클라이언트 |
| `python-dotenv` | 1.0.1 | 환경변수 로딩 |
| `torch` / `torchaudio` | 최신 | ML 백엔드 |
| `numpy` | ≥ 2.0.0 | 수치 연산 |

---

## 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집합니다:

### 필수 / 핵심 변수

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `GEMINI_API_KEY` | LLM 필수* | - | Gemini API 키 (우선 사용) |
| `OPENAI_API_KEY` | LLM 필수* | - | OpenAI API 키 (폴백 LLM + Whisper API) |
| `HF_TOKEN` | 선택 | - | HuggingFace Read 토큰 (화자 분리용) |
| `WHISPER_MODEL` | 선택 | `base` | Whisper 모델 크기 (`tiny`/`base`/`small`/`medium`/`large`) |
| `LLM_MODEL` | 선택 | `gemini-2.0-flash` | 분석에 사용할 LLM 모델명 |
| `VAULT_PATH` | 필수 | - | Obsidian Vault 절대 경로 |
| `ALLOW_CPU` | 선택 | `false` | CPU 모드 허용 (`true` 설정 시 GPU 없어도 실행) |
| `DOMAIN_VOCAB` | 선택 | - | 전사 정확도 향상을 위한 도메인 어휘 목록 (쉼표 구분) |

> \* `GEMINI_API_KEY` 또는 `OPENAI_API_KEY` 중 **하나 이상** 필수

### Vault 폴더 경로 변수

| 변수 | 기본값 | 카테고리 |
|------|--------|----------|
| `MEETINGS_FOLDER` | `10_Calendar/13_Meetings` | 회의 (`meeting`) |
| `INBOX_FOLDER` | `00_Inbox` | 보이스메모 (`voice_memo`) |
| `DAILY_FOLDER` | `10_Calendar/11_Daily` | 일간 노트 (`daily`) |
| `AREAS_FOLDER` | `30_Areas` | 강의 (`lecture`) |
| `PROJECTS_FOLDER` | `20_Projects` | 프로젝트 논의 (`discussion`) |
| `RESOURCES_FOLDER` | `40_Resources` | 레퍼런스 (`reference`) |

### 모바일 접속 보안 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ACCESS_PIN` | `""` (인증 없음) | 숫자 PIN (설정 시 로그인 필요) |
| `SECRET_KEY` | 랜덤 생성 | 세션 쿠키 서명 키 (재시작 시 로그인 유지 불가) |

> 원격 접속 시 `ACCESS_PIN` 설정 강력 권장

### HuggingFace 라이선스 동의 (화자 분리 사용 시)

아래 두 페이지에서 로그인 후 **Accept** 클릭:

- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

---

## 3. 실행 명령어

| 명령어 | 설명 |
|--------|------|
| `run.bat` | Windows 전용 실행 스크립트 (CUDA 경로 포함, `cloudflared` 자동 감지) |
| `uvicorn main:app --host 0.0.0.0 --port 8765` | 서버 직접 실행 |
| `python tunnel.py` | Cloudflare Tunnel 단독 실행 (QR 코드 출력) |
| `python diagnose.py` | 환경 진단 |

서버 시작 후 브라우저에서 **http://localhost:8765** 접속.

---

## 4. 테스트

### 단위 테스트

```bash
cd meetscribe
pytest tests/ -v
```

#### 개별 테스트 모듈

| 파일 | 대상 |
|------|------|
| `tests/test_note_builder.py` | Obsidian 노트 마크다운 생성 (MD 임포트 포함) |
| `tests/test_vault_writer.py` | Vault 파일 저장 (MD dual-note 포함) |
| `tests/test_md_upload.py` | `read_md_text()` — MD 파일 인코딩 파싱 |
| `tests/test_analyzer.py` | Gemini/GPT 분석 파이프라인 |
| `tests/test_speaker_map.py` | 화자 매핑 로직 |
| `tests/test_vocab_context.py` | 도메인 어휘 컨텍스트 |
| `tests/test_projects_api.py` | 프로젝트 API 엔드포인트 |
| `tests/test_confirm_api.py` | 확인 API 엔드포인트 |
| `tests/test_upload_category.py` | 오디오 카테고리 파라미터 |
| `tests/test_prompts.py` | LLM 프롬프트 템플릿 |
| `tests/test_pin_auth.py` | PIN 인증 로직 |
| `tests/test_pin_config.py` | PIN / SECRET_KEY 환경변수 로딩 |
| `tests/test_integration.py` | 파이프라인 통합 테스트 |

### E2E 테스트 (실제 오디오 파일 필요)

```bash
# 테스트용 오디오 생성 (gtts 필요)
pip install gtts
python tests/generate_test_audio.py

# E2E 실행 (서버 없이 직접 파이프라인 실행)
MEETSCRIBE_E2E_AUDIO="C:/path/to/audio.m4a" python tests/e2e_test.py
```

### 서버 동작 테스트

```bash
python tests/test_server.py
```

---

## 5. 디렉토리 구조

```
meetscribe/
├── main.py              # FastAPI 서버 (업로드, 상태 폴링, 파이프라인 실행)
├── config.py            # 환경변수 로딩 및 검증
├── run.bat              # Windows 실행 스크립트 (CUDA 경로 설정 + cloudflared 자동 시작)
├── tunnel.py            # Cloudflare Tunnel 실행 및 QR 코드 출력
├── diagnose.py          # 환경 진단 스크립트
├── requirements.txt     # Python 패키지 목록
├── .env.example         # 환경변수 템플릿
├── .env                 # 실제 환경변수 (직접 생성, 커밋 금지)
├── CLAUDE.md            # Claude Code 프로젝트 지침
├── AGENTS.md            # AI 에이전트 협업 가이드
├── pipeline/
│   ├── transcriber.py   # WhisperX 전사 + 화자 분리 (pyannote)
│   ├── analyzer.py      # Gemini/GPT-4o-mini AI 분석
│   ├── prompts.py       # 카테고리별 LLM 시스템 프롬프트
│   ├── note_builder.py  # Obsidian 노트 마크다운 생성
│   └── vault_writer.py  # Vault 파일 저장
├── static/
│   └── index.html       # 웹 UI (드래그 앤 드롭 업로드, PWA)
├── tests/
│   ├── e2e_test.py           # 전사 E2E 테스트 (서버 없이 직접 실행)
│   ├── test_server.py        # 서버 동작 확인 스크립트
│   ├── generate_test_audio.py # 테스트용 오디오 생성
│   └── test_*.py            # 각 모듈별 단위 테스트
├── uploads/             # 임시 업로드 파일 (처리 후 자동 삭제)
└── docs/                # 문서
    ├── plans/           # 설계/계획 문서
    ├── CONTRIB.md       # 이 파일
    └── RUNBOOK.md       # 운영 런북
```

---

## 6. 기여 워크플로우

### 코드 변경 시

1. `.env`가 정상 설정되어 있는지 확인
2. 변경 사항 구현
3. 단위 테스트 실행: `pytest tests/ -v`
4. (오디오 파일 있는 경우) E2E 테스트로 전체 파이프라인 검증

### 새 환경변수 추가 시

1. `config.py`에 변수 추가
2. `.env.example`에 예시값과 주석 추가
3. 이 파일(`CONTRIB.md`)의 환경변수 표 업데이트
4. `RUNBOOK.md`의 설정 변경 절차 업데이트 (필요시)

### 새 의존성 추가 시

1. `requirements.txt`에 버전 고정(`==`)하여 추가
2. 이 파일의 주요 의존성 표 업데이트

### 주의사항

- `.env` 파일은 절대 커밋하지 않습니다 (`.gitignore` 포함 확인)
- `uploads/` 폴더 내 파일은 커밋하지 않습니다
- `local-vault/` 폴더 내 파일은 커밋하지 않습니다
