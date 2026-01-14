cmake_minimum_required(VERSION 3.16)
project(nvme_tool VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler flags
if(MSVC)
    add_compile_options(/W4 /O2)
else()
    add_compile_options(-Wall -Wextra -O2)
endif()

# Main executable
add_executable(nvme_tool src/nvme_tool.cpp)

# Windows-specific libraries
if(WIN32)
    target_link_libraries(nvme_tool PRIVATE)
endif()

# Install
install(TARGETS nvme_tool DESTINATION bin)

# Package info
set(CPACK_PACKAGE_NAME "nvme-tool")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "NVMe Admin Command Tool")
include(CPack)
