/*
 * Resource IDs of zenobia.exe (zenobia.rc). The C sources may include this
 * file too, e.g. to give the window the program icon:
 *     LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCEW(IDI_ZENOBIA))
 * (NULL when the player was built without the icon: fall back to
 * IDI_APPLICATION).
 */
#ifndef ZEN_RESOURCE_H
#define ZEN_RESOURCE_H

/* Program icon. It has the lowest icon ID, so Explorer and the taskbar's
   pinned shortcut show it for the file. */
#define IDI_ZENOBIA 1

#endif
