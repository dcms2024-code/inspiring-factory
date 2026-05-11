import argparse
import asyncio
import json
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import edge_tts


STORY = {
    "title": "Ada Lovelace: la primera visionaria del codigo",
    "narration": (
        "Imagina una sala de Londres, llena de engranajes, planos y preguntas. "
        "Ada Lovelace no vio solo una maquina de calcular. Vio una idea nueva: "
        "si los numeros podian representar musica, simbolos o patrones, entonces "
        "una maquina podria trabajar con la imaginacion. En mil ochocientos cuarenta "
        "y tres, Ada escribio una nota sobre el motor analitico de Charles Babbage. "
        "En esa nota describio un algoritmo para calcular numeros de Bernoulli. "
        "Hoy muchos la recuerdan como la primera programadora de la historia. "
        "Pero su grandeza fue aun mayor. Ada mezclo matematicas y arte. Precision "
        "y fantasia. Razon y futuro. Antes de que existieran los ordenadores, ella "
        "intuyo que podrian crear musica, imagenes y conocimiento. Su vida nos deja "
        "una pregunta poderosa: no mires una herramienta solo por lo que hace hoy. "
        "Mira lo que puede llegar a ser cuando una mente valiente aprende a imaginarla."
    ),
    "scenes": [
        {
            "id": 1,
            "caption": "Londres, 1843",
            "prompt": (
                "Ada Lovelace in a 19th century London study, realistic animated film still, "
                "young Victorian mathematician, thoughtful expression, brass gears and papers, "
                "warm cinematic lighting, painterly realism, detailed face, elegant historical dress"
            ),
        },
        {
            "id": 2,
            "caption": "No vio una calculadora",
            "prompt": (
                "Ada Lovelace examining detailed mechanical plans of the Analytical Engine, "
                "realistic animation concept art, brass mechanisms, handwritten diagrams, "
                "soft candlelight, cinematic close up, hopeful mood, no readable text"
            ),
        },
        {
            "id": 3,
            "caption": "Vio simbolos e ideas",
            "prompt": (
                "Ada Lovelace imagining symbols, music notes and mathematical patterns floating "
                "above a mechanical computer, realistic animated historical fantasy, subtle magical realism, "
                "cinematic depth of field, elegant and inspiring, no readable text"
            ),
        },
        {
            "id": 4,
            "caption": "El primer algoritmo",
            "prompt": (
                "Victorian desk with Ada Lovelace writing an algorithm by candlelight, Bernoulli numbers "
                "suggested as abstract formulas, realistic animated film frame, detailed ink, gears in background, "
                "serious focused expression, no readable text"
            ),
        },
        {
            "id": 5,
            "caption": "Matematicas y arte",
            "prompt": (
                "Ada Lovelace standing beside an imagined mechanical engine transforming patterns into music "
                "and light, realistic animated movie still, inspiring atmosphere, warm highlights, "
                "Victorian science and art blended together, no readable text"
            ),
        },
        {
            "id": 6,
            "caption": "Lo que puede llegar a ser",
            "prompt": (
                "single centered portrait of Ada Lovelace, exactly one woman, exactly one head, one face only, "
                "looking toward a future made of soft glowing code and mechanical gears, realistic animated film still, "
                "dignified, inspiring, detailed realistic face, warm light, hopeful ending, no readable text"
            ),
        },
    ],
}

NEGATIVE_PROMPT = (
    "low quality, blurry, bad anatomy, distorted hands, extra fingers, deformed face, "
    "watermark, logo, text, readable letters, modern laptop, modern clothing, oversaturated, "
    "two heads, duplicate head, duplicate face, cloned face, multiple people, second person"
)


def run(cmd: list[str], cwd: str | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def queue_prompt(comfy_url: str, prompt: dict, client_id: str) -> dict:
    data = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        f"{comfy_url}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read())


def get_history(comfy_url: str, prompt_id: str) -> dict:
    with urllib.request.urlopen(f"{comfy_url}/history/{prompt_id}", timeout=60) as response:
        return json.loads(response.read())


def download_asset(comfy_url: str, asset: dict, out_path: Path) -> None:
    params = urllib.parse.urlencode(
        {
            "filename": asset["filename"],
            "subfolder": asset.get("subfolder", ""),
            "type": asset.get("type", "output"),
        }
    )
    with urllib.request.urlopen(f"{comfy_url}/view?{params}", timeout=180) as response:
        out_path.write_bytes(response.read())


def build_image_workflow(
    checkpoint: str,
    prompt: str,
    seed: int,
    width: int,
    height: int,
    steps: int,
    cfg: float,
) -> dict:
    positive = (
        f"{prompt}, high quality, realistic animated feature film style, cinematic composition, "
        "vertical portrait framing, rich period detail, expressive eyes, natural skin texture"
    )
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE_PROMPT, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ada_scene", "images": ["6", 0]}},
    }


