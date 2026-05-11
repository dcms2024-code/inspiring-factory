from models.qwen import ask_qwen
from models.mistral import ask_mistral


def choose_model(task_type: str) -> str:
    creative_tasks = {
        "story",
        "script",
        "title",
        "scene_prompt",
    }

    validation_tasks = {
        "validate",
        "cleanup",
        "json",
    }

    if task_type in creative_tasks:
        return "qwen"

    if task_type in validation_tasks:
        return "mistral"

    return "qwen"


def run_task(task_type: str, prompt: str) -> str:
    model = choose_model(task_type)

    if model == "qwen":
        return ask_qwen(prompt)

    if model == "mistral":
        return ask_mistral(prompt)

    return ask_qwen(prompt)
