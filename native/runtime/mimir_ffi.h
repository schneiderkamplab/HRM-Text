#pragma once
#ifdef __cplusplus
extern "C" {
#endif
#if defined(_WIN32)
#define MIMIR_API __declspec(dllexport)
#else
#define MIMIR_API __attribute__((visibility("default"), used))
#endif
// Commands/events are UTF-8 JSON. One command at a time; events are polled on UI.
MIMIR_API void * mimir_create(void);
MIMIR_API int mimir_submit(void * engine, const char * command);
MIMIR_API char * mimir_poll(void * engine);
MIMIR_API void mimir_free(char * value);
MIMIR_API void mimir_cancel(void * engine);
// Cancels and drains work. Invoke away from the UI thread, exactly once.
MIMIR_API void mimir_destroy(void * engine);
#ifdef __cplusplus
}
#endif
