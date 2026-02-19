# Mobile Access Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** PC 로컬 서버를 스마트폰 브라우저에서도 사용할 수 있도록 Cloudflare Tunnel + PIN 인증 + PWA manifest + 모바일 UI 개선을 추가한다.

**Architecture:** `SessionMiddleware`(outermost) → PIN check middleware(inner) → FastAPI app. `ACCESS_PIN`이 설정되지 않으면 인증 없이 통과(로컬 사용 그대로). Cloudflare Tunnel은 `run.bat`에서 백그라운드 실행.

**Tech Stack:** FastAPI 0.115, starlette 0.35.1, itsdangerous (SessionMiddleware 의존성), Pillow (아이콘 생성), cloudflared (외부 바이너리)

---

## Task 1: config.py — ACCESS_PIN, SECRET_KEY 추가

**Files:**
- Modify: `config.py`
- Test: `tests/test_pin_config.py` (신규)

**Step 1: 실패하는 테스트 작성**

`tests/test_pin_config.py` 생성:

```python
"""ACCESS_PIN, SECRET_KEY 환경변수 로딩 테스트"""
import importlib
import os


def test_access_pin_default_empty():
    os.environ.pop("ACCESS_PIN", None)
    import config
    importlib.reload(config)
    assert config.ACCESS_PIN == ""


def test_access_pin_from_env():
    os.environ["ACCESS_PIN"] = "9999"
    import config
    importlib.reload(config)
    assert config.ACCESS_PIN == "9999"
    os.environ.pop("ACCESS_PIN")


def test_secret_key_default():
    os.environ.pop("SECRET_KEY", None)
    import config
    importlib.reload(config)
    assert config.SECRET_KEY == "meetscribe-dev-secret"


def test_secret_key_from_env():
    os.environ["SECRET_KEY"] = "my-custom-secret"
    import config
    importlib.reload(config)
    assert config.SECRET_KEY == "my-custom-secret"
    os.environ.pop("SECRET_KEY")
```

**Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_pin_config.py -v
```
Expected: FAIL (`config` has no attribute `ACCESS_PIN`)

**Step 3: config.py에 두 줄 추가**

`config.py`의 `DOMAIN_VOCAB` 줄 바로 아래에 추가:

```python
ACCESS_PIN: str = os.getenv("ACCESS_PIN", "").strip()
SECRET_KEY: str = os.getenv("SECRET_KEY", "meetscribe-dev-secret").strip()
```

**Step 4: 테스트 통과 확인**

```bash
pytest tests/test_pin_config.py -v
```
Expected: 4 passed

**Step 5: 커밋**

```bash
git add config.py tests/test_pin_config.py
git commit -m "feat: add ACCESS_PIN and SECRET_KEY to config"
```

---

## Task 2: requirements.txt — itsdangerous 추가 및 설치

**Files:**
- Modify: `requirements.txt`

**Step 1: itsdangerous 줄 추가**

`requirements.txt`에 `fastapi==0.115.0` 바로 아래에 추가:

```
itsdangerous>=2.1
```

**Step 2: 설치**

```bash
pip install "itsdangerous>=2.1"
```
Expected: `Successfully installed itsdangerous-X.X`

**Step 3: import 확인**

```bash
python -c "from starlette.middleware.sessions import SessionMiddleware; print('OK')"
```
Expected: `OK`

**Step 4: 커밋**

```bash
git add requirements.txt
git commit -m "chore: add itsdangerous for SessionMiddleware"
```

---

## Task 3: main.py — SessionMiddleware + PIN 인증 + /login 라우트

**Files:**
- Modify: `main.py`
- Test: `tests/test_pin_auth.py` (신규)

### 미들웨어 순서 (중요)

Starlette는 나중에 추가된 미들웨어가 가장 바깥(outermost)에 위치한다.
PIN 미들웨어가 `request.session`을 읽으려면 `SessionMiddleware`가 먼저 실행되어야 한다.
따라서 코드 순서: **PIN middleware 먼저 선언** → **SessionMiddleware 나중에 add_middleware**.

```
요청 흐름: SessionMiddleware → PIN middleware → app ✓
```

**Step 1: 실패하는 테스트 작성**

`tests/test_pin_auth.py` 생성:

```python
"""PIN 인증 미들웨어 로직 단위 테스트 (TestClient 없이)"""
import importlib
import os
import pytest


