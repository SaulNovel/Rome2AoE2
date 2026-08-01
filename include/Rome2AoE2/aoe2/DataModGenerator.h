#pragma once

#include <cstdint>
#include <filesystem>

namespace Rome2AoE2
{

inline constexpr std::uint32_t Rome2AoE2UnitId = 2081;
// ID 2113 is unused in the baseline DAT supplied with this project.  It is
// reserved for the private corpse record required by the Crusader Knight.
inline constexpr std::uint32_t Rome2AoE2CorpseUnitId = 2113;

class DataModGenerator final
{
public:
    static constexpr std::uint32_t cataphractUnitId = 40;
    static constexpr std::uint32_t huskarlUnitId = 41;

    void generate(const std::filesystem::path& sourceDatPath,
                  const std::filesystem::path& modDirectory,
                  const std::filesystem::path& graphicsDirectory) const;

    void generateConvertedUnits(const std::filesystem::path& sourceDatPath,
                                const std::filesystem::path& modDirectory,
                                const std::filesystem::path& graphicsDirectory,
                                std::uint32_t firstCustomUnitId) const;

    [[nodiscard]] static std::filesystem::path datPath(
        const std::filesystem::path& modDirectory);
};

} // namespace Rome2AoE2
