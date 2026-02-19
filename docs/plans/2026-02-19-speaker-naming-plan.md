# 화자 이름 지정 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 미리보기 패널에서 Speaker A/B를 실명으로 매핑해 Vault 노트에 실명으로 저장한다.

**Architecture:** review 상태에 speakers 리스트 추가 → 프론트엔드가 화자별 입력 필드 생성 → confirm payload에 speaker_map 포함 → 백엔드가 segments.speaker 치환 후 NoteData 구성.

**Tech Stack:** FastAPI/Pydantic (백엔드), vanilla JS/CSS (프론트엔드)

---

### Task 1: 백엔드 — speakers 노출 + speaker_map 적용

**Files:**
- Modify: `main.py`
- Test: `tests/test_speaker_map.py` (신규)

**Step 1: 실패 테스트 작성**

`tests/test_speaker_map.py` 생성:

```python
"""화자 이름 매핑 로직 테스트"""
import pytest
from fastapi import HTTPException


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
    """speaker_map이 segments의 speaker 필드를 올바르게 치환하는지 검증."""
    from main import _apply_speaker_map

    segments = [
        {"timestamp": "00:01", "speaker": "Speaker A", "text": "안녕"},
        {"timestamp": "00:05", "speaker": "Speaker B", "text": "네"},
        {"timestamp": "00:10", "speaker": "Speaker A", "text": "감사합니다"},
    ]
    speaker_map = {"Speaker A": "홍길동", "Speaker B": "김철수"}
    result = _apply_speaker_map(segments, speaker_map)

    assert result[0]["speaker"] == "홍길동"
    assert result[1]["speaker"] == "김철수"
    assert result[2]["speaker"] == "홍길동"


def test_apply_speaker_map_empty_name_keeps_original():
    """이름이 빈 문자열이면 원래 이름 유지."""
    from main import _apply_speaker_map

    segments = [{"timestamp": "00:01", "speaker": "Speaker A", "text": "안녕"}]
    result = _apply_speaker_map(segments, {"Speaker A": ""})
    assert result[0]["speaker"] == "Speaker A"


def test_apply_speaker_map_missing_key_keeps_original():
    """매핑에 없는 화자는 원래 이름 유지."""
    from main import _apply_speaker_map

    segments = [{"timestamp": "00:01", "speaker": "Speaker C", "text": "안녕"}]
    result = _apply_speaker_map(segments, {"Speaker A": "홍길동"})
    assert result[0]["speaker"] == "Speaker C"
```

**Step 2: 테스트 실패 확인**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Whisper_Obsidian\meetscribe
python -m pytest tests/test_speaker_map.py -v
```
Expected: FAIL — `cannot import name '_apply_speaker_map' from 'main'`

**Step 3: main.py 수정**

**(3-a)** `ConfirmPayload`에 `speaker_map` 필드 추가:

현재:
```python
class ConfirmPayload(BaseModel):
    purpose: str = ""
    discussion: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    follow_up: list[str] = []
```

→ 교체:
```python
class ConfirmPayload(BaseModel):
    purpose: str = ""
    discussion: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    follow_up: list[str] = []
    speaker_map: dict[str, str] = {}
```

**(3-b)** `confirm_job` 함수 바로 위에 헬퍼 함수 추가:

```python
def _apply_speaker_map(segments: list[dict], speaker_map: dict[str, str]) -> list[dict]:
    """segments의 speaker 필드를 speaker_map으로 치환. 빈 값이면 원래 이름 유지."""
    for seg in segments:
        mapped = speaker_map.get(seg["speaker"], "")
        if mapped:
            seg["speaker"] = mapped
    return segments
```

**(3-c)** `_process()` 내부 review 블록에 speakers 추가 + while 루프 후 speaker_map 적용:

현재 review 블록:
```python
        # 사용자 검토 대기
        _log("AI 분석 완료. 결과를 확인하고 저장 버튼을 클릭하세요.")
        job_status[job_id].update({
            "status": "review", "step": "검토 중...", "progress": 97,
            "detail": "분석 결과를 확인하고 저장 버튼을 클릭하세요.",
            "analysis": analysis,
            "elapsed": int(time.time() - start_time),
        })

        while True:
            time.sleep(0.5)
            cur = job_status[job_id].get("status")
            if cur == "confirmed":
                edited = job_status[job_id].get("analysis_edited")
                if edited:
                    analysis = edited
                break
            if cur == "cancelling":
                mark_cancelled()
                return
```

→ 교체:
```python
        # 사용자 검토 대기 (speakers는 review panel에 표시하기 위해 미리 계산)
        review_speakers = sorted({seg["speaker"] for seg in transcript_result["segments"]})
        _log("AI 분석 완료. 결과를 확인하고 저장 버튼을 클릭하세요.")
        job_status[job_id].update({
            "status": "review", "step": "검토 중...", "progress": 97,
            "detail": "분석 결과를 확인하고 저장 버튼을 클릭하세요.",
            "analysis": analysis,
            "speakers": review_speakers,
            "elapsed": int(time.time() - start_time),
        })

        while True:
            time.sleep(0.5)
            cur = job_status[job_id].get("status")
            if cur == "confirmed":
                edited = job_status[job_id].get("analysis_edited") or {}
                speaker_map = edited.pop("speaker_map", {})
                if edited:
                    analysis = edited
                if speaker_map:
                    _apply_speaker_map(transcript_result["segments"], speaker_map)
                break
            if cur == "cancelling":
                mark_cancelled()
                return
