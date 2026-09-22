add_library(currency_core STATIC
        src/csv_parser.cpp
        src/rate_engine.cpp
        src/stats_engine.cpp
        include/ccd/csv_parser.h
)

target_include_directories(currency_core PUBLIC include)
target_compile_options(currency_core PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>
)