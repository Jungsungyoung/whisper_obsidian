# 브라우저 마이크 녹음 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 브라우저에서 마이크로 직접 녹음하고 중단 즉시 자동 전사·분석을 시작한다.

**Architecture:** 프론트엔드(`index.html`)만 수정. MediaRecorder API로 webm Blob 생성 → 기존 `setFile()` + `btn.click()`으로 업로드 로직 재사용. 백엔드 변경 없음.

**Tech Stack:** MediaRecorder API (브라우저 내장), vanilla JS, CSS animation

---

### Task 1: CSS — 녹음 버튼·상태 스타일 추가

**Files:**
- Modify: `static/index.html` (CSS `<style>` 블록 내부)

**Step 1: `#cancel-btn` 스타일 바로 뒤에 CSS 추가**

`</style>` 태그 바로 앞에 아래 블록 삽입:

```css
    /* mic recording */
    #rec-idle { margin-top: 10px; }
    #rec-start-btn {
      width: 100%; padding: 10px;
      background: none; border: 1px solid #ff444466; border-radius: 8px;
      color: #ff8080; font-size: 0.85rem; cursor: pointer;
      transition: background .15s, border-color .15s;
    }
    #rec-start-btn:hover:not(:disabled) { background: #ff44440f; border-color: #ff4444aa; }
    #rec-start-btn:disabled { opacity: 0.35; cursor: not-allowed; }
    #rec-active {
      display: none; align-items: center; gap: 10px;
      margin-top: 10px; padding: 10px 14px;
      background: #1a0000; border: 1px solid #ff444466; border-radius: 8px;
    }
    @keyframes pulse-dot {
      0%,100% { opacity:1; transform:scale(1); }
      50%      { opacity:.5; transform:scale(1.35); }
    }
    .pulse-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: #ff4444; flex-shrink: 0;
      animation: pulse-dot 1s ease-in-out infinite;
    }
    #rec-timer { font-size: 0.88rem; color: #ff8080; flex: 1; font-family: monospace; }
    #rec-stop-btn {
      padding: 6px 14px; background: none;
      border: 1px solid #ff444466; border-radius: 6px;
      color: #ff8080; font-size: 0.82rem; cursor: pointer;
      transition: background .15s;
    }
    #rec-stop-btn:hover { background: #ff44440f; }
    .rec-divider {
      text-align: center; margin: 10px 0 0;
      font-size: 0.72rem; color: #333; letter-spacing: .05em;
    }
```

**Step 2: 브라우저에서 CSS 오류 없는지 확인**

서버 실행 후 `http://localhost:8765` → DevTools Console에 CSS 오류 없으면 OK

---

### Task 2: HTML — 드롭존 아래 녹음 UI 삽입

**Files:**
- Modify: `static/index.html` (HTML body)

**Step 1: 드롭존 `</div>` 바로 뒤, `<input type="file">` 앞에 삽입**

현재 코드:
```html
  </div>
  <input type="file" id="fi" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">
```

→ 아래로 교체:
```html
  </div>

  <div class="rec-divider">── 또는 ──</div>
  <div id="rec-idle">
    <button id="rec-start-btn" type="button">🔴 마이크로 녹음 시작</button>
  </div>
  <div id="rec-active">
    <span class="pulse-dot"></span>
    <span id="rec-timer">00:00</span>
    <button id="rec-stop-btn" type="button">⏹ 녹음 중단</button>
  </div>

  <input type="file" id="fi" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">
```

**Step 2: 브라우저에서 UI 확인**

- 드롭존 아래에 "── 또는 ──" 구분선 + "🔴 마이크로 녹음 시작" 버튼이 보이면 OK
- `#rec-active`는 `display:none`이라 안 보여야 함

---

### Task 3: JS — MediaRecorder 녹음 로직

**Files:**
- Modify: `static/index.html` (`<script>` 블록)

**Step 1: 파일 선택 블록 바로 뒤에 녹음 변수·함수 추가**

`// ── 라이브 로그 + 깜빡이는 커서` 주석 바로 앞에 삽입:

```js
  // ── 마이크 녹음 ────────────────────────────────────────
  let recChunks = [];
  let mediaRecorder = null;
  let recStream = null;
  let recTimerInterval = null;
  let recSecs = 0;

  const recStartBtn = document.getElementById('rec-start-btn');
  const recStopBtn  = document.getElementById('rec-stop-btn');

  // MediaRecorder 미지원 브라우저 처리
  if (!window.MediaRecorder) {
    recStartBtn.disabled = true;
    recStartBtn.textContent = '🔴 녹음 (이 브라우저 미지원)';
  }

  recStartBtn.addEventListener('click', startRecording);
  recStopBtn.addEventListener('click', stopRecording);

  async function startRecording() {
    try {
      recStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      showErr('마이크 접근 권한이 필요합니다: ' + e.message);
      return;
    }

    recChunks = [];
    const mimeType = MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm' : 'audio/ogg';
    mediaRecorder = new MediaRecorder(recStream, { mimeType });

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) recChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      const blob = new Blob(recChunks, { type: mimeType });
      const ts = new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 15);
      const ext = mimeType.includes('webm') ? 'webm' : 'ogg';
      const recFile = new File([blob], `recording_${ts}.${ext}`, { type: mimeType });
      setFile(recFile);
      _stopRecTimer();
      _showRecIdle();
      // 자동 업로드
      document.getElementById('btn').click();
    };

    mediaRecorder.start();
    recSecs = 0;
    recTimerInterval = setInterval(() => {
      recSecs++;
      const m = String(Math.floor(recSecs / 60)).padStart(2, '0');
      const s = String(recSecs % 60).padStart(2, '0');
      document.getElementById('rec-timer').textContent = `${m}:${s}`;
    }, 1000);

    _showRecActive();
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (recStream) {
      recStream.getTracks().forEach(t => t.stop());
      recStream = null;
    }
  }

  function _stopRecTimer() {
    clearInterval(recTimerInterval);
    recTimerInterval = null;
  }

  function _showRecActive() {
    document.getElementById('rec-idle').style.display   = 'none';
    document.getElementById('rec-active').style.display = 'flex';
  }

  function _showRecIdle() {
    document.getElementById('rec-idle').style.display   = 'block';
    document.getElementById('rec-active').style.display = 'none';
  }
```

**Step 2: 브라우저에서 녹음 흐름 수동 검증**

1. `http://localhost:8765` 새로고침 (Ctrl+Shift+R)
2. "🔴 마이크로 녹음 시작" 클릭 → 권한 팝업 승인
3. 빨간 펄스 + 타이머 00:01, 00:02... 증가 확인
4. "⏹ 녹음 중단" 클릭 → 드롭존에 파일명(`recording_....webm`) 표시 확인
5. 자동으로 분석 시작 (업로드 → 전사 단계 이동) 확인

---

## 완료 기준

- [ ] 드롭존 아래 "── 또는 ──" 구분선 + 마이크 버튼 표시
- [ ] 클릭 시 권한 요청 → 승인 → 녹음 상태로 전환
- [ ] 녹음 중 빨간 펄스 + MM:SS 타이머 표시
- [ ] 중단 시 webm 파일 생성 → 자동 업로드 + 전사 시작
- [ ] 권한 거부 시 에러 메시지 표시
- [ ] MediaRecorder 미지원 브라우저 → 버튼 비활성화
