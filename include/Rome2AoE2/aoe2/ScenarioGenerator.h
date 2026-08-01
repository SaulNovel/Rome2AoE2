#pragma once

#include <cstdint>
#include <cstddef>
#include <filesystem>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace Rome2AoE2
{

struct UnitPlacement
{
    std::uint32_t unitId{};
    std::uint32_t playerId{1};
    float x{};
    float y{};
};

struct AnimationSet
{
    std::optional<std::filesystem::path> attack;
    std::optional<std::filesystem::path> death;
    std::optional<std::filesystem::path> decay;
    std::optional<std::filesystem::path> idle;
    std::optional<std::filesystem::path> walk;

    [[nodiscard]] std::vector<std::string> missingAnimations() const;
};

struct UnitDefinition
{
    std::string name;
    std::filesystem::path graphicsDirectory;
    AnimationSet animations;
};

class Logger
{
public:
    virtual ~Logger() = default;
    virtual void warning(const std::string& message) = 0;
};

class GraphicsScanner final
{
public:
    [[nodiscard]] std::vector<UnitDefinition> scan(
        const std::filesystem::path& graphicsDirectory,
        Logger& logger) const;
};

struct ScenarioGenerationOptions
{
    std::size_t unitsPerPlayer{30};
    std::uint32_t firstCustomUnitId{10000};
};

class ScenarioGenerator final
{
public:
    void generate(const std::filesystem::path& outputPath,
                  std::span<const UnitPlacement> units) const;

    void generateAll(const std::filesystem::path& outputPath,
                     const std::filesystem::path& graphicsDirectory,
                     const ScenarioGenerationOptions& options,
                     Logger& logger) const;

    [[nodiscard]] static std::vector<UnitPlacement> createPlacements(
        std::span<const UnitDefinition> units,
        const ScenarioGenerationOptions& options);
};

} // namespace Rome2AoE2
