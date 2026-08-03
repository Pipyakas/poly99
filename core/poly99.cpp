#include "poly99.h"

#include <cstdio>

namespace poly99 {

const char* hello() {
    return "Hello from poly99 core!";
}

} // namespace poly99

int main() {
    std::printf("%s\n", poly99::hello());
    return 0;
}
