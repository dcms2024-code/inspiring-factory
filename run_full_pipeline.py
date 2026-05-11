import argparse
import os
import subprocess
import sys

from core.config import default_channel_config_path, load_json


def run_step(label: str, cmd: list[str]) -> None:
    print("\n" + "=" * 60)
    print(label)
    print("=" * 60)
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    parser.add_argument("--figure", default=None)
    parser.add_argument("--figures", default=None, help="Path to figures JSON list (optional)")
    args = parser.parse_args()

    channel = load_json(args.channel)
    use_wan = bool(channel.get("video", {}).get("use_wan_i2v", False))

    python = sys.executable
    base_env = os.environ.copy()
    base_env["CHANNEL_CONFIG"] = os.path.abspath(args.channel)

    story_cmd = [python, "generate_and_save_story.py"]
    if args.figure:
        story_cmd += ["--figure", args.figure]
    story_cmd += ["--channel", args.channel]
    if args.figures:
        story_cmd += ["--figures", args.figures]

    run_step("1) Generate story JSON", story_cmd)
    run_step("2) Generate images (ComfyUI)", [python, "auto_generate_images.py", "--channel", args.channel])
    run_step("3) Generate voice + subtitles", [python, "generate_voice.py", "--channel", args.channel])

    if use_wan:
        run_step("4) Generate WAN image-to-video clips", [python, "generate_video_wan.py", "--channel", args.channel])
        run_step("5) Assemble final video (clips + audio + subs)", [python, "assemble_video.py", "--channel", args.channel])
    else:
        run_step("4) Assemble final video (slideshow + audio + subs)", [python, "assemble_video.py", "--channel", args.channel])

    print("\nOK: output/final_short.mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
