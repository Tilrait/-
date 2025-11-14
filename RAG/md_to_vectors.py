import sys, re, numpy as np
from sentence_transformers import SentenceTransformer

FILENAME = sys.argv[1] if len(sys.argv) > 1 else "input.md"

with open(FILENAME, "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

chunks = [c.strip() for c in re.split(r'(?m)^(?=#)', text) if c.strip()]

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
embs = model.encode(chunks, normalize_embeddings=True, convert_to_numpy=True)

np.savez("index.npz", embs=embs, texts=np.array(chunks, dtype=object))

print("Готово. Разделов:", len(chunks), "| Файл: index.npz")