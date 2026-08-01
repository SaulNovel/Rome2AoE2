#include <Rome2AoE2/aoe2/ScenarioGenerator.h>

#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace Rome2AoE2
{
namespace
{

std::string quoteArgument(const std::filesystem::path& path)
{
    return '"' + path.string() + '"';
}

std::string unitArguments(std::span<const UnitPlacement> units)
{
    std::string arguments;

    for (const UnitPlacement& unit : units)
    {
        arguments += " " + std::to_string(unit.unitId);
        arguments += " " + std::to_string(unit.playerId);
        arguments += " " + std::to_string(unit.x);
        arguments += " " + std::to_string(unit.y);
    }

    return arguments;
}

} // namespace

void ScenarioGenerator::generate(
    const std::filesystem::path& outputPath,
    std::span<const UnitPlacement> units) const
{
    if (units.empty())
    {
        throw std::invalid_argument(
            "At least one unit placement is required.");
    }

    const std::filesystem::path templatePath =
        std::filesystem::path(ROME2AOE2_EMPTY_MAP_PATH);
    const std::filesystem::path bridgePath =
        std::filesystem::path(ROME2AOE2_SCENARIO_BRIDGE_PATH);

    const std::string command =
        "\"" +
        quoteArgument(std::filesystem::path(ROME2AOE2_PYTHON_EXECUTABLE)) +
        " " + quoteArgument(bridgePath) +
        " " + quoteArgument(templatePath) +
        " " + quoteArgument(outputPath) +
        unitArguments(units) + "\"";

    if (std::system(command.c_str()) != 0)
    {
        throw std::runtime_error(
            "AoE2 scenario generation bridge failed: " + command);
    }
}

std::vector<UnitPlacement> ScenarioGenerator::createPlacements(
    std::span<const UnitDefinition> units,
    const ScenarioGenerationOptions& options)
{
    std::vector<UnitPlacement> placements;
    placements.reserve(units.size() * options.unitsPerPlayer * 2);

    constexpr std::size_t columnsPerPlayer = 55;
    for (std::size_t unitIndex = 0; unitIndex < units.size(); ++unitIndex)
    {
        const std::uint32_t unitId = options.firstCustomUnitId + static_cast<std::uint32_t>(unitIndex);
        for (std::uint32_t playerId : {1U, 2U})
        {
            const float baseX = playerId == 1 ? 5.0F : 65.0F;
            const float baseY = 5.0F;
            const std::size_t unitOffset = unitIndex * options.unitsPerPlayer;
            for (std::size_t instance = 0; instance < options.unitsPerPlayer; ++instance)
            {
                const std::size_t index = unitOffset + instance;
                placements.push_back({
                    .unitId = unitId,
                    .playerId = playerId,
                    .x = baseX + static_cast<float>(index % columnsPerPlayer),
                    .y = baseY + static_cast<float>(index / columnsPerPlayer)});
            }
        }
    }
    return placements;
}

void ScenarioGenerator::generateAll(
    const std::filesystem::path& outputPath,
    const std::filesystem::path& graphicsDirectory,
    const ScenarioGenerationOptions& options,
    Logger& logger) const
{
    GraphicsScanner scanner;
    const std::vector<UnitDefinition> units = scanner.scan(graphicsDirectory, logger);
    const std::vector<UnitPlacement> placements = createPlacements(units, options);

    const std::filesystem::path templatePath = std::filesystem::path(ROME2AOE2_EMPTY_MAP_PATH);
    const std::filesystem::path bridgePath = std::filesystem::path(ROME2AOE2_SCENARIO_BRIDGE_PATH);
    const std::string command =
        "\"" + quoteArgument(std::filesystem::path(ROME2AOE2_PYTHON_EXECUTABLE)) +
        " " + quoteArgument(bridgePath) +
        " " + quoteArgument(templatePath) +
        " " + quoteArgument(outputPath) +
        unitArguments(placements) + "\"";
    if (std::system(command.c_str()) != 0)
        throw std::runtime_error("AoE2 scenario generation bridge failed: " + command);
}

} // namespace Rome2AoE2
