#!/usr/bin/env python3
"""Bridge local Codex usage and completion events to FoloToy AI Passport."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
HEARTBEAT_SECONDS = 10.0
USAGE_REFRESH_SECONDS = 60.0
TASK_REFRESH_SECONDS = 2.0
USAGE_CACHE_FILE = "ai-passport-usage-cache.json"
SESSION_ACTIVE_LOOKBACK_SECONDS = 2 * 60 * 60


class CodexAppServer:
    """Small JSONL client for the public Codex app-server protocol."""

    def __init__(self, executable: str = "codex") -> None:
        self.executable = executable
        self.process: asyncio.subprocess.Process | None = None
        self.pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.next_id = 1
        self.reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            self.executable,
            "app-server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.reader_task = asyncio.create_task(self._read_stdout())
        await self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "folotoy-ai-passport",
                    "title": "FoloToy AI Passport Codex Bridge",
                    "version": "0.1.0",
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await self.notify("initialized")

    async def close(self) -> None:
        if self.process is not None:
            if self.process.stdin is not None:
                self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.terminate()
                await self.process.wait()
        if self.reader_task is not None:
            await self.reader_task

    async def request(self, method: str, params: Any = None) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self.pending[request_id] = future
        message: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        await self._write(message)
        try:
            response = await asyncio.wait_for(future, timeout=15.0)
        finally:
            self.pending.pop(request_id, None)
        if "error" in response:
            raise RuntimeError(f"Codex app-server error for {method}: {response['error']}")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    async def notify(self, method: str, params: Any = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        await self._write(message)

    async def rate_limits(self) -> dict[str, Any]:
        return normalize_rate_limits(await self.request("account/rateLimits/read"))

    async def running_task_count(self) -> int:
        """Count tasks whose current app-server thread status is active."""
        count = 0
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {
                "limit": 100,
                "archived": False,
                "useStateDbOnly": True,
            }
            if cursor is not None:
                params["cursor"] = cursor
            result = await self.request("thread/list", params)
            threads = result.get("data")
            if not isinstance(threads, list):
                break
            for thread in threads:
                if not isinstance(thread, dict):
                    continue
                status = thread.get("status")
                if (not is_subagent_source(thread.get("source"))
                        and not is_subagent_source(thread.get("threadSource"))
                        and isinstance(status, dict) and status.get("type") == "active"):
                    count += 1
            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        return count

    async def _write(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Codex app-server is not running")
        self.process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
        await self.process.stdin.drain()

    async def _read_stdout(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        while line := await self.process.stdout.readline():
            try:
                message = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            request_id = message.get("id")
            future = self.pending.get(request_id)
            if future is not None and not future.done():
                future.set_result(message)
        for future in self.pending.values():
            if not future.done():
                future.set_exception(RuntimeError("Codex app-server stopped"))


def normalize_rate_limits(response: dict[str, Any]) -> dict[str, Any]:
    """Return the stable, display-safe subset of a rate-limit response."""
    buckets = response.get("rateLimitsByLimitId")
    snapshot = buckets.get("codex") if isinstance(buckets, dict) else None
    if not isinstance(snapshot, dict):
        snapshot = response.get("rateLimits")
    if not isinstance(snapshot, dict):
        snapshot = {}

    def window(name: str) -> dict[str, int]:
        value = snapshot.get(name)
        empty = {"used": 0, "duration": 0, "reset": 0}
        if not isinstance(value, dict) or value.get("usedPercent") is None:
            return empty
        try:
            used = int(value["usedPercent"])
            duration = int(value.get("windowDurationMins") or 0)
            reset = int(value.get("resetsAt") or 0)
        except (ValueError, TypeError, OverflowError):
            return empty
        if duration <= 0:
            return empty
        return {
            "used": min(100, max(0, used)),
            "duration": duration,
            "reset": max(0, reset),
        }

    primary = window("primary")
    secondary = window("secondary")
    return {
        "plan": str(snapshot.get("planType") or "unknown")[:31],
        "primary": primary,
        "secondary": secondary,
        "available": bool(primary["duration"] or secondary["duration"]),
    }


def weekly_usage_window(usage: dict[str, Any]) -> dict[str, int] | None:
    """Find a real 7-day limit by duration, independently of the API slot."""
    if not usage.get("available"):
        return None
    for name in ("primary", "secondary"):
        value = usage.get(name)
        if (isinstance(value, dict) and value.get("duration") == 10080
                and isinstance(value.get("used"), int) and 0 <= value["used"] <= 100):
            return value
    return None


def roll_expired_usage_windows(
    usage: dict[str, Any], now: int | None = None
) -> bool:
    """Advance expired cached windows and clear their previous-period usage."""
    current_time = int(time.time()) if now is None else now
    changed = False
    for name in ("primary", "secondary"):
        window = usage.get(name)
        if not isinstance(window, dict):
            continue
        duration_seconds = max(0, int(window.get("duration", 0))) * 60
        resets_at = max(0, int(window.get("reset", 0)))
        if duration_seconds == 0 or resets_at == 0 or resets_at > current_time:
            continue
        elapsed_cycles = (current_time - resets_at) // duration_seconds + 1
        window["reset"] = resets_at + elapsed_cycles * duration_seconds
        window["used"] = 0
        changed = True
    return changed


def load_cached_usage(path: Path) -> dict[str, Any]:
    """Load the last valid usage snapshot, or return an unavailable snapshot."""
    fallback = normalize_rate_limits({})
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return fallback
    if not isinstance(cached, dict) or cached.get("available") is not True:
        return fallback
    primary = cached.get("primary")
    secondary = cached.get("secondary")
    if not isinstance(primary, dict) or not isinstance(secondary, dict):
        return fallback
    try:
        return {
            "plan": str(cached.get("plan") or "unknown")[:31],
            "primary": {
                "used": min(100, max(0, int(primary.get("used", 0)))),
                "duration": max(0, int(primary.get("duration", 0))),
                "reset": max(0, int(primary.get("reset", 0))),
            },
            "secondary": {
                "used": min(100, max(0, int(secondary.get("used", 0)))),
                "duration": max(0, int(secondary.get("duration", 0))),
                "reset": max(0, int(secondary.get("reset", 0))),
            },
            "available": True,
        }
    except (ValueError, TypeError):
        return fallback


def save_cached_usage(path: Path, usage: dict[str, Any]) -> None:
    """Atomically preserve only successful usage snapshots."""
    if usage.get("available") is not True:
        return
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(usage, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def is_subagent_source(source: Any) -> bool:
    if isinstance(source, str):
        return source.replace("_", "").replace("-", "").lower() == "subagent"
    return isinstance(source, dict) and any(is_subagent_source(key) for key in source)


class SessionWatcher:
    """Observe root-conversation lifecycle records, never message text or phases."""

    def __init__(self, codex_home: Path) -> None:
        self.sessions = codex_home / "sessions"
        self.state_path = codex_home / "ai-passport-bridge-state.json"
        self.offsets: dict[Path, int] = {}
        self.thread_ids: dict[Path, str] = {}
        self.ignored_sessions: set[Path] = set()
        self.active_turns: set[tuple[str, str]] = set()
        self.settled_turns: set[tuple[str, str]] = set()
        self.started_at = time.time()
        self.completion_sequence = self._load_sequence()
        recent_cutoff = self.started_at - SESSION_ACTIVE_LOOKBACK_SECONDS
        for path in self._files():
            try:
                stat = path.stat()
                self.offsets[path] = stat.st_size
                self._read_thread_id(path)
                if path not in self.ignored_sessions and stat.st_mtime >= recent_cutoff:
                    self._prime(path)
            except OSError:
                pass

    @property
    def running_count(self) -> int:
        return len({thread_id for thread_id, _turn_id in self.active_turns})

    @property
    def running(self) -> bool:
        return self.running_count > 0

    def _metadata(self, path: Path, payload: dict[str, Any]) -> None:
        thread_id = payload.get("id")
        if isinstance(thread_id, str) and thread_id:
            self.thread_ids[path] = thread_id
        if is_subagent_source(payload.get("source")):
            self.ignored_sessions.add(path)

    def _read_thread_id(self, path: Path) -> None:
        try:
            with path.open("r", encoding="utf-8") as stream:
                for _index, line in zip(range(32), stream):
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        continue
                    if record.get("type") == "session_meta":
                        payload = record.get("payload")
                        if isinstance(payload, dict):
                            self._metadata(path, payload)
                        return
        except (OSError, UnicodeError, json.JSONDecodeError):
            return

    def _prime(self, path: Path) -> None:
        # Replay recent root-session metadata without alerting. Reading from the
        # start also recovers a long-running turn whose start is far behind EOF.
        self.offsets[path] = 0
        self._read_appended(path, notify=False)

    def _read_appended(self, path: Path, notify: bool) -> bool:
        changed = False
        offset = self.offsets.get(path, 0)
        if path.stat().st_size < offset:
            offset = 0
        with path.open("rb") as stream:
            stream.seek(offset)
            while True:
                raw = stream.readline()
                if not raw or not raw.endswith(b"\n"):
                    break  # retain a partial record for the next poll
                offset = stream.tell()
                try:
                    changed = self._consume(path, raw.decode("utf-8"), historical=not notify) or changed
                except UnicodeError:
                    continue
        self.offsets[path] = offset
        return changed

    def poll(self, notify: bool = True) -> bool:
        changed = False
        for path in self._files():
            try:
                if path not in self.thread_ids:
                    self._read_thread_id(path)
                if path in self.ignored_sessions:
                    continue
                changed = self._read_appended(path, notify) or changed
            except OSError:
                continue
        return changed

    def _consume(self, path: Path, line: str, historical: bool = False) -> bool:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return False
        if not isinstance(record, dict):
            return False
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return False
        if record.get("type") == "session_meta":
            self._metadata(path, payload)
            return False
        if path in self.ignored_sessions or record.get("type") != "event_msg":
            return False
        event_type = payload.get("type")
        turn_id = payload.get("turn_id")
        if event_type not in ("task_started", "task_complete", "turn_aborted", "task_failed", "turn_failed"):
            return False
        if not isinstance(turn_id, str) or not turn_id:
            return False
        root_turn_id = payload.get("root_turn_id")
        if isinstance(root_turn_id, str) and root_turn_id and root_turn_id != turn_id:
            return False
        # A copied/resumed log can be discovered after startup. Its old records
        # rebuild state but must not become new completion notifications.
        stamp = record.get("timestamp")
        if isinstance(stamp, str):
            try:
                date = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                historical = historical or (date.tzinfo is not None and date.timestamp() < self.started_at)
            except ValueError:
                pass
        thread_id = self.thread_ids.get(path, str(path))
        key = (thread_id, turn_id)
        before = self.running_count
        if event_type == "task_started":
            if key not in self.settled_turns:
                self.active_turns.add(key)
        else:
            was_active = key in self.active_turns
            self.active_turns.discard(key)
            self.settled_turns.add(key)
            if event_type == "task_complete" and was_active and not historical:
                self.completion_sequence += 1
                self._save_sequence()
                label = self.thread_ids.get(path, "unknown")[-8:]
                print(f"Conversation task completed: thread={label}, turn={turn_id[-8:]}", flush=True)
                return True
        return self.running_count != before

    def _files(self) -> list[Path]:
        try:
            return sorted(self.sessions.rglob("*.jsonl"))
        except OSError:
            return []

    def _load_sequence(self) -> int:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return max(0, int(value.get("completionSequence", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def _save_sequence(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"completionSequence": self.completion_sequence}) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)


def heartbeat_payload(
    usage: dict[str, Any], watcher: SessionWatcher, running_count: int | None = None,
    completed: bool = False, completion_sequence: int | None = None,
) -> bytes:
    primary = usage.get("primary", {})
    secondary = usage.get("secondary", {})
    if running_count is None:
        running_count = watcher.running_count
    message = "任务已完成" if completed else (
        "助手正在工作" if running_count else "助手已就绪"
    )
    payload = {
        "total": running_count,
        "running": running_count,
        "waiting": 0,
        "msg": message,
        "entries": [],
        "tokens": 0,
        "tokens_today": 0,
        "codex": {
            "plan": usage.get("plan", "unknown"),
            "primary_used": primary.get("used", 0),
            "primary_window": primary.get("duration", 0),
            "primary_reset": primary.get("reset", 0),
            "secondary_used": secondary.get("used", 0),
            "secondary_window": secondary.get("duration", 0),
            "secondary_reset": secondary.get("reset", 0),
            "completion_seq": watcher.completion_sequence if completion_sequence is None else completion_sequence,
            "completion_event": completed,
            "available": bool(usage.get("available")),
        },
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


async def send_payload(client: Any, payload: bytes, *, confirmed: bool = False) -> None:
    characteristic = client.services.get_characteristic(NUS_RX_UUID)
    if characteristic is None:
        raise RuntimeError("Codex Buddy RX characteristic is missing")
    chunk_size = 20 if confirmed else max(20, int(getattr(characteristic, "max_write_without_response_size", 20)))
    for offset in range(0, len(payload), chunk_size):
        await client.write_gatt_char(
            NUS_RX_UUID, payload[offset : offset + chunk_size], response=confirmed
        )


async def send_completion_notifications(client: Any, usage: dict[str, Any],
                                        watcher: SessionWatcher, running_count: int,
                                        previous_sequence: int) -> int:
    last = watcher.completion_sequence
    for sequence in range(previous_sequence + 1, last + 1):
        await send_payload(client, heartbeat_payload(usage, watcher, running_count,
                           completed=True, completion_sequence=sequence), confirmed=True)
        print(f"Completion reminder accepted by device: sequence={sequence}", flush=True)
    return last


async def find_device(device_name: str | None) -> Any:
    from bleak import BleakScanner

    print("Scanning for Codex Buddy…", flush=True)
    devices = await BleakScanner.discover(timeout=8.0, service_uuids=[NUS_SERVICE_UUID])
    for device in devices:
        if device_name and (device.name == device_name or device.address == device_name):
            return device
        if not device_name and (device.name or "").startswith("Codex-"):
            return device
    raise RuntimeError("No Codex-* AI Passport found")


async def bridge_loop(args: argparse.Namespace) -> None:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    usage_cache_path = codex_home / USAGE_CACHE_FILE
    watcher = SessionWatcher(codex_home)
    app_server = CodexAppServer(args.codex)
    await app_server.start()
    try:
        usage = load_cached_usage(usage_cache_path)
        running_count = 0
        try:
            refreshed_usage = await app_server.rate_limits()
            if refreshed_usage.get("available"):
                usage = refreshed_usage
                save_cached_usage(usage_cache_path, usage)
        except Exception as error:
            print(
                f"Codex usage is temporarily unavailable: {error}. Will retry…",
                file=sys.stderr,
                flush=True,
            )
        if roll_expired_usage_windows(usage):
            save_cached_usage(usage_cache_path, usage)
        try:
            running_count = await app_server.running_task_count()
        except Exception as error:
            print(
                f"Codex task count is temporarily unavailable: {error}. Will retry…",
                file=sys.stderr,
                flush=True,
            )
        running_count = max(running_count, watcher.running_count)
        weekly = weekly_usage_window(usage)
        print("用量数据：7天已用=%s%%" % weekly["used"] if weekly is not None
              else "用量数据：7天窗口暂不可用", flush=True)
        print(f"正在进行的任务：{running_count}", flush=True)
        if args.dry_run:
            print(heartbeat_payload(usage, watcher, running_count).decode().rstrip())
            return
        from bleak import BleakClient

        while True:
            try:
                device = await find_device(args.device)
                print(f"Connecting to {device.name or device.address}…", flush=True)
                async with BleakClient(device, pair=True, timeout=60.0) as client:
                    await client.start_notify(NUS_TX_UUID, lambda _sender, _data: None)
                    watcher.poll(notify=False)  # reconnect is a silent baseline
                    previous_sequence = watcher.completion_sequence
                    print("Connected. Codex usage and completion alerts are live.", flush=True)
                    timezone_offset = int(
                        time.mktime(time.localtime()) - time.mktime(time.gmtime())
                    )
                    await send_payload(
                        client,
                        json.dumps({"time": [int(time.time()), timezone_offset]}).encode()
                        + b"\n",
                    )
                    last_heartbeat = 0.0
                    last_usage = 0.0
                    last_task_refresh = 0.0
                    while client.is_connected:
                        changed = watcher.poll()
                        completed = watcher.completion_sequence > previous_sequence
                        now = time.monotonic()
                        if roll_expired_usage_windows(usage):
                            save_cached_usage(usage_cache_path, usage)
                            changed = True
                        if now - last_usage >= USAGE_REFRESH_SECONDS:
                            try:
                                refreshed_usage = await app_server.rate_limits()
                                if refreshed_usage.get("available"):
                                    usage = refreshed_usage
                                    roll_expired_usage_windows(usage)
                                    save_cached_usage(usage_cache_path, usage)
                            except Exception as error:
                                print(
                                    f"Codex usage refresh failed: {error}. Will retry…",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            last_usage = now
                            changed = True
                        if now - last_task_refresh >= TASK_REFRESH_SECONDS:
                            try:
                                refreshed_count = await app_server.running_task_count()
                                refreshed_count = max(
                                    refreshed_count, watcher.running_count
                                )
                                changed = changed or refreshed_count != running_count
                                running_count = refreshed_count
                            except Exception as error:
                                print(
                                    f"Codex task-count refresh failed: {error}. Will retry…",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            last_task_refresh = now
                        if completed:
                            previous_sequence = await send_completion_notifications(
                                client, usage, watcher, running_count, previous_sequence)
                        if changed or now - last_heartbeat >= HEARTBEAT_SECONDS:
                            await send_payload(
                                client,
                                heartbeat_payload(usage, watcher, running_count),
                            )
                            last_heartbeat = now
                        await asyncio.sleep(1.0)
            except Exception as error:  # BLE backend errors vary by operating system.
                print(f"Bridge disconnected: {error}. Retrying…", file=sys.stderr, flush=True)
                await asyncio.sleep(3.0)
    finally:
        await app_server.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show Codex usage and task-completion alerts on FoloToy AI Passport"
    )
    parser.add_argument("--device", help="exact BLE device name or address")
    parser.add_argument("--codex", default="codex", help="path to the Codex CLI executable")
    parser.add_argument(
        "--dry-run", action="store_true", help="print one sanitized payload without using BLE"
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(bridge_loop(parse_args()))
    except KeyboardInterrupt:
        pass
