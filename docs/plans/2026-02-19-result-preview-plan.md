# 결과 미리보기 + 편집 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** AI 분석 완료 후 Vault 저장 전에 사용자가 결과를 확인·편집하고 최종 저장할 수 있도록 파이프라인을 일시 정지한다.

**Architecture:** 백그라운드 스레드가 분석 완료 후 status="review"로 전환 및 대기. 프론트엔드가 review 상태를 감지해 편집 패널을 표시. 사용자가 "저장" 클릭 시 `POST /confirm/{job_id}`로 편집 데이터 전송 → 스레드 재개 → Vault 저장.

**Tech Stack:** FastAPI, Pydantic, vanilla JS, CSS

---

### Task 1: 백엔드 — review 대기 + confirm 엔드포인트

**Files:**
- Modify: `main.py`
- Test: `tests/test_confirm_api.py` (신규)

**Step 1: 실패 테스트 작성**

`tests/test_confirm_api.py` 생성:

```python
import pytest
from fastapi.testclient import TestClient


def _make_client():
    import main
    return TestClient(main.app), main


def test_confirm_sets_confirmed_status():
    client, main = _make_client()
    job_id = "test-review-job"
    main.job_status[job_id] = {"status": "review", "analysis": {}}

    resp = client.post(f"/confirm/{job_id}", json={
        "purpose": "테스트 목적",
        "discussion": ["논의1"],
        "decisions": [],
        "action_items": ["할일1"],
        "follow_up": [],
    })

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert main.job_status[job_id]["status"] == "confirmed"
    assert main.job_status[job_id]["analysis_edited"]["purpose"] == "테스트 목적"
    del main.job_status[job_id]


def test_confirm_returns_404_for_unknown_job():
    client, _ = _make_client()
    resp = client.post("/confirm/nonexistent-job", json={
        "purpose": "", "discussion": [], "decisions": [],
        "action_items": [], "follow_up": [],
    })
    assert resp.status_code == 404


def test_confirm_returns_400_when_not_in_review():
    client, main = _make_client()
    job_id = "test-done-job"
    main.job_status[job_id] = {"status": "done"}

    resp = client.post(f"/confirm/{job_id}", json={
        "purpose": "", "discussion": [], "decisions": [],
        "action_items": [], "follow_up": [],
    })

    assert resp.status_code == 400
    del main.job_status[job_id]
```

**Step 2: 테스트 실패 확인**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Whisper_Obsidian\meetscribe
python -m pytest tests/test_confirm_api.py -v
```
Expected: FAIL — `404 Not Found` (엔드포인트 없음)

**Step 3: main.py에 ConfirmPayload 모델 + 엔드포인트 추가**

`SettingsPayload` 클래스 바로 뒤에 추가:

```python
class ConfirmPayload(BaseModel):
    purpose: str = ""
    discussion: list[str] = []
    decisions: list[str] = []
    action_items: list[str] = []
    follow_up: list[str] = []


@app.post("/confirm/{job_id}")
def confirm_job(job_id: str, payload: ConfirmPayload):
    if job_id not in job_status:
        raise HTTPException(404, "Job not found")
    if job_status[job_id].get("status") != "review":
        raise HTTPException(400, "Job is not in review state")
    job_status[job_id]["analysis_edited"] = payload.model_dump()
    job_status[job_id]["status"] = "confirmed"
    return {"ok": True}
```

**Step 4: _process()에 review 대기 로직 삽입**

`main.py`의 `_process()` 내부에서 아래 코드 교체:

현재 코드 (line 232~236):
```python
        analysis = analyze_transcript(transcript_result["full_text"])

        if is_cancelled():
            mark_cancelled()
            return

        update("building", "노트 생성 중...", 98, "노트 빌드 중...")
```

→ 아래로 교체:
```python
        analysis = analyze_transcript(transcript_result["full_text"])

        if is_cancelled():
            mark_cancelled()
            return

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

        update("building", "노트 생성 중...", 98, "노트 빌드 중...")
```

**Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_confirm_api.py -v
```
Expected: 3개 모두 PASS

**Step 6: 전체 테스트 확인**

```bash
python -m pytest tests/ -v
```
Expected: 전체 PASS

---

### Task 2: 프론트엔드 — CSS + HTML

**Files:**
- Modify: `static/index.html`

**Step 1: `</style>` 직전에 CSS 추가**

```css
    /* review panel */
    #review-panel {
      display: none; margin-top: 18px;
      background: #0f1e0f; border: 1px solid #4caf5033;
      border-radius: 12px; padding: 18px;
    }
    #review-panel h3 {
      font-size: 0.88rem; color: #88cc88; margin-bottom: 14px;
      display: flex; align-items: center; gap: 6px;
    }
    .rv-field { margin-bottom: 12px; }
    .rv-field label {
      display: block; font-size: 0.72rem; color: #666;
      text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px;
    }
    .rv-field textarea {
      width: 100%; padding: 8px 10px;
      background: #0a150a; border: 1px solid #ffffff0f; border-radius: 7px;
      color: #cce8cc; font-size: 0.8rem; font-family: inherit;
      resize: vertical; min-height: 52px; outline: none;
      transition: border-color .15s; line-height: 1.6;
    }
    .rv-field textarea:focus { border-color: #4caf5055; }
    .rv-actions { display: flex; gap: 10px; margin-top: 14px; }
    #rv-save-btn {
      flex: 1; padding: 11px;
      background: #4caf5022; border: 1px solid #4caf5066; border-radius: 8px;
      color: #88cc88; font-size: 0.9rem; font-weight: 600; cursor: pointer;
      transition: background .15s;
    }
    #rv-save-btn:hover { background: #4caf5044; }
    #rv-save-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    #rv-cancel-btn {
      padding: 11px 18px;
      background: none; border: 1px solid #ffffff11; border-radius: 8px;
      color: #555; font-size: 0.88rem; cursor: pointer;
      transition: background .15s;
    }
    #rv-cancel-btn:hover { background: #ffffff08; color: #888; }
```

