"""
Creates a quick "mock" vertical video (no ComfyUI required) by rendering the
scene descriptions as simple cards. Useful to validate ffmpeg installation.
"""

import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1920
SCENE_DURATION = 5
FPS = 30


def load_font(size: int, bold: bool = False):
    candidates = []
    if os.name == "nt":
        candidates += [
            r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def wrap_text(text: str, max_chars: int = 34) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        tentative = (current + " " + word).strip()
        if len(tentative) <= max_chars:
            current = tentative
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def main() -> int:
    os.makedirs("video/mock_frames", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    with open("stories/story.json", "r", encoding="utf-8") as f:
        story = json.load(f)

    scenes = story.get("scenes", [])
    title = story.get("title", "Inspirational Short")

    font_title = load_font(54, bold=True)
    font_text = load_font(38, bold=False)

    for i, scene in enumerate(scenes, start=1):
        img = Image.new("RGB", (WIDTH, HEIGHT), (15, 15, 20))
        draw = ImageDraw.Draw(img)

        desc = scene.get("description", "")
        draw.text((80, 160), title, font=font_title, fill=(240, 240, 240))

        y = 520
        for line in wrap_text(desc):
            draw.text((80, y), line, font=font_text, fill=(220, 220, 220))
            y += 58

        draw.text((80, 1680), f"Scene {i}", font=font_text, fill=(160, 160, 160))

        frame_path = f"video/mock_frames/scene_{i:02d}.png"
        img.save(frame_path)

    list_path = "video/mock_frames/frames.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for i in range(1, len(scenes) + 1):
            f.write(f"file 'scene_{i:02d}.png'\n")
            f.write(f"duration {SCENE_DURATION}\n")
        f.write(f"file 'scene_{len(scenes):02d}.png'\n")

    output_path = "output/short_mock.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        list_path,
        "-vf",
        f"fps={FPS},format=yuv420p",
        output_path,
    ]

    subprocess.run(cmd, check=True)
    print(f"OK: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
