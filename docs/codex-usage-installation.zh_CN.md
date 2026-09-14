# Codex 使用量小助手完整安装说明

“Codex 使用量”由两部分组成，二者缺一不可：

1. **小助手固件**：负责全屏显示用量进度条、剩余时间、正在进行的任务数、电量和任务完成提示。
2. **电脑桥接程序**：读取本机 Codex 的用量与任务状态，再通过加密蓝牙发送给小助手。

Type-C 只在刷固件时使用。安装完成后，日常同步不走数据线，电脑与小助手之间通过蓝牙连接。

## 一、准备工作

- FoloToy AI Passport 小助手和一根可传输数据的 Type-C 线。
- macOS 电脑，开启蓝牙并允许 Python 使用蓝牙。
- Python 3.10 或更高版本。
- 已安装并登录 Codex CLI。

没有新版 Python 时，可从 [Python 官方网站](https://www.python.org/downloads/macos/) 下载并安装。

如果还没有 Codex CLI，可在终端执行：

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex login
codex login status
```

Codex 的安装和登录方式以 [OpenAI 官方 Codex CLI 文档](https://learn.chatgpt.com/docs/codex/cli) 为准。

## 二、给小助手刷入固件

### 方法 A：从 FoloToy 社区安装

项目审核通过后，在 [FoloToy AI Passport 社区](https://ai-passport.folotoy.cn/plays/) 搜索“Codex 使用量”，按页面提示连接小助手并刷入。

### 方法 B：使用 GitHub 固件文件

1. 打开 [v0.1.0 发布页](https://github.com/zt20/codex-usage-ai-passport/releases/tag/v0.1.0)。
2. 下载 `Codex-Usage-Buddy-v0.1.0-full-0x0.bin`。
3. 打开 [FoloToy 网页刷机工具](https://ai-passport.folotoy.cn/tools/web-flasher/)。
4. 用 Type-C 连接小助手，选择下载的固件；手动选择地址时使用 `0x0`。
5. 等待刷写和重启完成，再拔掉 Type-C 线。

刷机过程中不要拔线或关闭浏览器。浏览器没有发现设备时，请换一根确认支持数据传输的 Type-C 线，并关闭占用串口的软件。

## 三、在 Mac 安装桥接程序

1. 在 [v0.1.0 发布页](https://github.com/zt20/codex-usage-ai-passport/releases/tag/v0.1.0) 下载 `Codex-Bridge-macOS-v0.1.0.zip`。
2. 双击解压 ZIP，打开 `Codex-Bridge-macOS-v0.1.0/macos` 文件夹。
3. 右键点击 `install.command`，选择“打开”，然后再次确认“打开”。
4. 安装器会创建独立环境、安装依赖并启动桥接程序，以后每次登录 Mac 都会自动运行。

如果 macOS 没有拦截，也可以直接双击 `install.command`。安装后无需一直打开终端窗口。

桥接程序安装在：

```text
~/Library/Application Support/CodexUsageBridge
```

运行日志位于：

```text
~/Library/Logs/CodexUsageBridge/bridge.log
```

## 四、首次蓝牙配对

1. 打开小助手和 Mac 蓝牙。
2. 桥接程序会自动扫描名称以 `Codex-` 开头的小助手。
3. 小助手屏幕会显示六位配对码。
4. 在 macOS 的蓝牙提示中确认或输入相同配对码。
5. 连接成功后，屏幕会显示 Codex 5 小时与 7 天窗口的剩余量、重置时间和正在进行的任务数。

首次取得用量通常需要几十秒，之后用量每 60 秒刷新，任务数每 2 秒刷新。Codex 生成最终回答后，小助手会显示约 6 秒的“任务已完成”提示。

## 五、查看状态、修复和卸载

- 查看桥接状态和最近日志：双击 `status.command`。
- 修复或升级桥接程序：重新双击 `install.command`。
- 卸载桥接程序：双击 `uninstall.command`，输入 `YES` 确认。

卸载不会删除日志；如不再需要，可自行删除 `~/Library/Logs/CodexUsageBridge`。

## 六、常见问题

### 小助手显示“暂未获取使用量”

1. 双击 `status.command`，确认状态不是“未运行”。
2. 在终端执行 `codex login status`，确认 Codex 已登录。
3. 确认 Mac 蓝牙已开启，系统设置中已经配对 `Codex-XXXXXX`。
4. 重新运行 `install.command`，然后重启小助手。

### 首次配对没有弹窗或总是重连

在 Mac 蓝牙设置中忽略原来的 `Codex-XXXXXX`；再在小助手设置中执行“取消配对”，随后重新运行安装器完成配对。附近有多台 Codex 小助手时，请暂时关闭其他设备。

### 用量已经重置，但进度条暂时没有恢复

桥接程序每 60 秒获取一次最新限额。先等待一分钟；如果仍未恢复，查看日志并确认 Codex 登录有效，然后重新安装桥接程序。

### 右上角电量显示 `--`

电量来自小助手自身的电池检测，不是电脑桥接程序提供。请让设备充电片刻并重启；若仍显示 `--`，需要检查硬件版本与电池检测驱动。

### 没有任务完成提醒

保持桥接程序运行，并使用同一台 Mac 上的 Codex。桥接程序只根据本机 Codex 任务事件发送提醒，不会读取其他电脑或云端设备上的任务。

## 七、隐私说明

桥接程序只把用量百分比、重置时间、任务数量和完成事件发送给已经配对的小助手。它不会把提示词、回答正文或 Codex 登录令牌发送到设备。

本项目是社区扩展，并非 OpenAI 官方硬件集成。
