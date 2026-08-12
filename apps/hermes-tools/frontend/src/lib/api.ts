export interface ToolInfo {
  name: string
  label: string
  description: string
  set: string
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro desconhecido" }))
    throw new Error(err.detail || `Erro ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function listTools(set?: string): Promise<{ tools: ToolInfo[] }> {
  const qs = set ? `?set=${encodeURIComponent(set)}` : ""
  return apiJson(`/api/tools${qs}`)
}

export function health(): Promise<{ status: string; tools: number }> {
  return apiJson("/api/health")
}

export async function processTool(
  toolName: string,
  params: Record<string, unknown>,
  initData: string,
): Promise<{ ok: boolean; data: Record<string, unknown> }> {
  return apiJson(`/api/${toolName}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData, params }),
  })
}

/** Calls the upload endpoint — RMBG-2.0, used by both the Mini App and the bot.
 *
 * The endpoint is authenticated: the Mini App presents Telegram initData, the
 * bot presents the MCP API key. Outside Telegram there is no credential to
 * send, so the request is rejected with 401 by design.
 */
export async function uploadRemoveBg(file: File, initData?: string): Promise<Blob> {
  const form = new FormData()
  form.append("file", file)
  const tgInitData = initData ?? window.Telegram?.WebApp?.initData ?? ""
  const headers: Record<string, string> = {}
  if (tgInitData) headers["X-Telegram-Init-Data"] = tgInitData
  const res = await fetch("/api/remove-bg/upload", {
    method: "POST",
    headers,
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao processar imagem" }))
    throw new Error(err.detail || `Erro ${res.status}`)
  }
  return res.blob()
}
