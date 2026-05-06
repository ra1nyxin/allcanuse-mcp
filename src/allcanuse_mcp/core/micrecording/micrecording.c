#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <mmsystem.h>
#pragma comment(lib, "winmm.lib")

#define SAMPLE_RATE 44100
#define BITS_PER_SAMPLE 16
#define CHANNELS 2

#pragma pack(push, 1)
typedef struct {
    char chunkID[4];      // "RIFF"
    DWORD chunkSize;      
    char format[4];       // "WAVE"
    char subchunk1ID[4];  // "fmt "
    DWORD subchunk1Size;  
    WORD audioFormat;     
    WORD numChannels;
    DWORD sampleRate;
    DWORD byteRate;
    WORD blockAlign;
    WORD bitsPerSample;
    char subchunk2ID[4];  // "data"
    DWORD subchunk2Size;  
} WaveHeader;
#pragma pack(pop)

void PrintUsage(void) {
    printf("micrecording.exe - Windows microphone WAV recorder\n");
    printf("\n");
    printf("Usage:\n");
    printf("  micrecording.exe -t <seconds> [-o <output.wav>]\n");
    printf("  micrecording.exe -h\n");
    printf("  micrecording.exe --help\n");
    printf("\n");
    printf("Arguments:\n");
    printf("  -t <seconds>     Required recording duration in seconds.\n");
    printf("  -o <output.wav>  Optional output WAV path. Default: recorded_audio.wav\n");
    printf("  -h, --help, /?   Show this usage guide without recording audio.\n");
    printf("\n");
    printf("Examples:\n");
    printf("  micrecording.exe -t 5\n");
    printf("  micrecording.exe -t 10 -o recorded_audio.wav\n");
    printf("  micrecording.exe -t 30 -o C:\\\\temp\\\\meeting.wav\n");
    printf("\n");
    printf("Recommended model workflow:\n");
    printf("  1. If you are unsure, run micrecording.exe with no arguments first.\n");
    printf("  2. Then run it with -t and optionally -o.\n");
    printf("  3. After recording, read or upload the generated WAV file as needed.\n");
    printf("\n");
    printf("Notes:\n");
    printf("  - Output is standard PCM WAV: 44.1 kHz, 16-bit, stereo.\n");
    printf("  - Make sure microphone privacy permission is enabled on Windows.\n");
    printf("  - The output directory must already exist.\n");
}

void NormalizePath(char* path) {
    if (!path) return;
    for (int i = 0; path[i] != '\0'; i++) {
        if (path[i] == '/') path[i] = '\\';
    }
}

void HandleAudioError(const char* context, MMRESULT res) {
    char errorDesc[MAXERRORLENGTH];
    fprintf(stderr, "\n[FATAL_EXCEPTION] Context: %s\n", context);
    if (res != MMSYSERR_NOERROR) {
        if (waveInGetErrorText(res, errorDesc, MAXERRORLENGTH) == MMSYSERR_NOERROR) {
            fprintf(stderr, "System Error Description: %s\n", errorDesc);
        }
        fprintf(stderr, "Error Code: 0x%08X\n", (unsigned int)res);
    }
    exit(EXIT_FAILURE);
}

