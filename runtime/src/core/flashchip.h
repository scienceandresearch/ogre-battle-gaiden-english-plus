/*
 * The cartridge flash chip's command interface (AMD-style command set of the
 * Neo Geo Pocket flash cartridges), emulated by the core for every frontend
 * (headless harness and player).
 *
 * Games can save without the BIOS. This one copies its own routines to RAM
 * and drives the chip directly: unlock AA -> base+5555, 55 -> base+2AAA,
 * then A0 and the data byte to the target address (byte program), or 80,
 * AA, 55 and 30 to a block address (block erase; 10 to 5555 erases the
 * chip); F0 returns to reading. Operations complete at once, so reading the
 * byte back returns the new data and the game's verify loop passes.
 * Programs and erases go through flash_write_block() / flash_erase_block(),
 * so the blocks are recorded for the save file and g_flash_dirty is set.
 *
 * On by default. g_flash_commands = false restores the old behaviour: CPU
 * writes to the cartridge are logged and ignored, and in-game saving fails
 * ("Could not save." in this game).
 *
 * The command-sequence state is not part of the core's save states (their
 * format is fixed). The core returns to read mode at reset and when a state
 * is loaded; a frontend that wants to keep a sequence across a state can
 * store flashchip_state() itself (the player does, in its state trailer).
 * States are saved between frames, which can fall inside a sequence while
 * the game's save loop runs (it spans several frames; a state saved after
 * frame 14 of Data -> Save is in the middle of one): loaded without the
 * sequence, that byte's verify fails once and the game programs it again,
 * so the save still completes with the same data.
 */
#ifndef NGP_FLASHCHIP_H
#define NGP_FLASHCHIP_H

#include <stdbool.h>
#include <stdint.h>

extern bool g_flash_commands;   /* emulate the command interface (default true) */

/* A CPU write to the cartridge range (called by flash_command_write). */
void     flashchip_write(uint32_t addr, uint8_t value);
/* Back to read mode (ngp_reset and state loads do this). */
void     flashchip_reset(void);
/* Command sequence state: 0 = read mode, 1-6 = inside a sequence. */
uint32_t flashchip_state(void);
void     flashchip_set_state(uint32_t state);   /* out-of-range values mean read mode */

/* Statistics since the program started. */
uint64_t flashchip_programs(void);              /* bytes programmed */
uint64_t flashchip_erases(void);                /* blocks erased */
uint32_t flashchip_block_erases(int chip, int block);   /* erases of one block */

#endif
