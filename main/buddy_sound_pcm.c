#include "buddy_sound_pcm.h"

int16_t buddy_sound_sample(size_t index)
{
    static const int16_t wave[] = {
        0, 2296, 4243, 5543, 6000, 5543, 4243, 2296,
        0, -2296, -4243, -5543, -6000, -5543, -4243, -2296,
    };
    const size_t fade_samples = 80U;
    size_t envelope;

    if (index >= BUDDY_SOUND_SAMPLE_COUNT) {
        return 0;
    }
    envelope = BUDDY_SOUND_SAMPLE_COUNT - 1U - index;
    if (envelope > index) {
        envelope = index;
    }
    if (envelope > fade_samples) {
        envelope = fade_samples;
    }
    return (int16_t)((int32_t)wave[index % 16U] * (int32_t)envelope /
                     (int32_t)fade_samples);
}
