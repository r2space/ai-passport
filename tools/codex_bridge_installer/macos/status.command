#!/bin/bash

set -u

LABEL="com.folotoy.ai-passport-codex-bridge"
USER_DOMAIN="gui/$(id -u)"
LOG_PATH="$HOME/Library/Logs/CodexUsageBridge/bridge.log"

echo "Codex 使用量桥接程序状态"
echo "--------------------------------"
if launchctl print "$USER_DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "状态：已安装并正在由系统管理"
    launchctl print "$USER_DOMAIN/$LABEL" | awk '/state =|pid =|runs =|last exit code =/ {print}'
else
    echo "状态：未运行"
fi

echo
echo "最近日志："
if [[ -f "$LOG_PATH" ]]; then
    tail -n 30 "$LOG_PATH"
else
    echo "尚未生成日志。"
fi

echo
read -r -p "按回车键关闭…"
