#include "ipc_bridge.hpp"
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace soda::ipc {
    void* attach_shm(const std::string& name, size_t size) {
        int fd = shm_open(name.c_str(), O_RDWR, 0666);
        if (fd == -1) return nullptr;
        return mmap(0, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    }

    void detach_shm(void* ptr, size_t size) {
        munmap(ptr, size);
    }
}
