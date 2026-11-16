#include <assert.h>
#include <stdio.h>

#include "buddy_usage.h"

int main(void)
{
    buddy_codex_usage_t usage = {
        .present = true, .available = true,
        .primary_used_percent = 6, .primary_window_minutes = 10080,
        .primary_resets_at = 123456,
    };
    buddy_usage_window_t weekly;

    /* Current response: the sole primary slot holds the week, not five hours. */
    assert(buddy_usage_weekly(&usage, &weekly));
    assert(weekly.used_percent == 6 && weekly.resets_at == 123456);

    /* Older response: the weekly slot follows a distinct five-hour slot. */
    usage.primary_window_minutes = 300;
    usage.secondary_window_minutes = 10080;
    usage.secondary_used_percent = 62;
    usage.secondary_resets_at = 987654;
    assert(buddy_usage_weekly(&usage, &weekly));
    assert(weekly.used_percent == 62 && weekly.resets_at == 987654);

    /* Missing weekly data must not become a fabricated 100% remaining. */
    usage.secondary_window_minutes = 0;
    assert(!buddy_usage_weekly(&usage, &weekly));
    assert(weekly.used_percent == 0 && weekly.resets_at == 0);
    usage.primary_window_minutes = 10080;
    usage.primary_used_percent = 101;
    assert(!buddy_usage_weekly(&usage, &weekly));
    usage.primary_used_percent = 0;
    assert(buddy_usage_weekly(&usage, &weekly) && weekly.used_percent == 0);
    usage.primary_used_percent = 100;
    assert(buddy_usage_weekly(&usage, &weekly) && weekly.used_percent == 100);
    usage.available = false;
    assert(!buddy_usage_weekly(&usage, &weekly));
    usage.available = true;
    usage.present = false;
    assert(!buddy_usage_weekly(&usage, &weekly));
    assert(!buddy_usage_weekly(NULL, &weekly));
    assert(!buddy_usage_weekly(&usage, NULL));
    puts("Weekly usage selection: PASS");
    return 0;
}
