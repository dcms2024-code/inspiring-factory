import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

from core.config import default_channel_config_path, load_json


def queue_prompt(comfy_url: str, prompt: dict, client_id: str) -> dict:
    data = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{comfy_url}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def get_history(comfy_url: str, prompt_id: str) -> dict:
    with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}") as r:
        return json.loads(r.read())


def download_asset(comfy_url: str, filename: str, subfolder: str, folder_type: str, out_path: str) -> None:
    params = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": folder_type})
    with urllib.request.urlopen(f"{comfy_url}/view?{params}") as r:
        with open(out_path, "wb") as f:
            f.write(r.read())


def build_workflow(checkpoint: str, positive_prompt: str, negative_prompt: str, seed: int, width: int, height: int) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": positive_prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 25,
                "cfg": 7,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "scene", "images": ["6", 0]}},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    args = parser.parse_args()

    channel = load_json(args.channel)
    comfy_url = channel["image"]["comfy_url"].rstrip("/")
    checkpoint = channel["image"]["checkpoint"]
    suffix = channel["image"]["prompt_suffix"]
    negative = channel["image"]["negative_prompt"]
    img_steps = int(channel["image"].get("steps", 25))
    img_cfg = float(channel["image"].get("cfg", 7))

    os.makedirs("images/generated", exist_ok=True)

    with open("stories/story.json", "r", encoding="utf-8") as f:
        story = json.load(f)

    client_id = str(uuid.uuid4())

    width = int(channel["image"].get("width", 640))
    height = int(channel["image"].get("height", 1120))

    scenes = story.get("scenes", [])
    print(f"Generating {len(scenes)} images via ComfyUI at {comfy_url} ...")

    for scene in scenes:
        scene_number = int(scene["scene"])
        out_path = f"images/generated/scene_{scene_number:02d}.png"

        if os.path.exists(out_path):
            print(f"  Scene {scene_number:02d}: exists, skipping")
            continue

        visual_prompt = scene["visual_prompt"].strip()
        positive_prompt = f"{visual_prompt}, {suffix}"

        workflow = build_workflow(
            checkpoint=checkpoint,
            positive_prompt=positive_prompt,
            negative_prompt=negative,
            seed=scene_number * 1234567,
            width=width,
            height=height,
        )

        # Apply configurable sampler params
        workflow["5"]["inputs"]["steps"] = img_steps
        workflow["5"]["inputs"]["cfg"] = img_cfg

        result = queue_prompt(comfy_url, workflow, client_id)
        prompt_id = result["prompt_id"]

        while True:
            history = get_history(comfy_url, prompt_id)
            if prompt_id in history:
                break
            time.sleep(2)

        outputs = history[prompt_id]["outputs"]
        saved = False
        for node_output in outputs.values():
            if "images" in node_output and node_output["images"]:
                image = node_output["images"][0]
                download_asset(
                    comfy_url,
                    image["filename"],
                    image.get("subfolder", ""),
                    image.get("type", "output"),
                    out_path,
                )
                saved = True
                break

        if saved:
            print(f"  Scene {scene_number:02d}: saved {out_path}")
        else:
            raise RuntimeError(f"No image output found for scene {scene_number}")

    print("OK: images/generated/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