```

**Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/test_speaker_map.py -v
```
Expected: 4개 모두 PASS

**Step 5: 전체 테스트 확인**

```bash
python -m pytest tests/ --ignore=tests/test_integration.py -v
```
Expected: 전체 PASS

---

### Task 2: 프론트엔드 — 화자 입력 섹션

**Files:**
- Modify: `static/index.html`

**Step 1: CSS 추가 — `#rv-cancel-btn:hover` 뒤에 삽입**

```css
    /* speaker mapping */
    #rv-speakers { margin-bottom: 14px; }
    .rv-speaker-row {
      display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
    }
    .rv-speaker-label {
      font-size: 0.8rem; color: #667766; width: 72px; flex-shrink: 0;
    }
    .rv-speaker-arrow { color: #333; font-size: 0.8rem; }
    .rv-speaker-input {
      flex: 1; padding: 6px 10px;
      background: #0a150a; border: 1px solid #ffffff0f; border-radius: 6px;
      color: #cce8cc; font-size: 0.8rem; outline: none;
      transition: border-color .15s;
    }
    .rv-speaker-input:focus { border-color: #4caf5055; }
```

**Step 2: HTML — review panel 상단에 화자 섹션 추가**

현재 `#review-panel` 내부 첫 줄:
```html
    <h3>📋 분석 결과 검토</h3>
    <div class="rv-field">
      <label>회의 목적</label>
```

→ `<h3>` 뒤에 삽입:
```html
    <h3>📋 분석 결과 검토</h3>
    <div class="rv-field">
      <label>화자 이름 지정 (선택)</label>
      <div id="rv-speakers"></div>
    </div>
    <div class="rv-field">
      <label>회의 목적</label>
```

**Step 3: JS — showReviewPanel에 speakers 파라미터 추가**

현재:
```js
  function showReviewPanel(analysis) {
    if (!analysis) return;
    document.getElementById('rv-purpose').value      = analysis.purpose || '';
```

→ 교체:
```js
  function showReviewPanel(analysis, speakers) {
    if (!analysis) return;

    // 화자 입력 필드 생성
    const speakerSection = document.getElementById('rv-speakers');
    speakerSection.innerHTML = '';
    (speakers || []).forEach(sp => {
      const row = document.createElement('div');
      row.className = 'rv-speaker-row';
      row.innerHTML = `
        <span class="rv-speaker-label">${sp}</span>
        <span class="rv-speaker-arrow">→</span>
        <input type="text" class="rv-speaker-input" data-speaker="${sp}"
               placeholder="실명 (비워두면 ${sp})">
      `;
      speakerSection.appendChild(row);
    });

    document.getElementById('rv-purpose').value      = analysis.purpose || '';
```

**Step 4: JS — poll()의 review 핸들러에 speakers 전달**

현재:
```js
          showReviewPanel(d.analysis);
```

→ 교체:
```js
          showReviewPanel(d.analysis, d.speakers);
```

**Step 5: JS — confirm payload에 speaker_map 추가**

현재 `rv-save-btn` click 핸들러의 payload:
```js
    const payload = {
      purpose:      document.getElementById('rv-purpose').value.trim(),
      discussion:   parseLines('rv-discussion'),
      decisions:    parseLines('rv-decisions'),
      action_items: parseLines('rv-action-items'),
      follow_up:    parseLines('rv-follow-up'),
    };
```

→ 교체:
```js
    const speakerMap = {};
    document.querySelectorAll('.rv-speaker-input').forEach(input => {
      const val = input.value.trim();
      if (val) speakerMap[input.dataset.speaker] = val;
    });
    const payload = {
      speaker_map:  speakerMap,
      purpose:      document.getElementById('rv-purpose').value.trim(),
      discussion:   parseLines('rv-discussion'),
      decisions:    parseLines('rv-decisions'),
      action_items: parseLines('rv-action-items'),
      follow_up:    parseLines('rv-follow-up'),
    };
```

**Step 6: 브라우저에서 수동 검증**

1. 서버 재시작 후 Ctrl+Shift+R
2. 파일 업로드 → 전사 → 분석 완료 대기
3. 미리보기 패널 상단에 "화자 이름 지정" 섹션 표시 확인
4. Speaker A → "홍길동", Speaker B → "김철수" 입력
5. "Vault에 저장" 클릭
6. Obsidian 노트에서 `홍길동`, `김철수`로 표시되는지 확인

---

## 완료 기준

- [ ] `ConfirmPayload`에 `speaker_map: dict[str, str]` 추가
- [ ] `_apply_speaker_map()` 함수 동작 (빈 값 / 없는 키 처리 포함)
- [ ] review 상태에 `speakers` 리스트 포함
- [ ] 미리보기 패널 상단에 화자별 이름 입력 필드 자동 생성
- [ ] confirm 시 speaker_map 적용 → 노트에 실명 저장
- [ ] 전체 테스트 통과
