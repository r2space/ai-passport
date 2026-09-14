#!/bin/bash

set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRIDGE_ROOT="$HOME/Library/Application Support/CodexUsageBridge"
VENV_DIR="$BRIDGE_ROOT/venv"
LOG_DIR="$HOME/Library/Logs/CodexUsageBridge"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/com.folotoy.ai-passport-codex-bridge.plist"
LABEL="com.folotoy.ai-passport-codex-bridge"
USER_DOMAIN="gui/$(id -u)"

echo "Codex 使用量桥接程序安装器"
echo "--------------------------------"

PYTHON_BIN=""
for candidate in "$(command -v python3 || true)" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [[ -n "$candidate" && -x "$candidate" ]] && \
        "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' \
        >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "未找到 Python 3.10 或更高版本。请先安装新版 Python。"
    read -r -p "按回车键退出…"
    exit 1
fi

CODEX_BIN="$(command -v codex || true)"
if [[ -z "$CODEX_BIN" ]]; then
    for candidate in /opt/homebrew/bin/codex /usr/local/bin/codex "$HOME/.local/bin/codex"; do
        if [[ -x "$candidate" ]]; then
            CODEX_BIN="$candidate"
            break
        fi
    done
fi

if [[ -z "$CODEX_BIN" ]]; then
    echo "未找到 Codex CLI。请先安装并登录 Codex CLI，然后重新运行本安装器。"
    read -r -p "按回车键退出…"
    exit 1
fi

mkdir -p "$BRIDGE_ROOT" "$LOG_DIR" "$LAUNCH_AGENTS_DIR"
cp "$PACKAGE_DIR/codex_bridge.py" "$BRIDGE_ROOT/codex_bridge.py"
cp "$PACKAGE_DIR/requirements-codex-bridge.txt" "$BRIDGE_ROOT/requirements-codex-bridge.txt"

echo "正在创建独立 Python 环境…"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --quiet --upgrade pip
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --quiet \
    -r "$BRIDGE_ROOT/requirements-codex-bridge.txt"

export BRIDGE_ROOT VENV_DIR LOG_DIR PLIST_PATH CODEX_BIN LABEL
"$VENV_DIR/bin/python" - <<'PY'
import os
import plistlib
from pathlib import Path

payload = {
    "Label": os.environ["LABEL"],
    "ProgramArguments": [
        str(Path(os.environ["VENV_DIR"]) / "bin" / "python"),
        "-u",
        str(Path(os.environ["BRIDGE_ROOT"]) / "codex_bridge.py"),
        "--codex",
        os.environ["CODEX_BIN"],
    ],
    "WorkingDirectory": os.environ["BRIDGE_ROOT"],
    "RunAtLoad": True,
    "KeepAlive": True,
    "ProcessType": "Interactive",
    "StandardOutPath": str(Path(os.environ["LOG_DIR"]) / "bridge.log"),
    "StandardErrorPath": str(Path(os.environ["LOG_DIR"]) / "bridge.log"),
}
with Path(os.environ["PLIST_PATH"]).open("wb") as stream:
    plistlib.dump(payload, stream)
PY

launchctl bootout "$USER_DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "$USER_DOMAIN" "$PLIST_PATH"
launchctl kickstart -k "$USER_DOMAIN/$LABEL"

echo
echo "安装完成，桥接程序已经启动并会随登录自动运行。"
echo "请保持电脑蓝牙开启，并在首次弹窗中完成 Codex-* 设备配对。"
echo "日志：$LOG_DIR/bridge.log"
echo
read -r -p "按回车键关闭…"
