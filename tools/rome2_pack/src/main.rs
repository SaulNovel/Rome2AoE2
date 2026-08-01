use std::env;
use std::fs;
use std::io::Cursor;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;
use std::sync::OnceLock;

use rpfm_lib::files::{pack::Pack, Container, ContainerPath, FileType, RFile};
use rpfm_lib::files::{rigidmodel::RigidModel, Decodeable};
use rpfm_lib::games::supported_games::{SupportedGames, KEY_ROME_2};
use rpfm_lib::games::{pfh_file_type::PFHFileType, pfh_version::PFHVersion};
use serde_json::json;

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
    CreateTestPack {
        spec: PathBuf,
        output: PathBuf,
    },
    InspectRmv2 {
        input: PathBuf,
        validate_decode: bool,
    },
}

fn usage() -> &'static str {
    "Usage:\n  rome2aoe2-pack list --pack <pack-file>\n  rome2aoe2-pack contains --pack <pack-file> --path <pack-relative-path>\n  rome2aoe2-pack extract --pack <pack-file> --path <pack-relative-path> --output-root <directory>\n  rome2aoe2-pack create-test-pack --spec <json-file> --output <pack-file>\n  rome2aoe2-pack inspect-rmv2 --input <local-rmv2-file> [--decode]"
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
    let mut spec = None;
    let mut output = None;
    let mut input = None;
    let mut validate_decode = false;
    let mut index = 1;
    while index < arguments.len() {
        let option = arguments[index].as_str();
        index += 1;
        if option == "--decode" {
            validate_decode = true;
            continue;
        }
        if index == arguments.len() {
            return Err(format!("Missing value for '{}'.\n{}", option, usage()));
        }
        let value = &arguments[index];
        index += 1;
        match option {
            "--pack" => pack = Some(PathBuf::from(value)),
            "--path" => path = Some(parse_pack_relative_path(value)?),
            "--output-root" => output_root = Some(PathBuf::from(value)),
            "--spec" => spec = Some(PathBuf::from(value)),
            "--output" => output = Some(PathBuf::from(value)),
            "--input" => input = Some(PathBuf::from(value)),
            _ => return Err(format!("Unknown option '{}'.\n{}", option, usage())),
        }
    }

    if operation == "create-test-pack" {
        return Ok(Command::CreateTestPack {
            spec: spec.ok_or_else(|| "Missing --spec".to_owned())?,
            output: output.ok_or_else(|| "Missing --output".to_owned())?,
        });
    }
    if operation == "inspect-rmv2" {
        return Ok(Command::InspectRmv2 {
            input: input.ok_or_else(|| "Missing --input".to_owned())?,
            validate_decode,
        });
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

const RMV2_MAGIC: &[u8; 4] = b"RMV2";
const RMV2_V6_HEADER_BYTES: usize = 140;
const RMV2_V6_LOD_HEADER_BYTES: usize = 20;
const RMV2_V6_MESH_HEADER_BYTES: usize = 24;
const RMV2_V6_MATERIAL_OFFSET: usize = 80;
const DEFAULT_MATERIAL_FIXED_BYTES: usize = 860;

fn rmv2_u16(bytes: &[u8], offset: usize, context: &str) -> Result<u16, String> {
    let value = bytes
        .get(offset..offset + 2)
        .ok_or_else(|| format!("Malformed RMV2: {} is truncated", context))?;
    Ok(u16::from_le_bytes(
        value.try_into().expect("slice length checked"),
    ))
}

fn rmv2_u32(bytes: &[u8], offset: usize, context: &str) -> Result<u32, String> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or_else(|| format!("Malformed RMV2: {} is truncated", context))?;
    Ok(u32::from_le_bytes(
        value.try_into().expect("slice length checked"),
    ))
}

fn rmv2_f32(bytes: &[u8], offset: usize, context: &str) -> Result<f32, String> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or_else(|| format!("Malformed RMV2: {} is truncated", context))?;
    Ok(f32::from_le_bytes(
        value.try_into().expect("slice length checked"),
    ))
}

fn rmv2_fixed_string(
    bytes: &[u8],
    offset: usize,
    length: usize,
    context: &str,
) -> Result<String, String> {
    let value = bytes
        .get(offset..offset + length)
        .ok_or_else(|| format!("Malformed RMV2: {} is truncated", context))?;
    let value = value
        .split(|byte| *byte == 0)
        .next()
        .expect("a slice always has a first segment");
    std::str::from_utf8(value)
        .map(str::to_owned)
        .map_err(|error| format!("Malformed RMV2: {} is not UTF-8: {}", context, error))
}

