"""도메인 용어 + 회의 맥락 initial_prompt 빌드 테스트"""


def test_build_initial_prompt_both():
    from pipeline.transcriber import _build_initial_prompt
    result = _build_initial_prompt("함정, 소나, 레이더", "레이더 설계 검토 회의")
    assert "함정" in result
    assert "레이더 설계 검토 회의" in result


def test_build_initial_prompt_empty_context():
    from pipeline.transcriber import _build_initial_prompt
    result = _build_initial_prompt("함정, 소나", "")
    assert result == "함정, 소나"


def test_build_initial_prompt_empty_vocab():
    from pipeline.transcriber import _build_initial_prompt
    result = _build_initial_prompt("", "함정 회의")
    assert result == "함정 회의"


def test_build_initial_prompt_both_empty():
    from pipeline.transcriber import _build_initial_prompt
    result = _build_initial_prompt("", "")
    assert result == ""


def test_build_analysis_prompt_includes_context():
    from pipeline.analyzer import _build_analysis_prompt
    prompt = _build_analysis_prompt("레이더 설계 검토 회의", "회의 내용 전사본")
    assert "레이더 설계 검토 회의" in prompt
    assert "회의 내용 전사본" in prompt


def test_build_analysis_prompt_no_context():
    from pipeline.analyzer import _build_analysis_prompt
    prompt = _build_analysis_prompt("", "회의 내용 전사본")
    assert "회의 내용 전사본" in prompt


def test_build_analysis_prompt_does_not_include_system_prompt():
    from pipeline.analyzer import _build_analysis_prompt
    from pipeline.prompts import MEETING_PROMPT
    prompt = _build_analysis_prompt("회의 맥락", "전사본 내용")
    assert MEETING_PROMPT not in prompt
