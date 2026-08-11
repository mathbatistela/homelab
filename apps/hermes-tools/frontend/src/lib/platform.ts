import { useEffect, useState } from "react"

// Minimal typing for the Telegram Mini App WebApp bridge — only what we use.
export interface TelegramWebApp {
  ready(): void
  expand(): void
  close(): void
  sendData(data: string): void
  initData: string
  initDataUnsafe: Record<string, unknown>
  themeParams: Record<string, string>
  colorScheme: "light" | "dark"
  MainButton: {
    show(): void
    hide(): void
    setText(text: string): void
    onClick(cb: () => void): void
    offClick(cb: () => void): void
  }
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp }
  }
}

const TELEGRAM_SDK_URL = "https://telegram.org/js/telegram-web-app.js"

let sdkLoadPromise: Promise<void> | null = null

function loadTelegramSdk(): Promise<void> {
  if (window.Telegram?.WebApp) return Promise.resolve()
  if (sdkLoadPromise) return sdkLoadPromise
  sdkLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script")
    script.src = TELEGRAM_SDK_URL
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error("Falha ao carregar telegram-web-app.js"))
    document.head.appendChild(script)
  })
  return sdkLoadPromise
}

/** `?platform=telegram` is the explicit switch that puts the app in Mini App mode. */
export function isTelegramPlatform(): boolean {
  return new URLSearchParams(window.location.search).get("platform") === "telegram"
}

/** Loads the Telegram SDK and initializes the WebApp bridge only when isTelegramPlatform(). */
export function useTelegram() {
  const [tg, setTg] = useState<TelegramWebApp | null>(null)
  const isTelegram = isTelegramPlatform()

  useEffect(() => {
    if (!isTelegram) return
    let cancelled = false
    loadTelegramSdk()
      .then(() => {
        if (cancelled) return
        const webApp = window.Telegram?.WebApp
        if (!webApp) return
        webApp.ready()
        webApp.expand()
        setTg(webApp)
      })
      .catch((err: unknown) => console.error(err))
    return () => {
      cancelled = true
    }
  }, [isTelegram])

  return { isTelegram, tg }
}
