import json
import os

MEMORY_FILE = "memory.json"

def save_progress(topic, score):
    memory = []
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            memory = json.load(f)

    memory.append({
        "topic": topic,
        "score": score
    })

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def get_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE) as f:
        return json.load(f)
