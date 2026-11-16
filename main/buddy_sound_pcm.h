#pragma once

#include <stddef.h>
#include <stdint.h>

#define BUDDY_SOUND_SAMPLE_RATE 16000U
#define BUDDY_SOUND_SAMPLE_COUNT 3200U
#define BUDDY_SOUND_VOLUME 50U

/* A 200 ms tone with a short fade at each end. */
int16_t buddy_sound_sample(size_t index);