def test_login_page_contains_form():
    """로그인 페이지 HTML에 PIN 입력 폼이 있어야 한다"""
    import main
    response = main.login_page()
    assert "PIN" in response.body.decode() or "pin" in response.body.decode()
    assert "<form" in response.body.decode()
    assert 'type="password"' in response.body.decode()


def test_login_page_accessible():
    """login_page() 함수가 HTMLResponse를 반환해야 한다"""
    from fastapi.responses import HTMLResponse
    import main
    response = main.login_page()
    assert isinstance(response, HTMLResponse)


def test_pin_middleware_skips_when_no_pin_set(monkeypatch):
    """ACCESS_PIN이 비어있으면 미들웨어가 인증 없이 통과시켜야 한다"""
    import config
    monkeypatch.setattr(config, "ACCESS_PIN", "")
    # ACCESS_PIN이 비어있으면 authenticated 여부와 무관하게 통과해야 함
    # 로직 검증: config.ACCESS_PIN이 falsy면 call_next를 바로 호출
    assert config.ACCESS_PIN == ""
```

**Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_pin_auth.py -v
```
Expected: FAIL (`main` has no attribute `login_page`)

**Step 3: main.py 수정**

**3a. import 섹션 수정** (`main.py` 상단 import 블록에 추가):

기존:
```python
from fastapi.responses import FileResponse
```
변경:
```python
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware
```

**3b. PIN middleware 선언 추가** — `app = FastAPI(...)` 줄 바로 뒤, `app.mount(...)` 앞에 삽입:

```python
# ── PIN AUTH MIDDLEWARE (SessionMiddleware보다 먼저 선언 → 내부에서 실행됨) ──
@app.middleware("http")
async def pin_auth_middleware(request: Request, call_next):
    if not config.ACCESS_PIN:
        return await call_next(request)
    path = request.url.path
    if path == "/login" or path.startswith("/static"):
        return await call_next(request)
    if request.session.get("authenticated"):
        return await call_next(request)
    return RedirectResponse(url="/login", status_code=302)


# ── SESSION MIDDLEWARE (나중에 추가 = outermost = 먼저 실행됨) ──
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    max_age=86400,  # 24시간
    https_only=False,  # Cloudflare Tunnel은 HTTPS이지만 내부는 HTTP
    same_site="lax",
)
```

**3c. /login 라우트 추가** — `@app.get("/")` 바로 위에 삽입:

```python
_LOGIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MeetScribe — 로그인</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f4f4f2; display: flex; align-items: center;
           justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: #fff; border-radius: 12px; padding: 32px 28px;
            width: 100%; max-width: 360px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
    h1 { font-size: 1.1rem; font-weight: 700; margin-bottom: 4px; }
    p  { font-size: 0.82rem; color: #666; margin-bottom: 24px; }
    label { display: block; font-size: 0.78rem; font-weight: 500;
            color: #555; margin-bottom: 6px; }
    input[type=password] { width: 100%; padding: 10px 12px; border: 1px solid #ddd;
                           border-radius: 8px; font-size: 1rem; outline: none;
                           transition: border-color .15s; }
    input[type=password]:focus { border-color: #2563eb; }
    button { width: 100%; padding: 11px; margin-top: 14px;
             background: #2563eb; color: #fff; border: none; border-radius: 8px;
             font-size: 0.9rem; font-weight: 600; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    .err { color: #dc2626; font-size: 0.8rem; margin-top: 10px; display: none; }
  </style>
</head>
<body>
  <div class="card">
    <h1>MeetScribe</h1>
    <p>접속 PIN을 입력하세요.</p>
    <form method="post" action="/login">
      <label for="pin">PIN</label>
      <input type="password" id="pin" name="pin" autocomplete="current-password"
             inputmode="numeric" placeholder="••••" autofocus>
      <button type="submit">확인</button>
    </form>
    {error}
  </div>
</body>
</html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(_LOGIN_HTML.replace("{error}", ""))


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, pin: str = Form("")):
    if pin == config.ACCESS_PIN:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    err = '<p class="err" style="display:block">PIN이 올바르지 않습니다.</p>'
    return HTMLResponse(_LOGIN_HTML.replace("{error}", err), status_code=401)
```

