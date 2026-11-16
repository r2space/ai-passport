# FoloToy AI Passport · Codex Usage Buddy

[简体中文](README.zh_CN.md) · **English**

This firmware turns FoloToy AI Passport into a private Codex desk companion. It shows the
remaining share of the 7-day Codex limit as a single progress bar, shows the
number of active tasks, and displays a six-second **Task complete** celebration when a root-conversation turn
finishes. The top-right status area also shows the battery level.

Upstream release: **0.1.0**. Development build: **0.1.0-idle2**.

The weekly window is selected by its 10080-minute duration in either API slot;
missing weekly data shows `--`. The five-hour panel is removed from the home and info pages.
The local variant adds one 200 ms speaker tone when a new
Codex completion arrives. Its volume is fixed at 50%; repeated heartbeats do not replay it.
RX authorization also reconciles the current secured link after reconnecting.

The implementation starts from this repository's `demo/claude-buddy-port` reference and
keeps its bounded state machine, pixel UI, encrypted Nordic UART BLE transport, bonding,
and reconnect behavior. A local bridge translates Codex data into the device protocol.

## Source and development

This application is maintained on the `codex/usage-buddy` branch of
[`r2space/ai-passport`](https://github.com/r2space/ai-passport/tree/codex/usage-buddy),
based on [`zt20/codex-usage-ai-passport`](https://github.com/zt20/codex-usage-ai-passport)
revision `6b6b979d2b9df3e9f6f105445b35c626a38fcce1`.

```bash
git clone --branch codex/usage-buddy https://github.com/r2space/ai-passport.git codex-usage-ai-passport
cd codex-usage-ai-passport
```

Build the firmware and run `tools/codex_bridge.py` from this branch. The original
v0.1.0 release packages do not contain this branch's weekly-window and sound fixes.
Keep `dependencies.lock` tracked; build output, virtual environments and logs stay local.
[Debugging lessons](docs/reference/r2space/ble-completion-sound-lessons.md).

## Data flow and privacy

```text
Codex app-server ── rate-limit snapshot ─┐
                                         ├─ local Python bridge ── encrypted BLE ── Passport
~/.codex/sessions ─ lifecycle metadata ────┘
```

The bridge asks the local Codex app-server for `account/rateLimits/read`. Its
session watcher uses only source, conversation/turn IDs, timestamps and lifecycle
event types. It never forwards prompt or answer content or reads authentication tokens.

### Completion rule

- One alert per root-conversation turn: a `task_complete` must match a known
  `task_started`, and the conversation/turn pair is deduplicated across rollout files.
- Subagents, nested turns, aborted/failed turns, message `final_answer` phases and
  repeated terminal events do not generate completion alerts.
- Startup and reconnect synchronize state silently; offline history is not replayed.
- Different conversations finish independently. Other conversations may still be
  running when one alert sounds; the toast displays the running count.
- Multiple completions are sent as separate acknowledged events and queued as separate tones.

Use the bridge and firmware from this branch together. Only explicit
`codex.completion_event=true` packets with a new sequence trigger the toast and tone;
ordinary heartbeats only synchronize the sequence. Older bridges without this flag
can still show usage but do not generate completion alerts on this firmware.

Codex reports usage as percentages rather than absolute message counts, so the screen
shows `LEFT = 100 - usedPercent` for the available weekly window. If the service is temporarily
unavailable when a window resets, the bridge advances to the next period locally and
reconciles after connectivity returns. A never-observed snapshot is shown as unavailable.

## Build and flash the firmware

Use ESP-IDF 5.5.3 and target ESP32-C3:

```bash
get_idf553
idf.py set-target esp32c3
idf.py build
idf.py flash monitor
```

The device advertises as `Codex-<MAC suffix>`. The first encrypted connection displays a
six-digit passkey on the Passport; enter it in the operating system pairing dialog.

## Run the local bridge

Codex CLI must already be installed and signed in. Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-codex-bridge.txt
.venv/bin/python tools/codex_bridge.py
```

On macOS, `tools/run-codex-bridge.command` starts the bridge in the same `.venv`
without installing a login service.

Useful options:

```bash
# Verify the local Codex usage payload without Bluetooth.
python3 tools/codex_bridge.py --dry-run

# Select one device explicitly when several are nearby.
python3 tools/codex_bridge.py --device Codex-A1B2C3
```

The bridge refreshes usage every 60 seconds, active-task count every two seconds, sends a
heartbeat every 10 seconds, and reconnects automatically after a BLE interruption. Stop
it with `Ctrl+C`.

## Controls

- `UP`: cycle Home → Usage → Info.
- `DOWN`: scroll or change the current sub-page.
- Hold `OK`: open the menu.
- Settings → Unpair: delete the BLE bond after on-device confirmation.

## Idle power

The display blanks after 10 seconds without a meaningful event: both backlight
and panel display are disabled, and application rendering pauses. Task-count,
weekly-usage, approval and connection changes, new completion alerts, and button
presses restore the display for another 10 seconds. Clock/token updates and
unchanged heartbeats do not wake it. The first button press while blanked only
wakes the display; it cannot approve a hidden prompt or navigate a hidden menu.

The audio worker wakes ES8311 and clocks 200 ms of silence before each tone,
then verifies codec/I2S standby afterwards, including startup with no playback. CPU DFS uses 40–160 MHz and BLE
controller modem sleep uses the main crystal. System automatic Light-sleep and
Deep-sleep stay disabled while timely BLE notifications are needed. Wake restores
the panel before backlight; runtime blanking never uses the terminal deep-sleep
helper. Pairing, weekly usage and the 50% tone remain unchanged. Board-current
and battery-runtime savings require instrument measurements.

## Tests

```bash
get_idf553
cmake -S tests -B build-host
cmake --build build-host
ctest --test-dir build-host --output-on-failure
python3 -m unittest tests/test_codex_bridge.py
```

Firmware build success is not hardware validation. On-device acceptance must separately
verify pairing, weekly selection in either API slot, missing-data display, reset
countdowns, running/ready state, the completion tone, reconnect, battery display,
and a sustained BLE connection.

## Attribution

The BLE and Buddy application foundation derives from this repository's
`demo/claude-buddy-port` branch, which in turn documents compatibility with Anthropic's
public Hardware Buddy protocol. See [NOTICE](NOTICE) for attribution. The Codex extension
and bridge are not an official OpenAI hardware integration.
