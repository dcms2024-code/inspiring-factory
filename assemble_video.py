import argparse
import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

from core.config import default_channel_config_path, load_json


def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def run_ffmpeg(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def cta_filter(duration: float, cta_cfg: dict) -> str | None:
    if not cta_cfg.get("enabled"):
        return None
    lines = [l for l in cta_cfg.get("lines", [])]
    if not lines:
        return None

    show_last = float(cta_cfg.get("show_last_seconds", 6))
    fade_in = float(cta_cfg.get("fade_in_seconds", 1.5))
    font_size = int(cta_cfg.get("font_size", 28))
    font_color = cta_cfg.get("font_color", "white")
    box_color = cta_cfg.get("box_color", "black@0.6")
    box_border = int(cta_cfg.get("box_border", 12))
    start_t = max(0, duration - show_last)
    line_height = int(font_size * 1.5)

    filters = []
    total_lines = len(lines)
    center_y_start = f"(h/2)-({total_lines}*{line_height}/2)"

    for i, line in enumerate(lines):
        if not line:
            continue
        text_escaped = line.replace("'", "\\'").replace(":", "\\:")
        y_expr = f"({center_y_start})+({i}*{line_height})"
        alpha_expr = f"min(1\\,(t-{start_t:.2f})/{fade_in:.2f})"
        f = (
            f"drawtext=text='{text_escaped}'"
            f":fontsize={font_size}"
            f":fontcolor={font_color}@1"
            f":box=1:boxcolor={box_color}:boxborderw={box_border}"
            f":x=(w-text_w)/2:y={y_expr}"
            f":enable='gte(t\\,{start_t:.2f})'"
            f":alpha='{alpha_expr}'"
        )
        filters.append(f)

    return ",".join(filters)


def subtitle_filter(path: str, subtitles_cfg: dict) -> str:
    subs_escaped = path.replace("\\", "/").replace(":", "\\:")
    style = subtitles_cfg.get("force_style")
    if not style:
        font_name = subtitles_cfg.get("font_name", "DejaVu Sans")
        font_size = int(subtitles_cfg.get("font_size", 9))
        outline = int(subtitles_cfg.get("outline", 1))
        shadow = int(subtitles_cfg.get("shadow", 1))
        alignment = int(subtitles_cfg.get("alignment", 2))
        margin_v = int(subtitles_cfg.get("margin_v", 32))
        style = (
            f"FontName={font_name},FontSize={font_size},Outline={outline},"
            f"Shadow={shadow},Alignment={alignment},MarginV={margin_v}"
        )
    return f"subtitles={subs_escaped}:force_style='{style}'"


def build_concat_file_for_videos(video_paths: list[str], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for p in video_paths:
            # ffmpeg concat demuxer interprets paths relative to the list file location.
            # Keep entries simple (filenames or relative paths) to avoid platform quirks.
            f.write(f"file '{p}'\n")


def build_concat_file_for_images(images: list[str], per_scene: float, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for img in images:
            f.write(f"file '../{img}'\n")
            f.write(f"duration {per_scene:.2f}\n")
        f.write(f"file '../{images[-1]}'\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    args = parser.parse_args()

    channel = load_json(args.channel)
    video_cfg = channel.get("video", {})
    subtitles_cfg = channel.get("subtitles", {})
    cta_cfg = channel.get("cta", {})
    use_wan = bool(video_cfg.get("use_wan_i2v", False))

    with open("stories/story.json", "r", encoding="utf-8") as f:
        _story = json.load(f)

    audio_path = "audio/narration.mp3"
    subs_src = "audio/subtitles.srt"
    os.makedirs("output", exist_ok=True)
    os.makedirs("video", exist_ok=True)

    duration = get_audio_duration(audio_path)

    tmp_video = "output/tmp_notsubs.mp4"

    if use_wan:
        clips = sorted(glob.glob("video/clips/*.mp4"))
        if not clips:
            raise FileNotFoundError("No WAN clips found in video/clips/. Disable use_wan_i2v or generate clips first.")

        concat_list = "video/clips/concat.txt"
        build_concat_file_for_videos([Path(p).name for p in clips], concat_list)

        vf_parts = ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920"]
        output_fps = video_cfg.get("output_fps")
        if output_fps:
            vf_parts.append(f"fps={int(output_fps)}")

        cmd1 = [
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-i",
            audio_path,
            "-vf",
            ",".join(vf_parts),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-t",
            str(duration),
            tmp_video,
        ]
        print(f"Rendering from clips: {len(clips)} clips, audio {duration:.1f}s")
        run_ffmpeg(cmd1)
    else:
        images = sorted([f for f in os.listdir("images/generated") if f.endswith(".png")])
        if not images:
            raise FileNotFoundError("No images found in images/generated/. Generate images first.")

        per_scene = duration / len(images)
        motion = str(video_cfg.get("slideshow_motion", "none")).lower()

        if motion == "kenburns":
            fps = int(video_cfg.get("fps", 24))
            os.makedirs("video/slides", exist_ok=True)
            slide_paths: list[str] = []

            for img in images:
                scene_num = int(img.replace("scene_", "").replace(".png", ""))
                slide_path = f"video/slides/slide_{scene_num:02d}.mp4"
                slide_paths.append(slide_path)

                if os.path.exists(slide_path):
                    continue

                frames = max(1, int(round(per_scene * fps)))
                zoom_delta = 0.10  # total zoom amount over the clip (1.0 -> 1.10)
                z_expr = f"1+on/{frames}*{zoom_delta}"
                vf = (
                    "scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,"
                    f"zoompan=z='{z_expr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps={fps}:s=1080x1920"
                )

                cmd_slide = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    f"images/generated/{img}",
                    "-vf",
                    vf,
                    "-t",
                    f"{per_scene:.2f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    slide_path,
                ]
                run_ffmpeg(cmd_slide)

            concat_list = "video/slides/concat.txt"
            build_concat_file_for_videos([Path(p).name for p in slide_paths], concat_list)

            cmd1 = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-i",
                audio_path,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                tmp_video,
            ]
            print(f"Rendering Ken Burns slideshow: {len(images)} scenes, audio {duration:.1f}s ({per_scene:.1f}s/scene)")
            run_ffmpeg(cmd1)
        else:
            list_file = "video/images.txt"
            build_concat_file_for_images([f"images/generated/{img}" for img in images], per_scene, list_file)

            cmd1 = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-i",
                audio_path,
                "-vf",
                "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                tmp_video,
            ]
            print(f"Rendering slideshow: {len(images)} images, audio {duration:.1f}s ({per_scene:.1f}s/scene)")
            run_ffmpeg(cmd1)

    # Burn subtitles (copy to a temp with safe permissions)
    final_path = "output/final_short.mp4"
    subs_tmp = os.path.join("output", "subs_tmp.srt")
    shutil.copy(subs_src, subs_tmp)

    vf_parts = [subtitle_filter(subs_tmp, subtitles_cfg)]
    cta = cta_filter(duration, cta_cfg)
    if cta:
        vf_parts.append(cta)
    vf = ",".join(vf_parts)
    fade_start = max(0, duration - 2.0)
    cmd2 = [
        "ffmpeg",
        "-y",
        "-i",
        tmp_video,
        "-vf",
        vf,
        "-af",
        f"afade=t=out:st={fade_start:.2f}:d=2.0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        final_path,
    ]

    try:
        print("Burning subtitles...")
        run_ffmpeg(cmd2)
    except subprocess.CalledProcessError:
        print("Subtitle burn failed; saving without subtitles.")
        shutil.copy(tmp_video, final_path)

    for p in [tmp_video, subs_tmp]:
        if os.path.exists(p):
            os.remove(p)

    size_kb = os.path.getsize(final_path) // 1024
    print(f"OK: {final_path} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
