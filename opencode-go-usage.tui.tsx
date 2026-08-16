/** @jsxImportSource @opentui/solid */
import { createSignal } from "solid-js"

/**
 * OpenCode TUI plugin that puts the opencode-go usage on the prompt status
 * line (the row above the input box that already shows agent > model and,
 * on the next row, workspace > context window).
 *
 * OpenCode's built-in status row has no text hook, but the TUI plugin API
 * exposes the `session_prompt_right` / `home_prompt_right` slots. We render
 * into those slots so the usage appears on the same status line.
 */

const DEFAULT_INTERVAL_MS = 5 * 60 * 1000

function defaultCommand() {
  const dir = (import.meta as any).dir
  if (dir) {
    const python = process.env.OPENCODE_GO_USAGE_PYTHON ?? "python3"
    return [python, `${dir}/opencode-go-usage.py`, "--short"]
  }
  return ["opencode-go-usage", "--short"]
}

function parseCommand() {
  const raw = process.env.OPENCODE_GO_USAGE_TUI_CMD?.trim()
  if (raw) return raw.split(/\s+/)
  return defaultCommand()
}

function parseInterval() {
  const raw = process.env.OPENCODE_GO_USAGE_TUI_INTERVAL
  const value = raw ? Number(raw) : NaN
  return Number.isFinite(value) && value > 0 ? value : DEFAULT_INTERVAL_MS
}

export default {
  id: "opencode-go-usage",
  tui: async (api: any, _options: any) => {
    const command = parseCommand()
    const interval = parseInterval()
    const [usage, setUsage] = createSignal("OpenCode Go ?")
    let timer: any

    const refresh = async () => {
      try {
        const proc = Bun.spawn(command, {
          stdout: "pipe",
          stderr: "pipe",
          env: { ...process.env },
        })
        const text = (await new Response(proc.stdout).text()).trim()
        const exitCode = await proc.exited
        if (exitCode === 0 && text) setUsage(text)
      } catch (_error) {
        // Keep the last known value. The prompt must never block on a fetch.
      }
    }

    void refresh()
    timer = setInterval(() => {
      void refresh()
    }, interval)
    api.lifecycle.onDispose(() => {
      clearInterval(timer)
    })

    const render = (ctx: any, _value: any) => (
      <text fg={ctx.theme.current?.textMuted ?? "#a5a5a5"} wrapMode="none">
        {usage()}
      </text>
    )

    api.slots.register({
      slots: {
        session_prompt_right: render,
        home_prompt_right: render,
      },
    })
  },
}
