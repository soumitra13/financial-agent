"""Quick diagnostic — tests embedding call directly."""
import httpx

print("Testing embedding with all-minilm...", flush=True)
try:
    r = httpx.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "all-minilm", "prompt": "test sentence"},
        timeout=30.0,
    )
    print(f"Status: {r.status_code}", flush=True)
    data = r.json()
    if "embedding" in data:
        print(f"✓ Works! Dims: {len(data['embedding'])}", flush=True)
    else:
        print(f"✗ Unexpected response: {data}", flush=True)
except Exception as e:
    print(f"✗ Error: {e}", flush=True)
