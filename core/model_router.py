from models.qwen import ask_qwen
from models.mistral import ask_mistral
from models.groq_llm import ask_groq


def run_task(task_type: str, prompt: str, provider: str = "ollama") -> str:
    creative_tasks = {"story", "script", "title", "scene_prompt"}
    validation_tasks = {"validate", "cleanup", "json"}

    if task_type in creative_tasks:
        if provider == "groq":
            return ask_groq(prompt)
        return ask_qwen(prompt)

    if task_type in validation_tasks:
        return ask_mistral(prompt)

    return ask_qwen(prompt)
