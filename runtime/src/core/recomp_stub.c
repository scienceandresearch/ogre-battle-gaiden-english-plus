/*
 * Default (empty) recompiled-code table: everything runs in the interpreter.
 */
#include "recomp.h"
#include <stddef.h>

const uint32_t g_recomp_entry_count = 0;

RecompFn recomp_lookup(uint32_t pc)
{
    (void)pc;
    return NULL;
}
