/*
 * GDI presentation of the 160x152 frame: nearest-neighbour StretchDIBits,
 * aspect ratio kept, black borders around the picture.
 */
#ifndef ZEN_VIDEO_H
#define ZEN_VIDEO_H

#include "util.h"

#include <stdint.h>

void video_set_integer_scaling(int on);
/* Draws frame (XRGB8888, 160x152) into the client area, or a hint text on
   black when frame is NULL. */
void video_draw(HWND hwnd, HDC hdc, const uint32_t *frame, const wchar_t *hint);
/* Convenience: GetDC + video_draw + ReleaseDC. */
void video_present(HWND hwnd, const uint32_t *frame, const wchar_t *hint);

#endif
