#include <Rome2AoE2/aoe2/DataModGenerator.h>
#include <Rome2AoE2/aoe2/ScenarioGenerator.h>

#include <cstdint>
#include <exception>
#include <filesystem>
#include <iostream>
#include <span>
#include <string>
#include <string_view>

namespace
{

class ConsoleLogger final : public Rome2AoE2::Logger
{
public:
    void warning(const std::string& message) override
    {
        std::cerr << "Warning: " << message << '\n';
    }
};

std::filesystem::path defaultGraphicsDirectory(const char* executablePath)
{
    return std::filesystem::absolute(executablePath).parent_path() / "graphics";
}

} // namespace

int main(int argumentCount, char* arguments[])
{
    if (argumentCount == 6 && std::string_view(arguments[1]) == "scenario")
    {
        try
        {
            const Rome2AoE2::UnitPlacement unit{
                .unitId = static_cast<std::uint32_t>(std::stoul(arguments[2])),
                .x = std::stof(arguments[3]),
                .y = std::stof(arguments[4])};
            Rome2AoE2::ScenarioGenerator generator;
            generator.generate(arguments[5], std::span{&unit, 1});
            std::cout << "Scenario generated successfully.\n";
            return 0;
        }
        catch (const std::exception& exception)
        {
            std::cerr << exception.what() << '\n';
            return 1;
        }
    }

    if (argumentCount == 8 && std::string_view(arguments[1]) == "pipeline")
    {
        try
        {
            Rome2AoE2::DataModGenerator dataModGenerator;
            dataModGenerator.generate(arguments[2], arguments[4], arguments[3]);

            const Rome2AoE2::UnitPlacement unit{
                .unitId = Rome2AoE2::Rome2AoE2UnitId,
                .x = std::stof(arguments[5]),
                .y = std::stof(arguments[6])};
            Rome2AoE2::ScenarioGenerator scenarioGenerator;
            scenarioGenerator.generate(arguments[7], std::span{&unit, 1});
            std::cout << "Data mod and scenario generated successfully.\n";
            return 0;
        }
        catch (const std::exception& exception)
        {
            std::cerr << exception.what() << '\n';
            return 1;
        }
    }

    if (argumentCount >= 3 && argumentCount <= 5 &&
        std::string_view(arguments[1]) == "generate-all")
    {
        try
        {
            Rome2AoE2::ScenarioGenerationOptions options;
            if (argumentCount >= 4)
                options.unitsPerPlayer = std::stoull(arguments[3]);

            const std::filesystem::path graphicsDirectory = argumentCount == 5
                ? std::filesystem::path(arguments[4])
                : defaultGraphicsDirectory(arguments[0]);
            ConsoleLogger logger;
            Rome2AoE2::ScenarioGenerator generator;
            generator.generateAll(arguments[2], graphicsDirectory, options, logger);
            std::cout << "Scenario generated successfully from " << graphicsDirectory << ".\n";
            return 0;
        }
        catch (const std::exception& exception)
        {
            std::cerr << exception.what() << '\n';
            return 1;
        }
    }

    if (argumentCount >= 4 && argumentCount <= 7 &&
        std::string_view(arguments[1]) == "generate-mod-scenario")
    {
        try
        {
            Rome2AoE2::ScenarioGenerationOptions options;
            if (argumentCount >= 5)
                options.unitsPerPlayer = std::stoull(arguments[4]);

            const std::filesystem::path graphicsDirectory = argumentCount >= 6
                ? std::filesystem::path(arguments[5])
                : defaultGraphicsDirectory(arguments[0]);
            const std::filesystem::path outputScenario(arguments[3]);
            const std::filesystem::path modDirectory = argumentCount == 7
                ? std::filesystem::path(arguments[6])
                : outputScenario.parent_path() / "ROME2AOE2_GENERATED_DATA_MOD";

            Rome2AoE2::DataModGenerator dataModGenerator;
            dataModGenerator.generateConvertedUnits(
                arguments[2], modDirectory, graphicsDirectory, options.firstCustomUnitId);
            ConsoleLogger logger;
            Rome2AoE2::ScenarioGenerator scenarioGenerator;
            scenarioGenerator.generateAll(outputScenario, graphicsDirectory, options, logger);
            std::cout << "Data mod generated at " << modDirectory << ".\n"
                      << "Scenario generated successfully from " << graphicsDirectory << ".\n";
            return 0;
        }
        catch (const std::exception& exception)
        {
            std::cerr << exception.what() << '\n';
            return 1;
        }
    }

    std::cerr << "Usage:\n"
              << "  Rome2AoE2 scenario <unit-id> <x> <y> <output-scenario>\n"
              << "  Rome2AoE2 pipeline <source-dat> <graphics-directory> <mod-directory> <x> <y> "
                 "<output-scenario>\n"
              << "  Rome2AoE2 generate-all <output-scenario> [units-per-player] [graphics-directory]\n"
              << "  Rome2AoE2 generate-mod-scenario <source-dat> <output-scenario> [units-per-player] "
                 "[graphics-directory] [mod-directory]\n";
    return 2;
}
