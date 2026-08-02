use std::env;
use std::fs;
use std::io::Cursor;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;
use std::sync::OnceLock;

use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine as _};
use rpfm_extensions::dependencies::Dependencies;
use rpfm_extensions::gltf::{gltf_from_rigid, save_gltf_to_disk};
use rpfm_lib::files::{pack::Pack, Container, ContainerPath, FileType, RFile};
use rpfm_lib::files::{
    rigidmodel::{MeshBlock, RigidModel},
    Decodeable,
};
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
    InspectSkeleton {
        anim: PathBuf,
        inverse_bind: PathBuf,
    },
    ExportRmv2Gltf {
        input: PathBuf,
        output: PathBuf,
        lod: LodSelection,
        skeleton_anim: Option<PathBuf>,
        inverse_bind: Option<PathBuf>,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum LodSelection {
    Highest,
    Index(usize),
}

fn usage() -> &'static str {
    "Usage:\n  rome2aoe2-pack list --pack <pack-file>\n  rome2aoe2-pack contains --pack <pack-file> --path <pack-relative-path>\n  rome2aoe2-pack extract --pack <pack-file> --path <pack-relative-path> --output-root <directory>\n  rome2aoe2-pack create-test-pack --spec <json-file> --output <pack-file>\n  rome2aoe2-pack inspect-rmv2 --input <local-rmv2-file> [--decode]\n  rome2aoe2-pack inspect-skeleton --anim <local-anim-file> --inverse-bind <local-bone-inv-trans-mats-file>\n  rome2aoe2-pack export-rmv2-gltf --input <local-rmv2-file> --output <output.gltf> --lod <highest|index> [--skeleton-anim <local-anim-file> --inverse-bind <local-bone-inv-trans-mats-file>]"
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
    let mut anim = None;
    let mut skeleton_anim = None;
    let mut inverse_bind = None;
    let mut validate_decode = false;
    let mut lod = None;
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
            "--anim" => anim = Some(PathBuf::from(value)),
            "--skeleton-anim" => skeleton_anim = Some(PathBuf::from(value)),
            "--inverse-bind" => inverse_bind = Some(PathBuf::from(value)),
            "--lod" => lod = Some(parse_lod_selection(value)?),
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
    if operation == "inspect-skeleton" {
        return Ok(Command::InspectSkeleton {
            anim: anim.ok_or_else(|| "Missing --anim".to_owned())?,
            inverse_bind: inverse_bind.ok_or_else(|| "Missing --inverse-bind".to_owned())?,
        });
    }
    if operation == "export-rmv2-gltf" {
        if skeleton_anim.is_some() != inverse_bind.is_some() {
            return Err(
                "Skinned export requires both --skeleton-anim and --inverse-bind".to_owned(),
            );
        }
        return Ok(Command::ExportRmv2Gltf {
            input: input.ok_or_else(|| "Missing --input".to_owned())?,
            output: output.ok_or_else(|| "Missing --output".to_owned())?,
            lod: lod.ok_or_else(|| "Missing --lod".to_owned())?,
            skeleton_anim,
            inverse_bind,
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

fn parse_lod_selection(value: &str) -> Result<LodSelection, String> {
    if value == "highest" {
        return Ok(LodSelection::Highest);
    }
    value
        .parse::<usize>()
        .map(LodSelection::Index)
        .map_err(|_| {
            format!(
                "Invalid --lod '{}': expected 'highest' or a non-negative LOD index",
                value
            )
        })
}

const SKELETON_INSPECTION_FORMAT: &str = "rome2aoe2.skeleton-inspection";
const SKELETON_INSPECTION_VERSION: u32 = 1;
const MATRIX_INVERSION_EPSILON: f64 = 1.0e-12;
const MATRIX_COMPARISON_EPSILON: f64 = 1.0e-8;

type Matrix4 = [[f64; 4]; 4];

#[derive(Clone, Debug)]
struct SkeletonBone {
    name: String,
    parent: Option<usize>,
}

#[derive(Clone, Debug)]
struct SkeletonAnim {
    skeleton_id: String,
    bones: Vec<SkeletonBone>,
    payload_bytes: usize,
}

fn take<const N: usize>(bytes: &[u8], offset: &mut usize, label: &str) -> Result<[u8; N], String> {
    let end = offset
        .checked_add(N)
        .ok_or_else(|| format!("{} offset overflows", label))?;
    let slice = bytes
        .get(*offset..end)
        .ok_or_else(|| format!("Truncated input while reading {} at byte {}", label, offset))?;
    *offset = end;
    Ok(slice.try_into().expect("slice length was checked"))
}

fn read_u16(bytes: &[u8], offset: &mut usize, label: &str) -> Result<u16, String> {
    Ok(u16::from_le_bytes(take(bytes, offset, label)?))
}

fn read_u32(bytes: &[u8], offset: &mut usize, label: &str) -> Result<u32, String> {
    Ok(u32::from_le_bytes(take(bytes, offset, label)?))
}

fn read_i32(bytes: &[u8], offset: &mut usize, label: &str) -> Result<i32, String> {
    Ok(i32::from_le_bytes(take(bytes, offset, label)?))
}

fn read_f32(bytes: &[u8], offset: &mut usize, label: &str) -> Result<f32, String> {
    Ok(f32::from_le_bytes(take(bytes, offset, label)?))
}

fn read_sized_string_u8(bytes: &[u8], offset: &mut usize, label: &str) -> Result<String, String> {
    let length = read_u16(bytes, offset, &format!("{} length", label))? as usize;
    let end = offset
        .checked_add(length)
        .ok_or_else(|| format!("{} length overflows", label))?;
    let value = bytes
        .get(*offset..end)
        .ok_or_else(|| format!("Truncated input while reading {} at byte {}", label, offset))?;
    *offset = end;
    String::from_utf8(value.to_vec()).map_err(|_| format!("{} is not valid UTF-8", label))
}

fn validate_hierarchy(bones: &[SkeletonBone]) -> Result<Vec<usize>, String> {
    let mut names = std::collections::BTreeSet::new();
    for (index, bone) in bones.iter().enumerate() {
        if bone.name.is_empty() {
            return Err(format!("Bone {} has an empty name", index));
        }
        if !names.insert(bone.name.clone()) {
            return Err(format!(
                "Duplicate bone name '{}' at index {}",
                bone.name, index
            ));
        }
        if let Some(parent) = bone.parent {
            if parent >= bones.len() {
                return Err(format!(
                    "Bone {} ('{}') has invalid parent index {} for {} bones",
                    index,
                    bone.name,
                    parent,
                    bones.len()
                ));
            }
        }
    }

    fn visit(index: usize, bones: &[SkeletonBone], states: &mut [u8]) -> Result<(), String> {
        match states[index] {
            1 => {
                return Err(format!(
                    "Skeleton hierarchy contains a cycle at bone {} ('{}')",
                    index, bones[index].name
                ))
            }
            2 => return Ok(()),
            _ => {}
        }
        states[index] = 1;
        if let Some(parent) = bones[index].parent {
            visit(parent, bones, states)?;
        }
        states[index] = 2;
        Ok(())
    }

    let mut states = vec![0; bones.len()];
    for index in 0..bones.len() {
        visit(index, bones, &mut states)?;
    }
    Ok(bones
        .iter()
        .enumerate()
        .filter_map(|(index, bone)| bone.parent.is_none().then_some(index))
        .collect())
}

fn decode_skeleton_anim(bytes: &[u8]) -> Result<SkeletonAnim, String> {
    let mut offset = 0;
    let version = read_u32(bytes, &mut offset, "animation version")?;
    if version != 5 {
        return Err(format!(
            "Unsupported skeleton .anim version {}; expected 5",
            version
        ));
    }
    let _unknown = read_u32(bytes, &mut offset, "animation header field")?;
    let frame_rate = read_f32(bytes, &mut offset, "animation frame rate")?;
    if !frame_rate.is_finite() {
        return Err("Skeleton .anim frame rate is not finite".to_owned());
    }
    let skeleton_id = read_sized_string_u8(bytes, &mut offset, "skeleton identifier")?;
    if skeleton_id.is_empty() {
        return Err("Skeleton identifier is empty".to_owned());
    }
    let end_time = read_f32(bytes, &mut offset, "animation end time")?;
    if !end_time.is_finite() {
        return Err("Skeleton .anim end time is not finite".to_owned());
    }
    let bone_count = read_u32(bytes, &mut offset, "bone count")? as usize;
    let mut bones = Vec::with_capacity(bone_count);
    for index in 0..bone_count {
        let name = read_sized_string_u8(bytes, &mut offset, &format!("bone {} name", index))?;
        let raw_parent = read_i32(bytes, &mut offset, &format!("bone {} parent", index))?;
        let parent = match raw_parent {
            -1 => None,
            value if value >= 0 => Some(value as usize),
            value => {
                return Err(format!(
                    "Bone {} has unsupported parent sentinel {}",
                    index, value
                ))
            }
        };
        bones.push(SkeletonBone { name, parent });
    }
    validate_hierarchy(&bones)?;
    Ok(SkeletonAnim {
        skeleton_id,
        bones,
        payload_bytes: bytes.len() - offset,
    })
}

fn decode_inverse_bind(bytes: &[u8]) -> Result<(u32, Vec<Matrix4>), String> {
    let mut offset = 0;
    let version = read_u32(bytes, &mut offset, "inverse-bind version")?;
    if version != 1 {
        return Err(format!(
            "Unsupported inverse-bind version {}; expected 1",
            version
        ));
    }
    let count = read_u32(bytes, &mut offset, "inverse-bind matrix count")? as usize;
    let expected = 8usize
        .checked_add(
            count
                .checked_mul(48)
                .ok_or_else(|| "Inverse-bind matrix byte count overflows".to_owned())?,
        )
        .ok_or_else(|| "Inverse-bind file size overflows".to_owned())?;
    if bytes.len() != expected {
        return Err(format!(
            "Inverse-bind file size mismatch: declared {} matrices require {} bytes, found {}",
            count,
            expected,
            bytes.len()
        ));
    }
    let mut matrices = Vec::with_capacity(count);
    for matrix_index in 0..count {
        let mut stored = [0.0; 12];
        for (entry, value) in stored.iter_mut().enumerate() {
            *value = read_f32(
                bytes,
                &mut offset,
                &format!(
                    "inverse-bind matrix {} stored entry {}",
                    matrix_index, entry
                ),
            )? as f64;
            if !value.is_finite() {
                return Err(format!(
                    "Inverse-bind matrix {} contains a non-finite value at stored entry {}",
                    matrix_index, entry
                ));
            }
        }
        let mut matrix = [[0.0; 4]; 4];
        for row in 0..3 {
            for column in 0..4 {
                // The file stores a row-vector affine 4x3: three basis rows
                // followed by a translation row. Normalize it by transposing
                // into the column-vector 4x4 convention used by this command.
                matrix[row][column] = stored[column * 3 + row];
            }
        }
        matrix[3][3] = 1.0;
        matrices.push(matrix);
    }
    Ok((version, matrices))
}

fn multiply_matrix(left: &Matrix4, right: &Matrix4) -> Matrix4 {
    let mut result = [[0.0; 4]; 4];
    for row in 0..4 {
        for column in 0..4 {
            result[row][column] = (0..4).map(|k| left[row][k] * right[k][column]).sum();
        }
    }
    result
}

fn matrices_approximately_equal(left: &Matrix4, right: &Matrix4) -> bool {
    left.iter()
        .flatten()
        .zip(right.iter().flatten())
        .all(|(left, right)| {
            let scale = 1.0f64.max(left.abs()).max(right.abs());
            (left - right).abs() <= MATRIX_COMPARISON_EPSILON * scale
        })
}

fn invert_matrix(matrix: &Matrix4, label: &str) -> Result<Matrix4, String> {
    let mut augmented = [[0.0; 8]; 4];
    for row in 0..4 {
        for column in 0..4 {
            augmented[row][column] = matrix[row][column];
        }
        augmented[row][row + 4] = 1.0;
    }
    for column in 0..4 {
        let pivot_row = (column..4)
            .max_by(|left, right| {
                augmented[*left][column]
                    .abs()
                    .total_cmp(&augmented[*right][column].abs())
            })
            .expect("pivot range is nonempty");
        let pivot = augmented[pivot_row][column];
        if !pivot.is_finite() || pivot.abs() <= MATRIX_INVERSION_EPSILON {
            return Err(format!("{} is singular at column {}", label, column));
        }
        augmented.swap(column, pivot_row);
        for value in &mut augmented[column] {
            *value /= pivot;
        }
        for row in 0..4 {
            if row == column {
                continue;
            }
            let factor = augmented[row][column];
            for entry in 0..8 {
                augmented[row][entry] -= factor * augmented[column][entry];
            }
        }
    }
    let mut inverse = [[0.0; 4]; 4];
    for row in 0..4 {
        inverse[row].copy_from_slice(&augmented[row][4..8]);
    }
    if inverse.iter().flatten().any(|value| !value.is_finite()) {
        return Err(format!("{} inverse contains a non-finite value", label));
    }
    Ok(inverse)
}

fn inspect_skeleton_bytes(
    anim_bytes: &[u8],
    inverse_bind_bytes: &[u8],
) -> Result<serde_json::Value, String> {
    let anim = decode_skeleton_anim(anim_bytes)?;
    let roots = validate_hierarchy(&anim.bones)?;
    let (inverse_bind_version, inverse_bind_matrices) = decode_inverse_bind(inverse_bind_bytes)?;
    if anim.bones.len() != inverse_bind_matrices.len() {
        return Err(format!(
            "Bone-count/matrix-count mismatch: .anim contains {} bones, inverse-bind file contains {} matrices",
            anim.bones.len(), inverse_bind_matrices.len()
        ));
    }
    let mut world_bind_matrices = Vec::with_capacity(anim.bones.len());
    for (index, matrix) in inverse_bind_matrices.iter().enumerate() {
        let world = invert_matrix(matrix, &format!("Inverse-bind matrix {}", index))?;
        if !matrices_approximately_equal(
            &multiply_matrix(matrix, &world),
            &[
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        ) {
            return Err(format!(
                "Inverse-bind matrix {} failed inversion verification",
                index
            ));
        }
        world_bind_matrices.push(world);
    }
    let mut local_bind_matrices = Vec::with_capacity(anim.bones.len());
    for (index, bone) in anim.bones.iter().enumerate() {
        let local = if let Some(parent) = bone.parent {
            multiply_matrix(&inverse_bind_matrices[parent], &world_bind_matrices[index])
        } else {
            world_bind_matrices[index]
        };
        if local.iter().flatten().any(|value| !value.is_finite()) {
            return Err(format!(
                "Derived local bind matrix {} contains a non-finite value",
                index
            ));
        }
        if let Some(parent) = bone.parent {
            if !matrices_approximately_equal(
                &multiply_matrix(&world_bind_matrices[parent], &local),
                &world_bind_matrices[index],
            ) {
                return Err(format!(
                    "Derived local bind matrix {} failed composition verification",
                    index
                ));
            }
        }
        local_bind_matrices.push(local);
    }
    let bones = anim
        .bones
        .iter()
        .enumerate()
        .map(|(index, bone)| {
            json!({
                "index": index,
                "name": bone.name,
                "parent": bone.parent,
                "local_bind_matrix": local_bind_matrices[index],
                "world_bind_matrix": world_bind_matrices[index],
                "inverse_bind_matrix": inverse_bind_matrices[index],
            })
        })
        .collect::<Vec<_>>();
    let attachment_ids = [1usize, 2, 3, 4, 5, 23]
        .into_iter()
        .map(|bone_id| {
            let bone = anim.bones.get(bone_id).ok_or_else(|| {
                format!(
                    "Known attachment bone ID {} is outside the skeleton",
                    bone_id
                )
            })?;
            Ok(json!({"bone_id": bone_id, "bone_name": bone.name}))
        })
        .collect::<Result<Vec<_>, String>>()?;
    Ok(json!({
        "format": SKELETON_INSPECTION_FORMAT,
        "version": SKELETON_INSPECTION_VERSION,
        "skeleton_id": anim.skeleton_id,
        "anim_version": 5,
        "inverse_bind_version": inverse_bind_version,
        "bone_count": anim.bones.len(),
        "roots": roots,
        "anim_payload": {
            "additional_pose_data_present": anim.payload_bytes != 0,
            "bytes": anim.payload_bytes,
            "decoded": false,
        },
        "matrix_convention": {
            "source_storage": "row-major affine 4x3 using row vectors; translation is the fourth stored row",
            "output_storage": "row-major 4x4 JSON arrays",
            "vectors": "column vectors (p' = M * p)",
            "translation": "fourth column",
            "composition": "world = parent_world * local",
            "gltf_conversion": "output matrices already use glTF's column-vector transform convention; flatten column-major when writing a glTF MAT4 accessor",
        },
        "resolved_attachment_bone_ids": attachment_ids,
        "bones": bones,
    }))
}

fn inspect_skeleton(anim: &Path, inverse_bind: &Path) -> Result<serde_json::Value, String> {
    let anim_bytes = fs::read(anim).map_err(|error| {
        format!(
            "Unable to read skeleton .anim '{}': {}",
            anim.display(),
            error
        )
    })?;
    let inverse_bind_bytes = fs::read(inverse_bind).map_err(|error| {
        format!(
            "Unable to read inverse-bind file '{}': {}",
            inverse_bind.display(),
            error
        )
    })?;
    inspect_skeleton_bytes(&anim_bytes, &inverse_bind_bytes)
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

fn selected_lod_index(selection: LodSelection, lod_count: usize) -> Result<usize, String> {
    let index = match selection {
        // RPFM documents the decoded LOD vector as highest-to-lowest quality.
        LodSelection::Highest => 0,
        LodSelection::Index(index) => index,
    };
    if index >= lod_count {
        return Err(format!(
            "Invalid LOD index {}: RMV2 contains {} LOD(s)",
            index, lod_count
        ));
    }
    Ok(index)
}

fn output_gltf_path(output: &Path) -> Result<(), String> {
    if output.file_name().is_none() {
        return Err(format!(
            "Invalid glTF output path '{}': file name is required",
            output.display()
        ));
    }
    if !output
        .extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case("gltf"))
    {
        return Err(format!(
            "Invalid glTF output path '{}': expected a .gltf file",
            output.display()
        ));
    }
    Ok(())
}

fn ensure_gltf_output_parent(output: &Path) -> Result<(), String> {
    if let Some(parent) = output.parent() {
        fs::create_dir_all(parent).map_err(|error| {
            format!(
                "Unable to create glTF output directory '{}': {}",
                parent.display(),
                error
            )
        })?;
    }
    Ok(())
}

fn filtered_model_for_lod(model: &RigidModel, lod_index: usize) -> Result<RigidModel, String> {
    let selected_lod = model.lods().get(lod_index).cloned().ok_or_else(|| {
        format!(
            "Invalid LOD index {}: RMV2 contains {} LOD(s)",
            lod_index,
            model.lods().len()
        )
    })?;
    let mut filtered_model = model.clone();
    *filtered_model.lods_mut() = vec![selected_lod];
    Ok(filtered_model)
}

fn gltf_export_result(
    input_name: &str,
    output_name: &str,
    model: &RigidModel,
    lod_index: usize,
    mesh_count: usize,
    vertex_count: usize,
    index_count: usize,
    materials: Vec<serde_json::Value>,
) -> serde_json::Value {
    json!({
        "format": "rome2aoe2.rmv2-gltf-export",
        "input": input_name,
        "material_types": materials,
        "mesh_count": mesh_count,
        "output": output_name,
        "rmv2_version": model.version(),
        "selected_lod": lod_index,
        "skeleton_id": model.skeleton_id(),
        "triangle_count": index_count / 3,
        "vertex_count": vertex_count,
        "version": 1,
    })
}

fn rmv2_material_metadata(mesh_block: &MeshBlock) -> serde_json::Value {
    let material = mesh_block.material();
    json!({
        "attachment_count": material.attachment_points().len(),
        "attachments": material.attachment_points().iter().map(|attachment| {
            let matrix = attachment.matrix();
            json!({
                "bone_id": attachment.bone_id(),
                "matrix": [
                    [matrix.m11, matrix.m12, matrix.m13, matrix.m14],
                    [matrix.m21, matrix.m22, matrix.m23, matrix.m24],
                    [matrix.m31, matrix.m32, matrix.m33, matrix.m34],
                ],
                "name": attachment.name(),
            })
        }).collect::<Vec<_>>(),
        "name": material.name(),
        "parameter_counts": {
            "float": material.params_f32().len(),
            "integer": material.params_i32().len(),
            "string": material.params_string().len(),
            "vector4": material.params_vector4df32().len(),
        },
        "parameters": {
            "float": material.params_f32(),
            "integer": material.params_i32(),
            "string": material.params_string(),
            "vector4": material.params_vector4df32().iter().map(|(key, value)| json!([key, [value[0], value[1], value[2], value[3]]])).collect::<Vec<_>>(),
        },
        "texture_directory": material.texture_directory(),
        "textures": material.textures().iter().map(|texture| json!({
            "path": texture.path(),
            "type": format!("{:?}", texture.tex_type()),
        })).collect::<Vec<_>>(),
        "type": format!("{:?}", mesh_block.mesh().material_type()),
    })
}

fn preserve_gltf_material_identity(
    output: &Path,
    source_materials: &[serde_json::Value],
) -> Result<(), String> {
    let mut document: serde_json::Value =
        serde_json::from_slice(&fs::read(output).map_err(|error| {
            format!(
                "Unable to read generated glTF '{}': {}",
                output.display(),
                error
            )
        })?)
        .map_err(|error| {
            format!(
                "Generated glTF '{}' is invalid JSON: {}",
                output.display(),
                error
            )
        })?;
    let gltf_materials = document
        .get_mut("materials")
        .and_then(serde_json::Value::as_array_mut)
        .ok_or_else(|| {
            format!(
                "Generated glTF '{}' has no material array",
                output.display()
            )
        })?;
    if gltf_materials.len() != source_materials.len() {
        return Err(format!(
            "Generated glTF '{}' has {} material(s), but selected RMV2 LOD has {} mesh material(s)",
            output.display(),
            gltf_materials.len(),
            source_materials.len()
        ));
    }
    for (gltf_material, source_material) in gltf_materials.iter_mut().zip(source_materials) {
        let source_name = source_material
            .get("name")
            .and_then(serde_json::Value::as_str)
            .ok_or_else(|| "RMV2 material metadata has no string name".to_owned())?;
        let object = gltf_material
            .as_object_mut()
            .ok_or_else(|| "Generated glTF material is not an object".to_owned())?;
        object.insert("name".to_owned(), json!(source_name));
        object.insert("extras".to_owned(), json!({"rome2aoe2": source_material}));
    }
    fs::write(
        output,
        serde_json::to_vec_pretty(&document).expect("glTF JSON must serialize"),
    )
    .map_err(|error| {
        format!(
            "Unable to update glTF material metadata '{}': {}",
            output.display(),
            error
        )
    })
}

fn json_matrix4(value: &serde_json::Value, label: &str) -> Result<Matrix4, String> {
    let rows = value
        .as_array()
        .ok_or_else(|| format!("{} is not a matrix", label))?;
    if rows.len() != 4 {
        return Err(format!("{} does not have four rows", label));
    }
    let mut matrix = [[0.0; 4]; 4];
    for (row_index, row) in rows.iter().enumerate() {
        let columns = row
            .as_array()
            .ok_or_else(|| format!("{} row {} is not an array", label, row_index))?;
        if columns.len() != 4 {
            return Err(format!(
                "{} row {} does not have four columns",
                label, row_index
            ));
        }
        for (column_index, entry) in columns.iter().enumerate() {
            matrix[row_index][column_index] = entry.as_f64().ok_or_else(|| {
                format!("{} [{},{}] is not numeric", label, row_index, column_index)
            })?;
        }
    }
    Ok(matrix)
}

fn gltf_column_major_matrix(matrix: &Matrix4) -> Vec<serde_json::Value> {
    (0..4)
        .flat_map(|column| (0..4).map(move |row| json!(matrix[row][column])))
        .collect()
}

fn inverse_bind_binary(inspection: &serde_json::Value) -> Result<Vec<u8>, String> {
    let bones = inspection["bones"]
        .as_array()
        .ok_or_else(|| "Skeleton inspection has no bones array".to_owned())?;
    let mut bytes = Vec::with_capacity(bones.len() * 64);
    for (index, bone) in bones.iter().enumerate() {
        let matrix = json_matrix4(
            &bone["inverse_bind_matrix"],
            &format!("Bone {} inverse bind matrix", index),
        )?;
        for column in 0..4 {
            for row in 0..4 {
                let value = matrix[row][column] as f32;
                if !value.is_finite() {
                    return Err(format!(
                        "Bone {} inverse bind matrix cannot be represented as finite f32",
                        index
                    ));
                }
                bytes.extend_from_slice(&value.to_le_bytes());
            }
        }
    }
    Ok(bytes)
}

fn replace_skin_attribute_data(
    document: &mut serde_json::Value,
    attributes: &[(Vec<u8>, Vec<u8>, usize)],
) -> Result<(), String> {
    let meshes = document["meshes"]
        .as_array()
        .ok_or_else(|| "Generated glTF has no meshes array".to_owned())?;
    if meshes.len() != attributes.len() {
        return Err(format!(
            "Generated glTF has {} meshes but decoded LOD has {} skin attribute sets",
            meshes.len(),
            attributes.len()
        ));
    }
    let accessor_pairs = meshes
        .iter()
        .enumerate()
        .map(|(index, mesh)| {
            let primitive = mesh["primitives"]
                .as_array()
                .and_then(|items| items.first())
                .ok_or_else(|| format!("glTF mesh {} has no primitive", index))?;
            let joints = primitive["attributes"]["JOINTS_0"]
                .as_u64()
                .ok_or_else(|| format!("glTF mesh {} has no JOINTS_0 accessor", index))?
                as usize;
            let weights = primitive["attributes"]["WEIGHTS_0"]
                .as_u64()
                .ok_or_else(|| format!("glTF mesh {} has no WEIGHTS_0 accessor", index))?
                as usize;
            Ok((joints, weights))
        })
        .collect::<Result<Vec<_>, String>>()?;

    for (mesh_index, ((joint_bytes, weight_bytes, count), (joint_accessor, weight_accessor))) in
        attributes.iter().zip(accessor_pairs).enumerate()
    {
        if joint_bytes.len() != count * 4 || weight_bytes.len() != count * 16 {
            return Err(format!(
                "Skin attribute byte count is invalid for mesh {}",
                mesh_index
            ));
        }
        let buffer_index = document["buffers"].as_array().map_or(0, Vec::len);
        document
            .as_object_mut().unwrap()
            .entry("buffers")
            .or_insert_with(|| json!([]))
            .as_array_mut().unwrap()
            .push(json!({
                "byteLength": joint_bytes.len() + weight_bytes.len(),
                "uri": format!("data:application/octet-stream;base64,{}", BASE64_STANDARD.encode([joint_bytes.as_slice(), weight_bytes.as_slice()].concat())),
            }));
        let view_index = document["bufferViews"].as_array().map_or(0, Vec::len);
        let views = document
            .as_object_mut()
            .unwrap()
            .entry("bufferViews")
            .or_insert_with(|| json!([]))
            .as_array_mut()
            .unwrap();
        views.push(json!({"buffer": buffer_index, "byteLength": joint_bytes.len()}));
        views.push(json!({"buffer": buffer_index, "byteOffset": joint_bytes.len(), "byteLength": weight_bytes.len()}));
        let accessors = document["accessors"].as_array_mut().unwrap();
        for (accessor_index, buffer_view, component_type) in [
            (joint_accessor, view_index, 5121),
            (weight_accessor, view_index + 1, 5126),
        ] {
            let accessor = accessors
                .get_mut(accessor_index)
                .and_then(serde_json::Value::as_object_mut)
                .ok_or_else(|| format!("Skin accessor {} is invalid", accessor_index))?;
            accessor.insert("bufferView".to_owned(), json!(buffer_view));
            accessor.insert("byteOffset".to_owned(), json!(0));
            accessor.insert("componentType".to_owned(), json!(component_type));
            accessor.insert("count".to_owned(), json!(count));
            accessor.insert("type".to_owned(), json!("VEC4"));
        }
    }
    Ok(())
}

fn decoded_skin_attribute_data(
    lod: &rpfm_lib::files::rigidmodel::Lod,
) -> Vec<(Vec<u8>, Vec<u8>, usize)> {
    lod.mesh_blocks()
        .iter()
        .map(|block| {
            let vertices = block.mesh().vertices();
            let mut joints = Vec::with_capacity(vertices.len() * 4);
            let mut weights = Vec::with_capacity(vertices.len() * 16);
            for vertex in vertices {
                let indices = vertex.bone_indices();
                joints.extend_from_slice(&[indices.x, indices.y, indices.z, indices.w]);
                let vertex_weights = vertex.weights();
                for value in [
                    vertex_weights.x,
                    vertex_weights.y,
                    vertex_weights.z,
                    vertex_weights.w,
                ] {
                    weights.extend_from_slice(&value.to_le_bytes());
                }
            }
            (joints, weights, vertices.len())
        })
        .collect()
}

fn augment_gltf_with_skin_document(
    document: &mut serde_json::Value,
    inspection: &serde_json::Value,
) -> Result<(), String> {
    let bones = inspection["bones"]
        .as_array()
        .ok_or_else(|| "Skeleton inspection has no bones array".to_owned())?;
    let roots = inspection["roots"]
        .as_array()
        .ok_or_else(|| "Skeleton inspection has no roots array".to_owned())?;
    if bones.is_empty() {
        return Err("Cannot create a glTF skin for an empty skeleton".to_owned());
    }

    let nodes = document
        .get_mut("nodes")
        .and_then(serde_json::Value::as_array_mut)
        .ok_or_else(|| "Generated glTF has no nodes array".to_owned())?;
    let original_node_count = nodes.len();
    let wrapper_node = original_node_count;
    let first_joint_node = wrapper_node + 1;
    let root_children = roots
        .iter()
        .map(|root| {
            root.as_u64()
                .map(|index| first_joint_node + index as usize)
                .ok_or_else(|| "Skeleton root is not an index".to_owned())
        })
        .collect::<Result<Vec<_>, String>>()?;
    nodes.push(json!({
        "name": format!("{}_skeleton", inspection["skeleton_id"].as_str().unwrap_or("skeleton")),
        "children": root_children,
    }));
    for (index, bone) in bones.iter().enumerate() {
        if bone["index"].as_u64() != Some(index as u64) {
            return Err(format!(
                "Skeleton bone ordering is unstable at index {}",
                index
            ));
        }
        let local = json_matrix4(
            &bone["local_bind_matrix"],
            &format!("Bone {} local bind matrix", index),
        )?;
        let children = bones
            .iter()
            .enumerate()
            .filter_map(|(child_index, child)| {
                (child["parent"].as_u64() == Some(index as u64))
                    .then_some(first_joint_node + child_index)
            })
            .collect::<Vec<_>>();
        let mut node = serde_json::Map::new();
        node.insert(
            "name".to_owned(),
            json!(bone["name"]
                .as_str()
                .ok_or_else(|| format!("Bone {} has no name", index))?),
        );
        node.insert(
            "matrix".to_owned(),
            serde_json::Value::Array(gltf_column_major_matrix(&local)),
        );
        if !children.is_empty() {
            node.insert("children".to_owned(), json!(children));
        }
        nodes.push(serde_json::Value::Object(node));
    }

    let bytes = inverse_bind_binary(inspection)?;
    let buffers = document
        .as_object_mut()
        .ok_or_else(|| "Generated glTF root is not an object".to_owned())?
        .entry("buffers")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or_else(|| "Generated glTF buffers is not an array".to_owned())?;
    let buffer_index = buffers.len();
    buffers.push(json!({
        "byteLength": bytes.len(),
        "uri": format!("data:application/octet-stream;base64,{}", BASE64_STANDARD.encode(&bytes)),
    }));
    let buffer_views = document
        .as_object_mut()
        .unwrap()
        .entry("bufferViews")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or_else(|| "Generated glTF bufferViews is not an array".to_owned())?;
    let buffer_view_index = buffer_views.len();
    buffer_views.push(json!({"buffer": buffer_index, "byteLength": bytes.len()}));
    let accessors = document
        .as_object_mut()
        .unwrap()
        .entry("accessors")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or_else(|| "Generated glTF accessors is not an array".to_owned())?;
    let accessor_index = accessors.len();
    accessors.push(json!({
        "bufferView": buffer_view_index,
        "byteOffset": 0,
        "componentType": 5126,
        "count": bones.len(),
        "type": "MAT4",
    }));
    let skins = document
        .as_object_mut()
        .unwrap()
        .entry("skins")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or_else(|| "Generated glTF skins is not an array".to_owned())?;
    let skin_index = skins.len();
    skins.push(json!({
        "name": inspection["skeleton_id"],
        "inverseBindMatrices": accessor_index,
        "joints": (0..bones.len()).map(|index| first_joint_node + index).collect::<Vec<_>>(),
        "skeleton": wrapper_node,
    }));

    let nodes = document["nodes"].as_array_mut().unwrap();
    for node in nodes.iter_mut().take(original_node_count) {
        if node.get("mesh").is_some() {
            node.as_object_mut()
                .ok_or_else(|| "Generated glTF mesh node is not an object".to_owned())?
                .insert("skin".to_owned(), json!(skin_index));
        }
    }
    let scenes = document["scenes"]
        .as_array_mut()
        .ok_or_else(|| "Generated glTF has no scenes array".to_owned())?;
    for scene in scenes {
        scene
            .as_object_mut()
            .ok_or_else(|| "Generated glTF scene is not an object".to_owned())?
            .entry("nodes")
            .or_insert_with(|| json!([]))
            .as_array_mut()
            .ok_or_else(|| "Generated glTF scene nodes is not an array".to_owned())?
            .push(json!(wrapper_node));
    }
    Ok(())
}

fn add_gltf_skin(
    output: &Path,
    inspection: &serde_json::Value,
    attributes: &[(Vec<u8>, Vec<u8>, usize)],
) -> Result<(), String> {
    let mut document: serde_json::Value = serde_json::from_slice(
        &fs::read(output)
            .map_err(|error| format!("Unable to read glTF '{}': {}", output.display(), error))?,
    )
    .map_err(|error| {
        format!(
            "Unable to decode glTF JSON '{}': {}",
            output.display(),
            error
        )
    })?;
    replace_skin_attribute_data(&mut document, attributes)?;
    augment_gltf_with_skin_document(&mut document, inspection)?;
    fs::write(
        output,
        serde_json::to_vec_pretty(&document).expect("skinned glTF JSON must serialize"),
    )
    .map_err(|error| {
        format!(
            "Unable to write skinned glTF '{}': {}",
            output.display(),
            error
        )
    })
}

fn validate_skin_skeleton_id(
    rmv2_skeleton_id: &str,
    inspection: &serde_json::Value,
) -> Result<(), String> {
    if rmv2_skeleton_id.is_empty() {
        return Err("Cannot create a skin because the RMV2 skeleton ID is empty".to_owned());
    }
    let resource_id = inspection["skeleton_id"]
        .as_str()
        .ok_or_else(|| "Skeleton inspection has no identifier".to_owned())?;
    if resource_id != rmv2_skeleton_id {
        return Err(format!(
            "Skeleton ID mismatch: RMV2 references '{}', skeleton resource identifies '{}'",
            rmv2_skeleton_id, resource_id
        ));
    }
    Ok(())
}

fn export_rmv2_gltf(
    input: &Path,
    output: &Path,
    selection: LodSelection,
    skeleton_resources: Option<(&Path, &Path)>,
) -> Result<serde_json::Value, String> {
    output_gltf_path(output)?;
    let bytes = fs::read(input)
        .map_err(|error| format!("Unable to read RMV2 '{}': {}", input.display(), error))?;
    let mut reader = Cursor::new(bytes);
    let model = RigidModel::decode(&mut reader, &None)
        .map_err(|error| format!("Unable to decode RMV2 '{}': {}", input.display(), error))?;
    let skeleton_inspection = if let Some((anim, inverse_bind)) = skeleton_resources {
        let inspection = inspect_skeleton(anim, inverse_bind)?;
        validate_skin_skeleton_id(model.skeleton_id(), &inspection)?;
        Some(inspection)
    } else {
        None
    };
    let lod_index = selected_lod_index(selection, model.lods().len())?;
    let selected_lod = model.lods()[lod_index].clone();
    let mesh_count = selected_lod.mesh_blocks().len();
    let vertex_count = selected_lod
        .mesh_blocks()
        .iter()
        .map(|mesh| mesh.mesh().vertices().len())
        .sum::<usize>();
    let index_count = selected_lod
        .mesh_blocks()
        .iter()
        .map(|mesh| mesh.mesh().indices().len())
        .sum::<usize>();
    let source_materials = selected_lod
        .mesh_blocks()
        .iter()
        .map(rmv2_material_metadata)
        .collect::<Vec<_>>();
    let materials = source_materials
        .iter()
        .map(|material| json!({"name": material["name"], "type": material["type"]}))
        .collect::<Vec<_>>();

    // The upstream exporter emits one scene per entry in `lods`. Keep a clone so
    // the decoded model remains intact while the exporter receives exactly one LOD.
    let filtered_model = filtered_model_for_lod(&model, lod_index)?;

    ensure_gltf_output_parent(output)?;
    let mut dependencies = Dependencies::default();
    let gltf = gltf_from_rigid(&filtered_model, &mut dependencies).map_err(|error| {
        format!(
            "Unable to export RMV2 '{}' LOD {} as glTF '{}': {}",
            input.display(),
            lod_index,
            output.display(),
            error
        )
    })?;
    save_gltf_to_disk(&gltf, output).map_err(|error| {
        format!(
            "Unable to write glTF '{}' for RMV2 '{}': {}",
            output.display(),
            input.display(),
            error
        )
    })?;
    if !output.is_file() {
        return Err(format!(
            "glTF export for '{}' reported success but output '{}' was not created",
            input.display(),
            output.display()
        ));
    }
    preserve_gltf_material_identity(output, &source_materials)?;
    if let Some(inspection) = &skeleton_inspection {
        add_gltf_skin(
            output,
            inspection,
            &decoded_skin_attribute_data(&selected_lod),
        )?;
    }

    Ok(gltf_export_result(
        input
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("<non-utf8>"),
        output
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("<non-utf8>"),
        &model,
        lod_index,
        mesh_count,
        vertex_count,
        index_count,
        materials,
    ))
}

fn run(command: Command) -> Result<serde_json::Value, String> {
    match command {
        Command::InspectRmv2 {
            input,
            validate_decode,
        } => inspect_rmv2(&input, validate_decode),
        Command::InspectSkeleton { anim, inverse_bind } => inspect_skeleton(&anim, &inverse_bind),
        Command::ExportRmv2Gltf {
            input,
            output,
            lod,
            skeleton_anim,
            inverse_bind,
        } => export_rmv2_gltf(
            &input,
            &output,
            lod,
            skeleton_anim.as_deref().zip(inverse_bind.as_deref()),
        ),
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

    fn synthetic_anim(version: u32, parents: &[i32]) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&version.to_le_bytes());
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&20.0f32.to_le_bytes());
        let skeleton_id = b"synthetic_skeleton";
        bytes.extend_from_slice(&(skeleton_id.len() as u16).to_le_bytes());
        bytes.extend_from_slice(skeleton_id);
        bytes.extend_from_slice(&0.1f32.to_le_bytes());
        bytes.extend_from_slice(&(parents.len() as u32).to_le_bytes());
        for (index, parent) in parents.iter().enumerate() {
            let name = format!("bone_{:02}", index);
            bytes.extend_from_slice(&(name.len() as u16).to_le_bytes());
            bytes.extend_from_slice(name.as_bytes());
            bytes.extend_from_slice(&parent.to_le_bytes());
        }
        bytes.extend_from_slice(&[0xaa, 0xbb, 0xcc, 0xdd]);
        bytes
    }

    fn translation_matrix(x: f32, y: f32, z: f32) -> [[f32; 4]; 3] {
        [[1.0, 0.0, 0.0, x], [0.0, 1.0, 0.0, y], [0.0, 0.0, 1.0, z]]
    }

    fn synthetic_inverse_bind(version: u32, matrices: &[[[f32; 4]; 3]]) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&version.to_le_bytes());
        bytes.extend_from_slice(&(matrices.len() as u32).to_le_bytes());
        for matrix in matrices {
            for stored_row in 0..4 {
                for stored_column in 0..3 {
                    bytes.extend_from_slice(&matrix[stored_column][stored_row].to_le_bytes());
                }
            }
        }
        bytes
    }

    fn valid_parents() -> Vec<i32> {
        let mut parents = vec![-1];
        parents.extend((0..23).map(|index| index as i32));
        parents
    }

    fn identity_inverse_binds(count: usize) -> Vec<[[f32; 4]; 3]> {
        vec![translation_matrix(0.0, 0.0, 0.0); count]
    }

    #[test]
    fn skeleton_accepts_valid_synthetic_hierarchy() {
        let parents = valid_parents();
        let result = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &identity_inverse_binds(parents.len())),
        )
        .unwrap();
        assert_eq!(result["bone_count"], 24);
        assert_eq!(result["anim_payload"]["bytes"], 4);
    }

    #[test]
    fn skeleton_accepts_multiple_roots() {
        let mut parents = valid_parents();
        parents[7] = -1;
        let result = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &identity_inverse_binds(parents.len())),
        )
        .unwrap();
        assert_eq!(result["roots"], json!([0, 7]));
    }

    #[test]
    fn skeleton_rejects_invalid_parent_index() {
        let mut parents = valid_parents();
        parents[3] = 99;
        assert!(decode_skeleton_anim(&synthetic_anim(5, &parents))
            .unwrap_err()
            .contains("invalid parent index"));
    }

    #[test]
    fn skeleton_rejects_direct_cycle() {
        let mut parents = valid_parents();
        parents[3] = 3;
        assert!(decode_skeleton_anim(&synthetic_anim(5, &parents))
            .unwrap_err()
            .contains("cycle"));
    }

    #[test]
    fn skeleton_rejects_indirect_cycle() {
        let mut parents = valid_parents();
        parents[2] = 3;
        parents[3] = 2;
        assert!(decode_skeleton_anim(&synthetic_anim(5, &parents))
            .unwrap_err()
            .contains("cycle"));
    }

    #[test]
    fn skeleton_rejects_mismatched_counts() {
        let parents = valid_parents();
        let error = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &identity_inverse_binds(parents.len() - 1)),
        )
        .unwrap_err();
        assert!(error.contains("Bone-count/matrix-count mismatch"));
    }

    #[test]
    fn skeleton_rejects_truncated_matrix_file() {
        let mut bytes = synthetic_inverse_bind(1, &identity_inverse_binds(1));
        bytes.pop();
        assert!(decode_inverse_bind(&bytes)
            .unwrap_err()
            .contains("file size mismatch"));
    }

    #[test]
    fn skeleton_rejects_non_finite_matrix() {
        let mut matrices = identity_inverse_binds(1);
        matrices[0][0][0] = f32::NAN;
        assert!(decode_inverse_bind(&synthetic_inverse_bind(1, &matrices))
            .unwrap_err()
            .contains("non-finite"));
    }

    #[test]
    fn skeleton_rejects_singular_matrix() {
        let parents = valid_parents();
        let mut matrices = identity_inverse_binds(parents.len());
        matrices[3][0] = [0.0; 4];
        assert!(inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &matrices),
        )
        .unwrap_err()
        .contains("singular"));
    }

    #[test]
    fn skeleton_reconstructs_deterministic_world_bind() {
        let parents = valid_parents();
        let mut matrices = identity_inverse_binds(parents.len());
        matrices[0] = translation_matrix(-2.0, -3.0, -4.0);
        let result = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &matrices),
        )
        .unwrap();
        assert_eq!(result["bones"][0]["world_bind_matrix"][0][3], 2.0);
        assert_eq!(result["bones"][0]["world_bind_matrix"][1][3], 3.0);
        assert_eq!(result["bones"][0]["world_bind_matrix"][2][3], 4.0);
    }

    #[test]
    fn skeleton_derives_deterministic_local_bind() {
        let parents = valid_parents();
        let mut matrices = identity_inverse_binds(parents.len());
        matrices[0] = translation_matrix(-2.0, 0.0, 0.0);
        matrices[1] = translation_matrix(-5.0, 0.0, 0.0);
        let result = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &matrices),
        )
        .unwrap();
        assert_eq!(result["bones"][1]["local_bind_matrix"][0][3], 3.0);
    }

    #[test]
    fn skeleton_resolves_attachment_bone_ids() {
        let parents = valid_parents();
        let result = inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &identity_inverse_binds(parents.len())),
        )
        .unwrap();
        assert_eq!(
            result["resolved_attachment_bone_ids"][0],
            json!({"bone_id": 1, "bone_name": "bone_01"})
        );
        assert_eq!(
            result["resolved_attachment_bone_ids"][5],
            json!({"bone_id": 23, "bone_name": "bone_23"})
        );
    }

    #[test]
    fn skeleton_json_is_deterministic() {
        let parents = valid_parents();
        let anim = synthetic_anim(5, &parents);
        let inverse = synthetic_inverse_bind(1, &identity_inverse_binds(parents.len()));
        let first =
            serde_json::to_string(&inspect_skeleton_bytes(&anim, &inverse).unwrap()).unwrap();
        let second =
            serde_json::to_string(&inspect_skeleton_bytes(&anim, &inverse).unwrap()).unwrap();
        assert_eq!(first, second);
    }

    #[test]
    fn skeleton_rejects_unsupported_versions() {
        let parents = valid_parents();
        assert!(decode_skeleton_anim(&synthetic_anim(4, &parents))
            .unwrap_err()
            .contains("expected 5"));
        assert!(
            decode_inverse_bind(&synthetic_inverse_bind(2, &identity_inverse_binds(1)))
                .unwrap_err()
                .contains("expected 1")
        );
    }

    fn synthetic_skin_inspection() -> serde_json::Value {
        let mut parents = vec![-1; 6];
        parents.extend((6..50).map(|_| 0));
        inspect_skeleton_bytes(
            &synthetic_anim(5, &parents),
            &synthetic_inverse_bind(1, &identity_inverse_binds(50)),
        )
        .unwrap()
    }

    fn synthetic_gltf_document() -> serde_json::Value {
        json!({
            "asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1,
                "TEXCOORD_0": 2, "JOINTS_0": 3, "WEIGHTS_0": 4}, "indices": 5, "material": 0}]}],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC2"},
                {"bufferView": 0, "componentType": 5121, "count": 3, "type": "VEC4"},
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC4"},
                {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}],
            "buffers": [{"byteLength": 128, "uri": "data:application/octet-stream;base64,AA=="}],
            "bufferViews": [{"buffer": 0, "byteLength": 122},
                {"buffer": 0, "byteOffset": 122, "byteLength": 6}],
            "materials": [{"name": "fixture"}]
        })
    }

    fn augmented_skin_document() -> serde_json::Value {
        let mut document = synthetic_gltf_document();
        augment_gltf_with_skin_document(&mut document, &synthetic_skin_inspection()).unwrap();
        document
    }

    #[test]
    fn skin_preserves_fifty_joint_ordering() {
        let document = augmented_skin_document();
        let joints = document["skins"][0]["joints"].as_array().unwrap();
        assert_eq!(joints.len(), 50);
        assert_eq!(
            (joints[0].clone(), joints[49].clone()),
            (json!(2), json!(51))
        );
        assert_eq!(
            (
                document["nodes"][2]["name"].clone(),
                document["nodes"][51]["name"].clone()
            ),
            (json!("bone_00"), json!("bone_49"))
        );
    }

    #[test]
    fn skin_generates_multiple_root_wrapper() {
        let document = augmented_skin_document();
        assert_eq!(document["nodes"][1]["children"], json!([2, 3, 4, 5, 6, 7]));
        assert_eq!(document["skins"][0]["skeleton"], 1);
        assert_eq!(document["scenes"][0]["nodes"], json!([0, 1]));
    }

    #[test]
    fn skin_generates_parent_child_relationships() {
        let document = augmented_skin_document();
        let children = document["nodes"][2]["children"].as_array().unwrap();
        assert_eq!(children.len(), 44);
        assert!(children.contains(&json!(8)) && children.contains(&json!(51)));
    }

    #[test]
    fn skin_converts_local_matrix_to_gltf_column_major() {
        let matrix = [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ];
        assert_eq!(
            serde_json::Value::Array(gltf_column_major_matrix(&matrix)),
            json!([
                1.0, 5.0, 9.0, 13.0, 2.0, 6.0, 10.0, 14.0, 3.0, 7.0, 11.0, 15.0, 4.0, 8.0, 12.0,
                16.0
            ])
        );
    }

    #[test]
    fn skin_generates_inverse_bind_accessor() {
        let document = augmented_skin_document();
        let accessor = document["accessors"].as_array().unwrap().last().unwrap();
        assert_eq!(
            (
                accessor["componentType"].clone(),
                accessor["count"].clone(),
                accessor["type"].clone()
            ),
            (json!(5126), json!(50), json!("MAT4"))
        );
        assert_eq!(
            document["buffers"].as_array().unwrap().last().unwrap()["byteLength"],
            3200
        );
    }

    #[test]
    fn skin_generates_skin_entry_and_mesh_assignment() {
        let document = augmented_skin_document();
        assert_eq!(document["skins"].as_array().unwrap().len(), 1);
        assert_eq!(document["nodes"][0]["skin"], 0);
        assert_eq!(document["skins"][0]["name"], "synthetic_skeleton");
    }

    #[test]
    fn skin_preserves_joint_and_weight_attributes() {
        let before = synthetic_gltf_document();
        let after = augmented_skin_document();
        for semantic in ["JOINTS_0", "WEIGHTS_0"] {
            assert_eq!(
                after["meshes"][0]["primitives"][0]["attributes"][semantic],
                before["meshes"][0]["primitives"][0]["attributes"][semantic]
            );
        }
    }

    #[test]
    fn skin_attribute_replacement_preserves_decoded_values_and_semantics() {
        let mut document = synthetic_gltf_document();
        let joints = vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
        let logical_weights = [
            1.0f32, 0.0, 0.0, 0.0, 0.75, 0.25, 0.0, 0.0, 0.5, 0.3, 0.2, 0.0,
        ];
        let weights = logical_weights
            .iter()
            .flat_map(|value| value.to_le_bytes())
            .collect::<Vec<_>>();
        replace_skin_attribute_data(&mut document, &[(joints.clone(), weights.clone(), 3)])
            .unwrap();
        assert_eq!(
            document["meshes"][0]["primitives"][0]["attributes"],
            synthetic_gltf_document()["meshes"][0]["primitives"][0]["attributes"]
        );
        let uri = document["buffers"].as_array().unwrap().last().unwrap()["uri"]
            .as_str()
            .unwrap();
        let decoded = BASE64_STANDARD
            .decode(uri.split_once(',').unwrap().1)
            .unwrap();
        assert_eq!(&decoded[..joints.len()], joints);
        assert_eq!(&decoded[joints.len()..], weights);
    }

    #[test]
    fn skin_preserves_geometry_accessors_and_buffers() {
        let before = synthetic_gltf_document();
        let after = augmented_skin_document();
        assert_eq!(
            &after["accessors"].as_array().unwrap()[..6],
            before["accessors"].as_array().unwrap()
        );
        assert_eq!(
            &after["buffers"].as_array().unwrap()[..1],
            before["buffers"].as_array().unwrap()
        );
        assert_eq!(
            &after["bufferViews"].as_array().unwrap()[..2],
            before["bufferViews"].as_array().unwrap()
        );
        assert_eq!(after["meshes"], before["meshes"]);
    }

    #[test]
    fn skin_augmentation_json_is_deterministic() {
        assert_eq!(
            serde_json::to_string(&augmented_skin_document()).unwrap(),
            serde_json::to_string(&augmented_skin_document()).unwrap()
        );
    }

    #[test]
    fn static_export_command_remains_backward_compatible() {
        let command = parse_command(&[
            "export-rmv2-gltf".to_owned(),
            "--input".to_owned(),
            "model.rigid_model_v2".to_owned(),
            "--output".to_owned(),
            "model.gltf".to_owned(),
            "--lod".to_owned(),
            "highest".to_owned(),
        ])
        .unwrap();
        assert!(matches!(
            command,
            Command::ExportRmv2Gltf {
                skeleton_anim: None,
                inverse_bind: None,
                ..
            }
        ));
    }

    #[test]
    fn skin_rejects_skeleton_id_mismatch() {
        let error =
            validate_skin_skeleton_id("different_rig", &synthetic_skin_inspection()).unwrap_err();
        assert!(error.contains("Skeleton ID mismatch"));
    }

    #[test]
    fn skin_rejects_empty_rigid_model_skeleton_id() {
        assert!(validate_skin_skeleton_id("", &synthetic_skin_inspection())
            .unwrap_err()
            .contains("RMV2 skeleton ID is empty"));
    }

    #[test]
    fn skinned_export_requires_both_skeleton_resources() {
        let error = parse_command(&[
            "export-rmv2-gltf".to_owned(),
            "--input".to_owned(),
            "model.rigid_model_v2".to_owned(),
            "--output".to_owned(),
            "model.gltf".to_owned(),
            "--lod".to_owned(),
            "highest".to_owned(),
            "--skeleton-anim".to_owned(),
            "missing.anim".to_owned(),
        ])
        .unwrap_err();
        assert!(error.contains("requires both"));
    }

    #[test]
    fn skeleton_inspection_rejects_missing_resource() {
        let temp = tempdir().unwrap();
        let error = inspect_skeleton(
            &temp.path().join("missing.anim"),
            &temp.path().join("missing.bone_inv_trans_mats"),
        )
        .unwrap_err();
        assert!(error.contains("Unable to read skeleton .anim"));
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

    #[test]
    fn export_highest_selects_lod_zero() {
        assert_eq!(selected_lod_index(LodSelection::Highest, 4).unwrap(), 0);
    }

    #[test]
    fn export_accepts_explicit_lod_and_rejects_invalid_indices() {
        assert_eq!(selected_lod_index(LodSelection::Index(2), 4).unwrap(), 2);
        assert!(selected_lod_index(LodSelection::Index(4), 4)
            .unwrap_err()
            .contains("contains 4 LOD"));
        assert!(parse_lod_selection("not-a-lod").is_err());
    }

    #[test]
    fn export_requires_a_gltf_output_path() {
        assert!(output_gltf_path(Path::new("build/output.gltf")).is_ok());
        assert!(output_gltf_path(Path::new("build/output.glb"))
            .unwrap_err()
            .contains(".gltf"));
        assert!(output_gltf_path(Path::new("build/"))
            .unwrap_err()
            .contains(".gltf"));
    }

    #[test]
    fn export_creates_output_parent_directory() {
        let temp = tempdir().unwrap();
        let output = temp.path().join("nested/output/praetorian-helmet.gltf");
        ensure_gltf_output_parent(&output).unwrap();
        assert!(output.parent().unwrap().is_dir());
    }

    #[test]
    fn export_filters_model_to_exactly_one_selected_lod() {
        let mut model = RigidModel::default();
        *model.lods_mut() = vec![
            rpfm_lib::files::rigidmodel::Lod::default(),
            rpfm_lib::files::rigidmodel::Lod::default(),
            rpfm_lib::files::rigidmodel::Lod::default(),
        ];
        let filtered = filtered_model_for_lod(&model, 1).unwrap();
        assert_eq!(model.lods().len(), 3);
        assert_eq!(filtered.lods().len(), 1);
    }

    #[test]
    fn export_result_json_is_deterministic() {
        let model = RigidModel::default();
        let first = serde_json::to_string(&gltf_export_result(
            "helmet.rigid_model_v2",
            "helmet.gltf",
            &model,
            0,
            1,
            3,
            3,
            vec![json!({"name": "helmet", "type": "WeightedDirtmap"})],
        ))
        .unwrap();
        let second = serde_json::to_string(&gltf_export_result(
            "helmet.rigid_model_v2",
            "helmet.gltf",
            &model,
            0,
            1,
            3,
            3,
            vec![json!({"name": "helmet", "type": "WeightedDirtmap"})],
        ))
        .unwrap();
        assert_eq!(first, second);
    }

    fn source_material(name: &str, material_type: &str, texture: &str) -> serde_json::Value {
        json!({
            "attachment_count": 0,
            "name": name,
            "parameter_counts": {"float": 0, "integer": 0, "string": 0, "vector4": 0},
            "parameters": {"float": [], "integer": [], "string": [], "vector4": []},
            "texture_directory": "variantmeshes/test/tex/",
            "textures": [{"path": texture, "type": "Diffuse"}],
            "type": material_type,
        })
    }

    #[test]
    fn gltf_postprocessing_preserves_material_identity_without_touching_geometry() {
        let temp = tempdir().unwrap();
        let output = temp.path().join("identity.gltf");
        let document = json!({
            "asset": {"version": "2.0"},
            "accessors": [{"count": 3}],
            "buffers": [{"uri": "data:application/octet-stream;base64,AA==", "byteLength": 1}],
            "materials": [{}, {}],
        });
        fs::write(&output, serde_json::to_vec_pretty(&document).unwrap()).unwrap();
        let source = vec![
            source_material("helmet", "WeightedDirtmap", "helmet_diffuse.dds"),
            source_material("crest", "DecalDirtmap", "crest_diffuse.dds"),
        ];
        preserve_gltf_material_identity(&output, &source).unwrap();
        let result: serde_json::Value =
            serde_json::from_slice(&fs::read(&output).unwrap()).unwrap();
        assert_eq!(result["materials"][0]["name"], "helmet");
        assert_eq!(result["materials"][1]["name"], "crest");
        assert_eq!(
            result["materials"][0]["extras"]["rome2aoe2"]["type"],
            "WeightedDirtmap"
        );
        assert_eq!(
            result["materials"][0]["extras"]["rome2aoe2"]["textures"][0]["path"],
            "helmet_diffuse.dds"
        );
        assert!(result.get("images").is_none());
        assert_eq!(result["accessors"], document["accessors"]);
        assert_eq!(result["buffers"], document["buffers"]);
    }

    #[test]
    fn gltf_material_postprocessing_is_deterministic() {
        let temp = tempdir().unwrap();
        let document = json!({"asset": {"version": "2.0"}, "materials": [{}]});
        let source = vec![source_material(
            "helmet",
            "WeightedDirtmap",
            "helmet_diffuse.dds",
        )];
        let first = temp.path().join("first.gltf");
        let second = temp.path().join("second.gltf");
        for output in [&first, &second] {
            fs::write(output, serde_json::to_vec_pretty(&document).unwrap()).unwrap();
            preserve_gltf_material_identity(output, &source).unwrap();
        }
        assert_eq!(fs::read(first).unwrap(), fs::read(second).unwrap());
    }

    #[test]
    fn export_reports_input_failure_with_context() {
        let temp = tempdir().unwrap();
        let error = export_rmv2_gltf(
            &temp.path().join("missing.rigid_model_v2"),
            &temp.path().join("nested/output.gltf"),
            LodSelection::Highest,
            None,
        )
        .unwrap_err();
        assert!(error.contains("Unable to read RMV2"));
        assert!(error.contains("missing.rigid_model_v2"));
    }
}
