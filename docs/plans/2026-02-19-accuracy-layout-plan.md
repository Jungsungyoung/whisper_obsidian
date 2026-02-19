# 전사 정확도 + 레이아웃 2단 분할 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 함정·선박 도메인 용어를 Whisper initial_prompt와 Gemini 컨텍스트에 주입해 전사/분석 품질을 높이고, UI를 좌우 2단 레이아웃으로 재구성한다.

**Architecture:** DOMAIN_VOCAB(.env) + 회의별 context(Form) → `_build_initial_prompt()` → WhisperX `model.transcribe(initial_prompt=...)` + Gemini 프롬프트 앞에 주입. 프론트엔드는 `.card`를 `max-width:960px` 2컬럼 CSS grid로 전환, 오른쪽에 review/result 패널 배치.

**Tech Stack:** FastAPI/Pydantic (백엔드), vanilla JS/CSS Grid (프론트엔드), WhisperX, google-genai

---

### Task 1: 백엔드 — initial_prompt 빌더 + transcriber 연결

**Files:**
- Modify: `pipeline/transcriber.py`
- Modify: `config.py`
- Test: `tests/test_vocab_context.py` (신규)

**Step 1: 실패 테스트 작성**

`tests/test_vocab_context.py` 생성:

```python
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
```

**Step 2: 테스트 실패 확인**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Whisper_Obsidian\meetscribe
python -m pytest tests/test_vocab_context.py -v
```
Expected: FAIL — `cannot import name '_build_initial_prompt'`

**Step 3: config.py에 DOMAIN_VOCAB 추가**

현재 `config.py` 마지막 변수 줄:
```python
ALLOW_CPU: bool = os.getenv("ALLOW_CPU", "false").strip().lower() == "true"
```

→ 아래에 한 줄 추가:
```python
ALLOW_CPU: bool = os.getenv("ALLOW_CPU", "false").strip().lower() == "true"
DOMAIN_VOCAB: str = os.getenv("DOMAIN_VOCAB", "함정, 선박, 전투체계, 소나, 레이더, 추진체계, 함교, 수상함, 잠수함, 어뢰, 기관실, 항법, 통신체계").strip()
```

**Step 4: transcriber.py에 `_build_initial_prompt` + `initial_prompt` 파라미터 추가**

`transcriber.py` 상단 `def transcribe(...)` 바로 위에 헬퍼 추가:

```python
def _build_initial_prompt(domain_vocab: str, context: str) -> str:
    """DOMAIN_VOCAB + 회의 맥락을 합성해 Whisper initial_prompt 생성."""
    parts = [p for p in [domain_vocab.strip(), context.strip()] if p]
    return ". ".join(parts)
```

`transcribe()` 시그니처 변경:
```python
def transcribe(audio_path: Path, on_progress=None, context: str = "") -> dict:
```
내부 첫 줄 추가:
```python
    initial_prompt = _build_initial_prompt(config.DOMAIN_VOCAB, context)
```
`_transcribe_local` 호출 변경:
```python
    try:
        return _transcribe_local(audio_path, on_progress, initial_prompt)
    except RuntimeError:
        raise
    except Exception as e:
        print(f"[Transcriber] 로컬 Whisper 실패: {e}. OpenAI API로 폴백.")
        return _transcribe_api(audio_path)
```

`_transcribe_local()` 시그니처 변경:
```python
def _transcribe_local(audio_path: Path, on_progress=None, initial_prompt: str = "") -> dict:
```

`model.transcribe()` 호출 변경 (현재: `result = model.transcribe(audio, batch_size=batch_size)`):
```python
    transcribe_kwargs = {"batch_size": batch_size}
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt
    result = model.transcribe(audio, **transcribe_kwargs)
