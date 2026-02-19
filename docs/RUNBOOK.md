# MeetScribe 운영 런북 (Runbook)

> 소스 기준: `meetscribe/config.py`, `meetscribe/main.py`, `meetscribe/MANUAL.md`
> 최종 업데이트: 2026-02-19

---

## 목차

1. [배포 절차](#1-배포-절차)
2. [서버 시작 및 종료](#2-서버-시작-및-종료)
3. [상태 확인 및 모니터링](#3-상태-확인-및-모니터링)
4. [자주 발생하는 문제 및 해결](#4-자주-발생하는-문제-및-해결)
5. [롤백 절차](#5-롤백-절차)
6. [설정 변경 절차](#6-설정-변경-절차)

---

## 1. 배포 절차

MeetScribe는 로컬 웹 애플리케이션입니다. 별도 클라우드 배포 없이 로컬 PC에서 실행됩니다.

### 최초 설치

```bash
# 1. 패키지 설치
cd meetscribe
pip install -r requirements.txt

# 2. GPU 사용 시 (선택)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 3. 환경변수 파일 생성
cp .env.example .env
# .env 파일 편집 (필수값 입력)
```

### 업데이트 배포

```bash
# 1. 새 코드 반영 후 의존성 업데이트
cd meetscribe
pip install -r requirements.txt

# 2. 서버 재시작 (기존 서버 종료 후 재시작)
# run.bat 재실행 또는 uvicorn 재시작
```

> `.env` 파일은 업데이트 시 덮어쓰이지 않습니다. 새 환경변수가 추가된 경우 `.env.example`과 비교해 수동으로 추가합니다.

---

## 2. 서버 시작 및 종료

### 시작

**Windows (권장)**
```bat
run.bat
```

**직접 실행**
```bash
cd meetscribe
uvicorn main:app --host 0.0.0.0 --port 8765
```

### 정상 시작 확인

서버가 정상 시작되면 콘솔에 다음이 출력됩니다:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8765
```

브라우저에서 **http://localhost:8765** 접속 → 업로드 화면이 보이면 정상.

### 종료

- `run.bat` 실행 중: 콘솔 창 닫기 또는 `Ctrl+C` 후 `Y`
- 직접 실행 중: `Ctrl+C`

---

## 3. 상태 확인 및 모니터링

### 서버 헬스체크

```bash
curl http://localhost:8765/
```
→ HTTP 200 응답 확인

### 처리 진행 상태 확인

파일 처리 중 상태는 폴링 API로 확인 가능합니다:
```bash
curl http://localhost:8765/status/{job_id}
```

### 로그 확인 항목

서버 콘솔에서 아래 로그를 확인합니다:

| 로그 패턴 | 의미 |
|-----------|------|
| `[Transcriber] WhisperX device=cuda` | GPU 모드로 실행 중 |
| `[Transcriber] WhisperX device=cpu` | CPU 모드로 실행 중 |
| `[Transcriber] fallback → OpenAI API` | 로컬 전사 실패, API로 폴백 |
| `[Analyzer] using Gemini` | Gemini LLM 사용 중 |
| `[Analyzer] fallback → OpenAI` | Gemini 실패, OpenAI로 폴백 |
| `[VaultWriter] saved:` | Vault 저장 완료 |

### 업로드 임시 파일 정리

처리 완료된 파일은 자동 삭제됩니다. 비정상 종료 시 잔류 파일이 남을 수 있습니다:

```bash
# uploads/ 폴더 확인
ls meetscribe/uploads/

# 수동 정리 (서버 종료 후)
rm meetscribe/uploads/*
```

---

## 4. 자주 발생하는 문제 및 해결

### 서버가 시작되지 않음

#### LLM API 키 누락
```
RuntimeError: LLM API 키 누락: OPENAI_API_KEY 또는 GEMINI_API_KEY 중 하나는 필요합니다.
```
**해결:** `.env` 파일에 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY` 입력

#### Vault 경로 오류
```
RuntimeError: Vault 경로를 찾을 수 없습니다: C:\...
```
**해결:** `VAULT_PATH` 값이 실제 존재하는 Obsidian Vault 경로인지 확인

#### GPU 없음 오류
```
RuntimeError: GPU(CUDA)를 사용할 수 없습니다.
```
**해결:** `.env`에 `ALLOW_CPU=true` 추가

---

### 전사 실패 / 오류

#### WhisperX 로컬 실패
자동으로 OpenAI Whisper API로 폴백됩니다. `OPENAI_API_KEY`가 설정되어 있어야 합니다.

#### 메모리 부족 (OOM)
더 작은 모델로 변경:
```env
WHISPER_MODEL=tiny
```

#### 전사 속도가 너무 느림

| 모델 | 상대 속도 | 정확도 |
|------|-----------|--------|
| `tiny` | 가장 빠름 | 낮음 |
| `base` | 빠름 | 보통 |
| `small` | 보통 | 좋음 |
| `medium` | 느림 | 매우 좋음 |
| `large` | 가장 느림 | 최고 |

`.env`에서 `WHISPER_MODEL=tiny` 또는 `WHISPER_MODEL=base`로 변경

---

### 화자 분리가 안 됨 (모두 Speaker A로 표시)

**원인 1:** HuggingFace 토큰 미설정
→ `.env`에 `HF_TOKEN=hf_...` 입력

**원인 2:** pyannote 라이선스 미동의
→ 아래 두 페이지에서 Accept 클릭:
- [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

> 화자 분리 실패 시 자동으로 모든 발언을 `Speaker A`로 처리하고 계속 진행됩니다.

---

### AI 분석 실패

**Gemini API 오류** → 자동으로 OpenAI GPT-4o-mini로 폴백
**OpenAI API 오류** → 두 키 모두 확인 필요

API 키 유효성 직접 확인:
```bash
# Gemini
curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"contents":[{"parts":[{"text":"hello"}]}]}'

# OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

### Obsidian에서 노트가 열리지 않음

- Obsidian이 실행 중인지 확인
- `VAULT_PATH`가 Obsidian에서 현재 열려 있는 Vault 경로와 일치하는지 확인
- Obsidian URI 스킴 활성화 여부 확인 (설정 → URI 스킴)

---

### 환경 진단

문제 원인 파악이 어려운 경우:
```bash
cd meetscribe
python diagnose.py
```

---

## 5. 롤백 절차

### 코드 롤백

MeetScribe는 로컬 실행 애플리케이션으로, 이전 버전 파일을 복원하면 됩니다.

```bash
# git을 사용하는 경우
git checkout <이전-커밋-해시>

# 수동 복원의 경우
# 이전 버전의 파일로 교체 후 서버 재시작
```

### 의존성 롤백

```bash
# 특정 버전으로 다운그레이드
pip install -r requirements.txt --force-reinstall
```

### 환경변수 롤백

`.env` 파일을 이전 버전으로 복원합니다. `.env.example`을 백업으로 참고합니다.

> **노트 파일은 영향 없음:** Vault에 이미 생성된 노트는 롤백의 영향을 받지 않습니다.

---

## 6. 설정 변경 절차

### Obsidian Vault 경로 변경

```env
# .env 수정
VAULT_PATH=C:\새로운\Vault\경로
MEETINGS_FOLDER=새로운/폴더/경로
```
→ 서버 재시작

### Whisper 모델 변경

```env
# .env 수정
WHISPER_MODEL=small   # tiny / base / small / medium / large
```
→ 서버 재시작 (모델 최초 실행 시 자동 다운로드)

### LLM 모델 변경

```env
# Gemini 사용 시
LLM_MODEL=gemini-2.0-flash

# OpenAI 사용 시
LLM_MODEL=gpt-4o-mini
```
→ 서버 재시작

### 도메인 어휘 추가 (전사 정확도 향상)

```env
# .env 수정 — 쉼표로 구분
DOMAIN_VOCAB=함정, 선박, 전투체계, 소나, 레이더, 추진체계, 새어휘1, 새어휘2
```
→ 서버 재시작
