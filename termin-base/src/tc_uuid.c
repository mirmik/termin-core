#include <tcbase/tc_uuid.h>

#include <stdbool.h>
#include <stdlib.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/time.h>
#include <unistd.h>
#endif

static bool g_random_seeded = false;

static void tc_ensure_random_seeded(void) {
    if (g_random_seeded) {
        return;
    }

#ifdef _WIN32
    LARGE_INTEGER counter;
    QueryPerformanceCounter(&counter);
    srand((unsigned int)(counter.QuadPart ^ GetCurrentProcessId()));
#else
    struct timeval tv;
    gettimeofday(&tv, NULL);
    srand((unsigned int)(tv.tv_sec ^ tv.tv_usec ^ getpid()));
#endif

    g_random_seeded = true;
}

static uint8_t tc_random_byte(void) {
    return (uint8_t)(rand() & 0xFF);
}

void tc_generate_uuid(char* out) {
    if (!out) {
        return;
    }

    tc_ensure_random_seeded();

    uint8_t bytes[16];
    for (int i = 0; i < 16; i++) {
        bytes[i] = tc_random_byte();
    }

    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;

    static const char hex[] = "0123456789abcdef";
    int p = 0;

    for (int i = 0; i < 4; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 4; i < 6; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 6; i < 8; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 8; i < 10; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }
    out[p++] = '-';

    for (int i = 10; i < 16; i++) {
        out[p++] = hex[(bytes[i] >> 4) & 0xF];
        out[p++] = hex[bytes[i] & 0xF];
    }

    out[p] = '\0';
}

uint64_t tc_compute_runtime_id(const char* uuid) {
    if (!uuid) {
        return 0;
    }

    uint64_t hash = 14695981039346656037ULL;
    const uint64_t prime = 1099511628211ULL;

    while (*uuid) {
        hash ^= (uint64_t)(unsigned char)*uuid++;
        hash *= prime;
    }

    return hash;
}
