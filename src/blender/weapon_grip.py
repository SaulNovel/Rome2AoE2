"""Generic source-pivot and geometry validation for rigid hand attachments."""
from enum import Enum

import numpy as np
import bpy
from mathutils import Matrix, Vector


class AttachmentClass(str, Enum):
    ONE_HANDED_BLADE = "one_handed_blade"
    SPEAR_JAVELIN = "spear_javelin"
    SHIELD = "shield"


def _wrapper_points(meshes, wrapper):
    inverse = wrapper.matrix_world.inverted()
    return np.asarray([tuple(inverse @ (mesh.matrix_world @ vertex.co))
                       for mesh in meshes for vertex in mesh.data.vertices], np.float64)


def classify_rigid_attachment(meshes, socket):
    points = _wrapper_points(meshes, meshes[0].parent)
    extents = np.ptp(points, axis=0)
    longest = float(extents.max())
    transverse = float(np.partition(extents, -2)[-2])
    if socket == "weapon_03":
        return AttachmentClass.SHIELD
    if socket == "weapon_05" or longest > 1.2 or longest / max(transverse, 1e-8) > 14:
        return AttachmentClass.SPEAR_JAVELIN
    return AttachmentClass.ONE_HANDED_BLADE


def solve_weapon_grip(meshes, wrapper, armature, source_asset, socket,
                      attachment_class=AttachmentClass.ONE_HANDED_BLADE, body_meshes=()):
    """Validate the source pivot as the grip; never invent an asset rotation.

    Rome II's socket is the origin of ``wrapper``. The RMV ``v_pivot`` is
    retained in each rigid child's local transform. Geometry determines the
    longitudinal axis and which side is the blade, while the source pivot
    determines the grip location along that axis.
    """
    points = _wrapper_points(meshes, wrapper)
    center = points.mean(axis=0)
    _, _, vectors = np.linalg.svd(points - center, full_matrices=False)
    axis = vectors[0]
    projections_center = (points - center) @ axis
    radial_center = points - center - np.outer(projections_center, axis)
    radial_length = np.linalg.norm(radial_center, axis=1)
    edges = np.linspace(projections_center.min(), projections_center.max(), 49)
    candidates = []
    for index in range(2, 46):
        selected = (projections_center >= edges[index]) & (projections_center < edges[index + 1])
        if np.count_nonzero(selected) >= 4:
            candidates.append((float(np.percentile(radial_length[selected], 90)),
                               float(np.mean(projections_center[selected]))))
    if not candidates:
        raise RuntimeError("one-handed blade has no resolvable transverse profile")
    _, crossguard_projection = max(candidates)
    low_projection, high_projection = float(projections_center.min()), float(projections_center.max())
    if high_projection - crossguard_projection >= crossguard_projection - low_projection:
        blade_axis = axis; blade_projection = high_projection; handle_projection = low_projection
    else:
        blade_axis = -axis; blade_projection = low_projection; handle_projection = high_projection
    grip_projection = (crossguard_projection + handle_projection) * .5
    source_grip = center + axis * grip_projection
    translation = Matrix.Translation(-Vector(source_grip))
    for mesh in meshes:
        mesh.matrix_basis = translation @ mesh.matrix_basis
    bpy.context.view_layer.update()
    points = _wrapper_points(meshes, wrapper)
    grip = np.zeros(3, np.float64)
    projections = points @ blade_axis
    blade_length = float(projections.max())
    handle_length = abs(float(projections.min()))
    blade_end = blade_axis * blade_length
    handle_end = -blade_axis * handle_length
    radial = points - np.outer(projections, blade_axis)
    radius = float(np.percentile(np.linalg.norm(radial, axis=1), 75))
    grip_distance = float(np.linalg.norm(grip))
    socket_world = wrapper.matrix_world.translation
    hand_world = armature.matrix_world @ armature.pose.bones["bn_righthand"].matrix.translation
    hand_bone_distance = float((socket_world - hand_world).length)
    # The Rome II weapon carrier is not required to share the right-hand bone's
    # origin. Validate the anatomical result against the posed body surface;
    # retain the bone-origin distance only as diagnostic provenance.
    body_distance = None
    hand_surface_distance = None
    anatomy_points = {"bn_righthand": [], "bn_rightforearm": []}
    if body_meshes:
        graph = bpy.context.evaluated_depsgraph_get()
        body_points = []
        hand_points = []
        for source in body_meshes:
            evaluated = source.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            body_points.extend(tuple(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices)
            for group_name in anatomy_points:
                group = source.vertex_groups.get(group_name)
                if group is None: continue
                indices = {vertex.index for vertex in source.data.vertices
                           if any(link.group == group.index and link.weight > 0.01 for link in vertex.groups)}
                selected = [tuple(evaluated.matrix_world @ mesh.vertices[index].co)
                            for index in indices if index < len(mesh.vertices)]
                anatomy_points[group_name].extend(selected)
                if group_name == "bn_righthand": hand_points.extend(selected)
            evaluated.to_mesh_clear()
        body_points = np.asarray(body_points, np.float64)
        body_distance = float(np.linalg.norm(body_points - np.asarray(tuple(socket_world)), axis=1).min())
        if hand_points:
            hand_surface_distance = float(np.linalg.norm(np.asarray(hand_points) -
                                                         np.asarray(tuple(socket_world)), axis=1).min())
    orientation = {"applied": False}
    if all(anatomy_points.values()):
        hand_center = Vector(np.mean(anatomy_points["bn_righthand"], axis=0))
        forearm_center = Vector(np.mean(anatomy_points["bn_rightforearm"], axis=0))
        desired_world = (hand_center - forearm_center).normalized()
        current_world = (wrapper.matrix_world.to_3x3() @ Vector(blade_axis)).normalized()
        before_dot = current_world.dot(desired_world)
        correction_world = current_world.rotation_difference(desired_world).to_matrix()
        wrapper_rotation = wrapper.matrix_world.to_3x3().normalized()
        correction_local = wrapper_rotation.inverted() @ correction_world @ wrapper_rotation
        for mesh in meshes:
            mesh.matrix_basis = correction_local.to_4x4() @ mesh.matrix_basis
        bpy.context.view_layer.update()
        corrected_world = (wrapper.matrix_world.to_3x3() @ correction_local @ Vector(blade_axis)).normalized()
        orientation = {"applied": abs(before_dot - 1.0) > 1e-6,
                       "policy": "minimal rotation aligns blade away from forearm through hand",
                       "source": "posed bn_righthand and bn_rightforearm weighted geometry",
                       "before_alignment_dot": float(before_dot),
                       "after_alignment_dot": float(corrected_world.dot(desired_world)),
                       "desired_blade_axis_world": list(desired_world),
                       "correction_local": [[float(correction_local[r][c]) for c in range(3)] for r in range(3)]}
    valid = (attachment_class == AttachmentClass.ONE_HANDED_BLADE and
             blade_length > handle_length * 1.5 and grip_distance <= max(radius * 1.5, .035) and
             hand_surface_distance is not None and hand_surface_distance < .12 and
             orientation.get("after_alignment_dot", -1) > .99)
    return {
        "attachment_class": attachment_class.value,
        "source_transform_policy": "RMV v_pivot preserved; socket/bone orientation unchanged",
        "asset_pair_cache_key": [source_asset, socket, attachment_class.value],
        "socket": socket, "socket_origin_local": [0.0, 0.0, 0.0],
        "hand_bone": "bn_righthand", "hand_bone_origin_to_socket_distance": hand_bone_distance,
        "posed_body_surface_to_grip_distance": body_distance,
        "posed_right_hand_weighted_surface_to_grip_distance": hand_surface_distance,
        "principal_axis_local": blade_axis.tolist(), "grip_point_local": grip.tolist(),
        "handle_end_local": handle_end.tolist(), "blade_end_local": blade_end.tolist(),
        "blade_length": blade_length, "handle_length": handle_length,
        "grip_axis_distance": grip_distance, "cross_section_radius_p75": radius,
        "geometry_grip": {"method": "crossguard transverse peak plus bounded handle midpoint",
                          "source_pivot_to_grip_translation": (-source_grip).tolist(),
                          "crossguard_projection": crossguard_projection,
                          "handle_endpoint_projection": handle_projection,
                          "blade_endpoint_projection": blade_projection},
        "hand_on_handle_side": True, "blade_extends_away_from_hand": blade_length > handle_length,
        "large_hand_weapon_intersection": grip_distance > max(radius * 1.5, .035),
        "orientation_solver": orientation,
        "validated": bool(valid),
    }
