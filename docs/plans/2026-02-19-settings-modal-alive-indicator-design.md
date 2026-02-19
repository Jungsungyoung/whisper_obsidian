# 설정 모달 + 실시간 표시기 설계

## 기능 1: 살아있음 표시기
- 로그 마지막 줄 끝에 깜빡이는 커서 `▌` CSS 애니메이션
- 새 로그 추가 시 커서가 새 줄로 이동

## 기능 2: 설정 모달
- 헤더 우상단 ⚙ 버튼 클릭 시 모달 팝업
- 설정 항목: WHISPER_MODEL, GEMINI_API_KEY, OPENAI_API_KEY, HF_TOKEN, VAULT_PATH, MEETINGS_FOLDER
- API 키는 마스킹(●●●●) 표시, 변경 시 입력

## 백엔드 API
- GET /settings — 현재 .env 값 반환 (API 키 마스킹)
- POST /settings — .env 파일 저장 + config 리로드

## 저장소: 서버 .env 파일
