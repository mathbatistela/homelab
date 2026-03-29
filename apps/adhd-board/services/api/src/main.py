import os
import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=os.environ.get("FRONTEND_URL", "*"))

_tasks: dict[str, dict] = {}


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/tasks")
def list_tasks():
    return jsonify({"tasks": list(_tasks.values())})


@app.post("/api/tasks")
def create_task():
    body = request.get_json(force=True)
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = {"id": str(uuid.uuid4()), "title": title, "done": False}
    _tasks[task["id"]] = task
    return jsonify({"task": task}), 201


@app.patch("/api/tasks/<task_id>")
def update_task(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True)
    if "done" in body:
        task["done"] = bool(body["done"])
    if "title" in body:
        task["title"] = str(body["title"]).strip() or task["title"]
    return jsonify({"task": task})


@app.delete("/api/tasks/<task_id>")
def delete_task(task_id: str):
    if task_id not in _tasks:
        return jsonify({"error": "not found"}), 404
    del _tasks[task_id]
    return "", 204


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
