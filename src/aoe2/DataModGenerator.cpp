#include <Rome2AoE2/aoe2/DataModGenerator.h>

#include <cstdlib>
#include <stdexcept>
#include <string>

namespace Rome2AoE2
{
namespace
{

std::string quoteArgument(const std::filesystem::path& path)
{
    return '"' + path.string() + '"';
}

} // namespace

void DataModGenerator::generate(const std::filesystem::path& sourceDatPath,
                                const std::filesystem::path& modDirectory,
                                const std::filesystem::path& graphicsDirectory) const
{
    if (!std::filesystem::is_regular_file(sourceDatPath))
    {
        throw std::invalid_argument("The source AoE2 DE DAT file does not exist: " +
                                    sourceDatPath.string());
    }

    if (modDirectory.empty())
    {
        throw std::invalid_argument("The generated mod directory must not be empty.");
    }

    if (!std::filesystem::is_directory(graphicsDirectory))
    {
        throw std::invalid_argument("The Crusader Knight graphics directory does not exist: " +
                                    graphicsDirectory.string());
    }

    const std::filesystem::path outputDatPath = datPath(modDirectory);
    const std::string command =
        "\"" + quoteArgument(std::filesystem::path(ROME2AOE2_PYTHON_EXECUTABLE)) +
        " " + quoteArgument(std::filesystem::path(ROME2AOE2_DATA_MOD_BRIDGE_PATH)) +
        " " + quoteArgument(sourceDatPath) +
        " " + quoteArgument(outputDatPath) +
        " " + quoteArgument(graphicsDirectory) +
        " " + std::to_string(cataphractUnitId) +
        " " + std::to_string(Rome2AoE2UnitId) +
        " " + std::to_string(Rome2AoE2CorpseUnitId) + "\"";

    if (std::system(command.c_str()) != 0)
    {
        throw std::runtime_error("AoE2 data-mod generation bridge failed: " + command);
    }

    if (!std::filesystem::is_regular_file(outputDatPath))
    {
        throw std::runtime_error("AoE2 data-mod generation bridge did not create: " +
                                 outputDatPath.string());
    }
}

void DataModGenerator::generateConvertedUnits(
    const std::filesystem::path& sourceDatPath,
    const std::filesystem::path& modDirectory,
    const std::filesystem::path& graphicsDirectory,
    std::uint32_t firstCustomUnitId) const
{
    if (!std::filesystem::is_regular_file(sourceDatPath))
        throw std::invalid_argument("The source AoE2 DE DAT file does not exist: " + sourceDatPath.string());
    if (!std::filesystem::is_directory(graphicsDirectory))
        throw std::invalid_argument("The graphics directory does not exist: " + graphicsDirectory.string());

    const std::filesystem::path outputDatPath = datPath(modDirectory);
    const std::string command =
        "\"" + quoteArgument(std::filesystem::path(ROME2AOE2_PYTHON_EXECUTABLE)) +
        " " + quoteArgument(std::filesystem::path(ROME2AOE2_CONVERTED_UNITS_MOD_BRIDGE_PATH)) +
        " " + quoteArgument(sourceDatPath) +
        " " + quoteArgument(outputDatPath) +
        " " + quoteArgument(graphicsDirectory) +
        " " + std::to_string(firstCustomUnitId) +
        " " + std::to_string(huskarlUnitId) + "\"";
    if (std::system(command.c_str()) != 0)
        throw std::runtime_error("AoE2 converted-units data-mod bridge failed: " + command);
    if (!std::filesystem::is_regular_file(outputDatPath))
        throw std::runtime_error("AoE2 converted-units data-mod bridge did not create: " + outputDatPath.string());
}

std::filesystem::path DataModGenerator::datPath(
    const std::filesystem::path& modDirectory)
{
    return modDirectory / "resources" / "_common" / "dat" /
           "empires2_x2_p1.dat";
}

} // namespace Rome2AoE2
