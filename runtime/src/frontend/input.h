/*
 * Keyboard and gamepad input mapped to the NGPC controls.
 *
 * Game buttons use the g_input_state layout: bit0 up, 1 down, 2 left,
 * 3 right, 4 A, 5 B, 6 option. XInput is loaded at run time
 * (xinput1_4.dll, then xinput9_1_0.dll, then xinput1_3.dll); without it only
 * the keyboard works.
 */
#ifndef ZEN_INPUT_H
#define ZEN_INPUT_H

#include <stdint.h>

#include "config.h"

void input_init(const Config *cfg);
void input_shutdown(void);

/* Key state from the window procedure. Left/right Shift, Ctrl and Alt
   should be passed as VK_L... / VK_R...; the generic code follows them. */
void input_key(int vk, int down);
void input_clear(void);
int  input_key_down(int vk);             /* the window saw vk go down and not up again */
int  input_action_down(int act);         /* any key bound to act is held */
int  input_is_bound(int act, int vk);    /* vk is one of act's keys */

/* Current game button bits from the keyboard and, when use_gamepad, from all
   connected XInput pads. *gamepad_ff receives the right-trigger state. */
uint8_t input_game_bits(int use_gamepad, int *gamepad_ff);

int  input_gamepads_connected(void);
const char *input_xinput_name(void);     /* loaded DLL, or NULL */

#endif
