#ifndef NGP_TLCS900H_INTERP_H
#define NGP_TLCS900H_INTERP_H

/* Execute one instruction at g_cpu.pc; returns the number of states used. */
int tlcs_interp_step(void);

/* Nonzero if the last step hit an undefined opcode. */
int tlcs_interp_last_bad(void);

#endif
