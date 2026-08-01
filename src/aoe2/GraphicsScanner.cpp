#include <Rome2AoE2/aoe2/ScenarioGenerator.h>

#include <algorithm>
#include <cctype>
#include <sstream>

namespace Rome2AoE2
{
namespace
{

std::string lowerCase(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    return value;
}

void assignAnimation(AnimationSet& animations,
                     const std::string& filename,
                     const std::filesystem::path& path)
{
    const std::string lowerFilename = lowerCase(filename);
    if (lowerFilename.find("attack") != std::string::npos)
        animations.attack = path;
    else if (lowerFilename.find("death") != std::string::npos)
        animations.death = path;
    else if (lowerFilename.find("decay") != std::string::npos)
        animations.decay = path;
    else if (lowerFilename.find("idle") != std::string::npos)
        animations.idle = path;
    else if (lowerFilename.find("walk") != std::string::npos)
        animations.walk = path;
}

} // namespace

std::vector<std::string> AnimationSet::missingAnimations() const
{
    std::vector<std::string> missing;
    if (!attack) missing.emplace_back("attack");
    if (!death) missing.emplace_back("death");
    if (!decay) missing.emplace_back("decay");
    if (!idle) missing.emplace_back("idle");
    if (!walk) missing.emplace_back("walk");
    return missing;
}

std::vector<UnitDefinition> GraphicsScanner::scan(
    const std::filesystem::path& graphicsDirectory,
    Logger& logger) const
{
    std::vector<UnitDefinition> validUnits;
    if (!std::filesystem::is_directory(graphicsDirectory))
    {
        logger.warning("Graphics directory does not exist; generating an empty scenario: " +
                       graphicsDirectory.string());
        return validUnits;
    }

    std::vector<std::filesystem::path> unitDirectories;
    for (const auto& entry : std::filesystem::directory_iterator(graphicsDirectory))
        if (entry.is_directory()) unitDirectories.push_back(entry.path());
    std::sort(unitDirectories.begin(), unitDirectories.end());

    for (const auto& directory : unitDirectories)
    {
        UnitDefinition unit{.name = directory.filename().string(), .graphicsDirectory = directory};
        for (const auto& entry : std::filesystem::directory_iterator(directory))
            if (entry.is_regular_file()) assignAnimation(unit.animations, entry.path().filename().string(), entry.path());

        const std::vector<std::string> missing = unit.animations.missingAnimations();
        if (missing.empty())
        {
            validUnits.push_back(std::move(unit));
            continue;
        }

        std::ostringstream warning;
        warning << "Skipping unit '" << unit.name << "'\n\nMissing animations:";
        for (const auto& animation : missing) warning << "\n    " << animation;
        logger.warning(warning.str());
    }
    return validUnits;
}

} // namespace Rome2AoE2
