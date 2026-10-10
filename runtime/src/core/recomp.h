/*
 * Interface between the runtime and statically recompiled game code.
 */
#ifndef NGP_RECOMP_H
#define NGP_RECOMP_H

#include <stdint.h>

typedef void (*RecompFn)(void);

/* Returns the recompiled function able to start executing at `pc`, or NULL.
   Implemented by the generated code (or a stub when built without it). */
RecompFn recomp_lookup(uint32_t pc);

/* Number of recompiled entry points (0 when built without generated code). */
extern const uint32_t g_recomp_entry_count;

#endif
