cmake_minimum_required(VERSION 3.16)
project(hdar_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# ── Dependencies ──────────────────────────────────────────────

# libsodium (Ed25519, SHA-256, random)
find_path(SODIUM_INCLUDE_DIR sodium.h PATHS /opt/homebrew/include /usr/local/include /usr/include)
find_library(SODIUM_LIBRARY NAMES sodium PATHS /opt/homebrew/lib /usr/local/lib /usr/lib)
if(NOT SODIUM_INCLUDE_DIR OR NOT SODIUM_LIBRARY)
    message(FATAL_ERROR "libsodium not found. Install with: brew install libsodium")
endif()
message(STATUS "Found libsodium: ${SODIUM_LIBRARY}")

# SQLite3 (lease manager)
find_package(SQLite3 QUIET)
if(NOT SQLite3_FOUND)
    find_path(SQLITE3_INCLUDE_DIR sqlite3.h PATHS /opt/homebrew/include /usr/local/include)
    find_library(SQLITE3_LIBRARY NAMES sqlite3 PATHS /opt/homebrew/lib /usr/local/lib)
    if(SQLITE3_INCLUDE_DIR AND SQLITE3_LIBRARY)
        set(SQLite3_FOUND TRUE)
    else()
        message(FATAL_ERROR "SQLite3 not found. Install with: brew install sqlite3")
    endif()
endif()
message(STATUS "Found SQLite3")

# ── HDAR library ──────────────────────────────────────────────

set(HDAR_SOURCES
    src/crypto.cpp
    src/store.cpp
    src/identity.cpp
    src/receipt.cpp
    src/seal.cpp
    src/restore.cpp
    src/capabilities.cpp
    src/restoration_contract.cpp
    src/state_machine.cpp
    src/effects.cpp
    src/lease.cpp
    src/controller.cpp
    src/provider_base.cpp
    src/unsafe_host.cpp
    src/apple_container.cpp
    src/execution_receipt.cpp
    src/termination_receipt.cpp
    src/host_attestation.cpp
    src/offline_verify.cpp
    src/continuity.cpp
    src/gateway.cpp
    src/reliability.cpp
    src/remote_ssh.cpp
)

add_library(hdar STATIC ${HDAR_SOURCES})
target_include_directories(hdar PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SODIUM_INCLUDE_DIR}
)
target_link_libraries(hdar PUBLIC ${SODIUM_LIBRARY})
if(SQLite3_FOUND)
    target_link_libraries(hdar PUBLIC SQLite::SQLite3)
else()
    target_include_directories(hdar PUBLIC ${SQLITE3_INCLUDE_DIR})
    target_link_libraries(hdar PUBLIC ${SQLITE3_LIBRARY})
endif()

# ── Demos ─────────────────────────────────────────────────────

add_executable(demo src/demo.cpp)
target_link_libraries(demo PRIVATE hdar)

add_executable(demo_continuity src/demo_continuity.cpp)
target_link_libraries(demo_continuity PRIVATE hdar)

# ── Tests ─────────────────────────────────────────────────────

enable_testing()
add_executable(test_hdar src/test_hdar.cpp)
target_link_libraries(test_hdar PRIVATE hdar)
add_test(NAME hdar_tests COMMAND test_hdar)
