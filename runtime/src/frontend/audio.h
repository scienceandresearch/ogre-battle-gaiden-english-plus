/*
 * Audio output: 48 kHz stereo int16 from audio_render() played through
 * waveOut. The emulator thread pushes samples into a ring buffer; a
 * dedicated thread keeps a few short device buffers queued.
 *
 * Latency stays bounded: playback (re)starts once ~40 ms are buffered,
 * buffering above 100 ms is trimmed, an empty ring is padded with a short
 * fade to silence, and audio_rate_adjust() gives the frame pacer a tiny
 * correction (at most 0.3 %) that keeps the fill level near its target so
 * trims and pads stay rare.
 */
#ifndef ZEN_AUDIO_H
#define ZEN_AUDIO_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    int      opened;            /* device open and thread running */
    uint64_t frames_pushed;     /* stereo frames accepted from the emulator */
    uint64_t frames_played;     /* frames of real sound handed to the device */
    uint64_t buffers_done;      /* device buffers completed (played) */
    uint64_t underruns;         /* refills that ran out of sound while playing */
    uint64_t trims;             /* times the buffer was trimmed for latency */
    uint64_t frames_dropped;    /* frames discarded by trims */
    int      peak;              /* largest absolute sample value pushed */
    int      level;             /* frames buffered after the last push */
} AudioStats;

int    audio_open(int volume_percent);  /* 1 = device open; 0 = run silent */
void   audio_close(void);
void   audio_set_volume(int percent);   /* 0..100 */
void   audio_push(const int16_t *frames, size_t count);  /* interleaved L/R */
void   audio_set_muted(int muted);      /* paused / fast-forward: drop sound */
void   audio_clear(void);               /* discard buffered sound */
double audio_rate_adjust(void);         /* multiply the frame period by this */
void   audio_get_stats(AudioStats *st);

#endif
