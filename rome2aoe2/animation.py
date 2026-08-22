from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from .errors import ConverterError, ErrorCode
from .models import ResolvedUnit


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ("idle", "walk", "attack", "death")
DEFAULT_SHORTLIST_SIZE = 5
PREVIEW_PROFILE = "native-contact-sheet-v3-all-native-weighted-basis"
FRAGMENT_ROOTS = (
    ROOT / "build/cache/rome2aoe2/assets-v1",
    ROOT / "build/cache/hastati-gameplay-source",
    ROOT / "build/local-integration/rome2/animation-v5",
)
ASSET_ROOTS = FRAGMENT_ROOTS + (
    ROOT / "build/validation/hastati-gameplay/native-death-investigation/source",
)
INSPECTOR = ROOT / "tools/rome2_pack/target/release/rome2aoe2-pack.exe"
SKELETON_ANIM = ROOT / "build/cache/rome2aoe2/assets-v1/animations/skeletons/rome_man_game.anim"
INVERSE_BIND = ROOT / "build/local-integration/rome2/animation-v5/animations/skeletons/rome_man_game.bone_inv_trans_mats"
METADATA_CACHE = ROOT / "build/cache/rome2aoe2/animation-metadata-v1"


@dataclass(frozen=True)
class FragmentMapping:
    state: str
    asset: str
    metadata: str | None
    attributes: Mapping[str, str]
    line: int


