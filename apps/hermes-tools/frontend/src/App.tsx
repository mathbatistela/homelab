import { useEffect, useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { Button } from "@/components/ui/button"
import { ToolGrid } from "@/components/ToolGrid"
import { RemoveBackground } from "@/components/tools/RemoveBackground"
import { useTelegram, type TelegramWebApp } from "@/lib/platform"
import type { ToolInfo } from "@/lib/api"

function applyTelegramTheme(tg: TelegramWebApp) {
  const root = document.documentElement
  const bg = tg.themeParams.bg_color
  if (bg) root.style.setProperty("--background", bg)
  document.body.style.backgroundColor = bg ?? ""
}

function getToolFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("tool")
}

const KNOWN_TOOL_COMPONENTS: Record<string, () => React.ReactElement> = {
  "remove-bg-rmbg": RemoveBackground,
  "remove-bg-sam": RemoveBackground,
}

function App() {
  const { isTelegram, tg } = useTelegram()
  const [selectedTool, setSelectedTool] = useState<string | null>(getToolFromUrl)

  useEffect(() => {
    if (tg) applyTelegramTheme(tg)
  }, [tg])

  function selectTool(tool: ToolInfo | null) {
    setSelectedTool(tool?.name ?? null)
    const url = new URL(window.location.href)
    if (tool) url.searchParams.set("tool", tool.name)
    else url.searchParams.delete("tool")
    window.history.pushState({}, "", url)
  }

  const ToolComponent = selectedTool ? KNOWN_TOOL_COMPONENTS[selectedTool] : null

  return (
    <div className={isTelegram ? "min-h-screen p-3" : "min-h-screen bg-background p-4 sm:p-8"}>
      <div className="mx-auto flex max-w-4xl flex-col gap-4">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-heading font-semibold">Hermes Tools</h1>
            {!isTelegram && (
              <p className="text-sm text-muted-foreground">
                Ferramentas de IA — remoção de fundo e mais
              </p>
            )}
          </div>
          {ToolComponent && (
            <Button variant="ghost" size="sm" onClick={() => selectTool(null)}>
              ← Voltar
            </Button>
          )}
        </header>

        <main>{ToolComponent ? <ToolComponent /> : <ToolGrid onSelect={selectTool} />}</main>
      </div>
      <Toaster />
    </div>
  )
}

export default App
