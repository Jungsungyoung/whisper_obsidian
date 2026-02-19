# 브라우저 마이크 녹음 설계

## 목표
파일 업로드 없이 브라우저에서 직접 마이크 녹음 → 전사 분석까지 이어지도록 한다.

## 범위
- 백엔드 변경 없음 (`.webm`은 이미 ALLOWED_EXTENSIONS 포함, `/upload` 재사용)
- `static/index.html`만 수정

## UX 흐름
1. 드롭존 하단에 "🔴 마이크로 녹음 시작" 버튼 표시
2. 클릭 → 브라우저 마이크 권한 요청
3. 승인 → 녹음 시작, 경과 타이머 + "⏹ 녹음 중단" 버튼 표시
4. 중단 → webm Blob 생성 → File 객체 변환 → 자동 업로드 + 분석 시작

## 기술
- MediaRecorder API (브라우저 내장)
- mimeType: `audio/webm`
- 파일명: `recording_YYYYMMDD_HHMMSS.webm`
- 중단 후 기존 upload 로직 재사용 (별도 코드 경로 없음)

## 에러 처리
- 마이크 권한 거부 → 에러 메시지 표시
- MediaRecorder 미지원 브라우저 → 버튼 비활성화
