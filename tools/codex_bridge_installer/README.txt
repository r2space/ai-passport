Codex 使用量桥接程序（macOS）
================================

用途
----
把本机 Codex 的 5 小时/7 天使用量、正在进行的任务数和回答完成事件，
通过蓝牙发送到已经刷入“Codex 使用量”固件的 FoloToy AI Passport。

安装前
------
1. 已安装并登录 Codex CLI。
2. 已安装 Python 3.10 或更高版本。
3. 电脑蓝牙已开启。
4. AI Passport 已刷入 Codex 使用量固件并保持开机。

安装
----
打开 macOS 文件夹，右键点击“install.command”，选择“打开”。

如果 macOS 阻止首次运行：
右键点击 install.command → 打开 → 再次点击“打开”。

首次连接
--------
1. 安装完成后，桥接程序会扫描名称以 Codex- 开头的设备。
2. AI Passport 会显示六位配对码。
3. 在 macOS 蓝牙配对提示中输入该配对码。
4. 屏幕顶部显示“已连接”后，用量会在约一分钟内出现。

管理
----
- 查看状态和日志：双击“status.command”。
- 重新安装或修复：再次双击“install.command”。
- 卸载：双击“uninstall.command”，按提示输入 YES。

隐私
----
桥接程序只读取本机 Codex 的限额状态和任务事件元数据，不会把提示词、
回答正文或 Codex 登录令牌发送到 AI Passport。

完整说明
--------
https://github.com/zt20/codex-usage-ai-passport/blob/main/docs/codex-usage-installation.zh_CN.md
