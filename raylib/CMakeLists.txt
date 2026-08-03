if(NOT DEFINED PLATFORM)
    set(PLATFORM "Desktop" CACHE STRING "Platform to target (Desktop/Web/Android)")
endif()

set(POLY99_TOUCH "AUTO" CACHE STRING "Default touch controls: OFF, ON, or AUTO")

add_subdirectory(raylib-src)

add_executable(poly99
    main.cpp
    config.cpp
    input.cpp
    json.cpp
    renderer.cpp
    audio.cpp
    ui.cpp
)

if(PLATFORM STREQUAL "Web")
    set_target_properties(poly99 PROPERTIES
        OUTPUT_NAME "index"
        SUFFIX ".html"
    )
    target_link_options(poly99 PRIVATE
        "--shell-file=${CMAKE_CURRENT_SOURCE_DIR}/web/shell.html"
        "-sASYNCIFY"
        "-sFORCE_FILESYSTEM"
        "--preload-file=${CMAKE_SOURCE_DIR}/config/game.json@/config/game.json"
    )
endif()

set_target_properties(poly99 PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")

target_link_libraries(poly99 raylib poly99_core)

string(TOUPPER "${POLY99_TOUCH}" POLY99_TOUCH_UPPER)
if(POLY99_TOUCH_UPPER STREQUAL "ON")
    target_compile_definitions(poly99 PRIVATE POLY99_DEFAULT_TOUCH=1)
elseif(POLY99_TOUCH_UPPER STREQUAL "OFF")
    target_compile_definitions(poly99 PRIVATE POLY99_DEFAULT_TOUCH=0)
else()
    target_compile_definitions(poly99 PRIVATE POLY99_DEFAULT_TOUCH=2)
endif()
