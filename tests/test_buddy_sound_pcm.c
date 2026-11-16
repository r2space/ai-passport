#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "buddy_sound_pcm.h"

int main(void)
{
    int64_t sum = 0;
    int peak = 0;

    assert(BUDDY_SOUND_SAMPLE_COUNT * 1000U / BUDDY_SOUND_SAMPLE_RATE == 200U);
    assert(buddy_sound_sample(0) == 0);
    assert(buddy_sound_sample(BUDDY_SOUND_SAMPLE_COUNT - 1U) == 0);
    assert(buddy_sound_sample(BUDDY_SOUND_SAMPLE_COUNT) == 0);
    for (size_t i = 0; i < BUDDY_SOUND_SAMPLE_COUNT; ++i) {
        int sample = buddy_sound_sample(i);
        int magnitude = sample < 0 ? -sample : sample;

        assert(magnitude <= 6000);
        sum += sample;
        if (magnitude > peak) {
            peak = magnitude;
        }
    }
    assert(peak > 0);
    assert(sum > -100 && sum < 100);
    puts("Completion tone: PASS");
    return 0;
}
