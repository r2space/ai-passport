#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "buddy_state.h"

static buddy_event_t heartbeat(void)
{
    buddy_event_t event = {.type = BUDDY_EVENT_HEARTBEAT};
    event.heartbeat.connected = true;
    event.heartbeat.running = 1;
    event.heartbeat.codex_usage.present = true;
    event.heartbeat.codex_usage.available = true;
    event.heartbeat.codex_usage.primary_window_minutes = 10080;
    event.heartbeat.codex_usage.primary_used_percent = 12;
    return event;
}

static void reduce(buddy_state_t *state, buddy_event_t *event, uint64_t time_ms,
                   buddy_action_t *action)
{
    buddy_state_reduce(state, event, time_ms, action);
}

static void tick(buddy_state_t *state, uint64_t time_ms)
{
    buddy_event_t event = {.type = BUDDY_EVENT_TICK};
    buddy_action_t action;
    reduce(state, &event, time_ms, &action);
}

static void test_exact_idle_deadline(void)
{
    buddy_state_t state;
    buddy_state_init(&state, NULL);
    tick(&state, 9999);
    assert(!state.screen_off);
    tick(&state, 10000);
    assert(state.screen_off);
}

static void test_routine_packets_never_keep_screen_awake(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_event_t event = heartbeat();
    buddy_state_init(&state, NULL);
    reduce(&state, &event, 100, &action);
    reduce(&state, &event, 5100, &action);
    assert(state.last_display_activity_ms == 100);
    event.heartbeat.tokens = 100;
    reduce(&state, &event, 10100, &action);
    assert(state.screen_off);
    buddy_event_t time = {.type = BUDDY_EVENT_TIME};
    time.time.epoch_seconds = 100000;
    reduce(&state, &time, 10200, &action);
    assert(state.screen_off);
    reduce(&state, &event, 20100, &action);
    assert(state.screen_off);
    assert(state.connected);
}

static void test_fresh_events_wake_but_completion_replay_does_not(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_event_t event = heartbeat();
    buddy_state_init(&state, NULL);
    reduce(&state, &event, 100, &action);
    tick(&state, 10100);
    event.heartbeat.running = 2;
    reduce(&state, &event, 10200, &action);
    assert(!state.screen_off && state.last_display_activity_ms == 10200);
    reduce(&state, &event, 20200, &action);
    assert(state.screen_off);
    event.heartbeat.codex_usage.completion_sequence = 1;
    event.heartbeat.codex_usage.completion_event = true;
    reduce(&state, &event, 20300, &action);
    assert(!state.screen_off && action.completion_sound);
    assert(action.type == BUDDY_ACTION_SETTINGS);
    reduce(&state, &event, 30300, &action);
    assert(state.screen_off && !action.completion_sound);
    event.heartbeat.codex_usage.completion_event = false;
    event.heartbeat.codex_usage.completion_sequence = 2;
    reduce(&state, &event, 30400, &action);
    assert(state.screen_off && !action.completion_sound);
    event.heartbeat.codex_usage.primary_used_percent = 13;
    reduce(&state, &event, 30500, &action);
    assert(!state.screen_off);
}

static void test_hidden_prompt_requires_separate_wake_press(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_event_t event = heartbeat();
    buddy_state_init(&state, NULL);
    reduce(&state, &event, 100, &action);
    tick(&state, 10100);
    event.heartbeat.prompt.connected = true;
    strcpy(event.heartbeat.prompt.id, "prompt-one");
    event.heartbeat.prompt.id_length = strlen(event.heartbeat.prompt.id);
    strcpy(event.heartbeat.prompt.tool, "Bash");
    strcpy(event.heartbeat.prompt.hint, "confirm");
    reduce(&state, &event, 10200, &action);
    assert(!state.screen_off);
    reduce(&state, &event, 20200, &action);
    assert(state.screen_off);
    buddy_event_t key = {.type = BUDDY_EVENT_KEY_CLICK, .key = BUDDY_KEY_OK};
    reduce(&state, &key, 20300, &action);
    assert(!state.screen_off && !state.approval_locked);
    assert(action.type == BUDDY_ACTION_UI_REFRESH);
    reduce(&state, &key, 20400, &action);
    assert(state.approval_locked && action.type == BUDDY_ACTION_PERMISSION);
}

static void test_long_press_wakes_without_opening_menu(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_state_init(&state, NULL);
    tick(&state, 10000);
    buddy_event_t key = {.type = BUDDY_EVENT_KEY_LONG, .key = BUDDY_KEY_OK};
    reduce(&state, &key, 10100, &action);
    assert(!state.screen_off && !state.menu_open);
    reduce(&state, &key, 10200, &action);
    assert(state.menu_open);
    state.menu_selection = BUDDY_MENU_TURN_OFF;
    key.type = BUDDY_EVENT_KEY_CLICK;
    reduce(&state, &key, 10300, &action);
    assert(state.screen_off && action.type == BUDDY_ACTION_SCREEN_OFF);
}

static void test_link_changes_and_stale_security(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_state_init(&state, NULL);
    tick(&state, 10000);
    buddy_event_t connected = {.type = BUDDY_EVENT_BLE_CONNECTED};
    connected.ble.connection_generation = 7;
    reduce(&state, &connected, 10100, &action);
    assert(!state.screen_off);
    reduce(&state, &connected, 20100, &action);
    assert(state.screen_off);
    buddy_event_t passkey = {.type = BUDDY_EVENT_BLE_PASSKEY};
    passkey.ble.connection_generation = 6;
    passkey.ble.passkey = 123456;
    reduce(&state, &passkey, 20200, &action);
    assert(state.screen_off && !state.passkey_visible);
    passkey.ble.connection_generation = 7;
    reduce(&state, &passkey, 20300, &action);
    assert(!state.screen_off && state.passkey_visible);
    reduce(&state, &passkey, 30300, &action);
    assert(state.screen_off);
    buddy_event_t disconnected = {.type = BUDDY_EVENT_BLE_DISCONNECTED};
    disconnected.ble.connection_generation = 8;
    reduce(&state, &disconnected, 30400, &action);
    assert(!state.screen_off);
}

static void test_timeout_is_one_visible_change(void)
{
    buddy_state_t state;
    buddy_action_t action;
    buddy_event_t event = heartbeat();
    buddy_state_init(&state, NULL);
    reduce(&state, &event, 100, &action);
    tick(&state, 10100);
    assert(state.screen_off);
    tick(&state, 30100);
    assert(!state.screen_off && !state.connected);
    tick(&state, 40100);
    assert(state.screen_off);
    tick(&state, 50100);
    assert(state.screen_off);
}

int main(void)
{
    test_exact_idle_deadline();
    test_routine_packets_never_keep_screen_awake();
    test_fresh_events_wake_but_completion_replay_does_not();
    test_hidden_prompt_requires_separate_wake_press();
    test_long_press_wakes_without_opening_menu();
    test_link_changes_and_stale_security();
    test_timeout_is_one_visible_change();
    puts("buddy_idle: PASS (7 scenarios)");
    return 0;
}
