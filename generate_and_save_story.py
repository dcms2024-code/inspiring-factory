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
    story_type = channel.get("story_type", "inspirational")
    age_progression = channel.get("age_progression", True)

    hint_line = f"\nExtra context: {figure_hint}\n" if figure_hint else ""

    if age_progression:
        age_rules = (
            f"- STRICT AGE PROGRESSION: The figure must visually age from scene to scene. Never go backwards in age.\n"
            f"- Age guide for {scenes_count} scenes: "
            f"scene 1 (~8-12 years old, child face, no wrinkles), "
            f"scene 2 (~16-20 years old, teenage/young adult), "
            f"scene 3 (~25-30 years old, smooth skin, dark hair), "
            f"scene 4 (~35-40 years old, slight lines, still dark hair), "
            f"scene 5 (~45-52 years old, light gray temples, mature face), "
            f"scene 6 (~55-62 years old, salt-and-pepper hair, visible wrinkles), "
            f"scene 7 (~65-72 years old, gray or white hair, deep wrinkles, aged posture), "
            f"scene 8 (~75-85 years old, white hair, elderly face, or symbolic tribute shot), "
            f"scene {scenes_count} (legacy tribute: statue, memorial, or modern impact — no character age required).\n"
            f"- MANDATORY in every visual_prompt where the character appears: include the APPROXIMATE AGE as a number "
            f"AND at least one physical descriptor. Good examples: "
            f"'10-year-old boy with smooth skin and dark hair', "
            f"'28-year-old man with dark hair and sharp eyes', "
            f"'55-year-old man with salt-and-pepper hair and slight wrinkles', "
            f"'72-year-old woman with white hair, deep wrinkles, and a warm smile'. "
            f"NEVER use just 'young', 'older', 'mature' or 'elderly' without an age number.\n"
            f"- FORBIDDEN in visual_prompts for scenes 5 and beyond: words like 'young', 'child', 'early career', "
            f"'early life', 'as a student' — these imply ages already shown.\n"
            f"- Each scene must be set LATER in time than the previous scene. Never repeat a setting already shown."
        )
    else:
        age_rules = (
            f"- Do NOT apply age progression. Each scene should focus on atmosphere, setting, and mood "
            f"relevant to the topic. Scenes can jump between different moments, places, or perspectives freely.\n"
            f"- Show the subject (person or place) at the most relevant or iconic visual moment.\n"
            f"- Each scene must show a DIFFERENT visual moment, location, or angle to keep variety."
        )

    return f"""
Write a {story_type} short story for a YouTube Short about: {figure_name}.
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
{age_rules}

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
    parser.add_argument("--output", default="stories/story.json", help="Output JSON path")
    args = parser.parse_args()

    channel = load_json(args.channel)
    figures = load_json(args.figures)
    figure_name, figure_hint = pick_figure(figures, args.figure)

    prompt = build_prompt(channel, figure_name, figure_hint)
    provider = channel.get("story_provider", "ollama")
    raw = run_task("story", prompt, provider=provider)

    data = parse_json_strict(raw)

    os.makedirs(__import__("os").path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: {args.output}  (figure={figure_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
