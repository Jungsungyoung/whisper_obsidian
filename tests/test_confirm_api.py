"""
/confirm/{job_id} 엔드포인트 로직 테스트
TestClient 대신 job_status 딕셔너리를 직접 조작해 검증한다.
"""
import pytest
from fastapi import HTTPException


def test_confirm_sets_confirmed_status():
    import main
    from main import ConfirmPayload, confirm_job

    job_id = "test-review-job"
    main.job_status[job_id] = {"status": "review", "analysis": {}}

    payload = ConfirmPayload(
        purpose="테스트 목적",
        discussion=["논의1"],
        decisions=[],
        action_items=["할일1"],
        follow_up=[],
    )
    result = confirm_job(job_id, payload)

    assert result == {"ok": True}
    assert main.job_status[job_id]["status"] == "confirmed"
    assert main.job_status[job_id]["analysis_edited"]["purpose"] == "테스트 목적"
    assert main.job_status[job_id]["analysis_edited"]["action_items"] == ["할일1"]
    del main.job_status[job_id]


def test_confirm_returns_404_for_unknown_job():
    from main import ConfirmPayload, confirm_job

    payload = ConfirmPayload()
    with pytest.raises(HTTPException) as exc:
        confirm_job("nonexistent-job", payload)
    assert exc.value.status_code == 404


def test_confirm_returns_400_when_not_in_review():
    import main
    from main import ConfirmPayload, confirm_job

    job_id = "test-done-job"
    main.job_status[job_id] = {"status": "done"}

    payload = ConfirmPayload()
    with pytest.raises(HTTPException) as exc:
        confirm_job(job_id, payload)
    assert exc.value.status_code == 400
    del main.job_status[job_id]