@dataclass(frozen=True)
class AnimationCandidate:
    category: str
    states: tuple[str, ...]
    resolved_asset: str
    local_asset: str
    metadata_paths: tuple[str, ...]
    skeleton: str
    frame_count: int | None = None
    fps: float | None = None
    duration: float | None = None
    root_displacement: tuple[float, float, float] | None = None
    horizontal_displacement: float | None = None
    locomotion_speed: float | None = None
    weapon_bones: tuple[str, ...] = ()
    looping: bool | None = None
    context_tags: tuple[str, ...] = ()
    score: int = 0
    suitability: tuple[str, ...] = ()
    provenance: str = "animation_fragment"
    preview_path: str | None = None

    def manifest_record(self, mode: str) -> dict[str, Any]:
        return {
            "category": self.category,
            "mode": mode,
            "resolution_policy": "generic_suitability_then_canonical_path_v1" if mode == "deterministic_auto" else "exact_manifest_asset",
            "resolved_state": self.states[0],
            "source_states": list(self.states),
            "resolved_asset": self.resolved_asset,
            "asset_sha256": file_sha256(Path(self.local_asset)),
            "skeleton": self.skeleton,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration": self.duration,
            "root_displacement": list(self.root_displacement) if self.root_displacement else None,
            "horizontal_displacement": self.horizontal_displacement,
            "locomotion_speed": self.locomotion_speed,
            "weapon_bones": list(self.weapon_bones),
            "looping": self.looping,
            "context_tags": list(self.context_tags),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class CategoryDiscovery:
    category: str
    candidates: tuple[AnimationCandidate, ...]
    shortlist_size: int = DEFAULT_SHORTLIST_SIZE

    @property
    def shortlist(self) -> tuple[AnimationCandidate, ...]:
        return self.candidates[: self.shortlist_size]

    @property
    def additional(self) -> tuple[AnimationCandidate, ...]:
        return self.candidates[self.shortlist_size :]

    @property
    def recommendation(self) -> AnimationCandidate:
        if not self.candidates:
            raise ConverterError(ErrorCode.ANIMATION_NOT_FOUND, "No compatible animation candidate", category=self.category)
        return self.candidates[0]


_ROW = re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s+filename\s*=\s*"([^"]+\.anim)"(?:\s+metadata\s*=\s*"([^"]+)")?(.*)$')
_ATTRIBUTE = re.compile(r"([a-zA-Z0-9_]+)\s*=\s*([^,]+)")


def canonical_path(value: str) -> str:
    return value.replace("\\", "/").strip().casefold()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_animation(path: Path, expected_skeleton: str) -> dict[str, Any]:
    """Decode metadata only; this never constructs a Blender Action."""
    identity = hashlib.sha256((file_sha256(path) + expected_skeleton).encode()).hexdigest()
    cached = METADATA_CACHE / f"{identity}.json"
    if not cached.is_file():
        if not INSPECTOR.is_file() or not SKELETON_ANIM.is_file() or not INVERSE_BIND.is_file():
            raise ConverterError(ErrorCode.ANIMATION_NOT_FOUND, "Animation metadata inspector dependencies are unavailable",
                                 animation=str(path))
        cached.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([str(INSPECTOR), "inspect-animation", "--animation", str(path),
                                 "--skeleton-anim", str(SKELETON_ANIM), "--inverse-bind", str(INVERSE_BIND),
                                 "--output", str(cached)], capture_output=True, text=True)
        if result.returncode:
            raise ConverterError(ErrorCode.ANIMATION_NOT_FOUND, "Animation metadata inspection failed",
                                 animation=str(path), stderr=result.stderr.strip())
    document = json.loads(cached.read_text(encoding="utf-8"))
    if document.get("skeleton_id") != expected_skeleton:
        raise ConverterError(ErrorCode.SKELETON_MISMATCH, "Animation clip skeleton differs from family skeleton",
                             animation=str(path), expected=expected_skeleton, actual=document.get("skeleton_id"))
    frames = document["frames"]
    def hips(frame: Mapping[str, Any]) -> list[float]:
        bone = next(item for item in frame["bones"] if item["name"] == "bn_hips")
        return [float(bone["world_matrix"][i][3]) for i in range(3)]
    first, last = hips(frames[0]), hips(frames[-1])
    return {"frame_count": document["sample_count"], "fps": document["sample_rate"],
            "duration": document["duration"], "root_displacement": [last[i] - first[i] for i in range(3)]}


def enrich_metadata(discoveries: Mapping[str, CategoryDiscovery]) -> dict[str, CategoryDiscovery]:
    result = {}
    for category, group in discoveries.items():
        candidates = []
        for candidate in group.candidates:
            info = inspect_animation(Path(candidate.local_asset), candidate.skeleton)
            displacement = tuple(info["root_displacement"])
            horizontal = math.hypot(displacement[0], displacement[2])
            duration = info["duration"]
            candidates.append(replace(candidate, frame_count=info["frame_count"], fps=info["fps"], duration=duration,
                                      root_displacement=displacement, horizontal_displacement=horizontal,
                                      locomotion_speed=horizontal / duration if category == "walk" and duration else None))
        result[category] = CategoryDiscovery(category, tuple(candidates), group.shortlist_size)
    return result


def fragment_path(family: str, roots: Iterable[Path] = FRAGMENT_ROOTS) -> Path:
    relative = Path("animations/animation_fragments") / f"{family}_fragment.txt"
    for root in roots:
        path = root / relative
        if path.is_file():
            return path
    raise ConverterError(ErrorCode.UNRESOLVED_ANIMATION_FAMILY, "Authoritative animation fragment is unavailable", family=family)


def parse_fragment(path: Path) -> tuple[str, tuple[FragmentMapping, ...]]:
    skeleton = ""
    rows: list[FragmentMapping] = []
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.strip().startswith("skeleton_type"):
            skeleton = line.split(None, 1)[1].strip()
        match = _ROW.match(line)
        if match:
            attributes = {key.casefold(): value.strip() for key, value in _ATTRIBUTE.findall(match.group(4))}
            rows.append(FragmentMapping(match.group(1), canonical_path(match.group(2)),
                                        canonical_path(match.group(3)) if match.group(3) else None,
                                        attributes, number))
    if not skeleton or not rows:
        raise ConverterError(ErrorCode.UNRESOLVED_ANIMATION_FAMILY, "Animation fragment is malformed", path=str(path))
    return skeleton, tuple(rows)


def _semantic_category(state: str, asset: str) -> str | None:
    value = f"{state} {asset}".casefold()
    if "getup" in value or "get_up" in value:
        return None
    if "death" in value or "die" in value:
        return "death"
    if any(token in value for token in ("attack", "_atk", "strike")):
        return "attack"
    if any(token in value for token in ("walk", "locomotion")) and not any(token in value for token in ("to_walk", "walk_to", "turn")):
        return "walk"
    if state in {"STAND", "COMBAT_READY"} or "STAND_IDLE" in state:
        return "idle"
    return None


def _tags(states: Iterable[str], asset: str) -> tuple[str, ...]:
    value = " ".join(states) + " " + asset
    tests = {"combat-ready": ("COMBAT_READY", "_cr_"), "synchronized": ("SYNC",),
             "missile": ("MISSILE", "JAVELIN"), "melee": ("ATTACK", "_ATK"),
             "wounded": ("WOUND",), "movement": ("WALK", "RUN", "CHARGE"),
             "standing": ("STAND",)}
    upper = value.upper()
    return tuple(key for key, needles in tests.items() if any(item in upper for item in needles))


def _rank(category: str, states: tuple[str, ...], asset: str) -> tuple[int, tuple[str, ...]]:
    value = (" ".join(states) + " " + asset).casefold()
    score, reasons = 0, []
    if category == "idle":
        if "combat_ready" in value: score += 30; reasons.append("authoritative combat-ready state")
        if "stand" in value: score += 20; reasons.append("stable standing state")
        if "idle" in value: score += 10; reasons.append("idle-labelled source")
    elif category == "walk":
        if "walk" in value: score += 30; reasons.append("ordinary walk-labelled locomotion")
        if not any(x in value for x in ("run", "charge", "combat")): score += 10; reasons.append("not run/charge/combat-walk")
    elif category == "attack":
        if "sync" not in value: score += 25; reasons.append("independent attack")
        else: score -= 20; reasons.append("synchronized context penalty")
        if any(x in value for x in ("sword", "slash", "thrust", "_atk")): score += 10; reasons.append("melee-compatible source")
    elif category == "death":
        if "stand" in value: score += 20; reasons.append("ordinary standing death")
        if "combat_ready" in value: score += 10; reasons.append("combat-ready death")
        if "wound" in value: score -= 40; reasons.append("wounded transition penalty")
    return score, tuple(reasons)


def _find_asset(canonical: str, roots: Iterable[Path]) -> Path | None:
    relative = Path(*canonical.split("/"))
    for root in roots:
        direct = root / relative
        if direct.is_file():
            return direct
    basename = relative.name.casefold()
    flattened = canonical.replace("/", "__")
    for root in roots:
        if not root.is_dir():
            continue
        matches = sorted((item for item in root.rglob("*.anim")
                          if item.name.casefold() in {basename, flattened}), key=lambda p: str(p).casefold())
        if matches:
            return matches[0]
    return None


def discover(unit: ResolvedUnit, roots: Iterable[Path] = ASSET_ROOTS,
             metadata: Mapping[str, Mapping[str, Any]] | None = None,
             shortlist_size: int = DEFAULT_SHORTLIST_SIZE) -> dict[str, CategoryDiscovery]:
    path = fragment_path(unit.animation.family, roots)
    skeleton, mappings = parse_fragment(path)
    if skeleton != unit.animation.skeleton:
        raise ConverterError(ErrorCode.SKELETON_MISMATCH, "Fragment skeleton differs from unit skeleton",
                             family=unit.animation.family, expected=unit.animation.skeleton, actual=skeleton)
    grouped: dict[str, list[FragmentMapping]] = {}
    for row in mappings:
        grouped.setdefault(row.asset, []).append(row)
    found = {category: [] for category in CATEGORIES}
    metadata = metadata or {}
    for asset, rows in grouped.items():
        categories = {_semantic_category(row.state, asset) for row in rows}
        categories.discard(None)
        if len(categories) != 1:
            continue
        category = categories.pop()
        local = _find_asset(asset, roots)
        if local is None:
            continue
        states = tuple(dict.fromkeys(row.state for row in rows if _semantic_category(row.state, asset) == category))
        score, reasons = _rank(category, states, asset)
        info = metadata.get(asset, {})
        displacement = info.get("root_displacement")
        horizontal = math.hypot(displacement[0], displacement[1]) if displacement else None
        duration = info.get("duration")
        found[category].append(AnimationCandidate(
            category, states, asset, str(local), tuple(dict.fromkeys(row.metadata for row in rows if row.metadata)), skeleton,
            info.get("frame_count"), info.get("fps"), duration,
            tuple(displacement) if displacement else None, horizontal,
            horizontal / duration if horizontal is not None and duration else None,
            tuple(f"weapon_{index.zfill(2)}" for index in ("2", "3", "4", "5")
                  if any(row.attributes.get(f"weapon_bone_{int(index)}") == "on" for row in rows)),
            info.get("looping", category in {"idle", "walk"}), _tags(states, asset), score, reasons,
            f"{path.as_posix()} lines {min(row.line for row in rows)}-{max(row.line for row in rows)}"))
    return {category: CategoryDiscovery(category, tuple(sorted(found[category], key=lambda item: (-item.score, item.resolved_asset))), shortlist_size)
            for category in CATEGORIES}


def choose_candidate(discovery: CategoryDiscovery, value: str) -> tuple[AnimationCandidate, str]:
    if value.casefold() == "a":
        return discovery.recommendation, "deterministic_auto"
    try:
        index = int(value)
    except ValueError:
        index = 0
    if not 1 <= index <= len(discovery.candidates):
        raise ConverterError(ErrorCode.INVALID_ANIMATION_SELECTION, "Invalid animation candidate ID",
                             category=discovery.category, selection=value, valid=list(range(1, len(discovery.candidates) + 1)))
    return discovery.candidates[index - 1], "explicit"


def visual_identity(manifest: Mapping[str, Any]) -> str:
    stable = {"source": manifest["source"], "components": manifest["components"],
              "palette": manifest.get("palette", {}), "material_backend": "rome2_exact_material_backend-v1",
              "attachments": "generic-infantry-v1"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def preview_cache_identity(manifest: Mapping[str, Any], candidate: AnimationCandidate) -> str:
    stable = {"visual": visual_identity(manifest), "animation": candidate.resolved_asset,
              "animation_sha256": file_sha256(Path(candidate.local_asset)), "skeleton": candidate.skeleton,
              "profile": PREVIEW_PROFILE}
    if candidate.category == "death":
        stable["category_framing"] = "death-horizontal-only-v1"
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze_animations(manifest: Mapping[str, Any], selections: Mapping[str, tuple[AnimationCandidate, str]]) -> dict[str, Any]:
    document = json.loads(json.dumps(manifest))
    document["schema_version"] = 2
    document["animations"] = {category: selections[category][0].manifest_record(selections[category][1]) for category in CATEGORIES}
    return document
