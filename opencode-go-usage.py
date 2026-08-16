#!/usr/bin/env python3
"""OpenCode Go usage for Oh My Posh.

Prints the OpenCode Go subscription usage as a single line for the OMP
prompt, e.g.:

    OpenCode Go 5h 57% · 7d 36% · 30d 18% used

The data comes from the official endpoint used by the OpenCode Go console:

    https://opencode.ai/zen/go/v1/usage

The API key is read from OpenCode's own credential store
(~/.local/share/opencode/auth.json) so it never needs to live in the OMP
theme. A cache file is used so the prompt stays fast: when the cache is
stale, the stale value is printed immediately and a background process
refreshes it.

Environment variables:
    OPENCODE_GO_API_KEY    override the opencode-go API key
    OPENCODE_AUTH_FILE     override the auth.json location
    OPENCODE_GO_USAGE_URL  override the usage endpoint
    OPENCODE_GO_USAGE_TTL  cache freshness in seconds (default: 300)
    OPENCODE_GO_USAGE_TIMEOUT  HTTP timeout in seconds (default: 3)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

USAGE_URL = os.environ.get(
    "OPENCODE_GO_USAGE_URL", "https://opencode.ai/zen/go/v1/usage"
)
CACHE_TTL = float(os.environ.get("OPENCODE_GO_USAGE_TTL", "300"))
HTTP_TIMEOUT = float(os.environ.get("OPENCODE_GO_USAGE_TIMEOUT", "3"))
STALE_LOCK_AGE = 120  # seconds after which a leftover refresh lock is ignored

WINDOWS = (
    ("5h", "rolling"),
    ("7d", "weekly"),
    ("30d", "monthly"),
)


def data_home() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".local" / "share"


def auth_file() -> Path:
    override = os.environ.get("OPENCODE_AUTH_FILE")
    if override:
        return Path(override).expanduser()
    return data_home() / "opencode" / "auth.json"


def cache_file() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "opencode-go-usage.json"


def read_api_key() -> str | None:
    key = os.environ.get("OPENCODE_GO_APIKEY") or os.environ.get(
        "OPENCODE_GO_API_KEY"
    )
    if key:
        return key.strip()

    path = auth_file()
    try:
        with path.open("r", encoding="utf-8") as f:
            auth = json.load(f)
    except (OSError, ValueError):
        return None

    entry = auth.get("opencode-go") or auth.get("opencode_go")
    if isinstance(entry, dict):
        key = entry.get("key") or entry.get("apiKey")
        if isinstance(key, str):
            return key.strip()
    return None


def load_cache() -> dict | None:
    try:
        with cache_file().open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("usage"), dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def save_cache(payload: dict) -> None:
    path = cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fetch_usage() -> dict:
    key = read_api_key()
    if not key:
        raise RuntimeError("no opencode-go API key found in auth.json")

    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "opencode-go-usage/1.0 (oh-my-posh)",
        },
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("unexpected usage payload")

    for _, key in WINDOWS:
        window = usage.get(key)
        if not isinstance(window, dict) or not isinstance(
            window.get("percent"), (int, float)
        ):
            raise ValueError(f"usage payload is missing '{key}.percent'")

    payload["_fetched"] = time.time()
    return payload


def fetch_and_store() -> None:
    """Used by both the foreground (cold cache) and background refresh."""
    try:
        save_cache(fetch_usage())
    except Exception:
        pass


def format_text(usage: dict, short: bool = False) -> str:
    parts = []
    for label, key in WINDOWS:
        window = usage[key]
        percent = window.get("percent")
        try:
            percent = int(round(float(percent)))
        except (TypeError, ValueError):
            percent = "?"
        parts.append(f"{label} {percent}%")

    separator = " / " if short else " · "
    return "OpenCode Go " + separator.join(parts) + " used"


def lock_path() -> Path:
    return cache_file().with_name(cache_file().name + ".refresh.lock")


def acquire_lock() -> bool:
    """Atomically claim the background-refresh lock."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            stale = time.time() - path.stat().st_mtime > STALE_LOCK_AGE
        except OSError:
            stale = False
        if stale:
            try:
                path.unlink()
            except OSError:
                return False
            return acquire_lock()
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def release_lock() -> None:
    try:
        lock_path().unlink()
    except OSError:
        pass


def start_background_refresh() -> bool:
    if not acquire_lock():
        return False
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--refresh-only"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return True
    except OSError:
        release_lock()
        return False


def run_refresh_only() -> int:
    try:
        fetch_and_store()
    finally:
        release_lock()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print OpenCode Go usage for an Oh My Posh segment"
    )
    parser.add_argument(
        "--short", action="store_true", help="compact '5h 12%% / ...' output"
    )
    parser.add_argument(
        "--json", action="store_true", help="print the raw usage JSON"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="fetch synchronously, bypass cache"
    )
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if args.refresh_only:
        return run_refresh_only()

    cache = load_cache()

    if not args.no_cache and cache is not None:
        age = time.time() - float(cache.get("_fetched", 0))
        if age < CACHE_TTL:
            usage = cache["usage"]
        else:
            # Stale: serve the last known value instantly and refresh in the
            # background. If that fails, nothing is lost.
            start_background_refresh()
            usage = cache["usage"]
    else:
        try:
            cache = fetch_usage()
            save_cache(cache)
        except Exception:
            cache = load_cache()
        usage = cache["usage"] if cache else None

    if usage is None:
        print("OpenCode Go ?")
        return 0

    if args.json:
        json.dump(usage, sys.stdout, indent=2)
        print()
        return 0

    print(format_text(usage, short=args.short))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
