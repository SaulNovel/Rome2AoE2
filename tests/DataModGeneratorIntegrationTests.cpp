#include <Rome2AoE2/aoe2/DataModGenerator.h>

#include <gtest/gtest.h>

using namespace Rome2AoE2;

TEST(DataModGeneratorIntegrationTests, GeneratesTheCrusaderKnightAndItsAssets)
{
    const std::filesystem::path modDirectory =
        "Rome2AoE2DataModIntegrationTest";

    DataModGenerator generator;
    ASSERT_NO_THROW(generator.generate(
        ROME2AOE2_TEST_BASE_DAT_PATH, modDirectory, ROME2AOE2_TEST_GRAPHICS_PATH));
    EXPECT_TRUE(std::filesystem::is_regular_file(
        DataModGenerator::datPath(modDirectory)));
    EXPECT_TRUE(std::filesystem::is_regular_file(modDirectory / "info.json"));
    EXPECT_TRUE(std::filesystem::is_regular_file(
        modDirectory / "resources" / "_common" / "drs" / "graphics" /
        "u_cav_crusader_knight_idleA_x1.smx"));
    EXPECT_TRUE(std::filesystem::is_regular_file(
        modDirectory / "widgetui" / "textures" / "ingame" / "units" /
        "049_50730.dds"));
}
