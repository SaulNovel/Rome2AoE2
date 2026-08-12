"""Shared, capture-replay-validated Rome II material preparation.

This module deliberately has no Blender dependency.  Capture replays and the
production bridge both pass already sampled texture values and interpolated
geometric attributes through these functions.
"""
from dataclasses import dataclass

import numpy as np


DIRT_COLOUR = np.array((0.03, 0.025, 0.02), np.float32)
LUMA = np.array((0.2126, 0.7152, 0.0722), np.float32)


def normalize(value):
    value = np.asarray(value, np.float32)
    return value / np.maximum(np.linalg.norm(value, axis=-1, keepdims=True), 1e-20)


def _rgb(value):
    return np.asarray(value, np.float32)[..., :3]


def _channel(value, channel):
    return np.asarray(value, np.float32)[..., channel]


def ag_xy(normal_sample):
    """Decode the captured A/G tangent-normal payload."""
    normal_sample = np.asarray(normal_sample, np.float32)
    tx = 2.0 * (normal_sample[..., 3] + np.float32(0.5 / 255.0)) - 1.0
    ty = 2.0 * (normal_sample[..., 1] + np.float32(0.5 / 255.0)) - 1.0
    return tx, ty


def tangent_normal(normal_sample, normal, tangent, bitangent,
                   dirt_sample=None, dirt_mask=None,
                   reconstruct_z_before_dirt=True, normalize_tangent=False):
    """Evaluate the captured tangent normal, preserving dirt/z ordering.

    Skin reconstructs z from the base normal and only then perturbs x/y.
    DecalDirtmap perturbs an already reconstructed tangent vector and normalizes
    that tangent vector before applying the basis.
    """
    tx, ty = ag_xy(normal_sample)
    tz = np.sqrt(np.maximum(0.0, 1.0 - tx * tx - ty * ty))
    if dirt_sample is not None and dirt_mask is not None:
        dirt_sample = np.asarray(dirt_sample, np.float32)
        weight = _channel(dirt_mask, 3)
        tx = tx + (2.0 * dirt_sample[..., 0] - 1.0) * weight
        ty = ty + (2.0 * dirt_sample[..., 1] - 1.0) * weight
        if not reconstruct_z_before_dirt:
            tz = np.sqrt(np.maximum(0.0, 1.0 - tx * tx - ty * ty))
    tn = np.stack((tx, ty, tz), axis=-1)
    if normalize_tangent:
        tn = normalize(tn)
    # Callers pass Rome shader N, T, B as normal, tangent, bitangent.  Keep the
    # public order intuitive, while matching tx*T + ty*B + tz*N here.
    world = (tn[..., 0, None] * normalize(tangent) +
             tn[..., 1, None] * normalize(bitangent) +
             tn[..., 2, None] * normalize(normal))
    return normalize(world)


def faction_diffuse(diffuse, mask, colours):
    result = _rgb(diffuse).copy()
    if mask is None:
        return result
    mask = np.asarray(mask, np.float32)
    for channel, colour in enumerate(np.asarray(colours, np.float32)):
        result += mask[..., channel, None] * (result * colour - result)
    return result


def material_controls(diffuse, reflectivity, controls, specular=None):
    controls = np.asarray(controls if controls is not None else (0.0, 0.0), np.float32)
    boost, desaturate = controls[..., 0], controls[..., 1]
    diffuse = np.clip(diffuse + boost[..., None] * ((5.0 * diffuse + 0.2) - diffuse), 0.0, 1.0)
    lum = np.sum(diffuse * LUMA, axis=-1)
    diffuse = np.clip(diffuse + desaturate[..., None] * (lum[..., None] - diffuse), 0.0, 1.0)
    reflectivity = reflectivity * (1.0 - boost) * (1.0 - desaturate)
    if specular is not None:
        flum = np.sum(specular * LUMA, axis=-1)
        specular = np.clip(specular + desaturate[..., None] * (flum[..., None] - specular), 0.0, 1.0)
    return diffuse, reflectivity, specular


@dataclass
class PreparedMaterial:
    normal: np.ndarray
    diffuse: np.ndarray
    specular: np.ndarray
    smoothness: np.ndarray
    reflectivity: np.ndarray
    alpha: np.ndarray
    gbuffer_family: str


def prepare_weighted(diffuse, specular, normal_sample, gloss, normal, tangent, bitangent,
                     mask=None, faction_colours=None):
    d = faction_diffuse(diffuse, mask, faction_colours) if faction_colours is not None else _rgb(diffuse)
    return PreparedMaterial(
        tangent_normal(normal_sample, normal, tangent, bitangent), d, _rgb(specular),
        _channel(gloss, 0), _channel(gloss, 1), _channel(diffuse, 3), "standard")