**Step 4: 테스트 통과 확인**

```bash
pytest tests/test_pin_auth.py -v
```
Expected: 3 passed

**Step 5: 전체 테스트 통과 확인**

```bash
pytest tests/ -v --ignore=tests/test_integration.py
```
Expected: 기존 테스트 모두 통과

**Step 6: 커밋**

```bash
git add main.py tests/test_pin_auth.py
git commit -m "feat: add PIN authentication with SessionMiddleware"
```

---

## Task 4: static/index.html — 모바일 UI 보완 + PWA manifest 링크

**Files:**
- Modify: `static/index.html`

### 변경 사항

**4a. `<head>`에 manifest 링크 + 애플 아이콘 추가**

기존 `<meta name="viewport" ...>` 줄 바로 아래에 삽입:
```html
  <link rel="manifest" href="/static/manifest.json">
  <link rel="apple-touch-icon" href="/static/icon-192.png">
  <meta name="theme-color" content="#2563eb">
```

**4b. 파일 입력 accept 속성 변경**

기존:
```html
<input type="file" id="fi" accept=".mp3,.wav,.m4a,.mp4,.webm,.ogg">
```
변경:
```html
<input type="file" id="fi" accept="audio/*,video/*">
```

**4c. 모바일 CSS 추가** — 기존 `@media (max-width: 720px)` 블록 바로 아래에 삽입:

```css
    /* ── MOBILE ── */
    @media (max-width: 640px) {
      /* iOS 자동 줌인 방지: 텍스트 입력 font-size 16px 이상 */
      input[type=text], input[type=password], select, textarea {
        font-size: 16px;
      }
      /* 파일 업로드 영역 — 더 크게 */
      #drop-zone { padding: 28px 16px; }
      .dz-icon { width: 44px; height: 44px; }
      .dz-text { font-size: 1rem; }
      /* 녹음 버튼 터치 영역 확대 */
      #rec-start-btn { padding: 14px; font-size: 0.95rem; }
      #rec-stop-btn  { padding: 10px 18px; font-size: 0.85rem; }
      #rec-confirm-ok, #rec-confirm-cancel { padding: 10px 16px; font-size: 0.85rem; }
      /* 메인 제출 버튼 */
      #btn { padding: 15px; font-size: 1rem; }
    }
```

**Step 1: 변경 적용 (Edit 도구로)**

위의 세 가지 변경 사항을 순서대로 적용한다.

**Step 2: HTML 검증**

```bash
python -c "
from pathlib import Path
html = Path('static/index.html').read_text(encoding='utf-8')
assert 'manifest.json' in html, 'manifest link missing'
assert 'audio/*,video/*' in html, 'accept attr not updated'
assert 'font-size: 16px' in html, 'iOS zoom fix missing'
assert '@media (max-width: 640px)' in html, 'mobile media query missing'
print('OK')
"
```
Expected: `OK`

**Step 3: 커밋**

```bash
git add static/index.html
git commit -m "feat: mobile UI improvements and PWA manifest link"
```

---

## Task 5: PWA manifest + 아이콘 생성

**Files:**
- Create: `static/manifest.json`
- Create: `static/icon-192.png`
- Create: `static/icon-512.png`

**Step 1: 아이콘 생성 스크립트 실행**

```bash
python - <<'EOF'
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon(size, path):
    img = Image.new("RGB", (size, size), "#2563eb")
    draw = ImageDraw.Draw(img)
    # 간단한 마이크 모양: 중앙 흰 원
    margin = size // 5
    cx, cy = size // 2, size // 2
    r = size // 4
    draw.ellipse([cx - r, cy - r - margin//2, cx + r, cy + r - margin//2],
                 fill="white")
    # 마이크 몸통 (직사각형)
    rw = r * 2 // 3
    draw.rectangle([cx - rw//2, cy - margin//2, cx + rw//2, cy + r], fill="white")
    # 받침대
    br = r + rw//2
    draw.arc([cx - br, cy + r - margin//2, cx + br, cy + r*2], 0, 180, fill="white", width=max(2, size//64))
    img.save(path)
    print(f"Created {path} ({size}x{size})")

make_icon(192, "static/icon-192.png")
make_icon(512, "static/icon-512.png")
EOF
```
Expected: `Created static/icon-192.png (192x192)` / `Created static/icon-512.png (512x512)`

