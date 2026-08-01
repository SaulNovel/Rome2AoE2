use std::env;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;
use std::sync::OnceLock;

use rpfm_lib::files::{pack::Pack, Container, ContainerPath};
use rpfm_lib::games::supported_games::{SupportedGames, KEY_ROME_2};
use serde_json::json;

#[cfg(test)]
use rpfm_lib::files::{FileType, RFile};
#[cfg(test)]
use rpfm_lib::games::{pfh_file_type::PFHFileType, pfh_version::PFHVersion};

const RESULT_FORMAT: &str = "rome2aoe2.pack-result";
const RESULT_VERSION: u32 = 1;

#[derive(Clone, Debug, PartialEq, Eq)]
struct PackRelativePath {
    original: String,
    slash_normalized: String,
    comparison_key: String,
}

#[derive(Debug)]
enum Command {
    List {
        pack: PathBuf,
    },
    Contains {
        pack: PathBuf,
        requested_path: PackRelativePath,
    },
    Extract {
        pack: PathBuf,
        requested_path: PackRelativePath,
        output_root: PathBuf,
    },
}

fn usage() -> &'static str {
    "Usage:\n  rome2aoe2-pack list --pack <pack-file>\n  rome2aoe2-pack contains --pack <pack-file> --path <pack-relative-path>\n  rome2aoe2-pack extract --pack <pack-file> --path <pack-relative-path> --output-root <directory>"
}

fn parse_pack_relative_path(value: &str) -> Result<PackRelativePath, String> {
    let original = value.trim().to_owned();
    if original.is_empty() {
        return Err("Invalid pack-relative path: path is empty".to_owned());
    }

    let slash_normalized = original.replace('\\', "/");
    if slash_normalized.starts_with('/') || slash_normalized.starts_with("//") {
        return Err(format!(
            "Invalid pack-relative path '{}': absolute paths are not allowed",
            original
        ));
    }

    let components = slash_normalized
        .split('/')
        .filter(|component| !component.is_empty())
        .collect::<Vec<_>>();
    if components.is_empty()
        || components
            .iter()
            .any(|component| *component == "." || *component == "..")
        || components
            .first()
            .is_some_and(|component| component.len() >= 2 && component.as_bytes()[1] == b':')
    {
        return Err(format!(
            "Invalid pack-relative path '{}': traversal or drive-qualified paths are not allowed",
            original
        ));
    }

    let slash_normalized = components.join("/");
    Ok(PackRelativePath {
        comparison_key: slash_normalized.to_lowercase(),
        original,
        slash_normalized,
    })
}

fn parse_command(arguments: &[String]) -> Result<Command, String> {
    if arguments.is_empty() {
        return Err(usage().to_owned());
    }

    let operation = arguments[0].as_str();
    let mut pack = None;
    let mut path = None;
    let mut output_root = None;
    let mut index = 1;
    while index < arguments.len() {
        let option = arguments[index].as_str();
        index += 1;
        if index == arguments.len() {
            return Err(format!("Missing value for '{}'.\n{}", option, usage()));
        }
        let value = &arguments[index];
        index += 1;
        match option {
            "--pack" => pack = Some(PathBuf::from(value)),
            "--path" => path = Some(parse_pack_relative_path(value)?),
            "--output-root" => output_root = Some(PathBuf::from(value)),
            _ => return Err(format!("Unknown option '{}'.\n{}", option, usage())),
        }
    }

    let pack = pack.ok_or_else(|| format!("Missing --pack.\n{}", usage()))?;
    match operation {
        "list" if path.is_none() && output_root.is_none() => Ok(Command::List { pack }),
        "contains" if output_root.is_none() => Ok(Command::Contains {
            pack,
            requested_path: path.ok_or_else(|| format!("Missing --path.\n{}", usage()))?,
        }),
        "extract" => Ok(Command::Extract {
            pack,
            requested_path: path.ok_or_else(|| format!("Missing --path.\n{}", usage()))?,
            output_root: output_root
                .ok_or_else(|| format!("Missing --output-root.\n{}", usage()))?,
        }),
        _ => Err(format!("Invalid options for '{}'.\n{}", operation, usage())),
    }
}

fn rome_2_game() -> Result<&'static rpfm_lib::games::GameInfo, String> {
    static GAMES: OnceLock<SupportedGames> = OnceLock::new();
    GAMES
        .get_or_init(SupportedGames::default)
        .game(KEY_ROME_2)
        .ok_or_else(|| "RPFM does not provide Rome II game configuration".to_owned())
}

fn open_pack(pack_path: &Path) -> Result<Pack, String> {
    if !pack_path.is_file() {
        return Err(format!("Pack file not found: '{}'", pack_path.display()));
    }
    Pack::read_and_merge(&[pack_path.to_owned()], rome_2_game()?, true, false, false).map_err(
        |error| {
            format!(
                "Failed to open Rome II pack '{}': {}",
                pack_path.display(),
                error
            )
        },
    )
}

