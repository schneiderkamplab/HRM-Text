cmake_minimum_required(VERSION 3.20)
project(mimir_native LANGUAGES C CXX)
get_filename_component(MIMIR_PLUGIN_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." REALPATH)
include("${MIMIR_PLUGIN_ROOT}/desktop.cmake")
