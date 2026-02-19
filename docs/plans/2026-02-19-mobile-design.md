# Mobile Access Design

**Date:** 2026-02-19
**Status:** Approved

## Goal

PC에서 FastAPI 서버를 실행한 채, 스마트폰 브라우저에서 외부 접속하여 오디오 녹음·업로드·전사·노트 저장까지 동일하게 사용할 수 있도록 한다.

## Approach

A안 (최소 변경) + PWA manifest 추가.

- Cloudflare Tunnel로 외부 접근
- PIN 인증으로 보안
- 모바일 UI 보완
- PWA manifest로 홈 화면 앱처럼 설치 가능

## Architecture

### 1. Network — Cloudflare Tunnel

- `cloudflared tunnel --url http://localhost:8765` 실행 시 `https://xxxxx.trycloudflare.com` URL 자동 생성
- `run.bat`에 cloudflared 백그라운드 실행 추가
- HTTPS는 Cloudflare가 자동 제공
- 재시작마다 URL이 바뀌는 것이 불편하면 Cloudflare 계정 연결로 고정 URL 가능 (별도 설정)

### 2. Authentication — PIN Middleware

- `.env`에 `ACCESS_PIN=1234` 설정 (미설정 시 인증 없이 통과 — 로컬 사용 그대로 유지)
- FastAPI `SessionMiddleware` + `/login` 라우트 추가
- 올바른 PIN 입력 → `session` 쿠키 발급 (24시간 유효)
- 모든 API/페이지 요청에서 쿠키 검증
- `/login`, `/static` 경로는 인증 예외 처리

### 3. Mobile UI

- `@media (max-width: 640px)`: 파일 선택 버튼, 마이크 버튼 터치 영역 확대
- `<input accept="audio/*,video/*">`: iOS 파일 앱/카메라 롤에서 선택 가능하도록
- 텍스트 입력창 `font-size: 16px` 고정 (iOS 자동 줌인 방지)
- 전체 레이아웃 구조 변경 없음 (이미 단일 컬럼 반응형 대응)

### 4. PWA Manifest

- `static/manifest.json`: 앱 이름, 아이콘, `display: standalone`, 테마 색상
- `static/icon-192.png`, `static/icon-512.png`: 앱 아이콘
- `index.html <head>`에 `<link rel="manifest" href="/static/manifest.json">` 추가
- Service Worker 없음 (캐싱/오프라인 불필요)

## Files Changed

| 파일 | 변경 내용 |
|------|-----------|
| `run.bat` | cloudflared 백그라운드 실행 추가 |
| `main.py` | `SessionMiddleware`, `/login` GET/POST 라우트, PIN 검증 미들웨어 |
| `config.py` | `ACCESS_PIN` 환경변수 추가 |
| `static/index.html` | PWA manifest 링크, 모바일 CSS 보완, accept 속성 수정 |
| `static/manifest.json` | 신규 생성 |
| `static/icon-192.png` | 신규 생성 |
| `static/icon-512.png` | 신규 생성 |
| `.env.example` | `ACCESS_PIN` 항목 추가 |

## Out of Scope

- Service Worker / 오프라인 캐싱
- 별도 모바일 전용 UI
- 푸시 알림
- Cloudflare 계정 연결 고정 URL (선택 사항, 추후)
