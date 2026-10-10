/*
 * GDI presentation. See video.h.
 */
#include "video.h"

#include "core/ngp.h"

static int    s_integer_scaling = 1;
static HFONT  s_font;
static UINT   s_font_dpi;

typedef UINT (WINAPI *GetDpiForWindowFn)(HWND hwnd);

void video_set_integer_scaling(int on)
{
    s_integer_scaling = on != 0;
}

/* Segoe UI 11 pt for the window's DPI (recreated when the DPI changes). */
static HFONT hint_font(HWND hwnd)
{
    HMODULE u = GetModuleHandleW(L"user32.dll");
    GetDpiForWindowFn get = u ? (GetDpiForWindowFn)(void (*)(void))GetProcAddress(u, "GetDpiForWindow") : NULL;
    UINT dpi = get ? get(hwnd) : 96;
    if (!dpi) dpi = 96;
    if (!s_font || dpi != s_font_dpi) {
        if (s_font) DeleteObject(s_font);
        s_font = CreateFontW(-MulDiv(11, (int)dpi, 72), 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
                             OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        s_font_dpi = dpi;
    }
    return s_font;
}

static void fit_rect(int cw, int ch, RECT *r)
{
    int w, h;
    int s = cw / NGP_SCREEN_W < ch / NGP_SCREEN_H ? cw / NGP_SCREEN_W : ch / NGP_SCREEN_H;
    if (s_integer_scaling && s >= 1) {
        w = NGP_SCREEN_W * s;
        h = NGP_SCREEN_H * s;
    } else if ((long long)cw * NGP_SCREEN_H > (long long)ch * NGP_SCREEN_W) {
        h = ch;
        w = (int)((long long)ch * NGP_SCREEN_W / NGP_SCREEN_H);
    } else {
        w = cw;
        h = (int)((long long)cw * NGP_SCREEN_H / NGP_SCREEN_W);
    }
    r->left = (cw - w) / 2;
    r->top = (ch - h) / 2;
    r->right = r->left + w;
    r->bottom = r->top + h;
}

void video_draw(HWND hwnd, HDC hdc, const uint32_t *frame, const wchar_t *hint)
{
    RECT cr;
    GetClientRect(hwnd, &cr);
    int cw = cr.right - cr.left, ch = cr.bottom - cr.top;
    if (cw <= 0 || ch <= 0) return;

    if (!frame) {
        HBRUSH black = (HBRUSH)GetStockObject(BLACK_BRUSH);
        FillRect(hdc, &cr, black);
        if (hint) {
            SetBkMode(hdc, TRANSPARENT);
            SetTextColor(hdc, RGB(200, 200, 200));
            HFONT font = hint_font(hwnd);
            HGDIOBJ old = SelectObject(hdc, font ? (HGDIOBJ)font : GetStockObject(DEFAULT_GUI_FONT));
            RECT tr = cr;
            InflateRect(&tr, -16, -16);
            /* centre the wrapped text vertically (DT_VCENTER is single-line only) */
            RECT calc = tr;
            DrawTextW(hdc, hint, -1, &calc, DT_CALCRECT | DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);
            int th = calc.bottom - calc.top;
            if (th < tr.bottom - tr.top) tr.top += ((tr.bottom - tr.top) - th) / 2;
            DrawTextW(hdc, hint, -1, &tr, DT_CENTER | DT_WORDBREAK | DT_NOPREFIX);
            SelectObject(hdc, old);
        }
        return;
    }

    RECT d;
    fit_rect(cw, ch, &d);
    /* black borders around the picture (drawn separately: no flicker) */
    if (d.top > 0) PatBlt(hdc, 0, 0, cw, d.top, BLACKNESS);
    if (d.bottom < ch) PatBlt(hdc, 0, d.bottom, cw, ch - d.bottom, BLACKNESS);
    if (d.left > 0) PatBlt(hdc, 0, d.top, d.left, d.bottom - d.top, BLACKNESS);
    if (d.right < cw) PatBlt(hdc, d.right, d.top, cw - d.right, d.bottom - d.top, BLACKNESS);

    BITMAPINFO bmi;
    ZeroMemory(&bmi, sizeof(bmi));
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = NGP_SCREEN_W;
    bmi.bmiHeader.biHeight = -NGP_SCREEN_H;   /* top-down rows */
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;
    SetStretchBltMode(hdc, COLORONCOLOR);     /* nearest neighbour */
    StretchDIBits(hdc, d.left, d.top, d.right - d.left, d.bottom - d.top,
                  0, 0, NGP_SCREEN_W, NGP_SCREEN_H, frame, &bmi, DIB_RGB_COLORS, SRCCOPY);
}

void video_present(HWND hwnd, const uint32_t *frame, const wchar_t *hint)
{
    HDC hdc = GetDC(hwnd);
    if (!hdc) return;
    video_draw(hwnd, hdc, frame, hint);
    ReleaseDC(hwnd, hdc);
}
