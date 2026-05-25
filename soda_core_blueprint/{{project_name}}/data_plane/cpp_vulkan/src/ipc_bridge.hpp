#pragma once
#include <string>

namespace soda::ipc {
    void* attach_shm(const std::string& name, size_t size);
    void detach_shm(void* ptr, size_t size);
}
