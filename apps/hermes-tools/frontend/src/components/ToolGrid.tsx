import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { listTools, type ToolInfo } from "@/lib/api"

interface ToolGridProps {
  onSelect: (tool: ToolInfo) => void
}

export function ToolGrid({ onSelect }: ToolGridProps) {
  const [tools, setTools] = useState<ToolInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listTools()
      .then((res) => setTools(res.tools))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Erro ao carregar ferramentas"))
  }, [])

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }

  if (!tools) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {tools.map((tool) => (
        <Card
          key={tool.name}
          onClick={() => onSelect(tool)}
          className="cursor-pointer transition-colors hover:bg-muted/50"
        >
          <CardHeader>
            <Badge variant="secondary" className="w-fit">
              {tool.set}
            </Badge>
            <CardTitle>{tool.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{tool.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
