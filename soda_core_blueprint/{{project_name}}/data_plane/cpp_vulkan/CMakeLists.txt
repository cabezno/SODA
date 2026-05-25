cmake_minimum_required(VERSION 3.25)
project(soda_vulkan_node LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Vulkan REQUIRED)

add_executable(soda_vulkan_node src/compute_node.cpp src/ipc_bridge.cpp)
target_link_libraries(soda_vulkan_node PRIVATE Vulkan::Vulkan)
target_include_directories(soda_vulkan_node PRIVATE src)
