from pipeline.analyzer import parse_llm_response

SAMPLE_RESPONSE = """
PURPOSE: 스프린트 리뷰 및 3월 배포 계획 논의

DISCUSSION:
- ECS V1.2 개발 진행률 75% 완료
- 해상 시험 일정 조정 논의 (3/15 → 3/20)
- Autopilot 알고리즘 파라미터 튜닝 필요

DECISIONS:
- 해상 시험 3월 20일 확정
- 추가 문서화 마감: 3월 5일

ACTION_ITEMS:
- ECS V1.2 코드 유닛 테스트 완료 (Speaker B, ~02/25)
- 추가 문서화 작성 시작 (Speaker A, ~02/28)

FOLLOW_UP:
- Autopilot 시뮬레이션 파라미터 최적화 방법 조사
"""


def test_parses_purpose():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert result["purpose"] == "스프린트 리뷰 및 3월 배포 계획 논의"


def test_parses_discussion_items():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["discussion"]) == 3
    assert "ECS V1.2 개발 진행률 75% 완료" in result["discussion"]


def test_parses_decisions():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["decisions"]) == 2


def test_parses_action_items():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["action_items"]) == 2
    assert "ECS V1.2 코드 유닛 테스트 완료 (Speaker B, ~02/25)" in result["action_items"]


def test_parses_follow_up():
    result = parse_llm_response(SAMPLE_RESPONSE)
    assert len(result["follow_up"]) == 1


def test_handles_empty_sections():
    minimal = """
PURPOSE: 간단한 미팅

DISCUSSION:
- 항목 하나

DECISIONS:

ACTION_ITEMS:

FOLLOW_UP:
"""
    result = parse_llm_response(minimal)
    assert result["purpose"] == "간단한 미팅"
    assert result["decisions"] == []
    assert result["action_items"] == []


# ── 카테고리별 파서 테스트 ─────────────────────────────────────────

VOICE_MEMO_RESPONSE = """
SUMMARY: 프로젝트 아이디어 메모

KEY_POINTS:
- 새 API 설계 필요
- 팀원 피드백 반영

ACTION_ITEMS:
- API 설계서 초안 작성
"""

DAILY_RESPONSE = """
TASKS_DONE:
- 코드 리뷰 완료
- 단위 테스트 작성

TASKS_TOMORROW:
- 문서 작성

ISSUES:
- 빌드 오류 발생

REFLECTION: 생산적인 하루였다
"""

LECTURE_RESPONSE = """
SUMMARY: 제어 시스템 기초 강의

KEY_CONCEPTS:
- PID 제어기
- 상태 공간 표현

IMPORTANT_POINTS:
- 안정성 조건 확인 필요

REFERENCES:
- 교재 3장

QUESTIONS:
- 비선형 시스템 적용 방법?
"""

REFERENCE_RESPONSE = """
SUMMARY: USV 자율항법 논문 검토

KEY_FINDINGS:
- GPS 오류 보정 알고리즘 제안

METHODOLOGY: 시뮬레이션 기반 검증

APPLICABILITY: 현 프로젝트 항법 모듈에 직접 적용 가능

CITATIONS:
- "The proposed algorithm reduces error by 40%"
"""


def test_parse_voice_memo_summary():
    result = parse_llm_response(VOICE_MEMO_RESPONSE, "voice_memo")
    assert result["summary"] == "프로젝트 아이디어 메모"


def test_parse_voice_memo_lists():
    result = parse_llm_response(VOICE_MEMO_RESPONSE, "voice_memo")
    assert len(result["key_points"]) == 2
    assert "새 API 설계 필요" in result["key_points"]
    assert len(result["action_items"]) == 1


def test_parse_daily_tasks():
    result = parse_llm_response(DAILY_RESPONSE, "daily")
    assert result["tasks_done"] == ["코드 리뷰 완료", "단위 테스트 작성"]
    assert result["tasks_tomorrow"] == ["문서 작성"]
    assert result["issues"] == ["빌드 오류 발생"]


def test_parse_daily_reflection():
    result = parse_llm_response(DAILY_RESPONSE, "daily")
    assert result["reflection"] == "생산적인 하루였다"


def test_parse_lecture():
    result = parse_llm_response(LECTURE_RESPONSE, "lecture")
    assert result["summary"] == "제어 시스템 기초 강의"
    assert "PID 제어기" in result["key_concepts"]
    assert len(result["questions"]) == 1


def test_parse_reference():
    result = parse_llm_response(REFERENCE_RESPONSE, "reference")
    assert result["summary"] == "USV 자율항법 논문 검토"
    assert result["methodology"] == "시뮬레이션 기반 검증"
    assert len(result["citations"]) == 1


def test_unknown_category_falls_back_to_meeting():
    result = parse_llm_response(SAMPLE_RESPONSE, "unknown_cat")
    assert "purpose" in result
