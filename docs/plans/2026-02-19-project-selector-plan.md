# Project Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Vault의 `20_Projects/` 폴더를 스캔해 활성 프로젝트를 드롭다운으로 선택할 수 있게 한다.

**Architecture:** 백엔드에 `GET /projects` 엔드포인트 추가 → frontmatter `status: 진행`인 Dashboard 파일만 수집 → 프론트엔드에서 `<select>` 드롭다운으로 표시.

**Tech Stack:** FastAPI, Python pathlib, PyYAML (frontmatter 파싱), vanilla JS fetch

---

### Task 1: 백엔드 — GET /projects 엔드포인트

**Files:**
- Modify: `main.py` (엔드포인트 추가)
- Test: `tests/test_projects_api.py` (신규)

**Step 1: 실패 테스트 작성**

`tests/test_projects_api.py` 파일 생성:

```python
import pytest
from pathlib import Path
import tempfile, textwrap

def _make_vault(tmp_path: Path) -> Path:
    """테스트용 가짜 Vault 구조 생성."""
    projects = tmp_path / "20_Projects"

    # 활성 프로젝트
    (projects / "22_USV_ECS_개발").mkdir(parents=True)
    (projects / "22_USV_ECS_개발" / "USV Project Dashboard.md").write_text(
        textwrap.dedent("""\
            ---
            status: 진행
            ---
            # USV ECS 개발
        """), encoding="utf-8"
    )

    # 완료 프로젝트 (포함 안 돼야 함)
    (projects / "10_완료_프로젝트").mkdir(parents=True)
    (projects / "10_완료_프로젝트" / "Done Project Dashboard.md").write_text(
        textwrap.dedent("""\
            ---
            status: 완료
            ---
            # 완료된 프로젝트
        """), encoding="utf-8"
    )

    return tmp_path


def test_get_projects_returns_active_only(tmp_path):
    from main import _scan_projects
    vault = _make_vault(tmp_path)
    result = _scan_projects(vault)
    assert len(result) == 1
    assert result[0]["display"] == "USV ECS 개발"
    assert result[0]["link"] == "[[USV Project Dashboard]]"


def test_get_projects_empty_when_no_projects_folder(tmp_path):
    from main import _scan_projects
    result = _scan_projects(tmp_path)  # 20_Projects 폴더 없음
    assert result == []


def test_get_projects_empty_on_error(tmp_path):
    from main import _scan_projects
    # 존재하지 않는 경로
    result = _scan_projects(Path("/nonexistent/path"))
    assert result == []
```

**Step 2: 테스트 실패 확인**

```bash
cd D:\01_DevProjects\VibeCoding_Projects\06_Whisper_Obsidian\meetscribe
pytest tests/test_projects_api.py -v
```
Expected: FAIL — `ImportError: cannot import name '_scan_projects' from 'main'`

**Step 3: main.py에 _scan_projects 함수 + 엔드포인트 추가**

`main.py`의 `_write_env` 함수 바로 아래에 추가:

```python
def _scan_projects(vault_path: Path) -> list[dict]:
    """Vault의 20_Projects/ 폴더에서 status: 진행 Dashboard 파일 수집."""
    import yaml
    projects_dir = vault_path / "20_Projects"
    if not projects_dir.exists():
        return []
    result = []
    try:
        for folder in sorted(projects_dir.iterdir()):
            if not folder.is_dir():
                continue
            for md_file in folder.glob("*Dashboard*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                    # frontmatter 파싱 (--- ... --- 사이)
                    if text.startswith("---"):
                        end = text.index("---", 3)
                        fm = yaml.safe_load(text[3:end])
                        if isinstance(fm, dict) and fm.get("status") == "진행":
                            # 폴더명에서 숫자 접두사 제거: "22_USV_ECS_개발" → "USV ECS 개발"
                            raw = folder.name
                            display = "_".join(raw.split("_")[1:]).replace("_", " ")
                            link = f"[[{md_file.stem}]]"
                            result.append({"display": display, "link": link})
                except Exception:
                    continue
    except Exception:
        return []
    return result


@app.get("/projects")
def get_projects():
    return _scan_projects(config.VAULT_PATH)
```

**주의**: `yaml` 모듈은 `PyYAML` 패키지. 설치 확인:
```bash
pip show pyyaml
```
없으면: `pip install pyyaml`

**Step 4: 테스트 통과 확인**

```bash
pytest tests/test_projects_api.py -v
```
Expected: 3개 모두 PASS

**Step 5: 전체 테스트 확인**

```bash
pytest tests/ -v
```
Expected: 전체 PASS

---

### Task 2: 프론트엔드 — 드롭다운으로 교체

**Files:**
- Modify: `static/index.html`

**Step 1: 프로젝트 필드 교체**

`static/index.html`에서 현재 프로젝트 입력 필드:

```html
  <div class="field">
    <label for="project">프로젝트 (선택)</label>
    <input type="text" id="project" placeholder="예: [[USV Project Dashboard]]">
  </div>
```

→ 아래로 교체:

```html
  <div class="field">
    <label for="project">프로젝트 (선택)</label>
    <select id="project">
      <option value="">선택 안 함</option>
    </select>
  </div>
```

**Step 2: JS에 프로젝트 로드 함수 추가**

`</script>` 태그 바로 위에 추가:

```js
  // ── 프로젝트 목록 로드 ──────────────────────────────────
  async function loadProjects() {
    try {
      const projects = await fetch('/projects').then(r => r.json());
      const sel = document.getElementById('project');
      projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.link;
        opt.textContent = p.display;
        sel.appendChild(opt);
      });
    } catch (e) {
      console.warn('프로젝트 목록 로드 실패:', e);
    }
  }
  loadProjects();
```

**Step 3: 업로드 시 select value 전송 확인**

`btn.addEventListener('click', ...)` 내부 FormData 부분은 이미 `document.getElementById('project').value`를 사용하고 있으므로 변경 불필요. `<select>`의 `.value`도 동일하게 동작함.

**Step 4: 브라우저에서 직접 확인**

서버 실행 후 `http://localhost:8765` 접속:
1. 프로젝트 필드가 드롭다운으로 표시되는지 확인
2. 활성 프로젝트 목록이 보이는지 확인
3. 선택 시 `[[WikiLink]]` 형식 값이 설정되는지 확인 (DevTools → 업로드 요청 payload)

---

## 완료 기준

- [ ] `GET /projects` → Vault 활성 프로젝트 반환
- [ ] `status: 진행` 아닌 프로젝트 제외
- [ ] 프론트엔드 드롭다운에 프로젝트 목록 표시
- [ ] 선택 시 `[[Dashboard명]]` 형식으로 업로드 요청에 포함
- [ ] `20_Projects` 폴더 없거나 오류 시 빈 목록 반환 (서버 오류 없음)
- [ ] 전체 테스트 통과
