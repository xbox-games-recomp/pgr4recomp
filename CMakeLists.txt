# pgr4recomp - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(pgr4recomp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(PGR4RECOMP_SOURCES
    src/main.cpp
    src/import_trace.cpp
    src/xam_fixes.cpp
    src/game_patches.cpp
    src/frame_stats.cpp
)

if(WIN32)
    add_executable(pgr4recomp WIN32 ${PGR4RECOMP_SOURCES})
else()
    add_executable(pgr4recomp ${PGR4RECOMP_SOURCES})
endif()

rexglue_setup_target(pgr4recomp)

# User graphics settings, loaded by the SDK from <exe dir>/pgr4recomp.toml. Copied once so local edits survive rebuilds.
add_custom_command(TARGET pgr4recomp POST_BUILD
    COMMAND ${CMAKE_COMMAND} -DSRC=${CMAKE_CURRENT_SOURCE_DIR}/config/pgr4recomp.toml
            -DDST=$<TARGET_FILE_DIR:pgr4recomp>/pgr4recomp.toml
            -P ${CMAKE_CURRENT_SOURCE_DIR}/scripts/copy_if_missing.cmake)

# launcher/ submodule (xbox-recomp-launcher): a settings window that starts the game with the options in
# launcher.ini (passed as cvars, overriding pgr4recomp.toml). Built as pgr4_launcher.exe next to the game
# and in the repository root.
add_subdirectory(launcher)
recomp_add_launcher(GAME_TARGET pgr4recomp OUTPUT_NAME pgr4_launcher COPY_TO_SOURCE_DIR)
