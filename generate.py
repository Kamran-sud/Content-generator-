"""Генерация короткого вертикального видео (Shorts/Reels) из script.txt.

1. Озвучка текста через edge-tts (ru-RU-DmitryNeural) -> voice.mp3
2. Кадр 1080x1920: тёмный фон + текст сценария по центру с автопереносом строк
3. Статичный кадр длительностью равной аудио + аудиодорожка
4. Результат -> final_video.mp4
"""

import asyncio
import os
import sys

import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:  # moviepy >= 2.0
    from moviepy import AudioFileClip, ImageClip

    MOVIEPY_V2 = True
except ImportError:  # moviepy 1.x
    from moviepy.editor import AudioFileClip, ImageClip

    MOVIEPY_V2 = False

SCRIPT_FILE = "script.txt"
AUDIO_FILE = "voice.mp3"
OUTPUT_FILE = "final_video.mp4"
VOICE = "ru-RU-DmitryNeural"

WIDTH, HEIGHT = 1080, 1920
BG_COLOR = (18, 18, 24)
TEXT_COLOR = (255, 255, 255)
MARGIN_X = 90
MAX_TEXT_HEIGHT = HEIGHT - 400
START_FONT_SIZE = 90
MIN_FONT_SIZE = 40
LINE_SPACING = 1.25
FPS = 30

FONT_CANDIDATES = [
    os.environ.get("FONT_PATH", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def read_script(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        text = " ".join(f.read().split())
    if not text:
        sys.exit(f"Файл {path} пуст")
    return text


async def synthesize(text: str, path: str) -> None:
    await edge_tts.Communicate(text, VOICE).save(path)


def find_font_path() -> str | None:
    for candidate in FONT_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def load_font(size: int) -> ImageFont.FreeTypeFont:
    path = find_font_path()
    if path is None:
        print("Внимание: TTF-шрифт с кириллицей не найден, используется шрифт по умолчанию")
        return ImageFont.load_default(size=size)
    return ImageFont.truetype(path, size)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_frame(text: str) -> np.ndarray:
    """Рисует кадр: тёмный фон + текст по центру, размер шрифта подбирается под экран."""
    max_width = WIDTH - 2 * MARGIN_X
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    size = START_FONT_SIZE
    while True:
        font = load_font(size)
        lines = wrap_text(text, font, max_width, probe)
        line_height = int(size * LINE_SPACING)
        total_height = line_height * len(lines)
        widest = max(probe.textlength(line, font=font) for line in lines)
        if (total_height <= MAX_TEXT_HEIGHT and widest <= max_width) or size <= MIN_FONT_SIZE:
            break
        size -= 4

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    y = (HEIGHT - total_height) // 2
    for line in lines:
        draw.text(
            (WIDTH // 2, y + line_height // 2),
            line,
            font=font,
            fill=TEXT_COLOR,
            anchor="mm",
            stroke_width=max(2, size // 25),
            stroke_fill=(0, 0, 0),
        )
        y += line_height
    return np.array(img)


def build_video(text: str) -> None:
    audio = AudioFileClip(AUDIO_FILE)
    duration = audio.duration

    frame = ImageClip(render_frame(text))

    if MOVIEPY_V2:
        video = frame.with_duration(duration).with_audio(audio)
    else:
        video = frame.set_duration(duration).set_audio(audio)

    video.write_videofile(
        OUTPUT_FILE,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )
    audio.close()
    video.close()


def main() -> None:
    text = read_script(SCRIPT_FILE)
    print(f"Сценарий: {text}")
    print(f"Озвучка голосом {VOICE} -> {AUDIO_FILE}")
    asyncio.run(synthesize(text, AUDIO_FILE))
    print(f"Сборка видео -> {OUTPUT_FILE}")
    build_video(text)
    print("Готово!")


if __name__ == "__main__":
    main()
