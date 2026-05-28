"""Poll an existing task by ID until it completes."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv; load_dotenv()
import httpx

BASE_URL = "http://localhost:8000"
task_id = sys.argv[1] if len(sys.argv) > 1 else None

if not task_id:
    print("Usage: python3 scripts/poll_task.py <task_id>")
    sys.exit(1)

print(f"Polling {task_id}...")
last = None
while True:
    r = httpx.get(f"{BASE_URL}/tasks/{task_id}", timeout=10)
    data = r.json()
    status = data.get("status")
    if status != last:
        print(f"  [{time.strftime('%H:%M:%S')}] {status}")
        last = status
    if status in ("completed", "failed"):
        print("\n" + json.dumps(data.get("result"), indent=2, default=str))
        break
    time.sleep(10)
