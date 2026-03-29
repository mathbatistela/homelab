import { useState, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/tasks`)
      .then((r) => r.json())
      .then((data) => setTasks(data.tasks ?? []))
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  const addTask = async () => {
    const title = input.trim();
    if (!title) return;
    const res = await fetch(`${API_URL}/api/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    const { task } = await res.json();
    setTasks((prev) => [...prev, task]);
    setInput("");
  };

  const toggleTask = async (id) => {
    const task = tasks.find((t) => t.id === id);
    const res = await fetch(`${API_URL}/api/tasks/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: !task.done }),
    });
    const { task: updated } = await res.json();
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)));
  };

  return (
    <main style={{ maxWidth: 600, margin: "2rem auto", fontFamily: "sans-serif", padding: "0 1rem" }}>
      <h1>adhd-board</h1>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addTask()}
          placeholder="What needs doing?"
          style={{ flex: 1, padding: "0.5rem", fontSize: "1rem" }}
        />
        <button type="button" onClick={addTask} style={{ padding: "0.5rem 1rem" }}>Add</button>
      </div>
      {loading ? (
        <p>Loading…</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {tasks.map((task) => (
            <li key={task.id} style={{ marginBottom: "0.5rem" }}>
              <button
                type="button"
                onClick={() => toggleTask(task.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "0.75rem",
                  background: task.done ? "#d4edda" : "#f8f9fa",
                  cursor: "pointer",
                  borderRadius: 4,
                  border: "none",
                  textDecoration: task.done ? "line-through" : "none",
                  fontSize: "1rem",
                }}
              >
                {task.title}
              </button>
            </li>
          ))}
          {tasks.length === 0 && <p style={{ color: "#999" }}>No tasks yet.</p>}
        </ul>
      )}
    </main>
  );
}
