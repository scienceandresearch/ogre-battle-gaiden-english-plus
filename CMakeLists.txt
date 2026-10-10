cmake_minimum_required(VERSION 3.20)
project(open_ogre_battle_gaiden C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

if(MSVC)
    add_compile_options(/W3 /utf-8 /wd4996)
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -Wno-unused-parameter)
endif()

# Emulation core shared by the harness and the standalone player.
set(NGP_CORE_SOURCES
    runtime/src/cpu/tlcs900h_interp.c
    runtime/src/core/mem.c
    runtime/src/core/io.c
    runtime/src/core/interrupts.c
    runtime/src/core/timers.c
    runtime/src/core/k2ge.c
    runtime/src/core/apu.c
    runtime/src/core/flash.c
    runtime/src/core/flashchip.c
    runtime/src/core/bios.c
    runtime/src/core/dispatch.c
    runtime/src/core/system.c
    runtime/src/core/png.c
    runtime/src/core/state.c
    runtime/src/core/recomp_stub.c
    third_party/z80/z80.c
)
add_library(ngp_core STATIC ${NGP_CORE_SOURCES})
target_include_directories(ngp_core PUBLIC runtime/src)
if(NOT MSVC)
    target_link_libraries(ngp_core PUBLIC m)
endif()

add_executable(ngp_harness runtime/src/tools/harness.c)
target_link_libraries(ngp_harness PRIVATE ngp_core)

# Standalone Windows player (Win32 API only, no third-party libraries).
if(WIN32)
    add_executable(zenobia WIN32
        runtime/src/frontend/main.c
        runtime/src/frontend/gui.c
        runtime/src/frontend/selftest.c
        runtime/src/frontend/video.c
        runtime/src/frontend/audio.c
        runtime/src/frontend/input.c
        runtime/src/frontend/config.c
        runtime/src/frontend/romload.c
        runtime/src/frontend/saves.c
        runtime/src/frontend/bps.c
        runtime/src/frontend/sha1.c
        runtime/src/frontend/util.c
        runtime/src/frontend/zipread.c
        runtime/src/frontend/zenobia.manifest
    )
    target_compile_definitions(zenobia PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN NOMINMAX)
    if(MSVC)
        # zenobia.exe is given to players: link the C runtime statically (/MT)
        # so it runs on a clean Windows without the Visual C++ Redistributable
        # (no VCRUNTIME140.dll). That needs a copy of the core built the same
        # way; ngp_core and ngp_harness keep the default DLL runtime (/MD).
        add_library(ngp_core_static STATIC ${NGP_CORE_SOURCES})
        target_include_directories(ngp_core_static PUBLIC runtime/src)
        set_target_properties(ngp_core_static zenobia PROPERTIES
            MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
        target_link_libraries(zenobia PRIVATE ngp_core_static)
        # no incremental-link padding in the distributed executable
        target_link_options(zenobia PRIVATE "$<$<NOT:$<CONFIG:Debug>>:/INCREMENTAL:NO;/OPT:REF;/OPT:ICF>")
    else()
        target_link_libraries(zenobia PRIVATE ngp_core)
    endif()
    target_link_libraries(zenobia PRIVATE user32 gdi32 winmm comdlg32 shell32 ole32)

    # Version resource and program icon (runtime/src/frontend/zenobia.rc;
    # docs/workstreams/release.md). The version comes from the VERSION file;
    # the icon is converted from assets/icon/zenobia.txt at build time when
    # Python 3 is available, and left out otherwise.
    file(STRINGS VERSION ZEN_VERSION LIMIT_COUNT 1)
    if(NOT ZEN_VERSION MATCHES "^([0-9]+)\\.([0-9]+)\\.([0-9]+)$")
        message(FATAL_ERROR "VERSION must hold MAJOR.MINOR.PATCH, found '${ZEN_VERSION}'")
    endif()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS VERSION)
    set(ZEN_RC_DEFINES ZEN_VERSION_MAJOR=${CMAKE_MATCH_1} ZEN_VERSION_MINOR=${CMAKE_MATCH_2}
        ZEN_VERSION_PATCH=${CMAKE_MATCH_3})
    find_package(Python3 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
        set(ZEN_ICON ${CMAKE_CURRENT_BINARY_DIR}/zenobia.ico)
        add_custom_command(OUTPUT ${ZEN_ICON}
            COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tools/release/mkicon.py
                    ${CMAKE_CURRENT_SOURCE_DIR}/assets/icon/zenobia.txt ${ZEN_ICON}
            DEPENDS tools/release/mkicon.py assets/icon/zenobia.txt
            VERBATIM)
        target_sources(zenobia PRIVATE ${ZEN_ICON})
        set_source_files_properties(runtime/src/frontend/zenobia.rc PROPERTIES OBJECT_DEPENDS ${ZEN_ICON})
        list(APPEND ZEN_RC_DEFINES ZEN_HAVE_ICON)
    else()
        message(STATUS "Python 3 not found: zenobia.exe is built without its icon")
    endif()
    target_sources(zenobia PRIVATE runtime/src/frontend/zenobia.rc)
    set_source_files_properties(runtime/src/frontend/zenobia.rc PROPERTIES
        COMPILE_DEFINITIONS "${ZEN_RC_DEFINES}" INCLUDE_DIRECTORIES ${CMAKE_CURRENT_BINARY_DIR})
endif()