```

**Step 5: 테스트 통과 확인**

```bash
python -m pytest tests/test_vocab_context.py -v
```
Expected: 4개 PASS

**Step 6: 전체 테스트 확인**

```bash
python -m pytest tests/ --ignore=tests/test_integration.py -v
```
Expected: 전체 PASS

---

### Task 2: 백엔드 — analyzer context 주입 + settings DOMAIN_VOCAB

**Files:**
- Modify: `pipeline/analyzer.py`
- Modify: `main.py`
- Test: `tests/test_vocab_context.py` (추가)

**Step 1: analyzer.py 테스트 추가**

`tests/test_vocab_context.py`에 추가:

```python
def test_build_analysis_prompt_includes_context():
    from pipeline.analyzer import _build_analysis_prompt
    prompt = _build_analysis_prompt("레이더 설계 검토 회의", "회의 내용 전사본")
    assert "레이더 설계 검토 회의" in prompt
    assert "회의 내용 전사본" in prompt


def test_build_analysis_prompt_no_context():
    from pipeline.analyzer import _build_analysis_prompt
    prompt = _build_analysis_prompt("", "회의 내용 전사본")
    assert "회의 내용 전사본" in prompt
```

**Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/test_vocab_context.py -v
```
Expected: 2개 신규 FAIL

**Step 3: analyzer.py 수정**

`_build_analysis_prompt` 헬퍼 추가 (SYSTEM_PROMPT 아래):

```python
def _build_analysis_prompt(context: str, transcript_text: str) -> str:
    """회의 맥락이 있으면 프롬프트 앞에 주입."""
    ctx_line = f"[회의 맥락: {context.strip()}]\n\n" if context.strip() else ""
    return f"{ctx_line}{SYSTEM_PROMPT}\n\n다음 회의 내용을 분석해주세요:\n\n{transcript_text}"
```

`analyze_transcript()` 시그니처 변경:
```python
def analyze_transcript(transcript_text: str, context: str = "") -> dict:
```

`_analyze_gemini()` 시그니처 변경:
```python
def _analyze_gemini(transcript_text: str, context: str = "") -> dict:
```
내부 `prompt` 변경:
```python
    prompt = _build_analysis_prompt(context, transcript_text)
    response = client.models.generate_content(
        model=config.LLM_MODEL,
        contents=prompt,
    )
```

`_analyze_openai()` 시그니처 변경:
```python
def _analyze_openai(transcript_text: str, context: str = "") -> dict:
```
내부 messages 변경:
```python
    prompt = _build_analysis_prompt(context, transcript_text)
    response = client.chat.completions.create(
        model=openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
```

`analyze_transcript()` 내부 폴백 체인에 context 전달:
```python
def analyze_transcript(transcript_text: str, context: str = "") -> dict:
    if config.GEMINI_API_KEY:
        try:
            return _analyze_gemini(transcript_text, context)
        except Exception as e:
            print(f"[Analyzer] Gemini 실패: {e}. OpenAI로 폴백.")

    if config.OPENAI_API_KEY:
        try:
            return _analyze_openai(transcript_text, context)
        except Exception as e:
            print(f"[Analyzer] OpenAI 실패: {e}. 기본 분석 사용.")

    return _analyze_basic(transcript_text)
```

**Step 4: main.py 수정**

**(4-a)** `/upload` Form에 `context` 파라미터 추가:

현재:
```python
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
):
```
→:
```python
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    project: str = Form(""),
    context: str = Form(""),
):
```

**(4-b)** `background_tasks.add_task()` 호출에 context 추가:

현재:
```python
    background_tasks.add_task(
        _process, job_id, save_path, effective_title, project.strip(), file.filename
    )
```
→:
```python
    background_tasks.add_task(
        _process, job_id, save_path, effective_title, project.strip(), file.filename, context.strip()
    )
```

**(4-c)** `_process()` 시그니처에 context 추가:

현재:
```python
def _process(job_id: str, audio_path: Path, title: str, project: str, original_filename: str):
```
→:
```python
def _process(job_id: str, audio_path: Path, title: str, project: str, original_filename: str, context: str = ""):
```

**(4-d)** `_process()` 내 `transcribe()` 호출에 context 추가:

