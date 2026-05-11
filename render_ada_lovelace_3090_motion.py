import argparse
import asyncio
import json
import shutil
import time
import urllib.error
import uuid
from pathlib import Path

from render_ada_lovelace_3090_preview import (
    NEGATIVE_PROMPT,
    STORY,
    audio_duration,
    download_asset,
    generate_images,
    generate_voice,
    get_history,
    queue_prompt,
    run,
)


MOTION_SUFFIX = (
    "subtle realistic animation, gentle camera motion, natural breathing, blinking eyes, "
    "soft moving candlelight, cloth and hair moving slightly, cinematic historical mood, "
    "stable identity, preserve face, preserve clothing, no text"
)


def copy_scene_to_comfy_input(base_dir: Path, input_dir: Path, scene_id: int) -> str:
    src = base_dir / "images" / "generated" / f"scene_{scene_id:02d}.png"
    if not src.exists():
        raise FileNotFoundError(src)

    input_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ada_motion_scene_{scene_id:02d}.png"
    shutil.copy(src, input_dir / filename)
    return filename


def build_wan_i2v_workflow(
    scene_id: int,
    image_filename: str,
    positive_prompt: str,
    width: int,
    height: int,
    frames: int,
    fps: int,
    steps: int,
    cfg: float,
    seed: int,
) -> dict:
    positive = f"{positive_prompt}, {MOTION_SUFFIX}"
    negative = (
        f"{NEGATIVE_PROMPT}, static image, frozen frame, violent motion, morphing face, "
        "extra person, duplicate head, warped eyes, unreadable subtitles, watermark"
    )

    return {
        "1": {
            "class_type": "WanVideoBlockSwap",
            "inputs": {
                "blocks_to_swap": 14,
                "offload_img_emb": False,
                "offload_txt_emb": False,
                "use_non_blocking": True,
                "vace_blocks_to_swap": 0,
                "prefetch_blocks": 0,
                "block_swap_debug": False,
            },
        },
        "2": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": "Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors",
                "base_precision": "fp16",
                "quantization": "fp8_e4m3fn_scaled",
                "load_device": "offload_device",
                "attention_mode": "sdpa",
                "block_swap_args": ["1", 0],
            },
        },
        "3": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {
                "model_name": "umt5-xxl-enc-bf16.safetensors",
                "precision": "bf16",
                "load_device": "offload_device",
                "quantization": "disabled",
            },
        },
        "4": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": positive,
                "negative_prompt": negative,
                "t5": ["3", 0],
                "force_offload": True,
                "model_to_offload": ["2", 0],
                "use_disk_cache": False,
                "device": "gpu",
            },
        },
        "5": {
            "class_type": "WanVideoVAELoader",
            "inputs": {
                "model_name": "Wan2_1_VAE_bf16.safetensors",
                "precision": "bf16",
                "use_cpu_cache": False,
                "verbose": False,
            },
        },
        "7": {"class_type": "LoadImage", "inputs": {"image": image_filename}},
        "8": {
            "class_type": "ImageResizeKJv2",
            "inputs": {
                "image": ["7", 0],
                "width": width,
                "height": height,
                "upscale_method": "lanczos",
                "keep_proportion": "crop",
                "pad_color": "0, 0, 0",
                "crop_position": "center",
                "divisible_by": 16,
                "device": "cpu",
            },
        },
        "10": {
            "class_type": "WanVideoImageToVideoEncode",
            "inputs": {
                "width": width,
                "height": height,
                "num_frames": frames,
                "noise_aug_strength": 0.04,
                "start_latent_strength": 0.92,
                "end_latent_strength": 1.0,
                "force_offload": True,
                "vae": ["5", 0],
                "start_image": ["8", 0],
                "fun_or_fl2v_model": False,
                "tiled_vae": False,
                "augment_empty_frames": 0.0,
            },
        },
        "11": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["2", 0],
                "image_embeds": ["10", 0],
                "steps": steps,
                "cfg": cfg,
                "shift": 5.0,
                "seed": seed + scene_id * 10007,
                "force_offload": True,
                "scheduler": "dpm++_sde",
                "riflex_freq_index": 0,
                "text_embeds": ["4", 0],
                "batched_cfg": False,
                "rope_function": "comfy",
                "start_step": 0,
                "end_step": -1,
                "add_noise_to_samples": False,
            },
        },
        "12": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae": ["5", 0],
                "samples": ["11", 0],
                "enable_vae_tiling": True,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
                "normalization": "default",
            },
        },
        "13": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["12", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": f"ada_wan_scene_{scene_id:02d}",
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True,
            },
        },
    }


def get_first_video_asset(history: dict, prompt_id: str) -> dict:
    outputs = history[prompt_id]["outputs"]
    for output in outputs.values():
        for key in ("videos", "gifs"):
            assets = output.get(key, [])
            if assets:
                return assets[0]
    raise RuntimeError(f"No video output found for prompt {prompt_id}")


