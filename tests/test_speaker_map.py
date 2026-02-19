"""화자 이름 매핑 로직 테스트"""

def test_confirm_stores_speaker_map():
    import main
    from main import ConfirmPayload, confirm_job

    job_id = "test-speaker-job"
    main.job_status[job_id] = {"status": "review"}

    payload = ConfirmPayload(
        purpose="테스트",
        speaker_map={"Speaker A": "홍길동", "Speaker B": "김철수"},
    )
    confirm_job(job_id, payload)

    assert main.job_status[job_id]["analysis_edited"]["speaker_map"] == {
        "Speaker A": "홍길동",
        "Speaker B": "김철수",
    }
    del main.job_status[job_id]


def test_apply_speaker_map_replaces_names():
    from main import _apply_speaker_map

    segments = [
        {"timestamp": "00:01", "speaker": "Speaker A", "text": "안녕"},
        {"timestamp": "00:05", "speaker": "Speaker B", "text": "네"},
        {"timestamp": "00:10", "speaker": "Speaker C", "text": "감사합니다"},
        {"timestamp": "00:15", "speaker": "Speaker A", "text": "잠깐요"},
    ]
    speaker_map = {"Speaker A": "홍길동", "Speaker B": "김철수", "Speaker C": "이영희"}
    result = _apply_speaker_map(segments, speaker_map)

    assert result[0]["speaker"] == "홍길동"
    assert result[1]["speaker"] == "김철수"
    assert result[2]["speaker"] == "이영희"
    assert result[3]["speaker"] == "홍길동"


def test_apply_speaker_map_empty_name_keeps_original():
    from main import _apply_speaker_map

    segments = [{"timestamp": "00:01", "speaker": "Speaker A", "text": "안녕"}]
    result = _apply_speaker_map(segments, {"Speaker A": ""})
    assert result[0]["speaker"] == "Speaker A"


def test_apply_speaker_map_missing_key_keeps_original():
    from main import _apply_speaker_map

    segments = [{"timestamp": "00:01", "speaker": "Speaker D", "text": "안녕"}]
    result = _apply_speaker_map(segments, {"Speaker A": "홍길동"})
    assert result[0]["speaker"] == "Speaker D"


def test_apply_speaker_map_empty_map_no_change():
    from main import _apply_speaker_map

    segments = [
        {"timestamp": "00:01", "speaker": "Speaker A", "text": "안녕"},
        {"timestamp": "00:05", "speaker": "Speaker B", "text": "네"},
    ]
    result = _apply_speaker_map(segments, {})
    assert result[0]["speaker"] == "Speaker A"
    assert result[1]["speaker"] == "Speaker B"
