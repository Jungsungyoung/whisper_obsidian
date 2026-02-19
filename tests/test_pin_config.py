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
    # SECRET_KEY가 없으면 랜덤 hex 토큰이 생성돼야 함 (예측 불가, 빈 문자열 아님)
    assert len(config.SECRET_KEY) == 64  # secrets.token_hex(32) → 64자 hex 문자열
    assert config.SECRET_KEY != "meetscribe-dev-secret"


def test_secret_key_from_env():
    os.environ["SECRET_KEY"] = "my-custom-secret"
    import config
    importlib.reload(config)
    assert config.SECRET_KEY == "my-custom-secret"
    os.environ.pop("SECRET_KEY")