int main(int argc, char* argv[]) {
    int duration = 0;
    char outputPath[MAX_PATH] = "recorded_audio.wav";
    int sawDurationFlag = 0;

    if (argc <= 1) {
        PrintUsage();
        return 0;
    }

    for (int i = 1; i < argc; i++) {
        if (_stricmp(argv[i], "-t") == 0 && i + 1 < argc) {
            duration = atoi(argv[++i]);
            sawDurationFlag = 1;
        } else if (_stricmp(argv[i], "-o") == 0 && i + 1 < argc) {
            strncpy_s(outputPath, MAX_PATH, argv[++i], _TRUNCATE);
        } else if (_stricmp(argv[i], "-h") == 0 || _stricmp(argv[i], "--help") == 0 || strcmp(argv[i], "/?") == 0) {
            PrintUsage();
            return 0;
        } else {
            fprintf(stderr, "Unknown or incomplete argument: %s\n\n", argv[i]);
            PrintUsage();
            return 1;
        }
    }

    if (!sawDurationFlag || duration <= 0) {
        fprintf(stderr, "You must provide a positive recording duration with -t.\n\n");
        PrintUsage();
        return 1;
    }

    NormalizePath(outputPath);
    printf("[SYS_INFO] Target: %s | Duration: %d seconds\n", outputPath, duration);

    WAVEFORMATEX wfx;
    wfx.wFormatTag = WAVE_FORMAT_PCM;
    wfx.nChannels = CHANNELS;
    wfx.nSamplesPerSec = SAMPLE_RATE;
    wfx.nAvgBytesPerSec = SAMPLE_RATE * CHANNELS * (BITS_PER_SAMPLE / 8);
    wfx.nBlockAlign = (CHANNELS * BITS_PER_SAMPLE) / 8;
    wfx.wBitsPerSample = BITS_PER_SAMPLE;
    wfx.cbSize = 0;

    HWAVEIN hWaveIn;
    MMRESULT res = waveInOpen(&hWaveIn, WAVE_MAPPER, &wfx, 0, 0, CALLBACK_NULL);
    if (res != MMSYSERR_NOERROR) {
        HandleAudioError("waveInOpen (Check Microphone Privacy Settings)", res);
    }

    // 注意：duration * nAvgBytesPerSec 可能在极长录制下溢出，在此场景下受 DWORD 限制
    DWORD dataSize = (DWORD)duration * wfx.nAvgBytesPerSec;
    char* pBuffer = (char*)malloc(dataSize);
    if (!pBuffer) {
        waveInClose(hWaveIn);
        HandleAudioError("Memory Allocation Failure", 0);
    }
    memset(pBuffer, 0, dataSize);

    WAVEHDR waveHdr = { 0 };
    waveHdr.lpData = pBuffer;
    waveHdr.dwBufferLength = dataSize;
    
    res = waveInPrepareHeader(hWaveIn, &waveHdr, sizeof(WAVEHDR));
    if (res != MMSYSERR_NOERROR) HandleAudioError("waveInPrepareHeader", res);

    res = waveInAddBuffer(hWaveIn, &waveHdr, sizeof(WAVEHDR));
    if (res != MMSYSERR_NOERROR) HandleAudioError("waveInAddBuffer", res);

    printf("[SYS_LOG] Capturing PCM Stream... ");
    res = waveInStart(hWaveIn);
    if (res != MMSYSERR_NOERROR) HandleAudioError("waveInStart", res);

    for (int i = duration; i > 0; i--) {
        printf("[%d s剩余] ", i);
        fflush(stdout);
        Sleep(1000);
    }
    printf("Complete.\n");

    waveInStop(hWaveIn);
    waveInReset(hWaveIn);

    FILE* fp = NULL;
    if (fopen_s(&fp, outputPath, "wb") != 0) {
        free(pBuffer);
        waveInClose(hWaveIn);
        HandleAudioError("FileSystem Access Denied (Check Directory Existence)", 0);
    }

    // 构建并写入 RIFF 结构
    WaveHeader header = { 0 };
    memcpy(header.chunkID, "RIFF", 4);
    header.chunkSize = 36 + waveHdr.dwBytesRecorded;
    memcpy(header.format, "WAVE", 4);
    memcpy(header.subchunk1ID, "fmt ", 4);
    header.subchunk1Size = 16;
    header.audioFormat = 1;
    header.numChannels = CHANNELS;
    header.sampleRate = SAMPLE_RATE;
    header.byteRate = wfx.nAvgBytesPerSec;
    header.blockAlign = wfx.nBlockAlign;
    header.bitsPerSample = BITS_PER_SAMPLE;
    memcpy(header.subchunk2ID, "data", 4);
    header.subchunk2Size = waveHdr.dwBytesRecorded;
    fwrite(&header, sizeof(WaveHeader), 1, fp);
    fwrite(pBuffer, 1, waveHdr.dwBytesRecorded, fp);
    fclose(fp);
    waveInUnprepareHeader(hWaveIn, &waveHdr, sizeof(WAVEHDR));
    free(pBuffer);
    waveInClose(hWaveIn);
    printf("[FINAL_ACTION] IO Success. Path: %s\n", outputPath);
    return 0;
}
