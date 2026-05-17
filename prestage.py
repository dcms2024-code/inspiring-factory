#!/usr/bin/env python3
"""Pre-generates story + voice for a figure into staging/. Launched during WAN of previous figure."""
from __future__ import annotations
import argparse, os, re, subprocess, sys, time
from pathlib import Path

DIR = Path("/home/andreu/inspiring-factory")
PYTHON = "/home/andreu/miniconda3/bin/python"
# Read STAGING_DIR from env var — allows mystery (staging_mystery/) to override default
STAGING_DIR = Path(os.environ.get("STAGING_DIR", str(DIR / "staging")))


def log(msg):
    print(f"[prestage] {msg}", flush=True)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def prestage(figure, channel):
    staging = STAGING_DIR / slug(figure)
    staging.mkdir(parents=True, exist_ok=True)

    story_path = staging / "story.json"
    narration_path = staging / "narration.mp3"

    if story_path.exists() and narration_path.exists():
        log(f"Ya pre-generado: {figure} — nada que hacer")
        return True

    # Only generate story if it doesn't already exist (e.g. manual ChatGPT script)
    if not story_path.exists():
        # Only start Ollama if GROQ_API_KEY is not available
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
            time.sleep(3)
            subprocess.Popen(["ollama", "serve"],
                             stdout=open("/tmp/ollama_prestage.log", "w"), stderr=subprocess.STDOUT)
            time.sleep(8)

        log(f"Historia: {figure}")
        r = subprocess.run(
            [PYTHON, "generate_and_save_story.py",
             "--channel", channel,
             "--figure", figure,
             "--output", str(story_path)],
            capture_output=True, text=True, cwd=DIR
        )
        if r.returncode != 0:
            log(f"ERROR historia: {r.stderr[:300]}")
            return False
        log(f"Historia OK")
    else:
        log(f"Historia ya existe — saltando generacion")

    # Generate narration (TTS only, no Ollama needed)
    if not narration_path.exists():
        log(f"Voz: {figure}")
        r = subprocess.run(
            [PYTHON, "generate_voice.py",
             "--channel", channel,
             "--story", str(story_path),
             "--output-dir", str(staging)],
            capture_output=True, text=True, cwd=DIR
        )
        if r.returncode != 0:
            log(f"ERROR voz: {r.stderr[:300]}")
            return False
        log(f"Voz OK -> {staging}/narration.mp3")
    else:
        log(f"Voz ya existe — saltando TTS")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--figure", required=True)
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    os.chdir(DIR)
    success = prestage(args.figure, args.channel)
    sys.exit(0 if success else 1)
