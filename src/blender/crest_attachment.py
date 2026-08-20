"""Geometry-derived Rome II helmet crest attachment and validation.

The socket orientation comes from the source RMV2 attachment.  This module
only solves its translation by bringing the rigid crest connector into contact
with the helmet's crest mount, expressed in the animated ``bn_head`` frame.
"""

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector


CONTACT_EPSILON = 1.0e-4
SUPPORT_TOLERANCE = 5.0e-4
PAIR_SOLUTION_CACHE = {}


def mesh_for_asset(asset_path, role):
    """Resolve an imported mesh by source asset identity, independent of unit."""
    token = str(asset_path).replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    matches = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and (
        token in obj.name.lower()
        or str(obj.get("source_asset", "")).replace("\\", "/").lower().endswith(
            str(asset_path).replace("\\", "/").lower()
        )
        or obj.get("attachment_role") == role
    )]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {role} mesh for asset {asset_path}, found {len(matches)}")
    return matches[0]


def _components_world(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        adjacency = [set() for _ in mesh.vertices]
        for edge in mesh.edges:
            a, b = edge.vertices
            adjacency[a].add(b)
            adjacency[b].add(a)
        unseen = set(range(len(mesh.vertices)))
        components = []
        while unseen:
            seed = unseen.pop()
            stack = [seed]
            indices = [seed]
            while stack:
                for neighbour in adjacency[stack.pop()]:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        stack.append(neighbour)
                        indices.append(neighbour)
            components.append(np.asarray([
                tuple(evaluated.matrix_world @ mesh.vertices[index].co)
                for index in indices
            ], dtype=np.float64))
        return components
    finally:
        evaluated.to_mesh_clear()


def _contact_geometry(helmet, crest, attachment_up, axis=None):
    """Find mating components by support geometry, without asset-specific IDs."""
    helmet_components = _components_world(helmet)
    crest_components = _components_world(crest)
    # The source socket orientation supplies the attachment/up axis. Resolve
    # the lower crest connector and upper helmet mount as support surfaces in
    # that frame; no component topology or unit identity is assumed.
    attachment_up = np.asarray(attachment_up, dtype=np.float64)
    attachment_up /= np.linalg.norm(attachment_up)
    lower_supports = [float((points @ attachment_up).min()) for points in crest_components]
    lowest = min(lower_supports)
    root_components = [points for points, support in zip(crest_components, lower_supports)
                       if support <= lowest + SUPPORT_TOLERANCE]
    roots = np.concatenate(root_components)
    if axis is None:
        centered = roots - roots.mean(axis=0)
        _, _, vectors = np.linalg.svd(centered, full_matrices=False)
        axis = vectors[0]
        if axis[2] < 0:
            axis = -axis
    axis = np.asarray(axis, dtype=np.float64)
    axis /= np.linalg.norm(axis)
    # The helmet crest mount is the connected component with the furthest
    # support surface along the connector axis.
    helmet_mount = max(helmet_components, key=lambda points: float((points @ axis).max()))
    mount_projection = helmet_mount @ axis
    root_projection = roots @ axis
    mount = helmet_mount[
        mount_projection >= mount_projection.max() - SUPPORT_TOLERANCE
    ].mean(axis=0)
    root = roots[
        root_projection <= root_projection.min() + SUPPORT_TOLERANCE
    ].mean(axis=0)
    return axis, mount, root, [len(points) for points in root_components], len(helmet_mount)


def _point(matrix, value):
    result = matrix @ Vector(value)
    return [float(result.x), float(result.y), float(result.z)]


def seat_crest(armature, helmet, crest, wrapper, reference_frame,
               helmet_asset, crest_asset, socket_name):
    """Seat an already source-oriented crest and return an audit record."""
    scene = bpy.context.scene
    previous_frame = scene.frame_current
    scene.frame_set(reference_frame)
    bpy.context.view_layer.update()
    pair_key = (str(helmet_asset).lower(), str(crest_asset).lower(), socket_name.lower())
    carrier_world = armature.matrix_world @ armature.pose.bones["bn_head"].matrix
    cached = PAIR_SOLUTION_CACHE.get(pair_key)
    if cached is not None:
        wrapper.matrix_basis = cached.copy()
        bpy.context.view_layer.update()
    attachment_up = wrapper.matrix_world.to_3x3().col[2]
    axis, mount, root, root_counts, mount_count = _contact_geometry(
        helmet, crest, attachment_up
    )
    raw_delta = mount - root
    translation = (np.zeros(3, dtype=np.float64) if cached is not None
                   else raw_delta + axis * CONTACT_EPSILON)
    carrier_inverse = carrier_world.inverted()
    orientation_before = wrapper.matrix_basis.to_3x3().copy()
    if cached is None:
        wrapper.matrix_basis = carrier_inverse @ (
            Matrix.Translation(tuple(translation)) @ wrapper.matrix_world
        )
    bpy.context.view_layer.update()
    attachment_up_after = wrapper.matrix_world.to_3x3().col[2]
    axis_after, mount_after, root_after, _, _ = _contact_geometry(
        helmet, crest, attachment_up_after, axis
    )
    residual = root_after - mount_after
    orientation_error = max(
        abs(wrapper.matrix_basis.to_3x3()[row][column] - orientation_before[row][column])
        for row in range(3) for column in range(3)
    )
    scene.frame_set(previous_frame)
    if cached is None:
        PAIR_SOLUTION_CACHE[pair_key] = wrapper.matrix_basis.copy()
    return {
        "method": "connected-component support contact in animated bn_head frame",
        "asset_pair_identity": {"helmet": str(helmet_asset), "crest": str(crest_asset),
                                "socket": socket_name},
        "solution_cache_key": list(pair_key),
        "derived_for_asset_pair": True,
        "reused_cached_asset_pair_solution": cached is not None,
        "reference_frame": reference_frame,
        "helmet_mount_component_vertices": mount_count,
        "crest_root_component_vertices": root_counts,
        "attachment_axis_world": axis.tolist(),
        "helmet_contact_carrier_local": _point(carrier_inverse, mount),
        "crest_contact_carrier_local_before": _point(carrier_inverse, root),
        "derived_translation_world": translation.tolist(),
        "derived_translation_carrier_local": _point(
            carrier_inverse.to_3x3().to_4x4(), translation
        ),
        "contact_epsilon": CONTACT_EPSILON,
        "final_contact_distance": float(np.linalg.norm(residual)),
        "final_axis_separation": float(residual @ axis_after),
        "orientation_matrix_max_error": orientation_error,
        "penetration": bool(float(residual @ axis_after) < -1.0e-6),
    }


def validate_crest_cycle(armature, helmet, crest, wrapper, frames):
    """Validate the fixed socket over every animation frame."""
    rows = []
    reference_local = wrapper.matrix_basis.copy()
    maximum_contact = maximum_drift = 0.0
    minimum_axis_separation = float("inf")
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        attachment_up = wrapper.matrix_world.to_3x3().col[2]
        axis, mount, root, _, _ = _contact_geometry(helmet, crest, attachment_up)
        residual = root - mount
        distance = float(np.linalg.norm(residual))
        separation = float(residual @ axis)
        drift = max(
            abs(wrapper.matrix_basis[row][column] - reference_local[row][column])
            for row in range(4) for column in range(4)
        )
        values = [value for matrix in (wrapper.matrix_world, reference_local)
                  for row in matrix for value in row]
        valid = all(math.isfinite(value) for value in values)
        rows.append({"frame": frame, "contact_distance": distance,
                     "axis_separation": separation, "socket_drift": drift,
                     "finite_transform": valid, "penetration": separation < -1.0e-6})
        maximum_contact = max(maximum_contact, distance)
        maximum_drift = max(maximum_drift, drift)
        minimum_axis_separation = min(minimum_axis_separation, separation)
    return {
        "frames": rows,
        "frame_count": len(rows),
        "maximum_contact_distance": maximum_contact,
        "maximum_socket_drift": maximum_drift,
        "minimum_axis_separation": minimum_axis_separation,
        "all_transforms_finite": all(row["finite_transform"] for row in rows),
        "penetration_detected": any(row["penetration"] for row in rows),
    }
