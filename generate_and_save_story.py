import argparse
import json
import os
import random

from core.config import (
    default_channel_config_path,
    default_figures_path,
    load_json,
)
from core.json_utils import parse_json_strict
from core.model_router import run_task


def build_prompt(channel: dict, figure_name: str, figure_hint: str | None) -> str:
    rules = "\n".join(f"- {r}" for r in channel.get("story_rules", []))
    scenes_count = int(channel.get("scenes_count", 5))
    language = channel.get("language", "en")
    tone = channel.get("tone", "inspiring")
    seconds = int(channel.get("duration_seconds_target", 50))

    hint_line = f"\nExtra context: {figure_hint}\n" if figure_hint else ""

    # Keep the schema compatible with the existing pipeline style (5 scenes).
    return f"""
Write an inspirational short story for a YouTube Short about the historical figure: {figure_name}.
Target duration: about {seconds} seconds.
Language: {language}.
Tone: {tone}.
{hint_line}
Rules:
{rules}
- Return ONLY valid JSON.
- No markdown.
- No extra keys beyond the schema.
- Create exactly {scenes_count} scenes.
- Each scene's visual_prompt must be in English and suitable for image generation.

Exact JSON schema:
{{
  "figure": {{
    "name": "{figure_name}"
  }},
  "title": "...",
  "hook": "...",
  "ending": "...",
  "scenes": [
    {{
      "scene": 1,
      "description": "...",
      "visual_prompt": "..."
    }}
  ]
}}
""".strip()


def pick_figure(figures: list[dict], requested: str | None) -> tuple[str, str | None]:
    if requested:
        return requested, None
    if not figures:
        return "Unknown historical figure", None
    chosen = random.choice(figures)
    return chosen.get("name", "Unknown historical figure"), chosen.get("one_liner")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default=default_channel_config_path())
    parser.add_argument("--figures", default=default_figures_path())
    parser.add_argument("--figure", default=None, help="Override figure name")
    args = parser.parse_args()

    channel = load_json(args.channel)
    figures = load_json(args.figures)
    figure_name, figure_hint = pick_figure(figures, args.figure)

    prompt = build_prompt(channel, figure_name, figure_hint)
    raw = run_task("story", prompt)

    data = parse_json_strict(raw)

    os.makedirs("stories", exist_ok=True)
    with open("stories/story.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: stories/story.json  (figure={figure_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
