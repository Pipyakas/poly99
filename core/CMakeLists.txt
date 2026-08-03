add_library(poly99_core STATIC poly99.cpp)

target_include_directories(poly99_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

target_compile_options(poly99_core PRIVATE -Wall -Wextra)
target_link_libraries(poly99_core PRIVATE m)

add_executable(core_tests core_tests.cpp)
target_link_libraries(core_tests poly99_core)

enable_testing()
add_test(NAME core_tests COMMAND core_tests)
