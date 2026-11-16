#include "buddy_usage.h"

#include <string.h>

bool buddy_usage_weekly(const buddy_codex_usage_t *usage, buddy_usage_window_t *weekly)
{
    if (weekly == NULL) {
        return false;
    }
    memset(weekly, 0, sizeof(*weekly));
    if (usage == NULL || !usage->present || !usage->available) {
        return false;
    }
    if (usage->primary_window_minutes == BUDDY_WEEKLY_WINDOW_MINUTES &&
        usage->primary_used_percent <= 100U) {
        weekly->used_percent = usage->primary_used_percent;
        weekly->resets_at = usage->primary_resets_at;
        return true;
    }
    if (usage->secondary_window_minutes == BUDDY_WEEKLY_WINDOW_MINUTES &&
        usage->secondary_used_percent <= 100U) {
        weekly->used_percent = usage->secondary_used_percent;
        weekly->resets_at = usage->secondary_resets_at;
        return true;
    }
    return false;
}