fn checked_rmv2_add(left: usize, right: usize, context: &str) -> Result<usize, String> {
    left.checked_add(right)
        .ok_or_else(|| format!("Malformed RMV2: {} overflows", context))
}

fn material_type_name(material_type: u16) -> Option<&'static str> {
    match material_type {
        65 => Some("Weighted"),
        68 => Some("DefaultMaterial"),
        70 => Some("WeightedSkin"),
        72 => Some("DecalDirtmap"),
        73 => Some("Dirtmap"),
        79 => Some("WeightedDirtmap"),
        82 => Some("WeightedSkinDirtmap"),
        _ => None,
    }
}

fn vertex_format_name(vertex_format: u16) -> Option<&'static str> {
    match vertex_format {
        0 => Some("Static"),
        1 => Some("Collision"),
        3 => Some("Weighted"),
        4 => Some("Cinematic"),
        5 => Some("Grass"),
        8 => Some("Uk8"),
        12 => Some("Uk12"),
        25 => Some("ClothSim"),
        _ => None,
    }
}

fn texture_type_name(texture_type: i32) -> Option<&'static str> {
    match texture_type {
        0 => Some("Diffuse"),
        1 => Some("Normal"),
        3 => Some("Mask"),
        5 => Some("AmbientOcclusion"),
        7 => Some("TilingDirtUV2"),
        8 => Some("DirtAlphaMask"),
        10 => Some("SkinMask"),
        11 => Some("Specular"),
        12 => Some("GlossMap"),
        13 => Some("DecalDirtmap"),
        14 => Some("DecalDirtmask"),
        15 => Some("DecalMask"),
        17 => Some("DiffuseDamage"),
        27 => Some("BaseColor"),
        29 => Some("MaterialMap"),
        _ => None,
    }
}

fn parse_default_layout_metadata(
    bytes: &[u8],
    offset: usize,
    material_bytes: usize,
) -> Result<serde_json::Value, String> {
    let material_end = checked_rmv2_add(offset, material_bytes, "material block end")?;
    if material_end > bytes.len() || material_bytes < DEFAULT_MATERIAL_FIXED_BYTES {
        return Err("default material block is truncated".to_owned());
    }

    let vertex_format = rmv2_u16(bytes, offset, "material vertex format")?;
    let name = rmv2_fixed_string(bytes, offset + 2, 32, "material name")?;
    let texture_directory =
        rmv2_fixed_string(bytes, offset + 34, 256, "material texture directory")?;
    let attachment_count = rmv2_u32(bytes, offset + 712, "material attachment count")? as usize;
    let texture_count = rmv2_u32(bytes, offset + 716, "material texture count")? as usize;
    let string_param_count =
        rmv2_u32(bytes, offset + 720, "material string parameter count")? as usize;
    let float_param_count =
        rmv2_u32(bytes, offset + 724, "material float parameter count")? as usize;
    let integer_param_count =
        rmv2_u32(bytes, offset + 728, "material integer parameter count")? as usize;
    let vector_param_count =
        rmv2_u32(bytes, offset + 732, "material vector parameter count")? as usize;

    let attachment_bytes = attachment_count
        .checked_mul(84)
        .ok_or_else(|| "default material attachment data overflows".to_owned())?;
    let texture_bytes = texture_count
        .checked_mul(260)
        .ok_or_else(|| "default material texture data overflows".to_owned())?;
    let textures_offset = checked_rmv2_add(
        checked_rmv2_add(
            offset + DEFAULT_MATERIAL_FIXED_BYTES,
            attachment_bytes,
            "texture table offset",
        )?,
        0,
        "texture table offset",
    )?;
    let mut cursor = checked_rmv2_add(textures_offset, texture_bytes, "parameter table offset")?;
    if cursor > material_end {
        return Err(
            "default material attachment or texture table exceeds material block".to_owned(),
        );
    }

    let mut textures = Vec::with_capacity(texture_count);
    for texture_index in 0..texture_count {
        let texture_offset =
            checked_rmv2_add(textures_offset, texture_index * 260, "texture entry offset")?;
        let texture_type = i32::from_le_bytes(
            bytes
                .get(texture_offset..texture_offset + 4)
                .ok_or_else(|| "default material texture entry is truncated".to_owned())?
                .try_into()
                .expect("slice length checked"),
        );
        let path = rmv2_fixed_string(bytes, texture_offset + 4, 256, "texture path")?;
        textures.push(json!({
            "path": path,
            "type": texture_type,
            "type_name": texture_type_name(texture_type),
        }));
    }

    for _ in 0..string_param_count {
        let length_offset = checked_rmv2_add(cursor, 4, "string parameter length")?;
        let length = rmv2_u16(bytes, length_offset, "string parameter length")? as usize;
        cursor = checked_rmv2_add(cursor, 6, "string parameter header")?;
        cursor = checked_rmv2_add(cursor, length, "string parameter value")?;
        if cursor > material_end {
            return Err("default material string parameter exceeds material block".to_owned());
        }
    }
    cursor = checked_rmv2_add(
        cursor,
        float_param_count
            .checked_mul(8)
            .ok_or_else(|| "default material float parameter data overflows".to_owned())?,
        "float parameter table",
    )?;
    cursor = checked_rmv2_add(
        cursor,
        integer_param_count
            .checked_mul(8)
            .ok_or_else(|| "default material integer parameter data overflows".to_owned())?,
        "integer parameter table",
    )?;
    cursor = checked_rmv2_add(
        cursor,
        vector_param_count
            .checked_mul(20)
            .ok_or_else(|| "default material vector parameter data overflows".to_owned())?,
        "vector parameter table",
    )?;
    if cursor != material_end {
        return Err(format!(
            "default material layout consumes {} bytes, but mesh header reserves {} bytes",
            cursor - offset,
            material_bytes
        ));
    }

    Ok(json!({
        "attachment_count": attachment_count,
        "layout": "default-material-compatible",
        "name": name,
        "parameter_counts": {
            "float": float_param_count,
            "integer": integer_param_count,
            "string": string_param_count,
            "vector4": vector_param_count,
        },
        "texture_directory": texture_directory,
        "textures": textures,
        "vertex_format": vertex_format,
        "vertex_format_name": vertex_format_name(vertex_format),
    }))
}

