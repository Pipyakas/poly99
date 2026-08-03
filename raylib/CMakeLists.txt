if(NOT DEFINED PLATFORM)
    set(PLATFORM "Desktop" CACHE STRING "Platform to target (Desktop/Web/Android)")
endif()

add_subdirectory(raylib-src)

add_executable(poly99 main.cpp)

if(PLATFORM STREQUAL "Web")
    set_target_properties(poly99 PROPERTIES
        OUTPUT_NAME "index"
        SUFFIX ".html"
    )
    target_link_options(poly99 PRIVATE "-sASYNCIFY")
endif()

set_target_properties(poly99 PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")

target_link_libraries(poly99 raylib)
