/*
 * waveOut audio output with a ring buffer. See audio.h.
 */
#include "audio.h"
#include "util.h"

#include <math.h>
#include <mmsystem.h>
#include <string.h>

#define AUDIO_RATE    48000
#define RING_FRAMES   16384u          /* power of two (341 ms) */
#define RING_MASK     (RING_FRAMES - 1u)
#define BUF_FRAMES    480u            /* 10 ms per device buffer */
#define NUM_BUFS      4               /* 40 ms queued in the device */
#define PRIME_FRAMES  1920u           /* 40 ms collected before playback (re)starts */
#define HIGH_FRAMES   4800u           /* more than 100 ms buffered: trim */
#define TRIM_TO       2400u           /* ... back to 50 ms */
#define TARGET_LEVEL  2400.0          /* desired fill right after a push */
#define RATE_GAIN     2e-6            /* period correction per frame of error */
#define RATE_LIMIT    0.003           /* at most 0.3 % */

static HWAVEOUT         s_wo;
static HANDLE           s_event;
static HANDLE           s_thread;
static volatile LONG    s_quit;
static WAVEHDR          s_hdr[NUM_BUFS];
static int16_t          s_buf[NUM_BUFS][BUF_FRAMES * 2];
static CRITICAL_SECTION s_lock;
static int              s_open;

/* shared state, guarded by s_lock */
static int16_t  s_ring[RING_FRAMES * 2];
static uint32_t s_r, s_w;             /* frame counters; level = s_w - s_r */
static int      s_priming = 1;
static int      s_muted;
static AudioStats s_stats;
static double   s_ema = TARGET_LEVEL;

/* producer-only state */
static float    s_volume = 1.0f;
static float    s_dc_xl, s_dc_yl, s_dc_xr, s_dc_yr;
static int      s_peak;
static uint64_t s_pushed;

/* consumer-only state */
static int16_t  s_last_l, s_last_r;

static void fill_buffer(int i)
{
    int16_t *out = s_buf[i];
    uint32_t n = 0;

    EnterCriticalSection(&s_lock);
    uint32_t avail = s_w - s_r;
    if (s_priming && avail >= PRIME_FRAMES) s_priming = 0;
    if (!s_priming) {
        n = avail < BUF_FRAMES ? avail : BUF_FRAMES;
        for (uint32_t k = 0; k < n; k++) {
            uint32_t idx = (s_r + k) & RING_MASK;
            out[k * 2] = s_ring[idx * 2];
            out[k * 2 + 1] = s_ring[idx * 2 + 1];
        }
        s_r += n;
        if (n < BUF_FRAMES) {
            if (!s_muted) s_stats.underruns++;
            s_priming = 1;
        }
        s_stats.frames_played += n;
    }
    LeaveCriticalSection(&s_lock);

    if (n) {
        s_last_l = out[n * 2 - 2];
        s_last_r = out[n * 2 - 1];
    }
    /* pad with a quick fade from the last sample to silence (no click) */
    for (uint32_t k = n; k < BUF_FRAMES; k++) {
        s_last_l = (int16_t)(s_last_l * 31 / 32);
        s_last_r = (int16_t)(s_last_r * 31 / 32);
        out[k * 2] = s_last_l;
        out[k * 2 + 1] = s_last_r;
    }
}

static DWORD WINAPI audio_thread(LPVOID param)
{
    (void)param;
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
    for (int i = 0; i < NUM_BUFS; i++) {
        fill_buffer(i);
        waveOutWrite(s_wo, &s_hdr[i], sizeof(WAVEHDR));
    }
    while (!s_quit) {
        WaitForSingleObject(s_event, 100);
        if (s_quit) break;
        for (int i = 0; i < NUM_BUFS; i++) {
            if (!(s_hdr[i].dwFlags & WHDR_DONE)) continue;
            EnterCriticalSection(&s_lock);
            s_stats.buffers_done++;
            LeaveCriticalSection(&s_lock);
            fill_buffer(i);
            waveOutWrite(s_wo, &s_hdr[i], sizeof(WAVEHDR));
        }
    }
    return 0;
}

int audio_open(int volume_percent)
{
    if (s_open) return 1;
    audio_set_volume(volume_percent);
    InitializeCriticalSection(&s_lock);
    s_event = CreateEventW(NULL, FALSE, FALSE, NULL);
    if (!s_event) { DeleteCriticalSection(&s_lock); return 0; }

    WAVEFORMATEX wf;
    memset(&wf, 0, sizeof(wf));
    wf.wFormatTag = WAVE_FORMAT_PCM;
    wf.nChannels = 2;
    wf.nSamplesPerSec = AUDIO_RATE;
    wf.wBitsPerSample = 16;
    wf.nBlockAlign = 4;
    wf.nAvgBytesPerSec = AUDIO_RATE * 4;
    if (waveOutOpen(&s_wo, WAVE_MAPPER, &wf, (DWORD_PTR)s_event, 0, CALLBACK_EVENT) != MMSYSERR_NOERROR) {
        CloseHandle(s_event);
        s_event = NULL;
        DeleteCriticalSection(&s_lock);
        return 0;
    }
    for (int i = 0; i < NUM_BUFS; i++) {
        memset(&s_hdr[i], 0, sizeof(WAVEHDR));
        s_hdr[i].lpData = (LPSTR)s_buf[i];
        s_hdr[i].dwBufferLength = BUF_FRAMES * 4;
        waveOutPrepareHeader(s_wo, &s_hdr[i], sizeof(WAVEHDR));
    }
    s_r = s_w = 0;
    s_priming = 1;
    s_quit = 0;
    memset(&s_stats, 0, sizeof(s_stats));
    s_thread = CreateThread(NULL, 0, audio_thread, NULL, 0, NULL);
    if (!s_thread) {
        waveOutReset(s_wo);
        for (int i = 0; i < NUM_BUFS; i++) waveOutUnprepareHeader(s_wo, &s_hdr[i], sizeof(WAVEHDR));
        waveOutClose(s_wo);
        CloseHandle(s_event);
        s_event = NULL;
        DeleteCriticalSection(&s_lock);
        return 0;
    }
    s_open = 1;
    return 1;
}

