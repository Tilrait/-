import os
from openai import OpenAI

API_KEY = 'sk-052d89cfe6be4d7d815c128ec700ba00'

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

conversation_history = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Привет!"},
]

print("🔄 Отправляем первый запрос...")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=conversation_history,
    stream=False
)

ai_response = response.choices[0].message.content
print("Первый ответ:", ai_response)

conversation_history.append({"role": "assistant", "content": ai_response})
conversation_history.append({"role": "user", "content": "Расскажи подробнее!"})

print("🔄 Отправляем второй запрос...")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=conversation_history,
    stream=False
)

print("Второй ответ:", response.choices[0].message.content)
print("Тест завершен успешно!")