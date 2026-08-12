import os
import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS

import store

app = Flask(__name__)
CORS(app, origins=os.environ.get("FRONTEND_URL", "*"))

# Tasks live in SQLite (see store.py) instead of a process-local dict, so they
# survive restarts and redeploys. DB_PATH must point at a mounted volume.
store.migrate()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/tasks")
def list_tasks():
    return jsonify({"tasks": store.all_tasks()})


@app.post("/api/tasks")
def create_task():
    body = request.get_json(force=True)
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = store.insert(str(uuid.uuid4()), title)
    return jsonify({"task": task}), 201


@app.patch("/api/tasks/<task_id>")
def update_task(task_id: str):
    task = store.get(task_id)
    if task is None:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True)

    done = bool(body["done"]) if "done" in body else None
    title = None
    if "title" in body:
        # Same semantics as before: a blank title leaves the old one in place.
        title = str(body["title"]).strip() or task["title"]

    updated = store.update(task_id, title=title, done=done)
    if updated is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"task": updated})


@app.delete("/api/tasks/<task_id>")
def delete_task(task_id: str):
    if not store.delete(task_id):
        return jsonify({"error": "not found"}), 404
    return "", 204


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
