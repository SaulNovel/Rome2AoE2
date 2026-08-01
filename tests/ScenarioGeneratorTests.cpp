#include <Rome2AoE2/aoe2/ScenarioGenerator.h>

#include <array>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>

#include <gtest/gtest.h>

using namespace Rome2AoE2;

namespace
{

class CapturingLogger final : public Logger
{
public:
    void warning(const std::string& message) override { warnings.push_back(message); }
    std::vector<std::string> warnings;
};

} // namespace

TEST(GraphicsScannerTests, AcceptsCompleteUnitDirectoriesAndSkipsIncompleteOnes)
{
    CapturingLogger logger;
    GraphicsScanner scanner;

    const auto units = scanner.scan(
        std::filesystem::path(__FILE__).parent_path().parent_path() / "test_data" / "graphics",
        logger);

    ASSERT_EQ(units.size(), 2u);
    EXPECT_EQ(units[0].name, "Archer");
    EXPECT_EQ(units[1].name, "Legionary");
    ASSERT_EQ(logger.warnings.size(), 1u);
    EXPECT_EQ(logger.warnings[0], "Skipping unit 'Cavalry'\n\nMissing animations:\n    decay");
}

TEST(ScenarioGeneratorTests, CreatesConfigurablePlacementsForBothPlayers)
{
    const std::array units{
        UnitDefinition{.name = "Archer"},
        UnitDefinition{.name = "Legionary"}};
    ScenarioGenerationOptions options{.unitsPerPlayer = 3, .firstCustomUnitId = 3000};

    const auto placements = ScenarioGenerator::createPlacements(units, options);

    ASSERT_EQ(placements.size(), 12u);
    EXPECT_EQ(placements[0].unitId, 3000u);
    EXPECT_EQ(placements[0].playerId, 1u);
    EXPECT_EQ(placements[3].unitId, 3000u);
    EXPECT_EQ(placements[3].playerId, 2u);
    EXPECT_EQ(placements[6].unitId, 3001u);
    EXPECT_EQ(placements[6].playerId, 1u);
    EXPECT_EQ(placements[9].unitId, 3001u);
    EXPECT_EQ(placements[9].playerId, 2u);
}

TEST(ScenarioGeneratorTests, GeneratesAndValidatesArbitraryUnitId)
{
    const std::filesystem::path outputPath =
        "Rome2AoE2GeneratedTest.aoe2scenario";

    ScenarioGenerator generator;
    const std::array units{
        UnitPlacement{.unitId = 4, .x = 12.0F, .y = 18.0F}};

    ASSERT_NO_THROW(generator.generate(outputPath, units));
    ASSERT_TRUE(std::filesystem::is_regular_file(outputPath));
    EXPECT_GT(std::filesystem::file_size(outputPath), 0u);
}

TEST(ScenarioGeneratorTests, RejectsAnEmptyUnitList)
{
    ScenarioGenerator generator;
    const std::array<UnitPlacement, 0> units;

    EXPECT_THROW(
        generator.generate("Unused.aoe2scenario", units),
        std::invalid_argument);
}
