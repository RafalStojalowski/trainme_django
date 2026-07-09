from ollama import chat

response = chat(
    model="qwen3:8b",
    messages=[
        {
            "role": "user",
            "content": "Opowiedz o NMR."
        }
    ]
)

print(response.message.content)