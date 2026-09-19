cmake_minimum_required(VERSION 3.25)
project(MimirApple LANGUAGES C CXX OBJCXX Swift)
if(NOT APPLE)
    message(FATAL_ERROR "Mimir Chat needs an Apple SDK")
endif()
set(CMAKE_Swift_LANGUAGE_VERSION 5)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_OBJCXX_STANDARD 17)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
if(CMAKE_OSX_SYSROOT MATCHES "iphonesimulator")
    set(GGML_METAL OFF CACHE BOOL "" FORCE)
else()
    set(GGML_METAL ON CACHE BOOL "" FORCE)
endif()
set(GGML_METAL_EMBED_LIBRARY ON CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(MIMIR_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(MIMIR_BUILD_CHAT ON CACHE BOOL "" FORCE)
add_subdirectory(../mimir runtime)
add_library(mimir-apple-bridge STATIC Bridge/MimirEngine.mm)
target_include_directories(mimir-apple-bridge PRIVATE ../mimir/tools)
target_link_libraries(mimir-apple-bridge PRIVATE mimir-chat-lib "-framework Foundation")
target_compile_options(mimir-apple-bridge PRIVATE -fobjc-arc)
set_target_properties(mimir-apple-bridge PROPERTIES XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC YES)
add_executable(MimirChat MACOSX_BUNDLE
    Sources/MimirApp.swift Sources/ContentView.swift Sources/ChatStore.swift Sources/Conversation.swift
    Sources/Branding.swift Sources/SelectableChatText.swift Sources/ModelProfile.swift Sources/GenerationSettings.swift Sources/SettingsView.swift Resources/Brand.xcassets)
set_source_files_properties(Resources/Brand.xcassets PROPERTIES MACOSX_PACKAGE_LOCATION Resources)
target_compile_options(MimirChat PRIVATE -import-objc-header "${CMAKE_CURRENT_SOURCE_DIR}/Bridge/MimirEngine.h")
target_link_libraries(MimirChat PRIVATE mimir-apple-bridge "-framework SwiftUI")
set_target_properties(MimirChat PROPERTIES
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_SOURCE_DIR}/Resources/Info.plist.in"
    MACOSX_BUNDLE_GUI_IDENTIFIER "dk.sdu.mimir.chat"
    MACOSX_BUNDLE_BUNDLE_NAME "DFM Mimir"
    XCODE_ATTRIBUTE_ASSETCATALOG_COMPILER_APPICON_NAME "AppIcon"
    XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "dk.sdu.mimir.chat"
    XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY "1,2"
    XCODE_ATTRIBUTE_SWIFT_VERSION "5.0"
    XCODE_ATTRIBUTE_CLANG_ENABLE_MODULES YES)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS")
    set_target_properties(MimirChat PROPERTIES
        XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY "-"
        XCODE_ATTRIBUTE_CODE_SIGN_ENTITLEMENTS "${CMAKE_CURRENT_SOURCE_DIR}/Resources/Mimir.entitlements")
else()
    set_target_properties(MimirChat PROPERTIES
        XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY "Apple Development"
        XCODE_ATTRIBUTE_CODE_SIGN_STYLE Automatic)
endif()
target_sources(MimirChat PRIVATE Resources/DFM-Mimir-LICENSE.txt)
set_source_files_properties(Resources/DFM-Mimir-LICENSE.txt PROPERTIES MACOSX_PACKAGE_LOCATION Resources)
set(MIMIR_MODEL_FILE "" CACHE FILEPATH "Compatible Mimir GGUF to bundle (optional for import-only builds)")
set(MIMIR_MODEL_PROFILE "" CACHE FILEPATH "Optional model profile JSON")
set(MODEL_PROFILE_JSON "null")
if(MIMIR_MODEL_PROFILE)
    file(READ "${MIMIR_MODEL_PROFILE}" MODEL_PROFILE_JSON)
    string(JSON MODEL_PROFILE_VERSION GET "${MODEL_PROFILE_JSON}" version)
endif()
if(MIMIR_MODEL_FILE)
    if(NOT EXISTS "${MIMIR_MODEL_FILE}")
        message(FATAL_ERROR "MIMIR_MODEL_FILE does not exist")
    endif()
    file(SHA256 "${MIMIR_MODEL_FILE}" MODEL_SHA256)
    file(CREATE_LINK "${MIMIR_MODEL_FILE}" "${CMAKE_CURRENT_BINARY_DIR}/Mimir.gguf" COPY_ON_ERROR)
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/Model.json"
        "{\"id\":\"${MODEL_SHA256}\",\"name\":\"DFM Mimir\",\"filename\":\"Mimir.gguf\",\"bundled\":true,\"profile\":${MODEL_PROFILE_JSON}}\n")
    target_sources(MimirChat PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/Mimir.gguf" "${CMAKE_CURRENT_BINARY_DIR}/Model.json")
    set_source_files_properties("${CMAKE_CURRENT_BINARY_DIR}/Mimir.gguf" "${CMAKE_CURRENT_BINARY_DIR}/Model.json"
        PROPERTIES MACOSX_PACKAGE_LOCATION Resources)
endif()
configure_file("../../llama.cpp/LICENSE" "${CMAKE_CURRENT_BINARY_DIR}/llama-LICENSE.txt" COPYONLY)
configure_file("../../mimir/LICENSE" "${CMAKE_CURRENT_BINARY_DIR}/Mimir-LICENSE.txt" COPYONLY)
target_sources(MimirChat PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/llama-LICENSE.txt" "${CMAKE_CURRENT_BINARY_DIR}/Mimir-LICENSE.txt")
set_source_files_properties("${CMAKE_CURRENT_BINARY_DIR}/llama-LICENSE.txt" "${CMAKE_CURRENT_BINARY_DIR}/Mimir-LICENSE.txt"
    PROPERTIES MACOSX_PACKAGE_LOCATION Resources)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "iOS")
    add_executable(mimir-native-bench Tools/benchmark-native.cpp)
    target_include_directories(mimir-native-bench PRIVATE ../mimir/tools ../../llama.cpp/vendor)
    target_link_libraries(mimir-native-bench PRIVATE mimir-chat-lib)
    add_executable(mimir-extended-context-tests Tests/ExtendedContextTests.cpp)
    target_include_directories(mimir-extended-context-tests PRIVATE ../mimir/tools)
    target_link_libraries(mimir-extended-context-tests PRIVATE mimir-chat-lib)
    add_executable(mimir-bridge-tests Tests/BridgeTests.mm)
    target_include_directories(mimir-bridge-tests PRIVATE Bridge)
    target_compile_options(mimir-bridge-tests PRIVATE -fobjc-arc)
    target_link_libraries(mimir-bridge-tests PRIVATE mimir-apple-bridge "-framework Foundation")
endif()
