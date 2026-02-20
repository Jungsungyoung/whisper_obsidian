"""MD 파일 처리 관련 단위 테스트 (TestClient 미사용, 함수 직접 호출)."""
import pytest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import read_md_text


def _write_temp_md(content: str, encoding: str = "utf-8") -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".md", mode="wb", delete=False)
    f.write(content.encode(encoding))
    f.close()
    return Path(f.name)


def test_read_md_text_utf8():
    path = _write_temp_md("# 제목\n\n한글 내용")
    result = read_md_text(path)
    assert "# 제목" in result
    assert "한글 내용" in result
    path.unlink()


def test_read_md_text_utf8_sig():
    """UTF-8 BOM 파일 처리."""
    path = _write_temp_md("# BOM 파일\n내용", "utf-8-sig")
    result = read_md_text(path)
    assert "# BOM 파일" in result
    path.unlink()


def test_read_md_text_empty_raises():
    path = _write_temp_md("   \n\n  ")
    with pytest.raises(ValueError, match="비어있습니다"):
        read_md_text(path)
    path.unlink()


def test_read_md_text_returns_str():
    path = _write_temp_md("내용 있음")
    result = read_md_text(path)
    assert isinstance(result, str)
    path.unlink()
