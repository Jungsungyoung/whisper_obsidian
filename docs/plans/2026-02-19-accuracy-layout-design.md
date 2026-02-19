# 전사 정확도 개선 + 레이아웃 2단 분할 설계

## 목표
함정·선박 도메인 전문 용어 인식률 향상 + 회의별 맥락 주입 + UI 2단 레이아웃으로 편의성 개선.

## 데이터 흐름
1. 사용자가 업로드/녹음 전 "회의 맥락" 입력 (선택)
2. `.env`의 `DOMAIN_VOCAB` + 회의 맥락 → Whisper `initial_prompt` 합성
3. 동일 맥락 → Gemini 시스템 프롬프트 앞에 컨텍스트로 추가
4. 결과는 오른쪽 패널에 표시 (분석 중 → review → done)

## 레이아웃
```
┌─────────────────────┬──────────────────────────┐
│  LEFT (입력/상태)    │  RIGHT (검토/결과)        │
│  업로드 / 녹음       │  분석 전: 빈 상태         │
│  회의 맥락 입력      │  review → 화자+분석 편집  │
│  프로젝트 선택       │  done → 저장 완료 결과    │
│  제목 입력           │                           │
│  스텝 + 로그         │                           │
└─────────────────────┴──────────────────────────┘
```

## 변경 범위
- `config.py`: `DOMAIN_VOCAB` 필드 추가
- `main.py`: `/upload` 엔드포인트에 `context` Form 파라미터 추가; `_process()`에 context 전달; `/settings` GET/POST에 DOMAIN_VOCAB 추가
- `pipeline/transcriber.py`: `transcribe()` + `_transcribe_local()`에 `initial_prompt` 파라미터 추가
- `pipeline/analyzer.py`: `analyze_transcript()`에 `context` 파라미터 추가, Gemini/OpenAI 프롬프트 앞에 주입
- `static/index.html`: 2단 레이아웃, 회의 맥락 입력 필드, 설정 모달에 DOMAIN_VOCAB 텍스트영역

## 기본 도메인 용어
함정, 선박, 전투체계, 소나, 레이더, 추진체계, 함교, 수상함, 잠수함, 어뢰, 기관실, 항법, 통신체계

## 빈 맥락 처리
- `context` 비어있으면 `initial_prompt`는 DOMAIN_VOCAB만 사용
- DOMAIN_VOCAB도 비어있으면 `initial_prompt` 없이 기존 동작 유지
