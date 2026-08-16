# omp-status-bar

Oh My Posh theme + OpenCode Go usage display for Oh My Pi / OpenCode.

## Components

### 1. Oh My Posh Theme — `opencode-go.omp.json`

A minimal prompt theme with two blocks:

- **Left prompt**: OS icon, working directory, Git branch, exit status.
- **Right prompt**: OpenCode Go usage (via `cmd "opencode-go-usage"`), current time.

Rendered with a Tokyo Night–inspired palette over powerline segments.

### 2. Usage Fetcher — `opencode-go-usage.py`

Fetches the current OpenCode Go subscription usage from `https://opencode.ai/zen/go/v1/usage` and prints a single line:

```
OpenCode Go 5h 57% · 7d 36% · 30d 18% used
```

**Cache-first**: displays the last known value immediately and spawns a background
process to refresh stale data — the prompt never blocks on a fetch.

**API key**: reads from `~/.local/share/opencode/auth.json` (OpenCode's own
credential store) or `OPENCODE_GO_API_KEY` / `OPENCODE_GO_API_KEY` env var.

**Flags**:

| Flag | Effect |
|---|---|
| `--short` | Compact format: `OpenCode Go 5h 57% / 7d 36% / 30d 18% used` |
| `--json` | Raw JSON for debugging |
| `--no-cache` | Force synchronous fetch, bypass cache |

**Env vars**:

| Variable | Default | Description |
|---|---|---|
| `OPENCODE_GO_API_KEY` | (auth.json) | API key override |
| `OPENCODE_AUTH_FILE` | `~/.local/share/opencode/auth.json` | Auth file path |
| `OPENCODE_GO_USAGE_URL` | `https://opencode.ai/zen/go/v1/usage` | Usage endpoint |
| `OPENCODE_GO_USAGE_TTL` | `300` | Cache freshness (seconds) |
| `OPENCODE_GO_USAGE_TIMEOUT` | `3` | HTTP timeout (seconds) |

### 3. OpenCode TUI Plugin — `opencode-go-usage.tui.tsx`

Registers an OpenCode TUI plugin that renders OpenCode Go usage in the
`session_prompt_right` / `home_prompt_right` slots — the status line above the
input box. Refreshes every 5 minutes by default, configurable via
`OPENCODE_GO_USAGE_TUI_INTERVAL` (ms).

**Env vars**:

| Variable | Description |
|---|---|
| `OPENCODE_GO_USAGE_TUI_CMD` | Override the command run to fetch usage |
| `OPENCODE_GO_USAGE_TUI_INTERVAL` | Refresh interval in ms (default: 300000) |

### 4. Oh My Pi Extension — `.omp/extensions/go-usage.ts`

Oh My Pi harness extension that calls `opencode-go-usage.py --short` and
displays the result in the harness status bar via `ctx.ui.setStatus("go", …)`.
Refreshes on every turn end and every 5 minutes.

## File Layout

```
.
├── opencode-go.omp.json          # Oh My Posh theme
├── opencode-go-usage.py          # Usage fetcher (Python)
├── opencode-go-usage.tui.tsx     # OpenCode TUI plugin
└── .omp/
    └── extensions/
        └── go-usage.ts           # Oh My Pi extension
```

## Quick Start

### Oh My Posh

1. Symlink or copy the theme:
   ```bash
   cp opencode-go.omp.json ~/.poshthemes/
   ```
2. Set it in your shell config:
   ```bash
   eval "$(oh-my-posh init zsh --config ~/.poshthemes/opencode-go.omp.json)"
   ```
3. Ensure `opencode-go-usage` is in `PATH`.

### Oh My Pi Extension

Place `.omp/extensions/go-usage.ts` inside a project that has Oh My Pi
harness running. The extension auto-registers and displays OpenCode Go usage in the
status bar.

### OpenCode TUI Plugin

Place `opencode-go-usage.tui.tsx` in OpenCode's plugin directory and
enable it in the TUI config.