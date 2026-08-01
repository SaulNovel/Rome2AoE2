#include <Rome2AoE2/aoe2/DataModGenerator.h>

#include <stdexcept>

#include <gtest/gtest.h>

using namespace Rome2AoE2;

TEST(DataModGeneratorTests, UsesTheExpectedAoE2DeModDatLocation)
{
    EXPECT_EQ(
        DataModGenerator::datPath("GeneratedMod"),
        std::filesystem::path("GeneratedMod") / "resources" / "_common" / "dat" /
            "empires2_x2_p1.dat");
}

TEST(DataModGeneratorTests, RejectsMissingBaselineDat)
{
    DataModGenerator generator;

    EXPECT_THROW(
        generator.generate("MissingBaseline.dat", "GeneratedMod", "graphics"),
        std::invalid_argument);
}
