import argparse
import json
import os
import random
import urllib.error
import urllib.parse
import urllib.request

from core.config import (
    default_channel_config_path,
    default_figures_path,
    load_json,
)
from core.json_utils import parse_json_strict
from core.model_router import run_task


def fetch_wikipedia_context(name: str, lang: str = "es", max_chars: int = 2000) -> str:
    """Fetch Wikipedia summary to ground visual_prompts in verified real facts."""

    def _get(slug: str, language: str) -> str:
        encoded = urllib.parse.quote(slug.replace(" ", "_"))
        url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "inspiring-factory/1.0 (educational content bot)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                extract = data.get("extract", "")
                if len(extract) > 120:
                    return extract[:max_chars]
        except Exception:
            pass
        return ""

    # 1. Exact name in target language
    result = _get(name, lang)
    if result:
        return result

    # 2. Without leading article (El, La, Los, Las, The)
    for prefix in ["El ", "La ", "Los ", "Las ", "The "]:
        if name.startswith(prefix):
            result = _get(name[len(prefix):], lang)
            if result:
                return result

    # 3. Cross-language fallback
    fallback = "en" if lang != "en" else "es"
    result = _get(name, fallback)
    if result:
        return result

    for prefix in ["El ", "La ", "Los ", "Las ", "The "]:
        if name.startswith(prefix):
            result = _get(name[len(prefix):], fallback)
            if result:
                return result

    return ""


def build_prompt(channel: dict, figure_name: str, figure_hint: str | None, wiki_context: str = "") -> str:
    rules = "\n".join(f"- {r}" for r in channel.get("story_rules", []))
    scenes_count = int(channel.get("scenes_count", 5))
    language = channel.get("language", "en")
    tone = channel.get("tone", "inspiring")
    seconds = int(channel.get("duration_seconds_target", 50))
    story_type = channel.get("story_type", "inspirational")
    age_progression = channel.get("age_progression", True)

    hint_line = f"\nExtra context: {figure_hint}\n" if figure_hint else ""

    if wiki_context:
        wiki_section = (
            "\n--- WIKIPEDIA RESEARCH (verified real facts) ---\n"
            f"{wiki_context}\n"
            "--- END RESEARCH ---\n\n"
            "MANDATORY: Every visual_prompt must be grounded in the facts above. "
            "Use real location names, real settings, real visual details documented here. "
            "FORBIDDEN: any visual element that contradicts or is unrelated to this Wikipedia context.\n"
        )
    else:
        wiki_section = ""

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
            "- MANDATORY in every visual_prompt where the character appears: include the APPROXIMATE AGE as a number "
            "AND at least one physical descriptor matching the Wikipedia description. Good examples: "
            "'10-year-old boy with smooth skin and dark hair', "
            "'28-year-old man with dark hair and sharp eyes', "
            "'55-year-old man with salt-and-pepper hair and slight wrinkles'. "
            "NEVER use just 'young', 'older', 'mature' or 'elderly' without an age number.\n"
            "- FORBIDDEN in visual_prompts for scenes 5 and beyond: words like 'young', 'child', 'early career'.\n"
            "- Each scene must be set LATER in time than the previous scene. Never repeat a setting already shown."
        )
    else:
        age_rules = (
            "- Do NOT apply age progression. Focus on atmosphere, setting, and mood relevant to the topic.\n"
            "- Show the subject at the most relevant or iconic visual moment documented in the Wikipedia research.\n"
            "- Each scene must show a DIFFERENT visual moment, location, or angle to keep variety."
        )

    return f"""Write a {story_type} short story for a YouTube Short about: {figure_name}.
Target duration: about {seconds} seconds.
Language: {language}.
Tone: {tone}.
{hint_line}{wiki_section}
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
}}""".strip()


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

    lang = channel.get("language", "es")[:2]
    print(f"Fetching Wikipedia context for '{figure_name}' ({lang})...")
    wiki_context = fetch_wikipedia_context(figure_name, lang=lang)
    if wiki_context:
        print(f"  Wikipedia: {len(wiki_context)} chars found")
    else:
        print("  Wikipedia: not found, generating without context")

    prompt = build_prompt(channel, figure_name, figure_hint, wiki_context)
    raw = run_task("story", prompt)

    data = parse_json_strict(raw)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"OK: {args.output}  (figure={figure_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
