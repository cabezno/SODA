// Win32 desktop application — window creation, message loop, GDI painting
// Entry point: WinMain (GUI app, no console). Set WIN32_EXECUTABLE TRUE in CMake.
#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <string>
#include <memory>
#include <stdexcept>

// ─── RAII wrappers for Win32 handles ─────────────────────────────────────────

struct HWNDDeleter  { void operator()(HWND h)  const { if (h)  DestroyWindow(h); } };
struct HBRUSHDeleter{ void operator()(HBRUSH h)const { if (h)  DeleteObject(h);  } };

using UniqueHBRUSH = std::unique_ptr<std::remove_pointer_t<HBRUSH>, HBRUSHDeleter>;

// ─── Application state ───────────────────────────────────────────────────────

struct AppState {
    std::wstring title   = L"My Application";
    std::wstring message = L"Hello, World!";
    int          clicks  = 0;
};

static AppState g_state;

// ─── Window procedure ────────────────────────────────────────────────────────

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch (msg) {

    case WM_CREATE: {
        // Create a button
        CreateWindowW(
            L"BUTTON", L"Click me",
            WS_TABSTOP | WS_VISIBLE | WS_CHILD | BS_DEFPUSHBUTTON,
            20, 60, 120, 32,
            hwnd, reinterpret_cast<HMENU>(1001),
            reinterpret_cast<HINSTANCE>(GetWindowLongPtr(hwnd, GWLP_HINSTANCE)),
            nullptr
        );
        return 0;
    }

    case WM_COMMAND: {
        if (LOWORD(wParam) == 1001) {  // Button clicked
            g_state.clicks++;
            g_state.message = L"Clicks: " + std::to_wstring(g_state.clicks);
            InvalidateRect(hwnd, nullptr, TRUE);
        }
        return 0;
    }

    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);

        // Background fill
        RECT rc;
        GetClientRect(hwnd, &rc);
        FillRect(hdc, &rc, reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1));

        // Draw message text
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(30, 30, 30));
        RECT textRc{20, 20, rc.right - 20, 50};
        DrawTextW(hdc, g_state.message.c_str(), -1, &textRc, DT_LEFT | DT_VCENTER | DT_SINGLELINE);

        EndPaint(hwnd, &ps);
        return 0;
    }

    case WM_SIZE:
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;

    default:
        return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}

// ─── Window registration + creation ─────────────────────────────────────────

HWND create_main_window(HINSTANCE hInst, const std::wstring& title) {
    const wchar_t* CLASS_NAME = L"MainWindowClass";

    WNDCLASSEXW wc{};
    wc.cbSize        = sizeof(WNDCLASSEXW);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = hInst;
    wc.hCursor       = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    wc.lpszClassName = CLASS_NAME;
    wc.hIcon         = LoadIconW(nullptr, IDI_APPLICATION);
    wc.hIconSm       = LoadIconW(nullptr, IDI_APPLICATION);

    if (!RegisterClassExW(&wc))
        throw std::runtime_error("RegisterClassEx failed");

    HWND hwnd = CreateWindowExW(
        0, CLASS_NAME, title.c_str(),
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 800, 600,
        nullptr, nullptr, hInst, nullptr
    );

    if (!hwnd) throw std::runtime_error("CreateWindowEx failed");
    return hwnd;
}

// ─── Entry point ─────────────────────────────────────────────────────────────

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE, LPSTR, int nCmdShow) {
    try {
        HWND hwnd = create_main_window(hInst, g_state.title);
        ShowWindow(hwnd, nCmdShow);
        UpdateWindow(hwnd);

        MSG msg{};
        while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        return static_cast<int>(msg.wParam);

    } catch (const std::exception& e) {
        MessageBoxA(nullptr, e.what(), "Fatal Error", MB_ICONERROR | MB_OK);
        return 1;
    }
}
