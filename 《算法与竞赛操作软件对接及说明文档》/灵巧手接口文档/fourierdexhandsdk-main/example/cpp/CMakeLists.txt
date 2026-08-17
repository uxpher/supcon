cmake_minimum_required(VERSION 3.16)

project(fourier_dexhand_sdk_demo)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/bin)

include_directories(${PROJECT_SOURCE_DIR}/include)

find_library(LIB_FOURIER_DEXHAND
    NAMES libFourierDexHand.so
    PATHS ${PROJECT_SOURCE_DIR}/include
    NO_DEFAULT_PATH
)

if(NOT LIB_FOURIER_DEXHAND)
    message(FATAL_ERROR "Failed to find libFourierDexHand.so. Please check the library path.")
endif()

add_executable(fourier_dexhand_sdk_demo fourier_dexhand_sdk_demo.cpp)

target_link_libraries(fourier_dexhand_sdk_demo
    PRIVATE
        ${LIB_FOURIER_DEXHAND}
        pthread
)