def generate_images(args: argparse.Namespace, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    client_id = str(uuid.uuid4())

    for scene in STORY["scenes"]:
        out_path = out_dir / f"scene_{scene['id']:02d}.png"
        if out_path.exists() and not args.force:
            print(f"Image {out_path.name}: exists")
            continue

        workflow = build_image_workflow(
            checkpoint=args.checkpoint,
            prompt=scene["prompt"],
            seed=args.seed + scene["id"] * 1009,
            width=args.image_width,
            height=args.image_height,
            steps=args.steps,
            cfg=args.cfg,
        )
        queued = queue_prompt(args.comfy_url, workflow, client_id)
        prompt_id = queued["prompt_id"]
        print(f"Image scene {scene['id']:02d}: queued {prompt_id}")

        while True:
            history = get_history(args.comfy_url, prompt_id)
            if prompt_id in history:
                break
            time.sleep(2)

        outputs = history[prompt_id]["outputs"]
        image_asset = None
        for output in outputs.values():
            images = output.get("images", [])
            if images:
                image_asset = images[0]
                break

        if image_asset is None:
            raise RuntimeError(f"No image output for scene {scene['id']}")

        download_asset(args.comfy_url, image_asset, out_path)
        print(f"Image scene {scene['id']:02d}: saved {out_path}")


async def generate_voice(base_dir: Path, voice: str) -> Path:
    audio_dir = base_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    raw_mp3 = audio_dir / "narration_raw.mp3"
    subtitles = audio_dir / "subtitles.srt"

    communicate = edge_tts.Communicate(
        STORY["narration"],
        voice,
        rate="-8%",
        pitch="-8Hz",
    )
    submaker = edge_tts.SubMaker()
    with raw_mp3.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                submaker.feed(chunk)

    subtitles.write_text(submaker.get_srt(), encoding="utf-8")

    final_wav = audio_dir / "narration_dark.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(raw_mp3),
            "-af",
            "rubberband=pitch=0.86:formant=preserved,loudnorm=I=-16:LRA=11:TP=-1.5",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(final_wav),
        ]
    )
    print(f"Voice saved: {final_wav}")
    return final_wav


def audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def write_concat(paths: list[Path], concat_path: Path) -> None:
    concat_path.parent.mkdir(parents=True, exist_ok=True)
    with concat_path.open("w", encoding="utf-8") as f:
        for path in paths:
            f.write(f"file '{path.name}'\n")


def render_slides(base_dir: Path, audio_path: Path, fps: int) -> Path:
    images_dir = base_dir / "images" / "generated"
    slides_dir = base_dir / "video" / "slides"
    output_dir = base_dir / "output"
    slides_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(images_dir.glob("scene_*.png"))
    if not image_paths:
        raise FileNotFoundError("No generated images found.")

    duration = audio_duration(audio_path)
    per_scene = duration / len(image_paths)
    slide_paths = []

    for index, image_path in enumerate(image_paths, start=1):
        slide_path = slides_dir / f"slide_{index:02d}.mp4"
        slide_paths.append(slide_path)
        frames = max(1, int(round(per_scene * fps)))
        pan = "iw/2-(iw/zoom/2)"
        if index % 2 == 0:
            pan = "(iw-iw/zoom)*on/{frames}".format(frames=frames)
        zoom = f"1+0.12*on/{frames}"
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"zoompan=z='{zoom}':d={frames}:x='{pan}':y='ih/2-(ih/zoom/2)':fps={fps}:s=1080x1920"
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-i",
                str(image_path),
                "-vf",
                vf,
                "-t",
                f"{per_scene:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                str(slide_path),
            ]
        )
        print(f"Slide {index:02d}: {slide_path}")

    concat_path = slides_dir / "concat.txt"
    write_concat(slide_paths, concat_path)
    no_subs = output_dir / "ada_lovelace_3090_no_subs.mp4"
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
            "-i",
            str(audio_path),
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

    final_path = output_dir / "ada_lovelace_3090_preview.mp4"
    subs_tmp = output_dir / "subtitles.srt"
    shutil.copy(base_dir / "audio" / "subtitles.srt", subs_tmp)
    subs_path = str(subs_tmp).replace(":", "\\:")
    subtitle_filter = (
        f"subtitles={subs_path}:"
        "force_style='FontName=DejaVu Sans,FontSize=9,Outline=1,Shadow=1,Alignment=2,MarginV=36'"
    )
    try:
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
                str(final_path),
            ]
        )
    except subprocess.CalledProcessError:
        shutil.copy(no_subs, final_path)

    print(f"Final video: {final_path}")
    return final_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default="/home/andreu/ai-projects/ada-lovelace-3090-preview")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--checkpoint", default="juggernaut.safetensors")
    parser.add_argument("--voice", default="es-ES-AlvaroNeural")
    parser.add_argument("--image-width", type=int, default=768)
    parser.add_argument("--image-height", type=int, default=1344)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--cfg", type=float, default=6.5)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=260511)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    (base_dir / "stories").mkdir(parents=True, exist_ok=True)
    (base_dir / "stories" / "story.json").write_text(json.dumps(STORY, indent=2, ensure_ascii=False), encoding="utf-8")

    generate_images(args, base_dir / "images" / "generated")
    audio_path = asyncio.run(generate_voice(base_dir, args.voice))
    final_path = render_slides(base_dir, audio_path, args.fps)

    print(str(final_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
