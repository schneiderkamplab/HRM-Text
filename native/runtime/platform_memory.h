#pragma once
#include <cstdint>
#if defined(__linux__)
#include <fstream>
#include <sstream>
#endif
#if defined(__APPLE__)
#include <mach/mach.h>
#include <TargetConditionals.h>
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
#include <os/proc.h>
#endif
#elif defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
namespace mimir::runtime {
inline uint64_t available_memory() {
#if defined(__APPLE__)
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
    return os_proc_available_memory();
#else
    vm_statistics64_data_t stats{}; mach_msg_type_number_t n = HOST_VM_INFO64_COUNT;
    mach_port_t host = mach_host_self(); vm_size_t page = 0; host_page_size(host, &page);
    auto status = host_statistics64(host, HOST_VM_INFO64, reinterpret_cast<host_info64_t>(&stats), &n);
    mach_port_deallocate(mach_task_self(), host);
    return status == KERN_SUCCESS ? (uint64_t(stats.free_count) + stats.inactive_count) * page : 1024ull*1024*1024;
#endif
#elif defined(__linux__)
    // MemAvailable includes reclaimable cache, unlike MemFree. This also covers
    // Android; it is a sizing hint, not a guarantee against memory pressure.
    std::ifstream info("/proc/meminfo");
    std::string line;
    while (std::getline(info, line)) {
        std::istringstream fields(line);
        std::string key, unit;
        uint64_t value;
        if (fields >> key >> value >> unit && key == "MemAvailable:" && unit == "kB") {
            return value * 1024;
        }
    }
    return 1024ull*1024*1024;
#elif defined(_WIN32)
    MEMORYSTATUSEX status{}; status.dwLength = sizeof(status);
    return GlobalMemoryStatusEx(&status) ? status.ullAvailPhys : 1024ull*1024*1024;
#else
    // Conservative until a platform-specific available-memory probe is qualified.
    return 1024ull*1024*1024;
#endif
}
}
