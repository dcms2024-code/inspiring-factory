from models.qwen import ask_qwen
from models.mistral import ask_mistral
from models.groq_llm import ask_groq


def choose_model(task_type: str) -> str:
    creative_tasks = {"story", "script", "title", "scene_prompt"}
    validation_tasks = {"validate", "cleanup", "json"}

    if task_type in creative_tasks:
        return "groq"
    if task_type in validation_tasks:
        return "mistral"
    return "groq"


def run_task(task_type: str, prompt: str) -> str:
    model = choose_model(task_type)

    if model == "groq":
        return ask_groq(prompt)
    if model == "qwen":
        return ask_qwen(prompt)
    if model == "mistral":
        return ask_mistral(prompt)

    return ask_groq(prompt)
