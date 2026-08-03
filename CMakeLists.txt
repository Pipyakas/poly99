cmake_minimum_required(VERSION 3.16)

project(poly99 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED PLATFORM)
    set(PLATFORM "Desktop" CACHE STRING "Platform to target (Desktop/Web/Android)")
endif()

add_subdirectory(core)
add_subdirectory(raylib)
