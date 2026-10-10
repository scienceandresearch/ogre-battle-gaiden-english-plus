#ifndef NGP_PNG_H
#define NGP_PNG_H

#include <stdint.h>

/* Write an XRGB8888 image as PNG, optionally upscaled by an integer factor. */
int png_write_rgb(const char *path, const uint32_t *xrgb, int w, int h, int scale);

#endif