현재:
```python
        transcript_result = transcribe(audio_path, on_progress=on_transcribe_progress)
```
→:
```python
        transcript_result = transcribe(audio_path, on_progress=on_transcribe_progress, context=context)
```

**(4-e)** `_process()` 내 `analyze_transcript()` 호출에 context 추가:

현재:
```python
        analysis = analyze_transcript(transcript_result["full_text"])
```
→:
```python
        analysis = analyze_transcript(transcript_result["full_text"], context=context)
```

**(4-f)** `get_settings()` 반환값에 DOMAIN_VOCAB 추가:

현재:
```python
    for k in ["WHISPER_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY", "HF_TOKEN", "VAULT_PATH", "MEETINGS_FOLDER"]:
```
→:
```python
    for k in ["WHISPER_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY", "HF_TOKEN", "VAULT_PATH", "MEETINGS_FOLDER", "DOMAIN_VOCAB"]:
```

**(4-g)** `SettingsPayload`에 DOMAIN_VOCAB 추가:

현재:
```python
class SettingsPayload(BaseModel):
    WHISPER_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HF_TOKEN: str = ""
    VAULT_PATH: str = ""
    MEETINGS_FOLDER: str = ""
```
→:
```python
class SettingsPayload(BaseModel):
    WHISPER_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    HF_TOKEN: str = ""
    VAULT_PATH: str = ""
    MEETINGS_FOLDER: str = ""
    DOMAIN_VOCAB: str = ""
```

**Step 5: config.py reload에서 DOMAIN_VOCAB 갱신 확인**

`save_settings()`에서 이미 `importlib.reload(config)`를 호출하므로 추가 변경 불필요.

**Step 6: 테스트 통과 확인**

```bash
python -m pytest tests/test_vocab_context.py -v
```
Expected: 6개 모두 PASS

```bash
python -m pytest tests/ --ignore=tests/test_integration.py -v
```
Expected: 전체 PASS

---

### Task 3: 프론트엔드 — 2단 레이아웃 + 회의 맥락 필드 + 설정 DOMAIN_VOCAB

**Files:**
- Modify: `static/index.html`

**Step 1: CSS — body/card를 2단 grid로 교체**

현재 `body` CSS:
```css
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card {
      width: 480px;
      background: #16213e;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }
```

→ 교체:
```css
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #1a1a2e;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding: 32px 16px;
    }
    .card {
      width: 100%;
      max-width: 960px;
      background: #16213e;
      border-radius: 16px;
      padding: 28px 32px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }
    .card-body {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 28px;
      align-items: start;
    }
    @media (max-width: 700px) {
      .card-body { grid-template-columns: 1fr; }
    }
    .col-left {}
    .col-right {
      min-height: 200px;
    }
```

**Step 2: CSS — 회의 맥락 textarea 추가 (`.rv-speaker-input:focus` 뒤에)**

```css
    /* 회의 맥락 */
    #context-field textarea {
      width: 100%; padding: 8px 10px;
      background: #0f3460; border: 1px solid #ffffff11; border-radius: 8px;
      color: #e0e0e0; font-size: 0.82rem; font-family: inherit;
      resize: vertical; min-height: 52px; outline: none;
      transition: border-color .15s; line-height: 1.5;
    }
    #context-field textarea:focus { border-color: #7c83fd; }

    /* 설정 모달 DOMAIN_VOCAB */
    .modal-field textarea {
      width: 100%; padding: 9px 12px;
      background: #0f3460; border: 1px solid #ffffff11; border-radius: 8px;
      color: #e0e0e0; font-size: 0.82rem; font-family: inherit;
      resize: vertical; min-height: 68px; outline: none;
      transition: border-color .15s; line-height: 1.5;
    }
    .modal-field textarea:focus { border-color: #7c83fd; }

    /* 오른쪽 컬럼 플레이스홀더 */
    #right-placeholder {
      display: flex; align-items: center; justify-content: center;
      height: 200px; color: #333; font-size: 0.82rem;
      border: 1px dashed #ffffff0a; border-radius: 12px;
    }
```