void audio_close(void)
{
    if (!s_open) return;
    InterlockedExchange(&s_quit, 1);
    SetEvent(s_event);
    WaitForSingleObject(s_thread, 2000);
    CloseHandle(s_thread);
    s_thread = NULL;
    waveOutReset(s_wo);
    for (int i = 0; i < NUM_BUFS; i++) waveOutUnprepareHeader(s_wo, &s_hdr[i], sizeof(WAVEHDR));
    waveOutClose(s_wo);
    CloseHandle(s_event);
    s_event = NULL;
    DeleteCriticalSection(&s_lock);
    s_open = 0;
}

void audio_set_volume(int percent)
{
    if (percent < 0) percent = 0;
    if (percent > 100) percent = 100;
    s_volume = (float)percent / 100.0f;
}

void audio_push(const int16_t *in, size_t count)
{
    int16_t tmp[1024 * 2];
    while (count) {
        size_t n = count > 1024 ? 1024 : count;
        for (size_t k = 0; k < n; k++) {
            /* one-pole DC blocker (cut-off ~8 Hz): the PSG's square waves sit
               above zero, so removing the offset keeps pauses click-free */
            float xl = (float)in[k * 2], xr = (float)in[k * 2 + 1];
            s_dc_yl = xl - s_dc_xl + 0.999f * s_dc_yl;
            s_dc_xl = xl;
            s_dc_yr = xr - s_dc_xr + 0.999f * s_dc_yr;
            s_dc_xr = xr;
            long l = lrintf(s_dc_yl * s_volume), r = lrintf(s_dc_yr * s_volume);
            if (l > 32767) l = 32767;
            if (l < -32768) l = -32768;
            if (r > 32767) r = 32767;
            if (r < -32768) r = -32768;
            tmp[k * 2] = (int16_t)l;
            tmp[k * 2 + 1] = (int16_t)r;
            int al = l < 0 ? -(int)l : (int)l, ar = r < 0 ? -(int)r : (int)r;
            if (al > s_peak) s_peak = al;
            if (ar > s_peak) s_peak = ar;
        }
        s_pushed += n;
        if (s_open) {
            EnterCriticalSection(&s_lock);
            uint32_t level = s_w - s_r;
            if (level + n > RING_FRAMES) {
                uint32_t drop = (uint32_t)(level + n - RING_FRAMES);
                s_r += drop;
                s_stats.frames_dropped += drop;
            }
            for (size_t k = 0; k < n; k++) {
                uint32_t idx = (s_w + (uint32_t)k) & RING_MASK;
                s_ring[idx * 2] = tmp[k * 2];
                s_ring[idx * 2 + 1] = tmp[k * 2 + 1];
            }
            s_w += (uint32_t)n;
            level = s_w - s_r;
            if (level > HIGH_FRAMES) {
                s_r = s_w - TRIM_TO;
                s_stats.frames_dropped += level - TRIM_TO;
                s_stats.trims++;
                level = TRIM_TO;
            }
            s_stats.level = (int)level;
            if (!s_priming) s_ema += ((double)level - s_ema) * 0.02;
            LeaveCriticalSection(&s_lock);
        }
        in += n * 2;
        count -= n;
    }
}

void audio_set_muted(int muted)
{
    if (!s_open) return;
    muted = muted != 0;
    EnterCriticalSection(&s_lock);
    if (muted != s_muted) {
        if (muted) {
            s_r = s_w;      /* drop what is buffered; the device fades out */
            s_priming = 1;
        } else {
            s_ema = TARGET_LEVEL;
        }
        s_muted = muted;
    }
    LeaveCriticalSection(&s_lock);
}

void audio_clear(void)
{
    if (!s_open) return;
    EnterCriticalSection(&s_lock);
    s_r = s_w;
    s_priming = 1;
    s_ema = TARGET_LEVEL;
    LeaveCriticalSection(&s_lock);
}

double audio_rate_adjust(void)
{
    if (!s_open) return 1.0;
    EnterCriticalSection(&s_lock);
    int active = !s_priming && !s_muted;
    double err = s_ema - TARGET_LEVEL;
    LeaveCriticalSection(&s_lock);
    if (!active) return 1.0;
    double adj = err * RATE_GAIN;
    if (adj > RATE_LIMIT) adj = RATE_LIMIT;
    if (adj < -RATE_LIMIT) adj = -RATE_LIMIT;
    return 1.0 + adj;
}

void audio_get_stats(AudioStats *st)
{
    if (s_open) {
        EnterCriticalSection(&s_lock);
        *st = s_stats;
        LeaveCriticalSection(&s_lock);
    } else {
        memset(st, 0, sizeof(*st));
    }
    st->opened = s_open;
    st->frames_pushed = s_pushed;
    st->peak = s_peak;
}
