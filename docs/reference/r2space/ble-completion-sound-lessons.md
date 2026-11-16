<p align="right">
  <a href="ble-completion-sound-lessons.zh_CN.md">简体中文</a> · <strong>English</strong>
</p>

# BLE Completion Alerts and Sound: Lessons Learned

Context: adding a completion tone to Codex Usage Buddy on an ESP32-C3 without
PSRAM, through local build `0.1.0-sound8` (2026-11-16). The application baseline
is [this source revision](https://github.com/zt20/codex-usage-ai-passport/tree/6b6b979d2b9df3e9f6f105445b35c626a38fcce1).

1. **Read existing experience and pin dependencies first.** Consult
   `docs/reference/` before hardware experiments. Use ESP-IDF 5.5.3; pin LVGL to
   9.5.0 for this application. The floating range selected 9.6 and changed the
   effective memory configuration during our first build.
2. **A white flash or an offline screen needs evidence.** Capture USB
   Serial/JTAG output before triggering the alert; use IDF Monitor's
   `--no-reset` and record any actual reset. Match the panic's ELF identity
   before decoding. USB re-enumeration can interrupt capture, so also inspect
   the computer-side BLE connection events.
3. **A small feature can exhaust a task stack.** Panics identified
   `buddy_sound` and `nimble_host`. Their stacks changed from 3072 to 4096 bytes
   and 4096 to 6144 bytes respectively. Later playback left about 876 bytes in
   the audio stack. These are measured application values, not board defaults;
   increasing stacks also consumes the shared RAM budget.
4. **Connected does not mean messages are accepted.** A protected read succeeded
   while an acknowledged write returned ATT error 15. RX authorization was
   changed to reconcile the cached security state with NimBLE's current
   connection state. Encryption, authentication, bonding and a 16-byte key
   remain required. Use acknowledged writes to diagnose rejection; a successful
   write-without-response call alone cannot prove device acceptance.
5. **Keep playback separate and confirm sound with a person.** Use a worker
   task for 16 kHz, 16-bit mono PCM, a soft 200 ms waveform and short fades.
   The BSP's six 240-frame DMA buffers can retain 90 ms of audio; allow 100 ms
   before muting. The user confirmed hearing the tone at a driver volume of
   60%, then requested 50%. Playback logs alone never established audibility.
6. **Verify the layout before preserving settings.** With the partition table
   verified unchanged, we wrote only the application at `0x10000`, retaining
   NVS and pairing. A merged image from `0x0` can overwrite stored settings;
   do not use a whole-chip erase as a routine retry.
7. **Make listening tests short and predictable.** Keep one bridge connection,
   send one new completion and verify duplicate heartbeats do not replay it.
   Once ready, count down three seconds, trigger, and immediately tell the user
   to listen for the next 1-2 seconds. Inspect logs after their feedback.
   Expanding the test into repeated reconnect experiments made this session
   much longer and obscured when the sound was expected.

Validation: firmware/image checks and 19 host tests passed; short connection,
reconnect and playback observations completed without a captured panic after
the fixes. The 50% volume was flashed but its listening acceptance, long-term
stability and battery impact remain unverified.

Related: [BLE idle and observation pitfalls](https://github.com/FoloToy/ai-passport/blob/main/docs/reference/shinku-chen/ble-active-idle-power.md)
and [audio ownership and RAM budgeting](https://github.com/FoloToy/ai-passport/blob/main/docs/reference/phoenixzhc/network-audio-streaming-and-memory.md).
