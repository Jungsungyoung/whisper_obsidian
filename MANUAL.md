# MeetScribe 사용자 매뉴얼

> 회의 녹음 파일을 업로드하면 자동으로 전사하고 AI가 분석해 Obsidian 노트를 생성합니다.

---

## 목차

1. [개요](#1-개요)
2. [시스템 요구사항](#2-시스템-요구사항)
3. [설치](#3-설치)
4. [환경 설정](#4-환경-설정)
5. [실행](#5-실행)
6. [사용 방법](#6-사용-방법)
7. [처리 파이프라인](#7-처리-파이프라인)
8. [출력 결과](#8-출력-결과)
9. [테스트](#9-테스트)
10. [문제 해결](#10-문제-해결)

---

## 1. 개요

MeetScribe는 회의 녹음 파일을 Obsidian 노트로 자동 변환해주는 로컬 웹 애플리케이션입니다.

**주요 기능**
- WhisperX를 이용한 로컬 음성 전사 (GPU/CPU 자동 감지)
- pyannote 기반 화자 분리 (Speaker A, Speaker B 구분)
- Gemini 2.5 Flash(또는 GPT-4o-mini) AI 자동 분석
- Obsidian Vault에 회의 노트 + 전사 노트 자동 생성

**지원 파일 형식**

| 형식 | 확장자 |
|------|--------|
| MP3 | `.mp3` |
| WAV | `.wav` |
| M4A | `.m4a` |
| MP4 | `.mp4` |
| WebM | `.webm` |
| OGG | `.ogg` |

---

## 2. 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| Python | 3.10+ | 3.12 |
| RAM | 8GB | 16GB |
| GPU | 없어도 가능 (CPU 모드) | NVIDIA CUDA 지원 GPU |
| OS | Windows 10+ | Windows 11 |
| Obsidian | 설치 필요 | - |

**API 키 (하나 이상 필요)**
- Gemini API 키 (우선) — [Google AI Studio](https://aistudio.google.com)에서 발급
- OpenAI API 키 (폴백) — [OpenAI Platform](https://platform.openai.com)에서 발급
- HuggingFace 토큰 (화자 분리용) — [HuggingFace Settings](https://huggingface.co/settings/tokens)에서 발급

---

## 3. 설치

### 3-1. 저장소 클론 또는 폴더로 이동

```bash
cd meetscribe
```

### 3-2. 패키지 설치

```bash
pip install -r requirements.txt
```

> **GPU 사용 시 추가 설치** (선택)
> ```bash
> pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
> ```

### 3-3. HuggingFace 라이선스 동의 (화자 분리 기능 사용 시)

아래 두 모델 페이지에서 로그인 후 **Accept** 클릭:

- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

> 라이선스 동의 없이 실행하면 화자 분리가 생략되고 모든 발언이 `Speaker A`로 표시됩니다.

---

## 4. 환경 설정

### 4-1. .env 파일 생성

프로젝트 루트의 `.env.example`을 복사해 `.env`로 저장합니다:

```bash
cp .env.example .env
```

### 4-2. .env 설정값 입력

```env
# LLM API 키 (Gemini 우선, OpenAI 폴백)
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# HuggingFace 토큰 (화자 분리용)
HF_TOKEN=hf_...

# Whisper 모델 크기 (tiny < base < small < medium < large)
# 클수록 정확하지만 느립니다. CPU에서는 base 권장
WHISPER_MODEL=base

# LLM 분석 모델
LLM_MODEL=gpt-4o-mini

# Obsidian Vault 경로 (본인 환경에 맞게 수정)
VAULT_PATH=C:\Users\Admin\OneDrive\문서\Obsidian Vault

# Vault 내 회의 노트 저장 폴더
MEETINGS_FOLDER=10_Calendar/13_Meetings
```

### 4-3. 설정값 설명

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GEMINI_API_KEY` | Gemini API 키 (분석용 LLM) | - |
| `OPENAI_API_KEY` | OpenAI API 키 (폴백 LLM, Whisper API 폴백) | - |
| `HF_TOKEN` | HuggingFace Read 토큰 | - |
| `WHISPER_MODEL` | 전사 모델 크기 | `base` |
| `VAULT_PATH` | Obsidian Vault 절대 경로 | - |
| `MEETINGS_FOLDER` | Vault 내 저장 위치 | `10_Calendar/13_Meetings` |

---

## 5. 실행

### Windows (권장)

```bat
run.bat
```

### 직접 실행

```bash
python main.py
# 또는
uvicorn main:app --port 8765
```

### 서버 시작 확인

브라우저에서 열기: **http://localhost:8765**

---

## 6. 사용 방법

### 6-1. 파일 업로드

![MeetScribe 화면](static/screenshot.png)

1. 브라우저에서 **http://localhost:8765** 접속
2. 파일을 **드래그 앤 드롭**하거나 영역을 **클릭**해 파일 선택
   - 지원 형식: mp3, wav, m4a, mp4, webm, ogg

### 6-2. 옵션 입력 (선택)

| 항목 | 설명 |
|------|------|
| **회의 제목** | 노트 파일명에 사용됩니다. 비워두면 파일명 사용 |
| **프로젝트** | Obsidian 링크 형식 입력 가능. 예: `[[프로젝트 대시보드]]` |

### 6-3. 분석 시작

**분석 시작** 버튼 클릭 후 진행 상황을 실시간으로 확인합니다.

| 단계 | 소요 시간 (예상) |
|------|----------------|
| 업로드 | 수초 |
| Whisper 전사 | 파일 길이 × 1~3배 (CPU 기준) |
| Gemini AI 분석 | 10~30초 |
| Vault 저장 | 1초 이내 |

> **CPU 모드 기준** 30분 녹음 파일 → 약 10~20분 소요
> **GPU(CUDA) 모드** 에서는 2~5배 빠릅니다.

### 6-4. 결과 확인

처리 완료 후 두 개의 버튼이 표시됩니다:

- **회의 노트 열기** — Obsidian에서 요약 노트 바로 열기
- **전사 노트 열기** — Obsidian에서 전체 전사본 바로 열기

---

## 7. 처리 파이프라인

```
오디오 파일 업로드
    │
    ▼
[1단계] WhisperX 전사 (로컬 CPU/GPU)
    │  ├─ 음성 활동 감지 (VAD)
    │  ├─ 음성 → 텍스트 변환
    │  └─ 단어 단위 시간 정렬
    │
    ▼
[2단계] 화자 분리 (pyannote)
    │  ├─ 누가 언제 말했는지 분석
    │  └─ Speaker A, Speaker B ... 로 라벨링
    │
    ▼
[3단계] AI 분석 (Gemini 2.5 Flash)
    │  ├─ 회의 목적 요약
    │  ├─ 주요 논의 사항
    │  ├─ 결정 사항
    │  ├─ 액션 아이템 (담당자 + 마감)
    │  └─ 후속 논의 필요 사항
    │
    ▼
[4단계] Obsidian 노트 생성
    ├─ [회의] YYYY-MM-DD 제목.md  ← 요약 노트
    └─ [전사] YYYY-MM-DD 제목.md  ← 전체 전사본
```

**폴백 처리**
- WhisperX 실패 시 → OpenAI Whisper API 자동 사용
- Gemini 실패 시 → OpenAI GPT-4o-mini 자동 사용
- 화자 분리 실패 시 → 모든 발언을 `Speaker A`로 처리 후 계속 진행

---

## 8. 출력 결과

회의 노트는 `VAULT_PATH/MEETINGS_FOLDER/` 에 저장됩니다.

### 회의 노트 (`[회의] YYYY-MM-DD 제목.md`)

```markdown
---
date: 2026-02-19
title: 주간 팀 미팅
audio: 음성_260219.m4a
duration: 32:14
speakers: [Speaker A, Speaker B]
project: "[[프로젝트 대시보드]]"
---

## 회의 목적
...

## 주요 논의
- ...

## 결정 사항
- ...

## 액션 아이템
- [ ] (담당자) 내용 — 마감: YYYY-MM-DD
- [ ] ...

## 후속 논의
- ...
```

### 전사 노트 (`[전사] YYYY-MM-DD 제목.md`)

```markdown
---
date: 2026-02-19
title: 주간 팀 미팅 (전사본)
---

← [[회의] 2026-02-19 주간 팀 미팅]

| 시각 | 화자 | 내용 |
|------|------|------|
| 00:00 | Speaker A | 안녕하세요, 오늘 미팅 시작하겠습니다. |
| 00:08 | Speaker B | 네, 먼저 지난주 액션 아이템 확인하겠습니다. |
| ... | ... | ... |
```

---

## 9. 테스트

### 단위 테스트 (22개)

```bash
cd meetscribe
pytest tests/ -v
```

### E2E 전사 테스트 (실제 오디오 파일 필요)

```bash
# 환경변수로 오디오 파일 경로 지정
MEETSCRIBE_E2E_AUDIO="C:/path/to/audio.m4a" python e2e_test.py
```

출력 예시:
```
audio: 음성_260206_093032.m4a (15MB)
transcription start...

[122.6s]  40% 전사 완료, 단어 정렬 중...
[406.8s]  70% 화자 분리 중...
[520.0s]  90% 변환 중...

finished in 540.3s
method: local
duration: 32:14
segments: 87
speakers: ['Speaker A', 'Speaker B']

=== transcript preview (first 10) ===
00:00  Speaker A   안녕하세요, 오늘 회의 시작하겠습니다.
...
```

---

## 10. 문제 해결

### 서버가 시작되지 않는 경우

**.env 파일 확인**
```
LLM API 키 누락: OPENAI_API_KEY 또는 GEMINI_API_KEY 중 하나는 필요합니다.
```
→ `.env` 파일에 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY` 입력

```
Vault 경로를 찾을 수 없습니다: C:\...
```
→ `VAULT_PATH` 값이 실제 존재하는 경로인지 확인

---

### 전사 속도가 너무 느린 경우

`.env` 에서 더 작은 모델 사용:
```env
WHISPER_MODEL=tiny
```

| 모델 | 상대 속도 | 정확도 |
|------|-----------|--------|
| `tiny` | 가장 빠름 | 낮음 |
| `base` | 빠름 | 보통 |
| `small` | 보통 | 좋음 |
| `medium` | 느림 | 매우 좋음 |
| `large` | 가장 느림 | 최고 |

---

### 화자 분리가 안 되는 경우 (모두 Speaker A로 표시)

1. HuggingFace 토큰이 `.env`에 설정되어 있는지 확인
2. 아래 두 모델 페이지에서 라이선스 동의 여부 확인:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

---

### GPU(CUDA)를 사용하고 싶은 경우

1. NVIDIA GPU + CUDA 드라이버 설치 확인
2. CUDA 버전에 맞는 PyTorch 설치:
   ```bash
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
3. 실행 시 자동으로 GPU 감지 (`[Transcriber] WhisperX device=cuda` 로그 확인)

---

### Obsidian에서 노트가 열리지 않는 경우

- `VAULT_PATH`가 Obsidian에서 실제 열려 있는 Vault 경로와 일치하는지 확인
- Obsidian이 실행 중인 상태에서 링크 클릭

---

## 부록: 디렉토리 구조

```
meetscribe/
├── main.py              # FastAPI 서버 (업로드, 상태 폴링, 파이프라인 실행)
├── config.py            # 환경변수 로딩 및 검증
├── run.bat              # Windows 실행 스크립트
├── e2e_test.py          # 전사 E2E 테스트 (서버 없이 직접 실행)
├── requirements.txt     # Python 패키지 목록
├── .env                 # 환경 설정 (직접 생성)
├── pipeline/
│   ├── transcriber.py   # WhisperX 전사 + 화자 분리
│   ├── analyzer.py      # Gemini/GPT 분석
│   ├── note_builder.py  # Obsidian 노트 마크다운 생성
│   └── vault_writer.py  # Vault 파일 저장
├── static/
│   └── index.html       # 웹 UI
├── tests/               # 단위 테스트
└── uploads/             # 임시 업로드 파일 (처리 후 자동 삭제)
```