fn find_archive_path(
    pack: &Pack,
    requested_path: &PackRelativePath,
) -> Result<Option<String>, String> {
    let mut matches = pack
        .files()
        .keys()
        .filter_map(|stored_path| {
            let parsed = parse_pack_relative_path(stored_path).ok()?;
            (parsed.comparison_key == requested_path.comparison_key)
                .then_some((parsed, stored_path))
        })
        .collect::<Vec<_>>();

    matches.sort_by(|left, right| left.1.cmp(right.1));
    if matches.is_empty() {
        return Ok(None);
    }

    if let Some((_, stored_path)) = matches
        .iter()
        .find(|(parsed, _)| parsed.slash_normalized == requested_path.slash_normalized)
    {
        return Ok(Some((*stored_path).to_owned()));
    }

    if matches.len() != 1 {
        let candidates = matches
            .iter()
            .map(|(_, path)| (*path).to_owned())
            .collect::<Vec<_>>()
            .join(", ");
        return Err(format!(
            "Ambiguous pack-relative path '{}': matches {}",
            requested_path.original, candidates
        ));
    }

    Ok(Some(matches[0].1.to_owned()))
}

fn output_path(output_root: &Path, archive_path: &str) -> Result<PathBuf, String> {
    let parsed = parse_pack_relative_path(archive_path)?;
    let relative_path = PathBuf::from_iter(parsed.slash_normalized.split('/'));
    if relative_path.components().any(|component| {
        matches!(
            component,
            Component::ParentDir | Component::RootDir | Component::Prefix(_)
        )
    }) {
        return Err(format!(
            "Unsafe archive path '{}' cannot be extracted",
            archive_path
        ));
    }
    Ok(output_root.join(relative_path))
}

fn result_pack_name(pack: &Path) -> String {
    pack.file_name()
        .unwrap_or(pack.as_os_str())
        .to_string_lossy()
        .to_string()
}

fn run(command: Command) -> Result<serde_json::Value, String> {
    match command {
        Command::List { pack } => {
            let pack_file = open_pack(&pack)?;
            let mut paths = pack_file.files().keys().cloned().collect::<Vec<_>>();
            paths.sort();
            Ok(json!({
                "format": RESULT_FORMAT,
                "operation": "list",
                "pack": result_pack_name(&pack),
                "paths": paths,
                "version": RESULT_VERSION,
            }))
        }
        Command::Contains {
            pack,
            requested_path,
        } => {
            let pack_file = open_pack(&pack)?;
            let matched_path = find_archive_path(&pack_file, &requested_path)?;
            Ok(json!({
                "exists": matched_path.is_some(),
                "format": RESULT_FORMAT,
                "matched_path": matched_path,
                "operation": "contains",
                "pack": result_pack_name(&pack),
                "requested_path": requested_path.original,
                "version": RESULT_VERSION,
            }))
        }
        Command::Extract {
            pack,
            requested_path,
            output_root,
        } => {
            let mut pack_file = open_pack(&pack)?;
            let matched_path =
                find_archive_path(&pack_file, &requested_path)?.ok_or_else(|| {
                    format!(
                        "Requested asset '{}' was not found in pack '{}' (output root '{}')",
                        requested_path.original,
                        pack.display(),
                        output_root.display()
                    )
                })?;
            let expected_output = output_path(&output_root, &matched_path)?;
            let extracted = pack_file
                .extract(
                    ContainerPath::File(matched_path.clone()),
                    &output_root,
                    true,
                    &None,
                    false,
                    true,
                    &None,
                )
                .map_err(|error| {
                    format!(
                        "Failed to extract '{}' from '{}' to '{}': {}",
                        requested_path.original,
                        pack.display(),
                        output_root.display(),
                        error
                    )
                })?;
            if extracted.len() != 1 || !expected_output.is_file() {
                return Err(format!("RPFM reported successful extraction of '{}' from '{}' to '{}' but expected output '{}' was not created", requested_path.original, pack.display(), output_root.display(), expected_output.display()));
            }
            let bytes_written = fs::metadata(&expected_output)
                .map_err(|error| {
                    format!(
                        "Unable to inspect extracted output '{}': {}",
                        expected_output.display(),
                        error
                    )
                })?
                .len();
            Ok(json!({
                "bytes_written": bytes_written,
                "format": RESULT_FORMAT,
                "matched_path": matched_path,
                "operation": "extract",
                "output_path": expected_output.to_string_lossy(),
                "pack": result_pack_name(&pack),
                "requested_path": requested_path.original,
                "version": RESULT_VERSION,
            }))
        }
    }
}

