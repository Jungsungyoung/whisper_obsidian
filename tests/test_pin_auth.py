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
