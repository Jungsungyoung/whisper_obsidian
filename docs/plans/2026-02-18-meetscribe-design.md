# MeetScribe 설계 문서

**작성일:** 2026-02-18
**프로젝트:** MeetScribe — 회의 녹음 → 자동 전사 → Obsidian 노트 파이프라인

---

## 개요

회의 녹음 파일(mp3/wav/m4a)을 업로드하면 Whisper로 전사하고, LLM이 분석해 기존 Obsidian Vault의 회의 노트 형식에 맞는 마크다운 파일을 자동 생성한다.

---

## 아키텍처

### 선택된 접근: FastAPI 파이프라인

```
meetscribe/
├── main.py                  # FastAPI 앱 진입점
├── config.py                # 설정 (vault 경로, LLM 키 등)
├── pipeline/
│   ├── transcriber.py       # Whisper 로컬 → API 폴백
│   ├── analyzer.py          # LLM 분석 (요약 + 액션아이템)
│   ├── note_builder.py      # Obsidian 마크다운 생성
│   └── vault_writer.py      # Vault 폴더에 파일 저장
├── static/
│   └── index.html           # 드래그앤드롭 업로드 UI
└── requirements.txt
```

### 전체 데이터 흐름

```
[파일 업로드 (mp3/wav/m4a)]
        ↓
[Transcriber]
  - pyannote.audio로 화자 구간 분리 (Speaker A/B)
  - Whisper 로컬 실행 (tiny/base/small/medium 선택 가능)
  - 실패 시 OpenAI Whisper API 폴백
  - 타임스탬프 + 화자 레이블 병합
        ↓
[Analyzer] — GPT-4o-mini 프롬프트
  - 목적 추론
  - 주요 논의 bullet 추출
  - 결정 사항 목록화
  - Action Items (담당자 + 마감일 파싱 시도)
  - 후속 질문 추출
        ↓
[NoteBuilder] — 2개 마크다운 파일 생성
  - [회의] 노트: 기존 Meeting Note 템플릿 형식
  - [전사] 노트: 전체 타임스탬프 전사본
        ↓
[VaultWriter]
  - 저장 위치: 10_Calendar/13_Meetings/
  - 파일명 컨벤션: [회의] / [전사] 유지
  - 완료 후 obsidian:// URI 반환
```

---

## 출력 노트 형식

### 파일 1: 메인 회의 노트
`10_Calendar/13_Meetings/[회의] YYYY-MM-DD 제목.md`

기존 Meeting Note 템플릿과 완전 호환:
```markdown
---
date: YYYY-MM-DD
type: meeting
project: ""
participants:
  - Speaker A
  - Speaker B
tags:
  - meeting
  - ai-transcribed
audio: "파일명.mp3"
duration: "HH:MM"
---

# [회의] YYYY-MM-DD 제목

> [!note] AI 자동 생성
> 전체 전사: [[전사] YYYY-MM-DD 제목]]

## 목적
(LLM 추론)

## 주요 논의
- (bullet 형식)

## 결정 사항
- (목록)

## Action Items
- [ ] 내용 (Speaker X, ~MM/DD)

## 후속 질문
- (목록)
```

### 파일 2: 전사 노트
`10_Calendar/13_Meetings/[전사] YYYY-MM-DD 제목.md`

```markdown
---
date: YYYY-MM-DD
type: meeting-transcript
tags:
  - transcript
---
# [전사] YYYY-MM-DD 제목

> 요약: [[회의] YYYY-MM-DD 제목]]

**[HH:MM:SS] Speaker A:** ...
**[HH:MM:SS] Speaker B:** ...
```

---

## 기술 스택

| 레이어 | 기술 | 이유 |
|--------|------|------|
| 백엔드 | FastAPI | async 처리, 파일 업로드 지원 |
| STT | `openai-whisper` (로컬) → `openai` API 폴백 | 프라이버시 + 안정성 |
| 화자 분리 | `pyannote.audio` | Whisper와 연동되는 diarization |
| LLM 분석 | OpenAI GPT-4o-mini | 비용/성능 균형 |
| 프론트엔드 | 순수 HTML/CSS/JS | 단순, 의존성 없음 |
| Vault 저장 | 파일 시스템 직접 쓰기 | Obsidian API 불필요 |

---

## 설정 (`config.py`)

```python
VAULT_PATH = r"C:\Users\Admin\OneDrive\문서\Obsidian Vault"
MEETINGS_FOLDER = "10_Calendar/13_Meetings"
WHISPER_MODEL = "base"        # tiny / base / small / medium
OPENAI_API_KEY = ""           # 폴백 + LLM 분석용
LLM_MODEL = "gpt-4o-mini"
```

---

## UI 흐름

```
┌─────────────────────────────────────┐
│  MeetScribe                         │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  파일을 여기에 드래그하세요    │  │
│  │  mp3 / wav / m4a / mp4        │  │
│  └───────────────────────────────┘  │
│                                     │
│  [회의 제목] ________________       │
│  [프로젝트]  ________________       │
│                                     │
│         [ 분석 시작 ]               │
│                                     │
│  진행 상황:                         │
│  ✅ 업로드 완료                      │
│  ⏳ 전사 중... (2:14 / 5:30)        │
│  ⬜ AI 분석                          │
│  ⬜ Vault 저장                       │
│                                     │
│  [Obsidian에서 열기] ← 완료 후 표시 │
└─────────────────────────────────────┘
```

---

## 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| Whisper 로컬 실패 | OpenAI API 폴백, UI에 표시 |
| 파일 형식 미지원 | 업로드 전 클라이언트 검증 |
| Vault 경로 없음 | 시작 시 체크 + 친절한 에러 메시지 |
| LLM API 실패 | 전사 텍스트만 노트로 저장 |
| 오디오 길이 초과 (>2h) | 경고 후 계속 진행 |

---

## MVP 범위

1. **Phase 1 (MVP):** 파일 업로드 → 전사 → 분석 → Vault 저장
2. **Phase 2:** 실시간 마이크 녹음 지원
3. **Phase 3:** Zoom/Teams 자동 연동

---

## Vault 정보

- **Vault 경로:** `C:\Users\Admin\OneDrive\문서\Obsidian Vault`
- **회의 노트 위치:** `10_Calendar/13_Meetings/`
- **기존 파일명 패턴:** `[회의] YYYY-MM-DD 제목.md`
- **기존 플러그인:** Templater, Dataview, Tasks, Calendar, Kanban, Excalidraw, obsidian-git
