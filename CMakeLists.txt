cmake_minimum_required(VERSION 3.25)

project(Rome2AoE2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

enable_testing()

find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)

if(MSVC)
    add_compile_options(/W4 /permissive-)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)

add_subdirectory(third_party/googletest)

add_library(Rome2AoE2Lib
    src/aoe2/DataModGenerator.cpp
    src/aoe2/GraphicsScanner.cpp
    src/aoe2/ScenarioGenerator.cpp
)

target_include_directories(Rome2AoE2Lib
    PUBLIC
        include
)

file(TO_CMAKE_PATH "${Python3_EXECUTABLE}" ROME2AOE2_PYTHON_EXECUTABLE_PATH)
file(TO_CMAKE_PATH "${CMAKE_SOURCE_DIR}/src/aoe2/generate_scenario.py" ROME2AOE2_SCENARIO_BRIDGE_PATH)
file(TO_CMAKE_PATH "${CMAKE_SOURCE_DIR}/src/aoe2/generate_data_mod.py" ROME2AOE2_DATA_MOD_BRIDGE_PATH)
file(TO_CMAKE_PATH "${CMAKE_SOURCE_DIR}/src/aoe2/generate_converted_units_mod.py" ROME2AOE2_CONVERTED_UNITS_MOD_BRIDGE_PATH)
file(TO_CMAKE_PATH "${CMAKE_SOURCE_DIR}/test_data/EmptyMap.aoe2scenario" ROME2AOE2_EMPTY_MAP_PATH)

set(ROME2AOE2_AOE2_DAT_PATH "${CMAKE_SOURCE_DIR}/test_data/empires2_x2_p1.dat" CACHE FILEPATH
    "Copied baseline AoE2 DE empires2_x2_p1.dat used to generate the local mod")
set(ROME2AOE2_CRUSADER_KNIGHT_GRAPHICS_PATH "${CMAKE_SOURCE_DIR}/graphics" CACHE PATH
    "Directory containing the Crusader Knight SMX and icon assets")
set(ROME2AOE2_DEMO_UNIT_X 10 CACHE STRING
    "X coordinate for the generated demonstration unit")
set(ROME2AOE2_DEMO_UNIT_Y 10 CACHE STRING
    "Y coordinate for the generated demonstration unit")

target_compile_definitions(Rome2AoE2Lib
    PRIVATE
        ROME2AOE2_PYTHON_EXECUTABLE="${ROME2AOE2_PYTHON_EXECUTABLE_PATH}"
        ROME2AOE2_SCENARIO_BRIDGE_PATH="${ROME2AOE2_SCENARIO_BRIDGE_PATH}"
        ROME2AOE2_DATA_MOD_BRIDGE_PATH="${ROME2AOE2_DATA_MOD_BRIDGE_PATH}"
        ROME2AOE2_CONVERTED_UNITS_MOD_BRIDGE_PATH="${ROME2AOE2_CONVERTED_UNITS_MOD_BRIDGE_PATH}"
        ROME2AOE2_EMPTY_MAP_PATH="${ROME2AOE2_EMPTY_MAP_PATH}"
)

add_custom_target(generate_scenario
    COMMAND $<TARGET_FILE:Rome2AoE2>
            scenario
            4
            ${ROME2AOE2_DEMO_UNIT_X}
            ${ROME2AOE2_DEMO_UNIT_Y}
            ${CMAKE_BINARY_DIR}/Rome2AoE2Generated.aoe2scenario
    DEPENDS
        Rome2AoE2
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Generating the Rome2AoE2 AoE2 DE demonstration scenario"
    VERBATIM
)

add_custom_target(generate_pipeline
    COMMAND $<TARGET_FILE:Rome2AoE2>
            pipeline
            ${ROME2AOE2_AOE2_DAT_PATH}
            ${ROME2AOE2_CRUSADER_KNIGHT_GRAPHICS_PATH}
            ${CMAKE_BINARY_DIR}/Rome2AoE2DataMod
            ${ROME2AOE2_DEMO_UNIT_X}
            ${ROME2AOE2_DEMO_UNIT_Y}
            ${CMAKE_BINARY_DIR}/Rome2AoE2Generated.aoe2scenario
    DEPENDS
        Rome2AoE2
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Generating the Rome2AoE2 data mod and demonstration scenario"
    VERBATIM
)

add_executable(Rome2AoE2
    src/app/main.cpp
)

target_link_libraries(Rome2AoE2
    PRIVATE
        Rome2AoE2Lib
)

add_executable(UnitTests
    tests/DataModGeneratorTests.cpp
    tests/ScenarioGeneratorTests.cpp
)

if(EXISTS "${ROME2AOE2_AOE2_DAT_PATH}" AND
   EXISTS "${ROME2AOE2_CRUSADER_KNIGHT_GRAPHICS_PATH}/u_cav_cavalier_attackA_x1.smx")
    file(TO_CMAKE_PATH "${ROME2AOE2_AOE2_DAT_PATH}" ROME2AOE2_TEST_BASE_DAT_PATH)
    target_sources(UnitTests
        PRIVATE
            tests/DataModGeneratorIntegrationTests.cpp
    )
    target_compile_definitions(UnitTests
        PRIVATE
            ROME2AOE2_TEST_BASE_DAT_PATH="${ROME2AOE2_TEST_BASE_DAT_PATH}"
            ROME2AOE2_TEST_GRAPHICS_PATH="${ROME2AOE2_CRUSADER_KNIGHT_GRAPHICS_PATH}"
    )
endif()

target_link_libraries(UnitTests
    PRIVATE
        Rome2AoE2Lib
        GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(UnitTests)

add_test(
    NAME VariantMeshDefinitionResolverTests
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/VariantMeshDefinitionResolverTests.py
)
set_tests_properties(VariantMeshDefinitionResolverTests PROPERTIES
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

add_test(
    NAME VariantMeshDefinitionAcquisitionTests
    COMMAND ${Python3_EXECUTABLE} -B ${CMAKE_SOURCE_DIR}/tests/VariantMeshDefinitionAcquisitionTests.py
)
set_tests_properties(VariantMeshDefinitionAcquisitionTests PROPERTIES
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)