**Step 3: HTML — .card 내부를 2단으로 재구성**

현재 메인 카드 HTML 구조 (`<div class="card">` 내부 전체):
```html
<!-- 메인 카드 -->
<div class="card">
  <div class="header">
    ...
  </div>

  <div id="drop-zone" ...>...</div>
  <div class="rec-divider">── 또는 ──</div>
  <div id="rec-idle">...</div>
  <div id="rec-active">...</div>
  <div id="rec-confirm">...</div>

  <input type="file" id="fi" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">

  <div class="field">
    <label for="title">회의 제목</label>
    <input type="text" id="title" placeholder="비워두면 파일명 사용">
  </div>
  <div class="field">
    <label for="project">프로젝트 (선택)</label>
    <select id="project">
      <option value="">선택 안 함</option>
    </select>
  </div>

  <button id="btn" disabled>분석 시작</button>
  <button id="cancel-btn">■ 처리 중단</button>

  <div id="progress">
    ...
  </div>

  <div id="log-panel"></div>
  <div id="review-panel">
    ...
  </div>

  <div id="err"></div>

  <div id="result">
    ...
  </div>
</div>
```

→ 전체 교체 (header는 그대로, card-body를 2단으로 분리):
```html
<!-- 메인 카드 -->
<div class="card">
  <div class="header">
    <div>
      <h1>MeetScribe</h1>
      <p class="sub">회의 녹음 → 자동 전사 → Obsidian 노트</p>
    </div>
    <button id="settings-btn" title="설정">⚙</button>
  </div>

  <div class="card-body">
    <!-- 왼쪽: 입력 + 진행 -->
    <div class="col-left">
      <div id="drop-zone" role="button" tabindex="0" aria-label="파일 업로드 영역"
           onclick="document.getElementById('fi').click()"
           onkeydown="if(event.key==='Enter')document.getElementById('fi').click()">
        <div class="ico">🎙️</div>
        <div>파일을 드래그하거나 클릭하세요</div>
        <div class="hint">mp3 · wav · m4a · mp4</div>
        <div id="fname"></div>
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
      <div id="rec-confirm">
        <span id="rec-confirm-label"></span>
        <button id="rec-confirm-ok" type="button">▶ 전사 시작</button>
        <button id="rec-confirm-cancel" type="button">✕ 다시 녹음</button>
      </div>

      <input type="file" id="fi" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">

      <div class="field">
        <label for="title">회의 제목</label>
        <input type="text" id="title" placeholder="비워두면 파일명 사용">
      </div>
      <div class="field">
        <label for="project">프로젝트 (선택)</label>
        <select id="project">
          <option value="">선택 안 함</option>
        </select>
      </div>
      <div class="field" id="context-field">
        <label for="context">회의 맥락 (선택 — 전사/분석 정확도 향상)</label>
        <textarea id="context" rows="2"
          placeholder="예: 레이더 시스템 설계 검토, 전투체계 통합 일정 논의"></textarea>
      </div>

      <button id="btn" disabled>분석 시작</button>
      <button id="cancel-btn">■ 처리 중단</button>

      <div id="progress">
        <div class="step" id="s-upload"><span class="ico">⬜</span>업로드</div>
        <div class="step" id="s-trans"><span class="ico">⬜</span>Whisper 전사</div>
        <div class="step" id="s-ai"><span class="ico">⬜</span>Gemini AI 분석</div>
        <div class="step" id="s-save"><span class="ico">⬜</span>Vault 저장</div>
        <div id="progress-bar-wrap"><div id="progress-bar"></div></div>
        <div id="progress-detail">
          <span class="detail-text" id="detail-text"></span>
          <span class="elapsed-text" id="elapsed-text"></span>
        </div>
      </div>

      <div id="log-panel"></div>
      <div id="err"></div>
    </div>

    <!-- 오른쪽: 검토/결과 -->
    <div class="col-right">
      <div id="right-placeholder">분석 완료 후 결과가 여기 표시됩니다</div>
      <div id="review-panel">
        <h3>📋 분석 결과 검토</h3>
        <div class="rv-field">
          <label>화자 이름 지정 (선택)</label>
          <div id="rv-speakers"></div>
        </div>
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
      <div id="result">
        <div class="result-box">
          <p>완료! Obsidian에서 열기:</p>
          <a id="lnk-meeting" class="obs-btn" href="#">📝 회의 노트 열기</a>
          <a id="lnk-transcript" class="obs-btn" href="#">📄 전사 노트 열기</a>
        </div>
      </div>
    </div>
  </div>
</div>
```

