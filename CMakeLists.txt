cmake_minimum_required(VERSION 3.16)
project(currency_converter_dashboard LANGUAGES C CXX)

# Options
option(BUILD_WASM "Build WebAssembly target" OFF)

# Core library
add_subdirectory(core)

# Native HTTP server
add_subdirectory(server)

# WASM target (only when requested)
if (BULD_WASM)
    add_subdirectory(wasm)
endif ()