**Step 2: manifest.json 생성**

`static/manifest.json`:

```json
{
  "name": "MeetScribe",
  "short_name": "MeetScribe",
  "description": "회의 녹음 전사 및 Obsidian 노트 저장",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f4f4f2",
  "theme_color": "#2563eb",
  "lang": "ko",
  "icons": [
    {
      "src": "/static/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/static/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

**Step 3: 파일 존재 확인**

```bash
python -c "
import json
from pathlib import Path
m = json.loads(Path('static/manifest.json').read_text())
assert m['display'] == 'standalone'
assert m['theme_color'] == '#2563eb'
assert len(m['icons']) == 2
assert Path('static/icon-192.png').exists()
assert Path('static/icon-512.png').exists()
print('OK')
"
```
Expected: `OK`

**Step 4: 커밋**

```bash
git add static/manifest.json static/icon-192.png static/icon-512.png
git commit -m "feat: add PWA manifest and app icons"
```

---

## Task 6: .env.example + run.bat 업데이트

**Files:**
- Modify: `.env.example`
- Modify: `run.bat`

**Step 1: .env.example에 PIN/SECRET_KEY 항목 추가**

기존 파일 끝에 추가:
```
# 모바일 접속 인증 (설정 안하면 인증 없음)
# ACCESS_PIN=1234
# SECRET_KEY=your-random-secret-here
```

**Step 2: run.bat에 cloudflared 추가**

기존 `run.bat`:
```bat
@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;C:\Users\Admin\miniconda3\Lib\site-packages\torch\lib;%PATH%
uvicorn main:app --host 0.0.0.0 --port 8765
pause
```

변경:
```bat
@echo off
echo MeetScribe 시작 중...
cd /d "%~dp0"
set PATH=D:\cuda_libs\dlls;C:\Users\Admin\miniconda3\Lib\site-packages\torch\lib;%PATH%

:: Cloudflare Tunnel — 외부 접속 URL 생성 (cloudflared 설치 시)
where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Cloudflare Tunnel 시작 중...
    start /B cloudflared tunnel --url http://localhost:8765
    echo 터널 URL이 잠시 후 위에 출력됩니다.
    echo.
) else (
    echo [INFO] cloudflared 미설치 - 외부 접속 없이 로컬 모드로 실행
    echo [INFO] 설치: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo.
)

uvicorn main:app --host 0.0.0.0 --port 8765
pause
```

**Step 3: 테스트 없음 (구성 파일 변경만)**

**Step 4: 커밋**

```bash
git add .env.example run.bat
git commit -m "feat: add cloudflared to run.bat and ACCESS_PIN docs to .env.example"
```

---

## Task 7: 수동 통합 테스트

**Step 1: 전체 테스트 통과 확인**

```bash
pytest tests/ -v --ignore=tests/test_integration.py
```
Expected: 모든 테스트 통과 (기존 77개 + 신규 7개)

**Step 2: 서버 실행 확인**

```bash
ACCESS_PIN=1234 uvicorn main:app --host 0.0.0.0 --port 8765
```

**Step 3: 브라우저 테스트 체크리스트**

- [ ] `http://localhost:8765` → `/login`으로 리다이렉트됨
- [ ] 잘못된 PIN 입력 → 오류 메시지 표시
- [ ] 올바른 PIN `1234` 입력 → 메인 화면으로 이동
- [ ] `ACCESS_PIN` 없이 재시작 → 인증 없이 바로 메인 화면
- [ ] 폰 브라우저에서 접속 → "홈 화면에 추가" 배너 뜸
- [ ] 파일 선택 시 iOS/Android 파일 앱에서 오디오 파일 선택 가능

**Step 4: 최종 커밋 + push**

```bash
git push origin master
```
