import textwrap
from pathlib import Path


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
        """),
        encoding="utf-8",
    )

    # 완료 프로젝트 (포함 안 돼야 함)
    (projects / "10_완료_프로젝트").mkdir(parents=True)
    (projects / "10_완료_프로젝트" / "Done Project Dashboard.md").write_text(
        textwrap.dedent("""\
            ---
            status: 완료
            ---
            # 완료된 프로젝트
        """),
        encoding="utf-8",
    )

    return tmp_path


def test_returns_active_projects_only(tmp_path):
    from main import _scan_projects

    vault = _make_vault(tmp_path)
    result = _scan_projects(vault)

    assert len(result) == 1
    assert result[0]["display"] == "USV ECS 개발"
    assert result[0]["link"] == "[[USV Project Dashboard]]"


def test_returns_empty_when_no_projects_folder(tmp_path):
    from main import _scan_projects

    result = _scan_projects(tmp_path)  # 20_Projects 폴더 없음
    assert result == []


def test_returns_empty_on_nonexistent_vault():
    from main import _scan_projects

    result = _scan_projects(Path("/nonexistent/vault/path"))
    assert result == []


def test_multiple_active_projects(tmp_path):
    from main import _scan_projects

    projects = tmp_path / "20_Projects"
    for folder, name in [
        ("21_Peru_PCS", "PERU Project Dashboard"),
        ("22_USV_ECS_개발", "USV Project Dashboard"),
    ]:
        (projects / folder).mkdir(parents=True)
        (projects / folder / f"{name}.md").write_text(
            "---\nstatus: 진행\n---\n", encoding="utf-8"
        )

    result = _scan_projects(tmp_path)
    assert len(result) == 2
    links = [r["link"] for r in result]
    assert "[[PERU Project Dashboard]]" in links
    assert "[[USV Project Dashboard]]" in links
