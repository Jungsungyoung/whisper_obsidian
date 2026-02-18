"""테스트용 짧은 한국어 오디오 파일 생성 (gTTS 사용)"""
from pathlib import Path


def generate():
    try:
        from gtts import gTTS
    except ImportError:
        print("pip install gtts 실행 후 다시 시도")
        return None

    text = (
        "안녕하세요. 오늘 회의를 시작하겠습니다. "
        "첫 번째 안건은 프로젝트 진행 상황입니다. "
        "네, 잘 진행되고 있습니다. "
        "다음 주까지 배포를 완료할 예정입니다."
    )
    out = Path(__file__).parent / "sample.mp3"
    gTTS(text=text, lang="ko").save(str(out))
    print(f"생성됨: {out}")
    return out


if __name__ == "__main__":
    generate()
