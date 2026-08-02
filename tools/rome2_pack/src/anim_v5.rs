use std::fs;
use std::path::Path;

use serde_json::{json, Map, Value};

use super::{
    decode_skeleton_anim, inspect_skeleton_bytes, multiply_matrix, validate_hierarchy, Matrix4,
    SkeletonBone,
};

const FORMAT: &str = "rome2aoe2.animation-pose";
const FORMAT_VERSION: u32 = 1;
const VERIFIED_BONE_COUNT: usize = 50;
const VERIFIED_TRANSLATION_TRACKS: usize = 6;
const VERIFIED_ROTATION_TRACKS: usize = 32;
const QUATERNION_MIN_NORM: f64 = 1.0e-8;
const QUATERNION_NORM_TOLERANCE: f64 = 1.0e-4;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum FrameSelection {
    First,
    Last,
    Index(usize),
}

impl FrameSelection {
    pub(super) fn parse(value: &str) -> Result<Self, String> {
        match value {
            "first" => Ok(Self::First),
            "last" => Ok(Self::Last),
            _ => value.parse::<usize>().map(Self::Index).map_err(|_| {
                format!(
                    "Invalid --frame '{}': expected 'first', 'last', or a non-negative index",
                    value
                )
            }),
        }
    }

    fn resolve(self, sample_count: usize) -> Result<usize, String> {
        let index = match self {
            Self::First => 0,
            Self::Last => sample_count
                .checked_sub(1)
                .ok_or_else(|| "Animation has no samples".to_owned())?,
            Self::Index(index) => index,
        };
        if index >= sample_count {
            return Err(format!(
                "Requested frame {} is outside animation sample range 0..{}",
                index,
                sample_count.saturating_sub(1)
            ));
        }
        Ok(index)
    }

