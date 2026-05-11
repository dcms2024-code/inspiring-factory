import os
import ollama


def ask_mistral(prompt: str) -> str:
    model_name = os.getenv("OLLAMA_MISTRAL_MODEL", "mistral")
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.message.content