**Step 4: JS — FormData에 context 추가**

현재:
```js
    fd.append('file', file);
    fd.append('title', document.getElementById('title').value);
    fd.append('project', document.getElementById('project').value);
```
→:
```js
    fd.append('file', file);
    fd.append('title', document.getElementById('title').value);
    fd.append('project', document.getElementById('project').value);
    fd.append('context', document.getElementById('context').value);
```

**Step 5: JS — review/result 표시 시 right-placeholder 숨김**

`showReviewPanel()` 함수 시작 부분에 추가:
```js
    document.getElementById('right-placeholder').style.display = 'none';
```

`show('result')` 호출 전에 추가:
```js
          document.getElementById('right-placeholder').style.display = 'none';
```

새 업로드 시작 시 (`btn.addEventListener('click', ...)` 내 초기화 부분) right-placeholder 다시 표시:
```js
    document.getElementById('right-placeholder').style.display = 'flex';
    hide('result'); hide('review-panel');
```

**Step 6: JS — 설정 모달에서 DOMAIN_VOCAB 로드/저장**

`openSettings()` 함수에 추가:
```js
      document.getElementById('s-domain-vocab').value = s.DOMAIN_VOCAB || '';
```

`save-btn` click 핸들러 payload에 추가:
```js
      DOMAIN_VOCAB: document.getElementById('s-domain-vocab').value,
```

**Step 7: HTML — 설정 모달에 DOMAIN_VOCAB 섹션 추가**

현재 설정 모달의 마지막 `.modal-section` (Obsidian Vault 섹션) 뒤, `.modal-actions` 앞에 삽입:

```html
    <div class="modal-section">
      <div class="modal-section-title">전사 정확도</div>
      <div class="modal-field">
        <label for="s-domain-vocab">도메인 용어 (Whisper 인식 힌트)</label>
        <textarea id="s-domain-vocab" rows="3"
          placeholder="함정, 선박, 전투체계, 소나, 레이더, ..."></textarea>
      </div>
    </div>
```

**Step 8: 브라우저에서 수동 검증**

1. 서버 재시작 후 Ctrl+Shift+R
2. 2단 레이아웃 확인 (왼쪽: 입력/진행, 오른쪽: 빈 상태)
3. 회의 맥락 필드에 "레이더 설계 검토 회의" 입력
4. 파일 업로드 후 분석 완료 → 오른쪽에 review panel 표시 확인
5. 저장 완료 → 오른쪽에 result panel 표시 확인
6. 설정(⚙) → 도메인 용어 확인 및 수정 가능 확인
7. 서버 콘솔에서 `[Transcriber]` 로그의 initial_prompt 확인

---

## 완료 기준

- [ ] `_build_initial_prompt()` 동작 (빈 값 처리 포함)
- [ ] WhisperX `initial_prompt`에 DOMAIN_VOCAB + context 주입
- [ ] Gemini/OpenAI 프롬프트에 context 주입
- [ ] 설정 모달에서 DOMAIN_VOCAB 편집 가능
- [ ] UI 2단 레이아웃 (960px 이하 1단 반응형)
- [ ] 오른쪽 패널: 대기 → review → result 순 전환
- [ ] 회의 맥락 입력 필드 동작
- [ ] 전체 테스트 통과
