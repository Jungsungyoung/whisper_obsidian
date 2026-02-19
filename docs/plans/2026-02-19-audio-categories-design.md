# MeetScribe 오디오 카테고리 확장 설계

> 최종 업데이트: 2026-02-19

---

## 목표

회의(meeting) 전용이었던 MeetScribe를 **6개 카테고리**로 확장한다.
사용자는 녹음 파일을 업로드할 때 카테고리를 선택하고, 카테고리에 따라 AI 분석 프롬프트·노트 템플릿·저장 폴더가 자동으로 결정된다.
기존 `.env`를 수정하지 않아도 동작하도록 **하위 호환**을 유지한다.

---

## 아키텍처

```
업로드 (카테고리 포함)
  → Transcriber (변경 없음)
  → Analyzer.analyze_transcript(text, category, context)  ← 카테고리별 프롬프트
  → NoteBuilder.build_note(category, ...)                 ← 카테고리별 템플릿
  → VaultWriter.save(category, ...)                       ← 카테고리별 폴더
```

카테고리는 문자열 리터럴로 전달된다:
`"meeting" | "voice_memo" | "daily" | "lecture" | "discussion" | "reference"`

---

## 섹션 1: 카테고리 시스템 & UI

### 6개 카테고리

| 카테고리 ID | 표시명 | 기본 저장 폴더 | 노트 수 |
|-------------|--------|----------------|---------|
| `meeting` | 회의 | `10_Calendar/13_Meetings` | 2 (회의+전사) |
| `voice_memo` | 보이스 메모 | `00_Inbox` | 1 |
| `daily` | 데일리 업무일지 | `10_Calendar/11_Daily` | 1 |
| `lecture` | 강의/세미나 | `30_Areas` | 1 |
| `discussion` | 프로젝트 논의 | `20_Projects/{project}` | 2 (논의+전사) |
| `reference` | 레퍼런스 리뷰 | `40_Resources` | 1 |

### UI 변경사항

- 업로드 카드에 **카테고리 탭** 추가 (6개 버튼, 클릭으로 선택)
- 카테고리별 **동적 폼 필드**:
  - `meeting`: 제목, 프로젝트(드롭다운), 참석자, 회의 맥락
  - `voice_memo`: 제목, 메모 맥락 (선택)
  - `daily`: 날짜(기본: 오늘), 추가 메모 (선택)
  - `lecture`: 제목, 강사/출처, 분야(Areas 하위폴더), 학습 맥락
  - `discussion`: 제목, 프로젝트(드롭다운, 필수), 참여자, 논의 맥락
  - `reference`: 제목, 출처, 분야(Areas 하위폴더), 검토 목적
- 리뷰 화면: 카테고리별 분석 결과 섹션 표시

---

## 섹션 2: AI 분석 프롬프트 & 출력 스키마

### 카테고리별 출력 스키마

**meeting / discussion** (기존 유지):
```
PURPOSE, DISCUSSION, DECISIONS, ACTION_ITEMS, FOLLOW_UP
```

**voice_memo**:
```
SUMMARY: [한 줄 요약]
KEY_POINTS:
- [핵심 포인트]
ACTION_ITEMS:
- [할 일]
```

**daily**:
```
TASKS_DONE:
- [완료 업무]
TASKS_TOMORROW:
- [내일 할 일]
ISSUES:
- [문제/이슈]
REFLECTION: [하루 소감 한 줄]
```

**lecture**:
```
SUMMARY: [강의 요약]
KEY_CONCEPTS:
- [핵심 개념]
IMPORTANT_POINTS:
- [중요 포인트]
REFERENCES:
- [참고 자료]
QUESTIONS:
- [생긴 질문]
```

**reference**:
```
SUMMARY: [문서/자료 요약]
KEY_FINDINGS:
- [핵심 발견]
METHODOLOGY: [연구/분석 방법]
APPLICABILITY: [업무 적용 가능성]
CITATIONS:
- [인용 가능한 문장]
```

### 구현

- `pipeline/prompts.py` 신규 생성: 카테고리별 SYSTEM_PROMPT 상수 딕셔너리
- `analyzer.analyze_transcript(text, category, context)`: `category` 파라미터 추가
- `analyzer.parse_llm_response(response, category)`: 카테고리별 파싱 로직

---

## 섹션 3: 노트 출력 템플릿

### Frontmatter 구조

**voice_memo**:
```yaml
---
type: voice_memo
date: YYYY-MM-DD
title: 제목
audio: 파일명.m4a
duration: MM:SS
tags: [voice_memo]
---
```

**daily**:
```yaml
---
type: daily
date: YYYY-MM-DD
title: Daily YYYY-MM-DD
audio: 파일명.m4a
duration: MM:SS
tags: [daily]
---
```

**lecture**:
```yaml
---
type: lecture
date: YYYY-MM-DD
title: 제목
source: 강사/출처
area: 분야
audio: 파일명.m4a
duration: MM:SS
tags: [lecture]
---
```

**discussion** (프로젝트 논의, meeting과 유사):
```yaml
---
type: discussion
date: YYYY-MM-DD
title: 제목
project: 프로젝트명
participants: [참여자]
audio: 파일명.m4a
duration: MM:SS
status: 진행
tags: [discussion]
---
```

**reference**:
```yaml
---
type: reference
date: YYYY-MM-DD
title: 제목
source: 출처
area: 분야
audio: 파일명.m4a
duration: MM:SS
tags: [reference]
---
```

### 노트 섹션 (Vault 기존 Weekly Review / Dataview 호환)

- `type: meeting` → Vault Weekly Review 쿼리 자동 수집 (기존 동작 유지)
- `type: daily` → Daily 폴더 자동 정렬
- `type: discussion` → 프로젝트별 Dataview 카운트에 포함

---

## 섹션 4: 파일 변경 범위 + 설정

### 변경 파일 목록

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `pipeline/prompts.py` | **신규** | 카테고리별 SYSTEM_PROMPT 상수 |
| `pipeline/analyzer.py` | 수정 | `category` 파라미터 추가, 라우팅 함수 |
| `pipeline/note_builder.py` | 수정 | `build_note(category, ...)` + 카테고리별 빌더 5개 |
| `pipeline/vault_writer.py` | 수정 | 카테고리별 폴더 결정 로직 |
| `main.py` | 수정 | `/upload`·`/confirm` 에 `category` 필드 |
| `config.py` | 수정 | 폴더 경로 5개 추가 (기본값 제공) |
| `.env.example` | 수정 | 신규 환경변수 예시 |
| `static/index.html` | 수정 | 카테고리 탭 UI, 동적 폼, 리뷰 화면 확장 |

### 신규 환경변수

```env
# 카테고리별 저장 폴더 (기본값 제공 — 기존 .env 수정 불필요)
INBOX_FOLDER=00_Inbox
DAILY_FOLDER=10_Calendar/11_Daily
AREAS_FOLDER=30_Areas
RESOURCES_FOLDER=40_Resources
PROJECTS_FOLDER=20_Projects
# MEETINGS_FOLDER 기존 유지
```

### 설정 모달 변경

설정 화면에 "폴더 설정" 섹션 추가:
- 카테고리별 저장 폴더 경로를 UI에서 직접 수정 가능

---

## 하위 호환 정책

- 기존 `category` 없이 들어오는 요청은 `"meeting"`으로 처리
- `MEETINGS_FOLDER` 기존 값 유지
- 신규 env 변수 없으면 기본값 사용
