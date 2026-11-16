#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "buddy_types.h"

#define BUDDY_WEEKLY_WINDOW_MINUTES (7U * 24U * 60U)

typedef struct {
    unsigned used_percent;
    uint64_t resets_at;
} buddy_usage_window_t;

/* Wire slots are not window identities. False means no usable weekly value. */
bool buddy_usage_weekly(const buddy_codex_usage_t *usage, buddy_usage_window_t *weekly);
