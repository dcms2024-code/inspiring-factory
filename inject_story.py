#!/usr/bin/env python3
"""
Inyecta guiones manuales en la cola staging_mystery del autopilot.

Formato del JSON de entrada (array de historias):
[
  {
    "topic": "El Paso Dyatlov",   <- debe coincidir EXACTAMENTE con TOPICS en autopilot_mystery.py
    "youtube_title": "¿Qué ocurrió realmente en el Paso Dyatlov?",
    "description": "Texto descripción YouTube.\n#misterios #misteriosaldia",
    "scenes": [
      {
        "narration": "Texto narrado por la voz...",
        "prompt": "cinematic image prompt in English..."
      }
    ]
  }
]

Uso:
  python3 inject_story.py guiones.json

El autopilot_mystery.py usa staging_mystery/{slug}/story.json automáticamente
si no hay narration.mp3 (genera la voz solo, sin llamar a Ollama).
"""
import json
import re
import sys
from pathlib import Path

DIR = Path("/home/andreu/inspiring-factory")
STAGING_DIR = DIR / "staging_mystery"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def convert(story: dict) -> dict:
    scenes = []
    for i, s in enumerate(story["scenes"], 1):
        scenes.append({
            "scene": i,
            "description": s["narration"],
            "visual_prompt": s["prompt"],
        })
    return {
        "title": story["youtube_title"],
        "youtube_description": story["description"],
        "scenes": scenes,
    }


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 inject_story.py guiones.json")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        stories = json.load(f)

    STAGING_DIR.mkdir(exist_ok=True)

    for s in stories:
        topic = s.get("topic")
        if not topic:
            yt = s.get("youtube_title", "?")
            print(f"ERROR: falta campo 'topic' en '{yt}' — añade \"topic\": \"<nombre exacto del TOPICS>\"")
            continue

        sl = slug(topic)
        staging = STAGING_DIR / sl
        staging.mkdir(exist_ok=True)

        out = staging / "story.json"
        if out.exists():
            print(f"  SKIP {sl} — ya existe story.json (bórralo antes si quieres sobreescribir)")
            continue

        story_json = convert(s)
        out.write_text(json.dumps(story_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  OK staging_mystery/{sl}/story.json — {len(s['scenes'])} escenas")

    print("\nListo. Arranca autopilot_mystery.py para procesar los guiones.")


if __name__ == "__main__":
    main()
