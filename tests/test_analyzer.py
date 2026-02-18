import pytest
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
