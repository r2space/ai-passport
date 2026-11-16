<p align="right">
  <strong>简体中文</strong> · <a href="ble-completion-sound-lessons.md">English</a>
</p>

# BLE 任务提醒与提示音：踩坑记录

背景：在无 PSRAM 的 ESP32-C3 上给 Codex Usage Buddy 加完成提示音，记录截至本地
`0.1.0-sound8`（2026-11-16）。应用基于[此源码版本](https://github.com/zt20/codex-usage-ai-passport/tree/6b6b979d2b9df3e9f6f105445b35c626a38fcce1)。

1. **先读已有经验，固定依赖。** 硬件试验前先查 `docs/reference/`。使用 ESP-IDF
   5.5.3，本应用固定 LVGL 9.5.0；首次构建时，浮动依赖选中了 9.6，实际内存配置也发生了变化。
2. **白闪、未连接都要用日志判断。** 触发提醒前开始采集 USB Serial/JTAG，使用
   IDF Monitor 的 `--no-reset` 并记录实际是否复位；崩溃地址必须用身份匹配的 ELF
   解码。USB 重新枚举可能中断采集，要同时看电脑端 BLE 连接事件。
3. **小功能也会耗尽任务栈。** 日志确认 `buddy_sound` 和 `nimble_host` 栈异常，
   分别从 3072 调至 4096 字节、4096 调至 6144 字节；后续播放时音频栈剩余约
   876 字节。这是本应用的实测配置，并非板卡通用值；增大栈也会挤占共享 RAM。
4. **连上不代表消息被接受。** 受保护的读取成功，带应答写入却返回 ATT 错误 15。
   修复是在接收时用 NimBLE 的当前连接状态同步安全状态缓存，仍要求加密、认证、
   已配对和 16 字节密钥。排查时用带应答写入；无应答写入调用成功不能证明设备接收成功。
5. **播放交给独立任务，听感由人确认。** 使用 16 kHz、16 位单声道 PCM、200 毫秒
   柔和波形与短渐变。BSP 的六个 240 帧 DMA 缓冲最多积压 90 毫秒音频，静音前等待
   100 毫秒。用户在驱动音量 60% 时确认听到，随后要求调至 50%；播放日志不能代替试听。
6. **保留设置前先核对布局。** 本次确认分区表未变，只写 `0x10000` 应用区，保留
   NVS 和配对。合并镜像从 `0x0` 写入可能覆盖设置，全片擦除不应成为常规重试手段。
7. **试听要短，时机要明确。** 保持同一条桥接连接，每次只发一个新完成事件，并确认
   重复心跳不重播。准备好再倒数三秒，触发后立即告诉用户听接下来 1～2 秒，反馈后再
   分析日志。本次把试听扩成反复重连实验，拖长了耗时，也让用户不知道什么时候该听。

验证边界：固件与镜像校验、19 项主机测试通过；修复后的短时连接、重连与播放观察未捕获
崩溃。50% 音量已刷入，听感验收、长期稳定性及续航影响仍待确认。

相关：[BLE 空闲与观察陷阱](https://github.com/FoloToy/ai-passport/blob/main/docs/reference/shinku-chen/ble-active-idle-power.zh_CN.md)、
[音频资源归属与内存预算](https://github.com/FoloToy/ai-passport/blob/main/docs/reference/phoenixzhc/network-audio-streaming-and-memory.zh_CN.md)。
