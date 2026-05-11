import os
import ollama


def ask_qwen(prompt: str) -> str:
    model_name = os.getenv("OLLAMA_QWEN_MODEL", "qwen2.5:14b")
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.message.content
