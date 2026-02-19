# 결과 미리보기 + 편집 설계

## 목표
AI 분석 완료 후 Vault 저장 전에 사용자가 결과를 확인·편집할 수 있도록 파이프라인을 일시 정지한다.

## 파이프라인 변경
- 분석 완료 → status="review", job_status에 analysis 데이터 저장
- 백그라운드 스레드가 0.5초 간격으로 폴링 대기
- 사용자가 편집 후 POST /confirm/{job_id} → status="confirmed" → 스레드 재개 → Vault 저장

## 새 API
- POST /confirm/{job_id}: ConfirmPayload(purpose, discussion, decisions, action_items, follow_up) 수신 → 파이프라인 재개

## 프론트엔드
- poll()에서 status="review" 감지 → #review-panel 표시
- 각 섹션을 <textarea>로 편집 (줄바꿈으로 항목 구분)
- "Vault에 저장" 클릭 → POST /confirm/{job_id} → 폴링 재개
- "취소" 클릭 → POST /cancel/{job_id}
