"""
Image-to-video via ComfyUI WanVideoWrapper API.

Takes each image from images/generated/ and generates an animated clip into video/clips/.
Requires ComfyUI running (default http://127.0.0.1:8188).

This is optional; enable it by setting config.video.use_wan_i2v=true in the channel config.
"""

import argparse
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
import uuid

import websocket

from core.config import default_channel_config_path, load_json


def queue_prompt(comfy_url: str, workflow: dict, client_id: str) -> dict:
    data = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{comfy_url}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def wait_for_completion(ws_url: str, prompt_id: str, client_id: str) -> None:
    ws = websocket.WebSocket()
    ws.connect(f"{ws_url}?clientId={client_id}")
    while True:
        raw = ws.recv()
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == "executing":
            data = msg.get("data", {})
            if data.get("node") is None and data.get("prompt_id") == prompt_id:
                break
        elif msg.get("type") == "execution_error":
            raise RuntimeError(f"ComfyUI error: {msg.get('data', {})}")
    ws.close()


def get_output_videos(comfy_url: str, prompt_id: str) -> list[dict]:
    with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}") as r:
        history = json.loads(r.read())
    outputs = history[prompt_id]["outputs"]
    videos: list[dict] = []
    for node_output in outputs.values():
        for key in ("videos", "gifs"):
            for v in node_output.get(key, []):
                videos.append(v)
    return videos


def download_video(comfy_url: str, filename: str, subfolder: str, folder_type: str, out_path: str) -> None:
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    with urllib.request.urlopen(f"{comfy_url}/view?{params}") as r:
        with open(out_path, "wb") as f:
            f.write(r.read())


def prepare_comfy_input(image_path: str, scene_num: int, comfy_input_dir: str | None) -> str:
    if not comfy_input_dir:
        return os.path.abspath(image_path)

    os.makedirs(comfy_input_dir, exist_ok=True)
    filename = f"inspiring_scene_{scene_num:02d}.png"
    shutil.copy(image_path, os.path.join(comfy_input_dir, filename))
    return filename


