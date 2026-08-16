import { join } from "node:path"
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent"

const STATUS_KEY = "go"
const REFRESH_MS = 5 * 60 * 1000

function parseCommand(): string[] {
  const raw = process.env.OPENCODE_GO_USAGE_TUI_CMD?.trim()
  if (raw) return raw.split(/\s+/)
  const dir =
    "dir" in import.meta && typeof import.meta.dir === "string"
      ? import.meta.dir
      : undefined
  if (dir) {
    const python = process.env.OPENCODE_GO_USAGE_PYTHON ?? "python3"
    return [python, join(dir, "..", "..", "opencode-go-usage.py"), "--short"]
  }
  return ["opencode-go-usage", "--short"]
}

async function fetchUsage(): Promise<string | null> {
  const proc = Bun.spawn(parseCommand(), {
    stdout: "pipe",
    stderr: "pipe",
    env: { ...process.env },
  })
  const text = (await new Response(proc.stdout).text()).trim()
  const exitCode = await proc.exited
  return exitCode === 0 && text ? text : null
}

export default function opencodeGoUsage(pi: ExtensionAPI): void {
  pi.setLabel("OpenCode Go usage")
  let current = "Go ?"

  async function refresh(ctx: ExtensionContext): Promise<void> {
    try {
      const text = await fetchUsage()
      if (text) current = text
    } catch {
      // Keep the last known value; the status bar must never block on a fetch.
    }
    ctx.ui.setStatus(STATUS_KEY, current)
  }

  function start(ctx: ExtensionContext): void {
    void refresh(ctx)
    ctx.setInterval(() => {
      void refresh(ctx)
    }, REFRESH_MS)
  }

  pi.on("session_start", (_event, ctx) => start(ctx))
  pi.on("session_switch", (_event, ctx) => start(ctx))
  pi.on("turn_end", (_event, ctx) => {
    void refresh(ctx)
  })
}
