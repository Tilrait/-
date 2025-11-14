import os
import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer

z = np.load("index.npz", allow_pickle=True)
embs = z["embs"]
texts = z["texts"].tolist()

model_embed = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

client = OpenAI(
    api_key="sk-052d89cfe6be4d7d815c128ec700ba00",
    base_url="https://api.deepseek.com"
)

while True:
    query = input("\n> ").strip()
    if not query:
        continue

    q_emb = model_embed.encode(query, normalize_embeddings=True, convert_to_numpy=True)

    sims = embs @ q_emb
    topk = sims.argsort()[-3:][::-1]

    retrieved_blocks = "\n\n---\n\n".join(texts[i] for i in topk)

    system_prompt = (
        "You are a helpful assistant. "
        "Use ONLY the provided context to answer. "
        "If the answer is not in the context, say you don't know.\n\n"
        f"=== CONTEXT START ===\n{retrieved_blocks}\n=== CONTEXT END ===\n"
    )

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        stream=False
    )

    print("\nANSWER:\n", resp.choices[0].message.content)