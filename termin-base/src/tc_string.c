#include <tcbase/tc_string.h>

#include <tcbase/tc_log.h>

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define TC_INTERN_INITIAL_BUCKET_COUNT 256u
#define TC_INTERN_MAX_LOAD_NUMERATOR 2u

typedef struct tc_intern_entry {
    struct tc_intern_entry* next;
    char str[];
} tc_intern_entry;

static tc_intern_entry** g_intern_buckets = NULL;
static size_t g_intern_bucket_count = 0;
static size_t g_intern_entry_count = 0;

static uint64_t tc_string_hash(const char* s) {
    uint64_t hash = 1469598103934665603ull;
    while (*s) {
        hash ^= (unsigned char)*s++;
        hash *= 1099511628211ull;
    }
    return hash;
}

static int tc_intern_init_table(void) {
    if (g_intern_buckets) {
        return 1;
    }

    g_intern_buckets = (tc_intern_entry**)calloc(
        TC_INTERN_INITIAL_BUCKET_COUNT,
        sizeof(tc_intern_entry*)
    );
    if (!g_intern_buckets) {
        tc_log_error("tc_intern_string: failed to allocate initial string intern table");
        return 0;
    }

    g_intern_bucket_count = TC_INTERN_INITIAL_BUCKET_COUNT;
    return 1;
}

static int tc_intern_grow_table(void) {
    size_t new_bucket_count = g_intern_bucket_count * 2u;
    if (new_bucket_count <= g_intern_bucket_count) {
        tc_log_error("tc_intern_string: intern table bucket count overflow");
        return 0;
    }

    tc_intern_entry** new_buckets = (tc_intern_entry**)calloc(
        new_bucket_count,
        sizeof(tc_intern_entry*)
    );
    if (!new_buckets) {
        tc_log_error(
            "tc_intern_string: failed to grow intern table from %zu to %zu buckets",
            g_intern_bucket_count,
            new_bucket_count
        );
        return 0;
    }

    for (size_t i = 0; i < g_intern_bucket_count; ++i) {
        tc_intern_entry* entry = g_intern_buckets[i];
        while (entry) {
            tc_intern_entry* next = entry->next;
            size_t bucket = (size_t)(tc_string_hash(entry->str) % new_bucket_count);
            entry->next = new_buckets[bucket];
            new_buckets[bucket] = entry;
            entry = next;
        }
    }

    free(g_intern_buckets);
    g_intern_buckets = new_buckets;
    g_intern_bucket_count = new_bucket_count;
    return 1;
}

static void tc_intern_maybe_grow_table(void) {
    if (!g_intern_buckets || g_intern_bucket_count == 0) {
        return;
    }

    if (g_intern_entry_count < g_intern_bucket_count * TC_INTERN_MAX_LOAD_NUMERATOR) {
        return;
    }

    (void)tc_intern_grow_table();
}

const char* tc_intern_string(const char* s) {
    if (!s) {
        return NULL;
    }

    if (!tc_intern_init_table()) {
        return NULL;
    }

    uint64_t hash = tc_string_hash(s);
    size_t bucket = (size_t)(hash % g_intern_bucket_count);

    for (tc_intern_entry* entry = g_intern_buckets[bucket]; entry; entry = entry->next) {
        if (strcmp(entry->str, s) == 0) {
            return entry->str;
        }
    }

    tc_intern_maybe_grow_table();
    bucket = (size_t)(hash % g_intern_bucket_count);

    size_t len = strlen(s);
    tc_intern_entry* new_entry = (tc_intern_entry*)malloc(sizeof(tc_intern_entry) + len + 1u);
    if (!new_entry) {
        tc_log_error("tc_intern_string: failed to allocate entry for '%s'", s);
        return NULL;
    }

    memcpy(new_entry->str, s, len + 1u);
    new_entry->next = g_intern_buckets[bucket];
    g_intern_buckets[bucket] = new_entry;
    ++g_intern_entry_count;

    return new_entry->str;
}

void tc_intern_cleanup(void) {
    if (!g_intern_buckets) {
        return;
    }

    for (size_t i = 0; i < g_intern_bucket_count; ++i) {
        tc_intern_entry* entry = g_intern_buckets[i];
        while (entry) {
            tc_intern_entry* next = entry->next;
            free(entry);
            entry = next;
        }
    }

    free(g_intern_buckets);
    g_intern_buckets = NULL;
    g_intern_bucket_count = 0;
    g_intern_entry_count = 0;
}

tc_intern_string_stats tc_intern_string_get_stats(void) {
    tc_intern_string_stats stats = {0};
    stats.entry_count = g_intern_entry_count;
    stats.bucket_count = g_intern_bucket_count;

    if (!g_intern_buckets) {
        return stats;
    }

    for (size_t i = 0; i < g_intern_bucket_count; ++i) {
        size_t depth = 0;
        for (tc_intern_entry* entry = g_intern_buckets[i]; entry; entry = entry->next) {
            ++depth;
        }
        if (depth > 0) {
            ++stats.non_empty_bucket_count;
        }
        if (depth > stats.max_bucket_depth) {
            stats.max_bucket_depth = depth;
        }
    }

    return stats;
}

void tc_intern_string_foreach(tc_intern_string_foreach_fn callback, void* user_data) {
    if (!callback || !g_intern_buckets) {
        return;
    }

    for (size_t bucket = 0; bucket < g_intern_bucket_count; ++bucket) {
        size_t depth = 0;
        for (tc_intern_entry* entry = g_intern_buckets[bucket]; entry; entry = entry->next) {
            callback(entry->str, bucket, depth, user_data);
            ++depth;
        }
    }
}
