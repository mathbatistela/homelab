import { useState } from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { uploadRemoveBg } from "@/lib/api"

export function RemoveBackground() {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function handleFile(f: File | null) {
    setFile(f)
    setResultUrl(null)
    setPreviewUrl(f ? URL.createObjectURL(f) : null)
  }

  async function handleSubmit() {
    if (!file) return
    setLoading(true)
    try {
      const blob = await uploadRemoveBg(file)
      setResultUrl(URL.createObjectURL(blob))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao remover fundo")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle>Remover Fundo</CardTitle>
        <CardDescription>
          Envie uma foto e receba um PNG com o fundo removido (RMBG-2.0)
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <input
          type="file"
          accept="image/*"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-foreground"
        />

        {(previewUrl || resultUrl) && (
          <div className="grid grid-cols-2 gap-3">
            {previewUrl && (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">Original</span>
                <img
                  src={previewUrl}
                  alt="Original"
                  className="max-h-56 w-full rounded-md border object-contain"
                />
              </div>
            )}
            {resultUrl && (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">Resultado</span>
                <img
                  src={resultUrl}
                  alt="Resultado sem fundo"
                  className="max-h-56 w-full rounded-md border bg-[repeating-conic-gradient(#e5e5e5_0%_25%,transparent_0%_50%)] bg-[length:16px_16px] object-contain"
                />
              </div>
            )}
          </div>
        )}

        {loading && <Progress value={66} className="animate-pulse" />}

        <div className="flex gap-2">
          <Button onClick={handleSubmit} disabled={!file || loading}>
            {loading ? "Processando..." : "Remover fundo"}
          </Button>
          {resultUrl && (
            <Button variant="secondary" asChild>
              <a href={resultUrl} download="resultado.png">
                Baixar PNG
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
