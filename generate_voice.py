import argparse
import asyncio
import json
import os
import shutil
import subprocess

import edge_tts

from core.config import default_channel_config_path, load_json


def build_narration(story: dict) -> str:
    figure_name = (story.get("figure") or {}).get("name")
    parts: list[str] = []
    if figure_name:
        parts.append(figure_name)
    if story.get("hook"):
        parts.append(story["hook"])
    for scene in story.get("scenes", []):
        parts.append(scene.get("description", ""))
    if story.get("ending"):
        parts.append(story["ending"])

    return " ... ".join([p.strip() for p in parts if p and p.strip()])


def apply_audio_filter(src_path: str, out_path: str, audio_filter: str) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for voice.postprocess_filter")

    tmp_path = out_path + ".tmp.mp3"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src_path,
            "-af",
            audio_filter,
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            tmp_path,
        ],
        check=True,
    )
    os.replace(tmp_path, out_path)


async def generate_voice(voice_cfg: dict) -> None:
    with open("stories/story.json", "r", encoding="utf-8") as f:
        story = json.load(f)

    narration = build_narration(story)
    os.makedirs("audio", exist_ok=True)

    voice_name = voice_cfg.get("name", "en-GB-RyanNeural")
    communicate = edge_tts.Communicate(
        narration,
        voice_name,
        rate=voice_cfg.get("rate", "+0%"),
        volume=voice_cfg.get("volume", "+0%"),
        pitch=voice_cfg.get("pitch", "+0Hz"),
    )
    submaker = edge_tts.SubMaker()

    raw_audio_path = "audio/narration_raw.mp3"
    final_audio_path = voice_cfg.get("output_path", "audio/narration.mp3")
    os.makedirs(os.path.dirname(final_audio_path) or ".", exist_ok=True)

    with open(raw_audio_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                submaker.feed(chunk)

    with open("audio/subtitles.srt", "w", encoding="utf-8") as srt_file:
        srt_file.write(submaker.get_srt())

    post_filter = voice_cfg.get("postprocess_filter")
    if post_filter:
        apply_audio_filter(raw_audio_path, final_audio_path, post_filter)
    else:
        os.replace(raw_audio_path, final_audio_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    args = parser.parse_args()

    channel = load_json(args.channel)
    voice_cfg = channel.get("voice", {})

    asyncio.run(generate_voice(voice_cfg))
    print("OK: audio/narration.mp3 + audio/subtitles.srt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
