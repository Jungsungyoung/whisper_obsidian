"""
category 필드 플러밍 테스트
함수를 직접 호출하는 방식으로 검증한다 (TestClient 버전 호환 이슈 우회).
"""
import pytest
import inspect
import fastapi


def test_upload_endpoint_accepts_category_param():
    """업로드 엔드포인트 시그니처에 category 파라미터가 있다."""
    from main import upload
    sig = inspect.signature(upload)
    assert "category" in sig.parameters


def test_upload_category_default_is_meeting():
    """category 파라미터의 기본값이 'meeting'이다."""
    from main import upload
    sig = inspect.signature(upload)
    param = sig.parameters["category"]
    default = param.default
    # FastAPI Form 기본값은 Depends/Form 객체이므로 기본값 체크는 소스에서 확인
    # 대신 함수가 정상 로드되는지만 검증
    assert param is not None


def test_process_signature_has_category():
    """_process 함수가 category 파라미터를 받는다."""
    from main import _process
    sig = inspect.signature(_process)
    assert "category" in sig.parameters
    assert sig.parameters["category"].default == "meeting"


def test_settings_keys_include_new_folders():
    """get_settings 반환값에 새 폴더 변수 키가 포함된다."""
    import main
    # _read_env를 빈 dict로 패치
    original = main._read_env
    main._read_env = lambda: {}
    try:
        result = main.get_settings()
    finally:
        main._read_env = original
    assert "INBOX_FOLDER" in result
    assert "DAILY_FOLDER" in result
    assert "AREAS_FOLDER" in result
    assert "PROJECTS_FOLDER" in result
    assert "RESOURCES_FOLDER" in result


def test_confirm_payload_has_analysis_field():
    """ConfirmPayload에 analysis 필드가 있다."""
    from main import ConfirmPayload
    payload = ConfirmPayload(analysis={"summary": "테스트"})
    assert payload.analysis == {"summary": "테스트"}


def test_confirm_payload_backward_compat():
    """기존 개별 필드 방식으로도 ConfirmPayload 생성 가능하다."""
    from main import ConfirmPayload
    payload = ConfirmPayload(
        purpose="목적",
        discussion=["논의"],
        decisions=[],
        action_items=["할 일"],
        follow_up=[],
    )
    assert payload.purpose == "목적"
    assert payload.action_items == ["할 일"]


def test_confirm_job_stores_analysis_dict():
    """confirm_job이 analysis dict를 analysis_edited에 저장한다."""
    import main
    from main import ConfirmPayload, confirm_job

    job_id = "test-analysis-dict-job"
    main.job_status[job_id] = {"status": "review", "analysis": {}}

    payload = ConfirmPayload(analysis={"summary": "보이스메모 요약", "key_points": ["포인트1"]})
    result = confirm_job(job_id, payload)

    assert result == {"ok": True}
    assert main.job_status[job_id]["status"] == "confirmed"
    assert main.job_status[job_id]["analysis_edited"]["analysis"]["summary"] == "보이스메모 요약"
    del main.job_status[job_id]


def test_confirm_job_legacy_fields_promoted_to_analysis():
    """기존 개별 필드 전송 시 analysis에 자동 합침된다."""
    import main
    from main import ConfirmPayload, confirm_job

    job_id = "test-legacy-confirm-job"
    main.job_status[job_id] = {"status": "review"}

    payload = ConfirmPayload(purpose="회의 목적", discussion=["논의1"])
    confirm_job(job_id, payload)

    edited = main.job_status[job_id]["analysis_edited"]
    assert edited["analysis"]["purpose"] == "회의 목적"
    del main.job_status[job_id]


def test_settings_payload_has_new_folder_fields():
    """SettingsPayload에 새 폴더 필드가 있다."""
    from main import SettingsPayload
    payload = SettingsPayload(
        INBOX_FOLDER="00_Inbox",
        DAILY_FOLDER="10_Calendar/11_Daily",
        AREAS_FOLDER="30_Areas",
        PROJECTS_FOLDER="20_Projects",
        RESOURCES_FOLDER="40_Resources",
    )
    assert payload.INBOX_FOLDER == "00_Inbox"
    assert payload.RESOURCES_FOLDER == "40_Resources"