fn inspect_rmv2(input: &Path, validate_decode: bool) -> Result<serde_json::Value, String> {
    let bytes = fs::read(input)
        .map_err(|error| format!("Unable to read RMV2 '{}': {}", input.display(), error))?;
    if bytes.get(..4) != Some(RMV2_MAGIC) {
        return Err(format!(
            "Invalid RMV2 '{}': expected RMV2 magic",
            input.display()
        ));
    }
    let rmv2_version = rmv2_u32(&bytes, 4, "version")?;
    if rmv2_version != 6 {
        return Err(format!(
            "Unsupported RMV2 version {} in '{}': metadata inspection currently supports Rome II RMV2 v6",
            rmv2_version,
            input.display()
        ));
    }
    if validate_decode {
        let mut reader = Cursor::new(bytes.clone());
        RigidModel::decode(&mut reader, &None)
            .map_err(|error| format!("Unable to decode RMV2 '{}': {}", input.display(), error))?;
    }

    let lod_count = rmv2_u16(&bytes, 8, "LOD count")? as usize;
    let skeleton_id = rmv2_fixed_string(&bytes, 12, 128, "skeleton id")?;
    let lod_headers_end = checked_rmv2_add(
        RMV2_V6_HEADER_BYTES,
        lod_count
            .checked_mul(RMV2_V6_LOD_HEADER_BYTES)
            .ok_or_else(|| "Malformed RMV2: LOD header table overflows".to_owned())?,
        "LOD header table end",
    )?;
    if lod_headers_end > bytes.len() {
        return Err("Malformed RMV2: LOD header table is truncated".to_owned());
    }

    let mut lods = Vec::with_capacity(lod_count);
    for lod_index in 0..lod_count {
        let header_offset = RMV2_V6_HEADER_BYTES + lod_index * RMV2_V6_LOD_HEADER_BYTES;
        let mesh_count = rmv2_u32(&bytes, header_offset, "LOD mesh count")? as usize;
        let mesh_offset = rmv2_u32(&bytes, header_offset + 12, "LOD mesh data offset")? as usize;
        let visibility_distance = rmv2_f32(&bytes, header_offset + 16, "LOD visibility distance")?;
        let mut offset = mesh_offset;
        let mut meshes = Vec::with_capacity(mesh_count);
        let mut vertex_count = 0usize;
        let mut index_count = 0usize;

        for mesh_index in 0..mesh_count {
            let header_end =
                checked_rmv2_add(offset, RMV2_V6_MESH_HEADER_BYTES, "mesh header end")?;
            if header_end > bytes.len() {
                return Err(format!(
                    "Malformed RMV2: LOD {} mesh {} header is truncated",
                    lod_index, mesh_index
                ));
            }
            let material_type = rmv2_u16(&bytes, offset, "mesh material type")?;
            let section_bytes = rmv2_u32(&bytes, offset + 4, "mesh section size")? as usize;
            let vertex_offset = rmv2_u32(&bytes, offset + 8, "mesh vertex offset")? as usize;
            let mesh_vertex_count = rmv2_u32(&bytes, offset + 12, "mesh vertex count")? as usize;
            let index_offset = rmv2_u32(&bytes, offset + 16, "mesh index offset")? as usize;
            let mesh_index_count = rmv2_u32(&bytes, offset + 20, "mesh index count")? as usize;
            let section_end = checked_rmv2_add(offset, section_bytes, "mesh section end")?;
            if section_end > bytes.len()
                || vertex_offset < RMV2_V6_MATERIAL_OFFSET
                || index_offset < vertex_offset
                || index_offset > section_bytes
            {
                return Err(format!(
                    "Malformed RMV2: LOD {} mesh {} has invalid section offsets",
                    lod_index, mesh_index
                ));
            }

            let material_offset =
                checked_rmv2_add(offset, RMV2_V6_MATERIAL_OFFSET, "material offset")?;
            let material_bytes = vertex_offset - RMV2_V6_MATERIAL_OFFSET;
            let material =
                match parse_default_layout_metadata(&bytes, material_offset, material_bytes) {
                    Ok(material) => material,
                    Err(reason) => json!({
                        "layout": "unrecognized",
                        "layout_reason": reason,
                    }),
                };
            let min_bounds = [
                rmv2_f32(&bytes, offset + 24, "mesh minimum bound x")?,
                rmv2_f32(&bytes, offset + 28, "mesh minimum bound y")?,
                rmv2_f32(&bytes, offset + 32, "mesh minimum bound z")?,
            ];
            let max_bounds = [
                rmv2_f32(&bytes, offset + 36, "mesh maximum bound x")?,
                rmv2_f32(&bytes, offset + 40, "mesh maximum bound y")?,
                rmv2_f32(&bytes, offset + 44, "mesh maximum bound z")?,
            ];
            vertex_count = vertex_count
                .checked_add(mesh_vertex_count)
                .ok_or_else(|| "Malformed RMV2: LOD vertex count overflows".to_owned())?;
            index_count = index_count
                .checked_add(mesh_index_count)
                .ok_or_else(|| "Malformed RMV2: LOD index count overflows".to_owned())?;
            meshes.push(json!({
                "bounds": {"max": max_bounds, "min": min_bounds},
                "index": mesh_index,
                "index_count": mesh_index_count,
                "material": material,
                "material_block_bytes": material_bytes,
                "material_type": material_type,
                "material_type_name": material_type_name(material_type),
                "triangle_count": mesh_index_count / 3,
                "vertex_count": mesh_vertex_count,
            }));
            offset = section_end;
        }

        lods.push(json!({
            "index": lod_index,
            "index_count": index_count,
            "mesh_count": mesh_count,
            "meshes": meshes,
            "triangle_count": index_count / 3,
            "vertex_count": vertex_count,
            "visibility_distance": visibility_distance,
        }));
    }

    Ok(json!({
        "decoded_with_rpfm":validate_decode,
        "format":"rome2aoe2.rmv2-inspection",
        "highest_detail_lod":0,
        "input":input.to_string_lossy(),
        "lod_count":lod_count,
        "lods":lods,
        "rmv2_version":rmv2_version,
        "skeleton_id":skeleton_id,
        "version":1,
    }))
}