    pub(super) fn label(self) -> String {
        match self {
            Self::First => "first".to_owned(),
            Self::Last => "last".to_owned(),
            Self::Index(index) => index.to_string(),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
struct Transform {
    translation: [f64; 3],
    rotation: [f64; 4],
}

#[derive(Clone, Debug)]
struct AnimationV5 {
    skeleton_id: String,
    sample_rate: f32,
    duration: f32,
    bones: Vec<SkeletonBone>,
    translation_map: Vec<i32>,
    rotation_map: Vec<i32>,
    translation_track_count: usize,
    rotation_track_count: usize,
    sample_count: usize,
    frame_data_offset: usize,
    bytes: Vec<u8>,
}

fn take<const N: usize>(bytes: &[u8], offset: &mut usize, label: &str) -> Result<[u8; N], String> {
    let end = offset
        .checked_add(N)
        .ok_or_else(|| format!("{} offset overflows", label))?;
    let value = bytes.get(*offset..end).ok_or_else(|| {
        format!(
            "Truncated payload while reading {} at byte {}",
            label, offset
        )
    })?;
    *offset = end;
    Ok(value.try_into().expect("slice length checked"))
}

fn u16_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<u16, String> {
    Ok(u16::from_le_bytes(take(bytes, offset, label)?))
}

fn i16_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<i16, String> {
    Ok(i16::from_le_bytes(take(bytes, offset, label)?))
}

fn u32_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<u32, String> {
    Ok(u32::from_le_bytes(take(bytes, offset, label)?))
}

fn i32_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<i32, String> {
    Ok(i32::from_le_bytes(take(bytes, offset, label)?))
}

fn f32_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<f32, String> {
    Ok(f32::from_le_bytes(take(bytes, offset, label)?))
}

fn string_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<String, String> {
    let length = u16_at(bytes, offset, &format!("{} length", label))? as usize;
    let end = offset
        .checked_add(length)
        .ok_or_else(|| format!("{} length overflows", label))?;
    let value = bytes.get(*offset..end).ok_or_else(|| {
        format!(
            "Truncated payload while reading {} at byte {}",
            label, offset
        )
    })?;
    *offset = end;
    String::from_utf8(value.to_vec()).map_err(|_| format!("{} is not valid UTF-8", label))
}

fn endpoint_sample_count(duration: f32, sample_rate: f32) -> Result<usize, String> {
    if !duration.is_finite() || duration < 0.0 {
        return Err(format!("Invalid animation duration {}", duration));
    }
    if !sample_rate.is_finite() || sample_rate <= 0.0 {
        return Err(format!("Invalid animation sample rate {}", sample_rate));
    }
    let intervals = (f64::from(duration) * f64::from(sample_rate)).round();
    if intervals < 0.0 || intervals > (usize::MAX - 1) as f64 {
        return Err("Animation sample count overflows".to_owned());
    }
    Ok(intervals as usize + 1)
}

fn frame_bytes(translation_tracks: usize, rotation_tracks: usize) -> Result<usize, String> {
    translation_tracks
        .checked_mul(12)
        .and_then(|bytes| {
            rotation_tracks
                .checked_mul(8)
                .and_then(|r| bytes.checked_add(r))
        })
        .ok_or_else(|| "Animation frame byte count overflows".to_owned())
}

fn parse(bytes: &[u8]) -> Result<AnimationV5, String> {
    let mut offset = 0;
    let version = u32_at(bytes, &mut offset, "animation version")?;
    if version != 5 {
        return Err(format!(
            "Unsupported animation version {}; expected verified Rome II version 5",
            version
        ));
    }
    let _unknown = u32_at(bytes, &mut offset, "animation header field")?;
    let sample_rate = f32_at(bytes, &mut offset, "sample rate")?;
    let skeleton_id = string_at(bytes, &mut offset, "skeleton identifier")?;
    if skeleton_id.is_empty() {
        return Err("Animation skeleton identifier is empty".to_owned());
    }
    let duration = f32_at(bytes, &mut offset, "duration")?;
    let bone_count = u32_at(bytes, &mut offset, "bone count")? as usize;
    let mut bones = Vec::with_capacity(bone_count);
    for index in 0..bone_count {
        let name = string_at(bytes, &mut offset, &format!("bone {} name", index))?;
        let raw_parent = i32_at(bytes, &mut offset, &format!("bone {} parent", index))?;
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

    let translation_map = (0..bone_count)
        .map(|index| {
            i32_at(
                bytes,
                &mut offset,
                &format!("bone {} translation map", index),
            )
        })
        .collect::<Result<Vec<_>, _>>()?;
    let rotation_map = (0..bone_count)
        .map(|index| i32_at(bytes, &mut offset, &format!("bone {} rotation map", index)))
        .collect::<Result<Vec<_>, _>>()?;
    let translation_track_count = count_at(bytes, &mut offset, "translation-track count")?;
    let rotation_track_count = count_at(bytes, &mut offset, "rotation-track count")?;
    let sample_count = count_at(bytes, &mut offset, "sample count")?;
    let frame_data_offset = offset;

    validate_map(&translation_map, translation_track_count, "translation")?;
    validate_map(&rotation_map, rotation_track_count, "rotation")?;
    let expected_size = frame_data_offset
        .checked_add(
            frame_bytes(translation_track_count, rotation_track_count)?
                .checked_mul(sample_count)
                .ok_or_else(|| "Animation payload byte count overflows".to_owned())?,
        )
        .ok_or_else(|| "Animation file size overflows".to_owned())?;
    match bytes.len().cmp(&expected_size) {
        std::cmp::Ordering::Less => {
            return Err(format!(
                "Truncated animation payload: counts require {} bytes, found {}",
                expected_size,
                bytes.len()
            ))
        }
        std::cmp::Ordering::Greater => {
            return Err(format!(
                "Unexpected trailing animation data: counts require {} bytes, found {} ({} extra)",
                expected_size,
                bytes.len(),
                bytes.len() - expected_size
            ))
        }
        std::cmp::Ordering::Equal => {}
    }

    Ok(AnimationV5 {
        skeleton_id,
        sample_rate,
        duration,
        bones,
        translation_map,
        rotation_map,
        translation_track_count,
        rotation_track_count,
        sample_count,
        frame_data_offset,
        bytes: bytes.to_vec(),
    })
}

fn count_at(bytes: &[u8], offset: &mut usize, label: &str) -> Result<usize, String> {
    let value = i32_at(bytes, offset, label)?;
    usize::try_from(value).map_err(|_| format!("{} is negative ({})", label, value))
}

fn validate_map(map: &[i32], track_count: usize, component: &str) -> Result<(), String> {
    for (bone, value) in map.iter().copied().enumerate() {
        if value < -1 || value >= track_count as i32 {
            return Err(format!(
                "Bone {} has invalid {} track-map index {} for {} tracks",
                bone, component, value, track_count
            ));
        }
    }
    Ok(())
}

impl AnimationV5 {
    fn frame_offset(&self, frame: usize) -> Result<usize, String> {
        if frame >= self.sample_count {
            return Err(format!(
                "Frame {} is outside {} samples",
                frame, self.sample_count
            ));
        }
        self.frame_data_offset
            .checked_add(
                frame_bytes(self.translation_track_count, self.rotation_track_count)?
                    .checked_mul(frame)
                    .ok_or_else(|| "Frame offset overflows".to_owned())?,
            )
            .ok_or_else(|| "Frame offset overflows".to_owned())
    }

    fn decode_tracks(&self, frame: usize) -> Result<(Vec<[f64; 3]>, Vec<[f64; 4]>), String> {
        let mut offset = self.frame_offset(frame)?;
        let mut translations = Vec::with_capacity(self.translation_track_count);
        for track in 0..self.translation_track_count {
            let mut value = [0.0; 3];
            for (component, destination) in value.iter_mut().enumerate() {
                *destination = f64::from(f32_at(
                    &self.bytes,
                    &mut offset,
                    &format!(
                        "frame {} translation track {} component {}",
                        frame, track, component
                    ),
                )?);
                if !destination.is_finite() {
                    return Err(format!(
                        "Frame {} translation track {} contains a non-finite component {}",
                        frame, track, component
                    ));
                }
            }
            translations.push(value);
        }
        let mut rotations = Vec::with_capacity(self.rotation_track_count);
        for track in 0..self.rotation_track_count {
            let mut value = [0.0; 4];
            for (component, destination) in value.iter_mut().enumerate() {
                *destination = f64::from(i16_at(
                    &self.bytes,
                    &mut offset,
                    &format!(
                        "frame {} rotation track {} component {}",
                        frame, track, component
                    ),
                )?) / 32767.0;
            }
            rotations.push(normalize_quaternion(value, frame, track)?);
        }
        Ok((translations, rotations))
    }

    fn expanded_frame(
        &self,
        frame: usize,
        fallback: &[Transform],
    ) -> Result<Vec<Transform>, String> {
        if fallback.len() != self.bones.len() {
            return Err(format!(
                "Skeleton fallback has {} bones, animation has {}",
                fallback.len(),
                self.bones.len()
            ));
        }
        let (translations, rotations) = self.decode_tracks(frame)?;
        self.translation_map
            .iter()
            .zip(&self.rotation_map)
            .enumerate()
            .map(|(bone, (&translation_track, &rotation_track))| {
                Ok(Transform {
                    translation: if translation_track == -1 {
                        fallback[bone].translation
                    } else {
                        translations[translation_track as usize]
                    },
                    rotation: if rotation_track == -1 {
                        fallback[bone].rotation
                    } else {
                        rotations[rotation_track as usize]
                    },
                })
            })
            .collect()
    }
}

fn normalize_quaternion(value: [f64; 4], frame: usize, track: usize) -> Result<[f64; 4], String> {
    if value.iter().any(|component| !component.is_finite()) {
        return Err(format!(
            "Frame {} rotation track {} contains a non-finite quaternion",
            frame, track
        ));
    }
    let norm = value
        .iter()
        .map(|component| component * component)
        .sum::<f64>()
        .sqrt();
    if !norm.is_finite() || norm <= QUATERNION_MIN_NORM {
        return Err(format!(
            "Frame {} rotation track {} has a zero or invalid quaternion norm",
            frame, track
        ));
    }
    if (norm - 1.0).abs() > QUATERNION_NORM_TOLERANCE {
        return Err(format!(
            "Frame {} rotation track {} quaternion norm {} exceeds tolerance {}",
            frame, track, norm, QUATERNION_NORM_TOLERANCE
        ));
    }
    Ok(value.map(|component| component / norm))
}

fn transform_matrix(transform: Transform) -> Matrix4 {
    let [x, y, z, w] = transform.rotation;
    [
        [
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
            transform.translation[0],
        ],
        [
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
            transform.translation[1],
        ],
        [
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
            transform.translation[2],
        ],
        [0.0, 0.0, 0.0, 1.0],
    ]
}

fn world_matrices(bones: &[SkeletonBone], local: &[Matrix4]) -> Result<Vec<Matrix4>, String> {
    validate_hierarchy(bones)?;
    if bones.len() != local.len() {
        return Err("Local transform count does not equal hierarchy bone count".to_owned());
    }
    fn evaluate(
        index: usize,
        bones: &[SkeletonBone],
        local: &[Matrix4],
        output: &mut [Option<Matrix4>],
    ) -> Result<Matrix4, String> {
        if let Some(matrix) = output[index] {
            return Ok(matrix);
        }
        let matrix = if let Some(parent) = bones[index].parent {
            multiply_matrix(&evaluate(parent, bones, local, output)?, &local[index])
        } else {
            local[index]
        };
        if matrix.iter().flatten().any(|value| !value.is_finite()) {
            return Err(format!("Bone {} world matrix is not finite", index));
        }
        output[index] = Some(matrix);
        Ok(matrix)
    }
    let mut output = vec![None; bones.len()];
    for index in 0..bones.len() {
        evaluate(index, bones, local, &mut output)?;
    }
    Ok(output.into_iter().map(Option::unwrap).collect())
}

fn validate_matching_skeletons(clip: &AnimationV5, skeleton: &AnimationV5) -> Result<(), String> {
    if clip.skeleton_id != skeleton.skeleton_id {
        return Err(format!(
            "Skeleton ID mismatch: animation targets '{}', skeleton resource is '{}'",
            clip.skeleton_id, skeleton.skeleton_id
        ));
    }
    if clip.bones.len() != skeleton.bones.len() {
        return Err(format!(
            "Bone-count mismatch: animation has {}, skeleton has {}",
            clip.bones.len(),
            skeleton.bones.len()
        ));
    }
    for (index, (clip_bone, skeleton_bone)) in clip.bones.iter().zip(&skeleton.bones).enumerate() {
        if clip_bone.name != skeleton_bone.name || clip_bone.parent != skeleton_bone.parent {
            return Err(format!(
                "Skeleton hierarchy mismatch at bone {}: animation is '{}'/parent {:?}, skeleton is '{}'/parent {:?}",
                index, clip_bone.name, clip_bone.parent, skeleton_bone.name, skeleton_bone.parent
            ));
        }
    }
    Ok(())
}

fn bone_json(
    index: usize,
    bones: &[SkeletonBone],
    translation_map: &[i32],
    rotation_map: &[i32],
    transforms: &[Transform],
    local: &[Matrix4],
    world: &[Matrix4],
) -> Value {
    json!({
        "index": index,
        "name": bones[index].name,
        "parent": bones[index].parent,
        "translation_track": (translation_map[index] >= 0).then_some(translation_map[index]),
        "rotation_track": (rotation_map[index] >= 0).then_some(rotation_map[index]),
        "local_translation": transforms[index].translation,
        "local_rotation_xyzw": transforms[index].rotation,
        "local_matrix": local[index],
        "world_matrix": world[index],
    })
}

fn inspect_bytes(
    animation_name: &str,
    animation_bytes: &[u8],
    skeleton_bytes: &[u8],
    inverse_bind_bytes: &[u8],
    selection: FrameSelection,
) -> Result<Value, String> {
    let clip = parse(animation_bytes)?;
    let skeleton = parse(skeleton_bytes)?;
    validate_matching_skeletons(&clip, &skeleton)?;
    if clip.bones.len() != VERIFIED_BONE_COUNT {
        return Err(format!(
            "Unsupported animation bone count {}; verified Rome II scope requires {}",
            clip.bones.len(),
            VERIFIED_BONE_COUNT
        ));
    }
    if clip.translation_track_count != VERIFIED_TRANSLATION_TRACKS
        || clip.rotation_track_count != VERIFIED_ROTATION_TRACKS
    {
        return Err(format!(
            "Unsupported clip track counts ({}, {}); verified scope requires ({}, {})",
            clip.translation_track_count,
            clip.rotation_track_count,
            VERIFIED_TRANSLATION_TRACKS,
            VERIFIED_ROTATION_TRACKS
        ));
    }
    let calculated_samples = endpoint_sample_count(clip.duration, clip.sample_rate)?;
    if clip.sample_count != calculated_samples {
        return Err(format!(
            "Stored sample count {} does not match endpoint-inclusive duration/rate count {}",
            clip.sample_count, calculated_samples
        ));
    }
    if skeleton.translation_track_count != VERIFIED_BONE_COUNT
        || skeleton.rotation_track_count != VERIFIED_BONE_COUNT
        || skeleton.sample_count != 2
    {
        return Err(format!(
            "Skeleton fallback payload must contain 50 translation tracks, 50 rotation tracks, and exactly two verified samples; found ({}, {}, {})",
            skeleton.translation_track_count, skeleton.rotation_track_count, skeleton.sample_count
        ));
    }
    for bone in 0..VERIFIED_BONE_COUNT {
        if skeleton.translation_map[bone] != bone as i32
            || skeleton.rotation_map[bone] != bone as i32
        {
            return Err(format!(
                "Skeleton fallback bone {} must map directly to track {}; found translation {} and rotation {}",
                bone, bone, skeleton.translation_map[bone], skeleton.rotation_map[bone]
            ));
        }
    }
    let skeleton_header = decode_skeleton_anim(skeleton_bytes)?;
    if skeleton_header.skeleton_id != clip.skeleton_id {
        return Err("Validated skeleton header identifier changed unexpectedly".to_owned());
    }
    inspect_skeleton_bytes(skeleton_bytes, inverse_bind_bytes)?;

    let (fallback_translations, fallback_rotations) = skeleton.decode_tracks(0)?;
    let fallback = (0..skeleton.bones.len())
        .map(|bone| Transform {
            translation: fallback_translations[skeleton.translation_map[bone] as usize],
            rotation: fallback_rotations[skeleton.rotation_map[bone] as usize],
        })
        .collect::<Vec<_>>();
    let frame_index = selection.resolve(clip.sample_count)?;
    let transforms = clip.expanded_frame(frame_index, &fallback)?;
    let local = transforms
        .iter()
        .copied()
        .map(transform_matrix)
        .collect::<Vec<_>>();
    let world = world_matrices(&clip.bones, &local)?;
    let bones = (0..clip.bones.len())
        .map(|index| {
            bone_json(
                index,
                &clip.bones,
                &clip.translation_map,
                &clip.rotation_map,
                &transforms,
                &local,
                &world,
            )
        })
        .collect::<Vec<_>>();

    let mut weapon_bones = Map::new();
    for (key, name) in [
        ("weapon_02", "bn_weapon_02"),
        ("weapon_03", "bn_weapon_03"),
        ("weapon_05", "bn_weapon_05"),
    ] {
        let index = clip
            .bones
            .iter()
            .position(|bone| bone.name == name)
            .ok_or_else(|| format!("Required weapon bone '{}' is missing", name))?;
        weapon_bones.insert(
            key.to_owned(),
            bone_json(
                index,
                &clip.bones,
                &clip.translation_map,
                &clip.rotation_map,
                &transforms,
                &local,
                &world,
            ),
        );
    }

    Ok(json!({
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "animation": animation_name,
        "skeleton_id": clip.skeleton_id,
        "sample_rate": clip.sample_rate,
        "duration": clip.duration,
        "sample_count": clip.sample_count,
        "frame_index": frame_index,
        "sample_time": frame_index as f64 / f64::from(clip.sample_rate),
        "bone_count": clip.bones.len(),
        "source_coordinate_convention": {
            "translation": "Rome II XYZ",
            "rotation": "Rome II quaternion XYZW, normalized after signed i16/32767 decoding",
            "vectors": "column vectors",
            "matrix_storage": "row-major JSON arrays",
            "composition": "world = parent_world * local",
            "scale": "identity"
        },
        "bones": bones,
        "weapon_bones": weapon_bones,
    }))
}

pub(super) fn inspect(
    animation: &Path,
    skeleton_anim: &Path,
    inverse_bind: &Path,
    selection: FrameSelection,
) -> Result<Value, String> {
    let animation_name = animation
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("<non-utf8-animation>");
    let requested = selection.label();
    let operation = || {
        let animation_bytes =
            fs::read(animation).map_err(|error| format!("Unable to read animation: {}", error))?;
        let skeleton_bytes = fs::read(skeleton_anim)
            .map_err(|error| format!("Unable to read skeleton animation: {}", error))?;
        let inverse_bind_bytes = fs::read(inverse_bind)
            .map_err(|error| format!("Unable to read inverse-bind resource: {}", error))?;
        inspect_bytes(
            animation_name,
            &animation_bytes,
            &skeleton_bytes,
            &inverse_bind_bytes,
            selection,
        )
    };
    operation().map_err(|error| {
        format!(
            "Animation '{}' requested frame '{}': {}",
            animation_name, requested, error
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn push_string(bytes: &mut Vec<u8>, value: &str) {
        bytes.extend_from_slice(&(value.len() as u16).to_le_bytes());
        bytes.extend_from_slice(value.as_bytes());
    }

    fn hierarchy() -> Vec<i32> {
        let mut parents = vec![-1; 6];
        parents.extend((6..50).map(|_| 0));
        parents
    }

    fn synthetic(
        version: u32,
        skeleton_id: &str,
        parents: &[i32],
        translation_map: &[i32],
        rotation_map: &[i32],
        translation_tracks: usize,
        rotation_tracks: usize,
        samples: usize,
        duration: f32,
    ) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&version.to_le_bytes());
        bytes.extend_from_slice(&1u32.to_le_bytes());
        bytes.extend_from_slice(&10.0f32.to_le_bytes());
        push_string(&mut bytes, skeleton_id);
        bytes.extend_from_slice(&duration.to_le_bytes());
        bytes.extend_from_slice(&(parents.len() as u32).to_le_bytes());
        for (index, parent) in parents.iter().enumerate() {
            let name = match index {
                2 => "bn_weapon_02".to_owned(),
                3 => "bn_weapon_03".to_owned(),
                5 => "bn_weapon_05".to_owned(),
                _ => format!("bone_{index:02}"),
            };
            push_string(&mut bytes, &name);
            bytes.extend_from_slice(&parent.to_le_bytes());
        }
        for value in translation_map {
            bytes.extend_from_slice(&value.to_le_bytes());
        }
        for value in rotation_map {
            bytes.extend_from_slice(&value.to_le_bytes());
        }
        bytes.extend_from_slice(&(translation_tracks as i32).to_le_bytes());
        bytes.extend_from_slice(&(rotation_tracks as i32).to_le_bytes());
        bytes.extend_from_slice(&(samples as i32).to_le_bytes());
        for frame in 0..samples {
            for track in 0..translation_tracks {
                for component in 0..3 {
                    bytes.extend_from_slice(
                        &((frame * 100 + track * 10 + component) as f32).to_le_bytes(),
                    );
                }
            }
            for track in 0..rotation_tracks {
                let quaternion = if track % 2 == 0 {
                    [0i16, 0, 0, 32767]
                } else {
                    [0i16, 0, 32767, 0]
                };
                for component in quaternion {
                    bytes.extend_from_slice(&component.to_le_bytes());
                }
            }
        }
        bytes
    }

    fn clip_maps() -> (Vec<i32>, Vec<i32>) {
        let mut translations = vec![-1; 50];
        for (index, value) in translations.iter_mut().take(6).enumerate() {
            *value = index as i32;
        }
        let mut rotations = vec![-1; 50];
        for (index, value) in rotations.iter_mut().take(32).enumerate() {
            *value = index as i32;
        }
        (translations, rotations)
    }

    fn skeleton_maps() -> (Vec<i32>, Vec<i32>) {
        let map = (0..50).collect::<Vec<i32>>();
        (map.clone(), map)
    }

    fn fixture() -> (Vec<u8>, Vec<u8>, Vec<u8>) {
        let parents = hierarchy();
        let (tm, rm) = clip_maps();
        let clip = synthetic(5, "rome_man_game", &parents, &tm, &rm, 6, 32, 2, 0.1);
        let (stm, srm) = skeleton_maps();
        let skeleton = synthetic(5, "rome_man_game", &parents, &stm, &srm, 50, 50, 2, 0.1);
        let mut inverse = Vec::new();
        inverse.extend_from_slice(&1u32.to_le_bytes());
        inverse.extend_from_slice(&50u32.to_le_bytes());
        for _ in 0..50 {
            for value in [
                1.0f32, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
            ] {
                inverse.extend_from_slice(&value.to_le_bytes());
            }
        }
        (clip, skeleton, inverse)
    }

    #[test]
    fn endpoint_count_includes_final_sample() {
        assert_eq!(endpoint_sample_count(2.8, 15.0).unwrap(), 43);
        assert_eq!(endpoint_sample_count(3.0, 20.0).unwrap(), 61);
    }

    #[test]
    fn decodes_translation_and_rotation_maps() {
        let (clip, _, _) = fixture();
        let parsed = parse(&clip).unwrap();
        assert_eq!(&parsed.translation_map[..7], &[0, 1, 2, 3, 4, 5, -1]);
        assert_eq!(&parsed.rotation_map[..4], &[0, 1, 2, 3]);
    }

    #[test]
    fn skeleton_sample_fills_missing_components() {
        let (clip, skeleton, _) = fixture();
        let clip = parse(&clip).unwrap();
        let skeleton = parse(&skeleton).unwrap();
        let (t, r) = skeleton.decode_tracks(0).unwrap();
        let fallback = (0..50)
            .map(|i| Transform {
                translation: t[i],
                rotation: r[i],
            })
            .collect::<Vec<_>>();
        let expanded = clip.expanded_frame(0, &fallback).unwrap();
        assert_eq!(expanded[49].translation, [490.0, 491.0, 492.0]);
        assert_eq!(expanded[49].rotation, fallback[49].rotation);
    }

    #[test]
    fn frame_major_offsets_and_xyz_translation_decode() {
        let (clip, _, _) = fixture();
        let parsed = parse(&clip).unwrap();
        assert_eq!(
            parsed.frame_offset(1).unwrap() - parsed.frame_offset(0).unwrap(),
            328
        );
        assert_eq!(parsed.decode_tracks(1).unwrap().0[2], [120.0, 121.0, 122.0]);
    }

    #[test]
    fn xyzw_i16_quaternion_decodes_and_normalizes() {
        let (clip, _, _) = fixture();
        let rotations = parse(&clip).unwrap().decode_tracks(0).unwrap().1;
        assert_eq!(rotations[0], [0.0, 0.0, 0.0, 1.0]);
        assert_eq!(rotations[1], [0.0, 0.0, 1.0, 0.0]);
        let normalized = normalize_quaternion([0.0, 0.0, 0.0, 0.99998], 0, 0).unwrap();
        assert_eq!(normalized, [0.0, 0.0, 0.0, 1.0]);
    }

    #[test]
    fn selects_first_last_and_index_and_rejects_invalid() {
        assert_eq!(FrameSelection::First.resolve(3).unwrap(), 0);
        assert_eq!(FrameSelection::Last.resolve(3).unwrap(), 2);
        assert_eq!(FrameSelection::Index(1).resolve(3).unwrap(), 1);
        assert!(FrameSelection::Index(3)
            .resolve(3)
            .unwrap_err()
            .contains("outside"));
    }

    #[test]
    fn rejects_invalid_track_map_index() {
        let parents = hierarchy();
        let (mut tm, rm) = clip_maps();
        tm[0] = 6;
        let error = parse(&synthetic(
            5,
            "rome_man_game",
            &parents,
            &tm,
            &rm,
            6,
            32,
            2,
            0.1,
        ))
        .unwrap_err();
        assert!(error.contains("invalid translation track-map index"));
    }

    #[test]
    fn rejects_truncated_and_trailing_payloads() {
        let (mut clip, _, _) = fixture();
        clip.pop();
        assert!(parse(&clip)
            .unwrap_err()
            .contains("Truncated animation payload"));
        let (mut clip, _, _) = fixture();
        clip.push(0);
        assert!(parse(&clip).unwrap_err().contains("Unexpected trailing"));
    }

    #[test]
    fn rejects_skeleton_id_and_bone_count_mismatch() {
        let (clip, _, inverse) = fixture();
        let parents = hierarchy();
        let (stm, srm) = skeleton_maps();
        let wrong = synthetic(5, "wrong", &parents, &stm, &srm, 50, 50, 2, 0.1);
        assert!(
            inspect_bytes("clip.anim", &clip, &wrong, &inverse, FrameSelection::First)
                .unwrap_err()
                .contains("Skeleton ID mismatch")
        );
        let short_parents = &parents[..49];
        let map = (0..49).collect::<Vec<i32>>();
        let short = synthetic(
            5,
            "rome_man_game",
            short_parents,
            &map,
            &map,
            49,
            49,
            2,
            0.1,
        );
        assert!(
            inspect_bytes("clip.anim", &clip, &short, &inverse, FrameSelection::First)
                .unwrap_err()
                .contains("Bone-count mismatch")
        );
    }

    #[test]
    fn composes_local_hierarchy_to_world() {
        let bones = vec![
            SkeletonBone {
                name: "root".to_owned(),
                parent: None,
            },
            SkeletonBone {
                name: "child".to_owned(),
                parent: Some(0),
            },
        ];
        let local = vec![
            transform_matrix(Transform {
                translation: [1.0, 2.0, 3.0],
                rotation: [0.0, 0.0, 0.0, 1.0],
            }),
            transform_matrix(Transform {
                translation: [4.0, 5.0, 6.0],
                rotation: [0.0, 0.0, 0.0, 1.0],
            }),
        ];
        let world = world_matrices(&bones, &local).unwrap();
        assert_eq!(
            [world[1][0][3], world[1][1][3], world[1][2][3]],
            [5.0, 7.0, 9.0]
        );
    }

    #[test]
    fn pose_json_is_deterministic() {
        let (clip, skeleton, inverse) = fixture();
        let first = inspect_bytes(
            "clip.anim",
            &clip,
            &skeleton,
            &inverse,
            FrameSelection::First,
        )
        .unwrap();
        let second = inspect_bytes(
            "clip.anim",
            &clip,
            &skeleton,
            &inverse,
            FrameSelection::First,
        )
        .unwrap();
        assert_eq!(
            serde_json::to_string(&first).unwrap(),
            serde_json::to_string(&second).unwrap()
        );
    }

    #[test]
    fn rejects_unsupported_version() {
        let parents = hierarchy();
        let (tm, rm) = clip_maps();
        assert!(parse(&synthetic(
            4,
            "rome_man_game",
            &parents,
            &tm,
            &rm,
            6,
            32,
            2,
            0.1
        ))
        .unwrap_err()
        .contains("expected verified Rome II version 5"));
    }
}
