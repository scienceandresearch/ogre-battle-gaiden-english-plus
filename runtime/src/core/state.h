/*
 * Save states: every module serialises its state through one symmetric
 * function, so saving and loading always agree.
 */
#ifndef NGP_STATE_H
#define NGP_STATE_H

#include <stdio.h>
#include <stddef.h>

typedef struct StateIO {
    FILE *f;
    int   loading;
    int   ok;
} StateIO;

void st_bytes(StateIO *s, void *p, size_t n);
#define ST(s, v) st_bytes((s), &(v), sizeof(v))

void io_state(StateIO *s);
void irq_state(StateIO *s);
void timers_state(StateIO *s);
void k2ge_state(StateIO *s);
void apu_state(StateIO *s);
void flash_state(StateIO *s);
void bios_state(StateIO *s);

int ngp_state_save(const char *path);
int ngp_state_load(const char *path);

#endif
