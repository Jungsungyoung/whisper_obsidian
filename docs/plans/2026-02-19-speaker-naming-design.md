# 화자 이름 지정 설계

## 목표
미리보기 패널에서 Speaker A/B를 실명으로 매핑해 Vault 노트에 실명으로 저장한다.

## 데이터 흐름
1. review 상태 전환 시 job_status에 speakers 리스트 추가
2. 프론트엔드: 화자별 입력 필드 자동 생성
3. "Vault에 저장" 클릭 시 speaker_map 포함해 POST /confirm
4. 백엔드: segments.speaker 치환 후 NoteData 구성

## 변경 범위
- main.py: review 상태에 speakers 추가, ConfirmPayload에 speaker_map, segments에 mapping 적용
- index.html: 미리보기 패널 상단에 화자 이름 입력 섹션

## 빈 입력 처리
이름 비워두면 원래 이름(Speaker A) 유지
