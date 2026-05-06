#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#pragma comment(lib, "winmm.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "shell32.lib")
#define ERR_EXIT(m) { fwprintf(stderr, L"[FATAL] %s (Code: %lu)\n", m, GetLastError()); exit(EXIT_FAILURE); }

void ShowUsage(const wchar_t* exe) {
    wprintf(L"Usage: %s -i \"<text>\" -w <ms>\n", exe);
    wprintf(L"Options:\n  -i\tString to type (supports Unicode, long strings)\n");
    wprintf(L"  -w\tInterval between keys in milliseconds\n");
    wprintf(L"  -h, --help, /?, -?\tShow this help\n");
}

int wmain() {
    int nArgs;
    LPWSTR *szArglist = CommandLineToArgvW(GetCommandLineW(), &nArgs);
    if (!szArglist) ERR_EXIT(L"CmdLineParse");
    LPWSTR txt = NULL; int wait = 0, run = 0;
    for (int i = 1; i < nArgs; i++) {
        if (!wcscmp(szArglist[i], L"-h") || !wcscmp(szArglist[i], L"--help") || 
            !wcscmp(szArglist[i], L"/?") || !wcscmp(szArglist[i], L"-?")) { ShowUsage(szArglist[0]); goto cleanup; }
        if (!wcscmp(szArglist[i], L"-i") && i + 1 < nArgs) { txt = szArglist[++i]; run = 1; }
        else if (!wcscmp(szArglist[i], L"-w") && i + 1 < nArgs) wait = _wtoi(szArglist[++i]);
    }
    if (!run || !txt) { ShowUsage(szArglist[0]); goto cleanup; }
    if (timeBeginPeriod(1) != TIMERR_NOERROR) fprintf(stderr, "[WARN] High-res timer unavailable\n");
    wprintf(L"[INFO] Ready. Simulation starts in 2s...\n");
    Sleep(2000);
    for (size_t j = 0; txt[j] != L'\0'; j++) {
        INPUT in[2] = {0};
        in[0].type = in[1].type = INPUT_KEYBOARD;
        in[0].ki.wScan = in[1].ki.wScan = txt[j];
        in[0].ki.dwFlags = KEYEVENTF_UNICODE;
        in[1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;        
        if (SendInput(2, in, sizeof(INPUT)) < 2) 
            fprintf(stderr, "[ERROR] Injection failed at index %zu\n", j);
        
        if (wait > 0) Sleep(wait);
    }
    timeEndPeriod(1);
    wprintf(L"[SUCCESS] Task finished.\n");

cleanup:
    LocalFree(szArglist);
    return 0;
}