fn run(command: Command) -> Result<serde_json::Value, String> {
    match command {
        Command::InspectRmv2 {
            input,
            validate_decode,
        } => inspect_rmv2(&input, validate_decode),
        Command::CreateTestPack { spec, output } => {
            let document: serde_json::Value =
                serde_json::from_slice(&fs::read(&spec).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?;
            if document["format"] != "rome2aoe2.test-pack-spec" || document["version"] != 1 {
                return Err("Invalid test-pack specification format/version".to_owned());
            }
            let files = document["files"]
                .as_array()
                .ok_or_else(|| "Test-pack spec requires files".to_owned())?;
            let mut pack = Pack::new_with_version(PFHVersion::PFH4);
            pack.header_mut().set_pfh_file_type(PFHFileType::Release);
            let mut seen = std::collections::BTreeSet::new();
            for file in files {
                let path = file["path"]
                    .as_str()
                    .ok_or_else(|| "Test-pack file requires path".to_owned())?;
                let parsed = parse_pack_relative_path(path)?;
                if !seen.insert(parsed.comparison_key) {
                    return Err(format!("Duplicate normalized test-pack path '{}'", path));
                }
                let content = file["content_utf8"]
                    .as_str()
                    .ok_or_else(|| "Test-pack file requires content_utf8".to_owned())?;
                pack.files_mut().insert(
                    path.to_owned(),
                    RFile::new_from_vec(content.as_bytes(), FileType::Text, 0, path),
                );
            }
            if let Some(parent) = output.parent() {
                fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            }
            pack.save(Some(&output), rome_2_game()?, &None)
                .map_err(|e| e.to_string())?;
            Ok(
                json!({"format": RESULT_FORMAT, "version": RESULT_VERSION, "operation":"create-test-pack", "output": output.to_string_lossy(), "file_count": files.len()}),
            )
        }
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

    fn write_u16(bytes: &mut [u8], offset: usize, value: u16) {
        bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn synthetic_rmv2_v6_with_default_layout_material(material_type: u16) -> Vec<u8> {
        let mesh_offset = RMV2_V6_HEADER_BYTES + RMV2_V6_LOD_HEADER_BYTES;
        let vertex_offset = RMV2_V6_MATERIAL_OFFSET + DEFAULT_MATERIAL_FIXED_BYTES;
        let index_offset = vertex_offset + 28;
        let section_bytes = index_offset + 6;
        let mut bytes = vec![0; mesh_offset + section_bytes];
        bytes[..4].copy_from_slice(RMV2_MAGIC);
        write_u32(&mut bytes, 4, 6);
        write_u16(&mut bytes, 8, 1);
        bytes[12..20].copy_from_slice(b"test_rig");

        write_u32(&mut bytes, RMV2_V6_HEADER_BYTES, 1);
        write_u32(&mut bytes, RMV2_V6_HEADER_BYTES + 4, 28);
        write_u32(&mut bytes, RMV2_V6_HEADER_BYTES + 8, 6);
        write_u32(&mut bytes, RMV2_V6_HEADER_BYTES + 12, mesh_offset as u32);

        write_u16(&mut bytes, mesh_offset, material_type);
        write_u32(&mut bytes, mesh_offset + 4, section_bytes as u32);
        write_u32(&mut bytes, mesh_offset + 8, vertex_offset as u32);
        write_u32(&mut bytes, mesh_offset + 12, 1);
        write_u32(&mut bytes, mesh_offset + 16, index_offset as u32);
        write_u32(&mut bytes, mesh_offset + 20, 3);

        let material_offset = mesh_offset + RMV2_V6_MATERIAL_OFFSET;
        write_u16(&mut bytes, material_offset, 3);
        bytes[material_offset + 2..material_offset + 15].copy_from_slice(b"weighted_dirt");
        bytes[material_offset + 34..material_offset + 38].copy_from_slice(b"tex/");
        bytes
    }

    #[test]
    fn inspect_rmv2_reports_metadata_for_default_compatible_unknown_material() {
        let temp = tempdir().unwrap();
        let input = temp.path().join("weighted_dirtmap.rigid_model_v2");
        fs::write(&input, synthetic_rmv2_v6_with_default_layout_material(79)).unwrap();

        let result = inspect_rmv2(&input, false).unwrap();
        assert_eq!(result["rmv2_version"], 6);
        assert_eq!(result["skeleton_id"], "test_rig");
        assert_eq!(result["lod_count"], 1);
        assert_eq!(result["lods"][0]["meshes"][0]["material_type"], 79);
        assert_eq!(
            result["lods"][0]["meshes"][0]["material_type_name"],
            "WeightedDirtmap"
        );
        assert_eq!(
            result["lods"][0]["meshes"][0]["material"]["layout"],
            "default-material-compatible"
        );
        assert_eq!(
            result["lods"][0]["meshes"][0]["material"]["name"],
            "weighted_dirt"
        );
    }

    #[test]
    fn inspect_rmv2_rejects_invalid_magic() {
        let temp = tempdir().unwrap();
        let input = temp.path().join("invalid.rigid_model_v2");
        fs::write(&input, b"not an RMV2").unwrap();
        assert!(inspect_rmv2(&input, false)
            .unwrap_err()
            .contains("expected RMV2 magic"));
    }

    #[test]
    fn inspect_rmv2_json_is_deterministic() {
        let temp = tempdir().unwrap();
        let input = temp.path().join("weighted_dirtmap.rigid_model_v2");
        fs::write(&input, synthetic_rmv2_v6_with_default_layout_material(79)).unwrap();
        let first = serde_json::to_string(&inspect_rmv2(&input, false).unwrap()).unwrap();
        let second = serde_json::to_string(&inspect_rmv2(&input, false).unwrap()).unwrap();
        assert_eq!(first, second);
    }
}