**Step 2: HTML — `#err` div 바로 앞에 review 패널 삽입**

현재:
```html
  <div id="err"></div>
```

→ 앞에 삽입:
```html
  <div id="review-panel">
    <h3>📋 분석 결과 검토</h3>
    <div class="rv-field">
      <label>회의 목적</label>
      <textarea id="rv-purpose" rows="2"></textarea>
    </div>
    <div class="rv-field">
      <label>주요 논의 (줄바꿈으로 구분)</label>
      <textarea id="rv-discussion" rows="3"></textarea>
    </div>
    <div class="rv-field">
      <label>결정 사항</label>
      <textarea id="rv-decisions" rows="2"></textarea>
    </div>
    <div class="rv-field">
      <label>액션 아이템</label>
      <textarea id="rv-action-items" rows="3"></textarea>
    </div>
    <div class="rv-field">
      <label>후속 과제</label>
      <textarea id="rv-follow-up" rows="2"></textarea>
    </div>
    <div class="rv-actions">
      <button id="rv-save-btn">Vault에 저장</button>
      <button id="rv-cancel-btn">취소</button>
    </div>
  </div>

  <div id="err"></div>
```

---

### Task 3: 프론트엔드 — JS 폴링 + confirm 로직

**Files:**
- Modify: `static/index.html` (`<script>` 블록)

**Step 1: btn.addEventListener('click', ...) 핸들러에 review panel 초기화 추가**

`hide('result'); hide('err');` 줄 뒤에 추가:
```js
    hide('review-panel');
```

**Step 2: poll() 함수의 cancelling 핸들러 바로 앞에 review 핸들러 삽입**

현재 poll() 내부:
```js
        if (d.status === 'cancelling') {
```

→ 앞에 삽입:
```js
        if (d.status === 'review') {
          setStep('s-ai', 'done');
          setProgress(97, '분석 완료 — 내용을 확인하고 저장하세요.');
          appendLogs(d.logs);
          showReviewPanel(d.analysis);
          return; // clearInterval 하지 않음 — 저장 후 계속 폴링
        } else if (d.status === 'confirmed' || d.status === 'building' || d.status === 'saving') {
          hide('review-panel');
        }
```

**주의**: `review` 상태에서는 `clearInterval(t)`를 호출하지 않아야 합니다. 사용자가 저장 버튼을 클릭하고 파이프라인이 재개되면 자동으로 `done` 상태가 되어 폴링이 종료됩니다.

**Step 3: showReviewPanel 함수 + rv 버튼 이벤트 추가**

`// ── 설정 모달` 주석 바로 앞에 삽입:

```js
  // ── 결과 미리보기 ───────────────────────────────────────
  function showReviewPanel(analysis) {
    if (!analysis) return;
    document.getElementById('rv-purpose').value =
      analysis.purpose || '';
    document.getElementById('rv-discussion').value =
      (analysis.discussion || []).join('\n');
    document.getElementById('rv-decisions').value =
      (analysis.decisions || []).join('\n');
    document.getElementById('rv-action-items').value =
      (analysis.action_items || []).join('\n');
    document.getElementById('rv-follow-up').value =
      (analysis.follow_up || []).join('\n');
    document.getElementById('review-panel').style.display = 'block';
    cancelBtn.style.display = 'none'; // 취소는 rv 패널 버튼으로 대체
  }

  function parseLines(id) {
    return document.getElementById(id).value
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean);
  }

  document.getElementById('rv-save-btn').addEventListener('click', async () => {
    const saveBtn = document.getElementById('rv-save-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = '저장 중...';
    const payload = {
      purpose:      document.getElementById('rv-purpose').value.trim(),
      discussion:   parseLines('rv-discussion'),
      decisions:    parseLines('rv-decisions'),
      action_items: parseLines('rv-action-items'),
      follow_up:    parseLines('rv-follow-up'),
    };
    try {
      const r = await fetch(`/confirm/${currentJobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(await r.text());
      hide('review-panel');
      setStep('s-save', 'active');
    } catch (e) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Vault에 저장';
      showErr('저장 요청 실패: ' + e.message);
    }
  });

  document.getElementById('rv-cancel-btn').addEventListener('click', async () => {
    if (!currentJobId) return;
    hide('review-panel');
    try { await fetch(`/cancel/${currentJobId}`, { method: 'POST' }); } catch (e) {}
  });
```

**Step 4: 브라우저에서 전체 흐름 수동 검증**

1. 서버 재시작 (변경사항 반영)
2. `http://localhost:8765` Ctrl+Shift+R
3. 파일 업로드 → 전사 → AI 분석 완료 대기
4. 분석 완료 시 녹색 "📋 분석 결과 검토" 패널 표시 확인
5. 텍스트 수정 후 "Vault에 저장" 클릭
6. 파이프라인 재개 → `✅ Vault 저장` → 완료 확인

---

## 완료 기준

- [ ] `POST /confirm/{job_id}` 엔드포인트 동작
- [ ] 분석 완료 후 status="review" → UI에 편집 패널 표시
- [ ] 모든 필드 편집 가능 (purpose, discussion, decisions, action_items, follow_up)
- [ ] "Vault에 저장" 클릭 시 편집 데이터로 Vault 저장
- [ ] "취소" 클릭 시 처리 취소
- [ ] 전체 테스트 통과
