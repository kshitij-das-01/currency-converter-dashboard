cmake_minimum_required(VERSION 3.16)

project(currency-converter-dashboard LANGUAGES C CXX)

option(BUILD_SERVER "Build the native HTTP server (cpp‑httplib)" ON)
option(BUILD_WASM   "Build the WebAssembly (Emscripten) target" OFF)

option(BUILD_TESTS  "Build unit tests" ON)

add_subdirectory(core)

if (BUILD_SERVER AND NOT BUILD_WASM)
    add_subdirectory(server)
endif()

if (BUILD_WASM)
    add_subdirectory(wasm)
endif()