def build_i2v_workflow(
    diffusion_model: str,
    text_encoder: str,
    vae_model: str,
    image_name: str,
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    frames: int,
    fps: int,
    steps: int,
    cfg: float,
    seed: int,
    base_precision: str,
    quantization: str,
    blocks_to_swap: int,
    use_clip_vision: bool,
    clip_vision: str,
) -> dict:
    prompt = f"{positive_prompt}, subtle realistic animation, gentle camera motion, natural breathing, blinking eyes, stable identity, preserve face, no text"
    workflow = {
        "1": {
            "class_type": "WanVideoBlockSwap",
            "inputs": {
                "blocks_to_swap": blocks_to_swap,
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
                "model": diffusion_model,
                "base_precision": base_precision,
                "quantization": quantization,
                "load_device": "offload_device",
                "attention_mode": "sdpa",
                "block_swap_args": ["1", 0],
            },
        },
        "3": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {"model_name": text_encoder, "precision": "bf16", "load_device": "offload_device", "quantization": "disabled"},
        },
        "4": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": prompt,
                "negative_prompt": negative_prompt,
                "t5": ["3", 0],
                "force_offload": True,
                "model_to_offload": ["2", 0],
                "use_disk_cache": False,
                "device": "gpu",
            },
        },
        "5": {"class_type": "WanVideoVAELoader", "inputs": {"model_name": vae_model, "precision": "bf16", "use_cpu_cache": False, "verbose": False}},
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "7": {
            "class_type": "ImageResizeKJv2",
            "inputs": {
                "image": ["6", 0],
                "width": width,
                "height": height,
                "upscale_method": "lanczos",
                "keep_proportion": "crop",
                "pad_color": "0, 0, 0",
                "crop_position": "center",
                "divisible_by": 16,
                "device": "gpu",
            },
        },
        "8": {
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
                "start_image": ["7", 0],
                "fun_or_fl2v_model": False,
                "tiled_vae": False,
                "augment_empty_frames": 0.0,
            },
        },
        "9": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["2", 0],
                "image_embeds": ["8", 0],
                "steps": steps,
                "cfg": cfg,
                "shift": 5.0,
                "seed": seed,
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
        "10": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae": ["5", 0],
                "samples": ["9", 0],
                "enable_vae_tiling": True,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
                "normalization": "default",
            },
        },
        "11": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["10", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": "wan_clip",
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

    if use_clip_vision:
        workflow["12"] = {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": clip_vision}}
        workflow["13"] = {
            "class_type": "WanVideoClipVisionEncode",
            "inputs": {
                "clip_vision": ["12", 0],
                "image_1": ["7", 0],
                "strength_1": 1.0,
                "strength_2": 1.0,
                "crop": "center",
                "combine_embeds": "average",
                "force_offload": True,
                "tiles": 0,
                "ratio": 0.5,
            },
        }
        workflow["8"]["inputs"]["clip_embeds"] = ["13", 0]

    return workflow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    args = parser.parse_args()

    channel = load_json(args.channel)
    video_cfg = channel.get("video", {})

    comfy_url = video_cfg.get("comfy_url", "http://127.0.0.1:8188").rstrip("/")
    ws_url = comfy_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"

    diffusion_model = video_cfg.get("diffusion_model", "Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors")
    text_encoder = video_cfg.get("text_encoder", "umt5-xxl-enc-bf16.safetensors")
    clip_vision = video_cfg.get("clip_vision", "open-clip-vit-huge_fp16.safetensors")
    vae_model = video_cfg.get("vae_model", "Wan2_1_VAE_bf16.safetensors")
    base_precision = video_cfg.get("base_precision", "fp16")
    quantization = video_cfg.get("quantization", "fp8_e4m3fn_scaled")
    blocks_to_swap = int(video_cfg.get("blocks_to_swap", 14))
    use_clip_vision = bool(video_cfg.get("use_clip_vision", False))
    comfy_input_dir = video_cfg.get("comfy_input_dir")
    negative_prompt = video_cfg.get(
        "negative_prompt",
        "low quality, blurry, static, watermark, text, duplicate face, duplicate head, bad anatomy",
    )

    width = int(video_cfg.get("width", 832))
    height = int(video_cfg.get("height", 480))
    frames = int(video_cfg.get("frames", 81))
    fps = int(video_cfg.get("fps", 24))
    steps = int(video_cfg.get("steps", 20))
    cfg = float(video_cfg.get("cfg", 6.0))

    os.makedirs("video/clips", exist_ok=True)

    images = sorted([f for f in os.listdir("images/generated") if f.endswith(".png")])
    if not images:
        raise FileNotFoundError("No images found in images/generated/. Generate images first.")

    with open("stories/story.json", "r", encoding="utf-8") as f:
        story = json.load(f)

    scene_prompts = {int(s["scene"]): s.get("visual_prompt", "") for s in story.get("scenes", [])}

    print(f"Generating {len(images)} WAN clips via ComfyUI at {comfy_url} ...")

    for img_file in images:
        scene_num = int(img_file.replace("scene_", "").replace(".png", ""))
        img_path = f"images/generated/{img_file}"
        prompt = scene_prompts.get(scene_num) or "gentle cinematic motion, subtle camera movement, hopeful mood"
        out_path = f"video/clips/clip_{scene_num:02d}.mp4"

        if os.path.exists(out_path):
            print(f"  Scene {scene_num:02d}: exists, skipping")
            continue

        client_id = str(uuid.uuid4())
        image_name = prepare_comfy_input(img_path, scene_num, comfy_input_dir)
        workflow = build_i2v_workflow(
            diffusion_model=diffusion_model,
            text_encoder=text_encoder,
            vae_model=vae_model,
            image_name=image_name,
            positive_prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            frames=frames,
            fps=fps,
            steps=steps,
            cfg=cfg,
            seed=scene_num * 1234567,
            base_precision=base_precision,
            quantization=quantization,
            blocks_to_swap=blocks_to_swap,
            use_clip_vision=use_clip_vision,
            clip_vision=clip_vision,
        )

        result = queue_prompt(comfy_url, workflow, client_id)
        prompt_id = result["prompt_id"]
        wait_for_completion(ws_url, prompt_id, client_id)

        videos = get_output_videos(comfy_url, prompt_id)
        if not videos:
            raise RuntimeError(f"No video output found for scene {scene_num}")

        v = videos[0]
        download_video(comfy_url, v["filename"], v.get("subfolder", ""), v.get("type", "output"), out_path)
        print(f"  Scene {scene_num:02d}: saved {out_path}")

        time.sleep(0.2)

    print("OK: video/clips/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
