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
)

if(WIN32)
    add_executable(pgr4recomp WIN32 ${PGR4RECOMP_SOURCES})
else()
    add_executable(pgr4recomp ${PGR4RECOMP_SOURCES})
endif()

rexglue_setup_target(pgr4recomp)