fn main() -> ExitCode {
    let arguments = env::args().skip(1).collect::<Vec<_>>();
    if arguments
        .iter()
        .any(|argument| argument == "--help" || argument == "-h")
    {
        println!("{}", usage());
        return ExitCode::SUCCESS;
    }

    match parse_command(&arguments).and_then(run) {
        Ok(result) => {
            println!(
                "{}",
                serde_json::to_string(&result).expect("pack result must serialize")
            );
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("rome2aoe2-pack: {}", error);
            ExitCode::from(1)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn write_synthetic_pack(root: &Path) -> PathBuf {
        let pack_path = root.join("synthetic.pack");
        let mut pack = Pack::new_with_version(PFHVersion::PFH4);
        pack.header_mut().set_pfh_file_type(PFHFileType::Release);
        pack.files_mut().insert(
            "VariantMeshes/VariantMeshDefinitions/Example.VariantMeshDefinition".to_owned(),
            RFile::new_from_vec(
                b"fixture definition\n",
                FileType::Text,
                0,
                "VariantMeshes/VariantMeshDefinitions/Example.VariantMeshDefinition",
            ),
        );
        pack.files_mut().insert(
            "textures/Shield.DDS".to_owned(),
            RFile::new_from_vec(&[1, 2, 3, 4], FileType::Unknown, 0, "textures/Shield.DDS"),
        );
        pack.save(Some(&pack_path), rome_2_game().unwrap(), &None)
            .unwrap();
        pack_path
    }

    #[test]
    fn rejects_unsafe_pack_relative_paths() {
        for path in [
            "",
            "/absolute/file",
            "C:\\drive\\file",
            "../escape",
            "folder/../escape",
        ] {
            assert!(
                parse_pack_relative_path(path).is_err(),
                "{} should be rejected",
                path
            );
        }
    }

    #[test]
    fn accepts_slash_variants_without_losing_original_spelling() {
        let path = parse_pack_relative_path("VariantMeshes\\Models/Helmet.Rigid_Model_V2").unwrap();
        assert_eq!(path.original, "VariantMeshes\\Models/Helmet.Rigid_Model_V2");
        assert_eq!(
            path.slash_normalized,
            "VariantMeshes/Models/Helmet.Rigid_Model_V2"
        );
        assert_eq!(
            path.comparison_key,
            "variantmeshes/models/helmet.rigid_model_v2"
        );
    }

    #[test]
    fn lists_contains_and_extracts_a_synthetic_nested_file() {
        let temp = tempdir().unwrap();
        let pack = write_synthetic_pack(temp.path());
        let requested = parse_pack_relative_path(
            "variantmeshes\\variantmeshdefinitions\\example.variantmeshdefinition",
        )
        .unwrap();

        let listed = run(Command::List { pack: pack.clone() }).unwrap();
        assert_eq!(
            listed["paths"],
            json!([
                "VariantMeshes/VariantMeshDefinitions/Example.VariantMeshDefinition",
                "textures/Shield.DDS",
            ])
        );

        let contains = run(Command::Contains {
            pack: pack.clone(),
            requested_path: requested.clone(),
        })
        .unwrap();
        assert_eq!(contains["exists"], true);
        assert_eq!(
            contains["matched_path"],
            "VariantMeshes/VariantMeshDefinitions/Example.VariantMeshDefinition"
        );

        let absent = run(Command::Contains {
            pack: pack.clone(),
            requested_path: parse_pack_relative_path("missing/file.xml").unwrap(),
        })
        .unwrap();
        assert_eq!(absent["exists"], false);

        let output_root = temp.path().join("output");
        let extracted = run(Command::Extract {
            pack,
            requested_path: requested,
            output_root: output_root.clone(),
        })
        .unwrap();
        let output_path = output_root
            .join("VariantMeshes")
            .join("VariantMeshDefinitions")
            .join("Example.VariantMeshDefinition");
        assert_eq!(
            extracted["output_path"],
            output_path.to_string_lossy().to_string()
        );
        assert_eq!(fs::read(output_path).unwrap(), b"fixture definition\n");
    }

    #[test]
    fn results_are_deterministic() {
        let temp = tempdir().unwrap();
        let pack = write_synthetic_pack(temp.path());
        let command = Command::Contains {
            pack,
            requested_path: parse_pack_relative_path("textures/shield.dds").unwrap(),
        };
        let first = serde_json::to_string(&run(command).unwrap()).unwrap();
        let second = serde_json::to_string(
            &run(Command::Contains {
                pack: temp.path().join("synthetic.pack"),
                requested_path: parse_pack_relative_path("textures/shield.dds").unwrap(),
            })
            .unwrap(),
        )
        .unwrap();
        assert_eq!(first, second);
    }
}
