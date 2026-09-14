#!/bin/bash

set -euo pipefail

BRIDGE_ROOT="$HOME/Library/Application Support/CodexUsageBridge"
PLIST_PATH="$HOME/Library/LaunchAgents/com.folotoy.ai-passport-codex-bridge.plist"
LABEL="com.folotoy.ai-passport-codex-bridge"
USER_DOMAIN="gui/$(id -u)"

echo "即将停止并卸载 Codex 使用量桥接程序。"
read -r -p "输入 YES 确认卸载：" CONFIRMATION
if [[ "$CONFIRMATION" != "YES" ]]; then
    echo "已取消。"
    exit 0
fi

launchctl bootout "$USER_DOMAIN" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"
if [[ -d "$BRIDGE_ROOT" && "$BRIDGE_ROOT" == "$HOME/Library/Application Support/CodexUsageBridge" ]]; then
    rm -rf "$BRIDGE_ROOT"
fi

echo "卸载完成。日志仍保留在：$HOME/Library/Logs/CodexUsageBridge"
read -r -p "按回车键关闭…"