def generate_wan_clips(args: argparse.Namespace, base_dir: Path, scene_ids: list[int]) -> list[Path]:
    clips_dir = base_dir / "video" / "wan"
    clips_dir.mkdir(parents=True, exist_ok=True)
    input_dir = Path(args.comfy_input_dir)
    client_id = str(uuid.uuid4())
    clips: list[Path] = []

    scenes_by_id = {int(scene["id"]): scene for scene in STORY["scenes"]}
    for scene_id in scene_ids:
        out_path = clips_dir / f"clip_{scene_id:02d}.mp4"
        clips.append(out_path)
        if out_path.exists() and not args.force_clips:
            print(f"WAN scene {scene_id:02d}: exists")
            continue

        image_filename = copy_scene_to_comfy_input(base_dir, input_dir, scene_id)
        scene = scenes_by_id[scene_id]
        workflow = build_wan_i2v_workflow(
            scene_id=scene_id,
            image_filename=image_filename,
            positive_prompt=scene["prompt"],
            width=args.wan_width,
            height=args.wan_height,
            frames=args.frames,
            fps=args.fps,
            steps=args.wan_steps,
            cfg=args.wan_cfg,
            seed=args.seed,
        )

        try:
            queued = queue_prompt(args.comfy_url, workflow, client_id)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ComfyUI rejected WAN workflow for scene {scene_id}: {detail}") from exc

        prompt_id = queued["prompt_id"]
        print(f"WAN scene {scene_id:02d}: queued {prompt_id}")
        while True:
            history = get_history(args.comfy_url, prompt_id)
            if prompt_id in history:
                break
            time.sleep(5)

        asset = get_first_video_asset(history, prompt_id)
        download_asset(args.comfy_url, asset, out_path)
        print(f"WAN scene {scene_id:02d}: saved {out_path}")

    return clips


def concat_file(clips: list[Path], concat_path: Path) -> None:
    with concat_path.open("w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{clip.name}'\n")


def render_final(base_dir: Path, clips: list[Path], audio_path: Path) -> Path:
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    concat_path = clips[0].parent / "concat_wan.txt"
    concat_file(clips, concat_path)

    raw = output_dir / "ada_lovelace_3090_motion_raw.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(raw),
        ]
    )

    video_duration = audio_duration(raw)
    narration_duration = audio_duration(audio_path)
    stretch = max(1.0, narration_duration / video_duration)
    no_subs = output_dir / "ada_lovelace_3090_motion_no_subs.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(raw),
            "-i",
            str(audio_path),
            "-filter_complex",
            f"[0:v]setpts={stretch:.6f}*PTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(no_subs),
        ]
    )

    final = output_dir / "ada_lovelace_3090_motion.mp4"
    subs_tmp = output_dir / "subtitles_motion.srt"
    shutil.copy(base_dir / "audio" / "subtitles.srt", subs_tmp)
    subs_path = str(subs_tmp).replace(":", "\\:")
    subtitle_filter = (
        f"subtitles={subs_path}:"
        "force_style='FontName=DejaVu Sans,FontSize=8,Outline=1,Shadow=1,Alignment=2,MarginV=28'"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(no_subs),
            "-vf",
            subtitle_filter,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            str(final),
        ]
    )
    print(f"Final motion video: {final}")
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="/home/andreu/ai-projects/ada-lovelace-3090-preview")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--comfy-input-dir", default="/home/andreu/ai-tools/ComfyUI/input")
    parser.add_argument("--checkpoint", default="juggernaut.safetensors")
    parser.add_argument("--voice", default="es-ES-AlvaroNeural")
    parser.add_argument("--image-width", type=int, default=768)
    parser.add_argument("--image-height", type=int, default=1344)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--cfg", type=float, default=6.5)
    parser.add_argument("--wan-width", type=int, default=480)
    parser.add_argument("--wan-height", type=int, default=832)
    parser.add_argument("--frames", type=int, default=81)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--wan-steps", type=int, default=12)
    parser.add_argument("--wan-cfg", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=260511)
    parser.add_argument("--max-scenes", type=int, default=6)
    parser.add_argument("--force-images", action="store_true")
    parser.add_argument("--force-clips", action="store_true")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--skip-voice", action="store_true")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    (base_dir / "stories").mkdir(parents=True, exist_ok=True)
    (base_dir / "stories" / "story.json").write_text(json.dumps(STORY, indent=2, ensure_ascii=False), encoding="utf-8")

    scene_ids = [int(scene["id"]) for scene in STORY["scenes"][: args.max_scenes]]

    if not args.skip_images:
        args.force = args.force_images
        generate_images(args, base_dir / "images" / "generated")

    audio_path = base_dir / "audio" / "narration_dark.wav"
    if not args.skip_voice or not audio_path.exists():
        audio_path = asyncio.run(generate_voice(base_dir, args.voice))

    clips = generate_wan_clips(args, base_dir, scene_ids)
    final = render_final(base_dir, clips, audio_path)
    print(str(final))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
