# FoloToy AI Passport · Codex 用量伙伴

**简体中文** · [English](README.md)

这个固件把 FoloToy AI Passport 变成一个注重隐私的 Codex 桌面伙伴：显示当前
7 天窗口的剩余比例、以单条进度条展示余量、显示正在进行的任务数，并在
每个主会话的一轮任务结束时显示 6 秒钟的 **任务完成提醒**。首页右上角同时显示电量。

上游发布版本：**0.1.0**。本地构建版本：**0.1.0-idle2**。

按 10080 分钟的实际时长识别任一 API 字段中的 7 天窗口；缺少周用量时显示 `--`。
首页与用量详情页均移除 5 小时区域。
本地版本在收到新的 Codex 任务完成事件时播放一次 200 毫秒的
扬声器提示音。音量固定为 50%；重复心跳不会重复播放。
接收消息时也会核对重连后的实时安全链路状态。

## 完成提醒规则

- 每个主会话的一轮任务只提醒一次：`task_complete` 必须匹配已知的 `task_started`，
  并按会话 ID 与任务 ID 去重，包括同一会话的多个日志文件。
- 子代理、嵌套任务、中断或失败、消息的 `final_answer` 阶段、重复结束事件都不触发完成提醒。
- 启动与重连只同步状态，不补响离线期间的历史完成事件。
- 各会话独立提醒；某个会话结束时，其他会话可能还在运行，提示框会显示运行任务数。
- 多个会话同时结束时，分别发送有应答的事件并排队播放，不合并成一次提醒。

桥接与固件应使用本分支的配套版本。只有显式的 `codex.completion_event=true`
加上新的序号才触发提示和声音，普通心跳只同步序号。旧桥接不带此标记时可显示用量，但不会提醒完成。

## 源码与开发

本应用在 [`r2space/ai-passport` 的 `codex/usage-buddy` 分支](https://github.com/r2space/ai-passport/tree/codex/usage-buddy)
维护，基于 [`zt20/codex-usage-ai-passport`](https://github.com/zt20/codex-usage-ai-passport)
的 `6b6b979d2b9df3e9f6f105445b35c626a38fcce1`。

```bash
git clone --branch codex/usage-buddy https://github.com/r2space/ai-passport.git codex-usage-ai-passport
cd codex-usage-ai-passport
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-codex-bridge.txt
.venv/bin/python tools/codex_bridge.py
```

固件使用本分支源码与 ESP-IDF 5.5.3 构建；主机测试命令见英文说明。
macOS 可用 `tools/run-codex-bridge.command` 从同一 `.venv` 启动，不安装登录服务。
`dependencies.lock` 纳入版本管理，构建产物、虚拟环境与日志留在本地。
[踩坑记录](docs/reference/r2space/ble-completion-sound-lessons.zh_CN.md)。

## 上游原版下载参考

下列 v0.1.0 发布包不含本分支的周窗口、提示音和蓝牙修复，请使用本分支构建的固件与桥接源码。

- [下载小助手固件和 macOS 桥接程序](https://github.com/zt20/codex-usage-ai-passport/releases/tag/v0.1.0)
- [查看完整中文安装、蓝牙配对与排障说明](docs/codex-usage-installation.zh_CN.md)

本功能必须同时安装小助手固件和电脑桥接程序。Type-C 只用于刷固件；日常用量、
任务数与完成提醒都由电脑桥接程序通过加密蓝牙同步。

实现基于仓库的 `demo/claude-buddy-port` 参考分支，保留了有界状态机、像素 UI、
加密 Nordic UART BLE、绑定与自动重连。新增的本机桥接器负责把 Codex 数据转换成
设备协议。

## 数据流与隐私

```text
Codex app-server ── 限额快照 ───────────┐
                                        ├─ 本机 Python 桥 ── 加密 BLE ── Passport
~/.codex/sessions ─ 消息元数据 ─────────┘
```

桥接器通过本机 Codex app-server 调用 `account/rateLimits/read`。为了识别任务开始和
`final_answer`，它只读取本地 JSONL 记录的类型、角色与阶段，不会把提示词或回答
正文发送到设备，也不会读取或复制 Codex 登录令牌。

Codex 返回的是已用百分比而不是绝对消息数，所以设备显示
`剩余 = 100 - usedPercent`。如果接口在窗口重置时暂时不可用，桥接器会先切换到
下一个周期并在恢复连接后校准；如果从未取得过快照，界面会明确显示不可用。

## 编译与烧录

使用 ESP-IDF 5.5.3，目标芯片为 ESP32-C3：

```bash
get_idf553
idf.py set-target esp32c3
idf.py build
idf.py flash monitor
```

设备名为 `Codex-<MAC 后缀>`。首次加密连接时 Passport 会显示六位配对码，请在
操作系统的蓝牙配对窗口中输入。

## 运行本机桥接器

普通用户请从发布页下载 `Codex-Bridge-macOS-v0.1.0.zip`，解压后右键打开
`macOS/install.command`；安装器会立即启动桥接程序并设置登录后自动运行。

开发者也可以从源码手动运行。请先安装并登录 Codex CLI，建议使用 Python 3.10
或更高版本：

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-codex-bridge.txt
.venv/bin/python tools/codex_bridge.py
```

常用选项：

```bash
# 不使用蓝牙，只验证本机 Codex 用量数据。
python3 tools/codex_bridge.py --dry-run

# 周围有多台设备时指定设备。
python3 tools/codex_bridge.py --device Codex-A1B2C3
```

桥接器每 60 秒刷新一次用量、每 2 秒刷新任务数、每 10 秒发送一次心跳，BLE
中断后会自动重连；按 `Ctrl+C` 停止。

## 按键

- `UP`：在首页、用量页、信息页之间切换。
- `DOWN`：滚动或切换子页面。
- 长按 `OK`：打开菜单。
- Settings → Unpair：经设备端确认后删除 BLE 绑定。

## 待机省电

10 秒没有有效事件后，关闭背光和面板显示，并暂停应用界面刷新。任务数量、
每周用量、待确认事项、连接状态发生变化，收到新完成提醒或按键时，重新亮屏
10 秒。时钟、Token 数更新和内容不变的心跳不会唤醒。熄屏后的第一次按键只
唤醒，不能确认隐藏的请求或操作隐藏的菜单。

音频工作任务在响铃前唤醒 ES8311，以 200 ms 静音预热，播放后校验芯片与 I2S
待机；开机尚未播放时也进入待机。CPU 使用 40–160 MHz 动态降频，蓝牙控制器使用主晶振进行
modem sleep。需要及时接收 BLE 提醒时，关闭整机自动轻睡和深睡。唤醒先恢复
面板再开背光，运行中熄屏不调用深睡专用接口。配对、每周用量和 50% 提示音
保持不变；实际电流和续航改善需要仪器测量。

## 测试

```bash
get_idf553
cmake -S tests -B build-host
cmake --build build-host
ctest --test-dir build-host --output-on-failure
python3 -m unittest tests/test_codex_bridge.py
```

固件编译成功不等于真机验收。真机还需分别验证配对、两个用量窗口、重置倒计时、
运行/就绪状态、完成庆祝提示、断线重连、电池显示和 BLE 长连接稳定性。

## 归属

BLE 与 Buddy 应用基础来自本仓库的 `demo/claude-buddy-port` 分支；该分支记录了与
Anthropic 公开 Hardware Buddy 协议的兼容关系。归属信息见 [NOTICE](NOTICE)。
本 Codex 扩展与桥接器不是 OpenAI 官方硬件集成。