def prepare_weighted_skin_dirtmap(diffuse, normal_sample, gloss, dirt_mask, dirt,
                                  skin_mask, normal, tangent, bitangent, controls=(0.0, 0.0)):
    amount = _channel(dirt, 3) * _channel(dirt_mask, 3)
    d = _rgb(diffuse) + amount[..., None] * (DIRT_COLOUR - _rgb(diffuse))
    r = _channel(gloss, 1)
    d, r, _ = material_controls(d, r, controls)
    return PreparedMaterial(
        tangent_normal(normal_sample, normal, tangent, bitangent, dirt, dirt_mask,
                       reconstruct_z_before_dirt=True),
        d, _rgb(skin_mask), _channel(gloss, 0), r, _channel(diffuse, 3), "skin")


def prepare_weighted_dirtmap(diffuse, specular, normal_sample, gloss, dirt_mask, dirt,
                             normal, tangent, bitangent, mask=None, faction_colours=None):
    """Recovered helmet dirt path; lighting remains StandardLighting1915.

    The family is not promoted to capture-replay VALIDATED by this extraction;
    this function merely removes the divergent production-node copy.
    """
    d = faction_diffuse(diffuse, mask, faction_colours) if faction_colours is not None else _rgb(diffuse)
    amount = _channel(dirt, 3) * _channel(dirt_mask, 3)
    d = d + amount[..., None] * (DIRT_COLOUR - d)
    f = _rgb(specular) * (1.0 - 0.99*amount)[..., None]
    return PreparedMaterial(
        tangent_normal(normal_sample, normal, tangent, bitangent, dirt, dirt_mask,
                       reconstruct_z_before_dirt=True),
        d, f, _channel(gloss, 0), _channel(gloss, 1), _channel(diffuse, 3), "standard")


def prepare_decal_dirtmap(diffuse, specular, normal_sample, gloss, colour_mask,
                          dirt_mask, dirt, normal, tangent, bitangent,
                          faction_colours, controls=(0.0, 0.0),
                          decal_diffuse=None, decal_normal=None, decal_mask=None):
    d = faction_diffuse(diffuse, colour_mask, faction_colours)
    f = _rgb(specular).copy()
    r = _channel(gloss, 1).copy()
    base_tn = np.stack((*ag_xy(normal_sample),
                        np.sqrt(np.maximum(0.0, 1.0 - ag_xy(normal_sample)[0] ** 2 - ag_xy(normal_sample)[1] ** 2))), axis=-1)
    if decal_diffuse is not None and decal_normal is not None and decal_mask is not None:
        alpha = _channel(decal_diffuse, 3) * _channel(decal_mask, 3)
        dtx, dty = ag_xy(decal_normal)
        dtn = np.stack((dtx, dty, np.sqrt(np.maximum(0.0, 1.0 - dtx*dtx - dty*dty))), axis=-1)
        r = r - 0.5 * r * alpha
        f = f + alpha[..., None] * (_rgb(decal_diffuse) * _channel(decal_mask, 3)[..., None] - f)
        d = (1.0-alpha[..., None])*d + _rgb(decal_diffuse)*_channel(decal_mask, 3)[..., None]
        base_tn = base_tn + alpha[..., None]*(dtn-base_tn)
    amount = _channel(dirt, 3) * _channel(dirt_mask, 3)
    d = d + amount[..., None] * (DIRT_COLOUR - d)
    base_tn[..., :2] += (2.0*np.asarray(dirt)[..., :2]-1.0)*_channel(dirt_mask, 3)[..., None]
    f *= (1.0 - 0.99*amount)[..., None]
    tn = normalize(base_tn)
    n = normalize(tn[..., 0, None]*normalize(tangent) + tn[..., 1, None]*normalize(bitangent) + tn[..., 2, None]*normalize(normal))
    d, r, f = material_controls(d, r, controls, f)
    return PreparedMaterial(n, d, f, _channel(gloss, 0), r, _channel(diffuse, 3), "standard")


def pack_gbuffer(prepared):
    n = prepared.normal
    encoded = np.clip(0.5 + 0.5*n/np.maximum(np.max(np.abs(n), axis=-1, keepdims=True), 1e-20), 0.0, 1.0)
    rt0 = np.concatenate((encoded, prepared.smoothness[..., None]), axis=-1)
    if prepared.gbuffer_family == "skin":
        rt1 = np.concatenate((prepared.diffuse, prepared.reflectivity[..., None]), axis=-1)
        f = prepared.specular
        rt2 = np.stack((f[..., 0], f[..., 1], f[..., 2], f[..., 2]), axis=-1)
    else:
        rt1 = np.concatenate((np.sqrt(np.clip(prepared.diffuse, 0.0, 1.0)), prepared.reflectivity[..., None]), axis=-1)
        rt2 = np.concatenate((prepared.specular, np.zeros_like(prepared.reflectivity)[..., None]), axis=-1)
    return rt0, rt1, rt2
