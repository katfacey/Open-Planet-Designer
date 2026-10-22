# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable reference math for substrate mixing, texture phase and clear air."""
import math


def smooth(value, lower=0., upper=1.):
    t = max(0., min(1., (value - lower) / max(1e-12, upper - lower)))
    return t * t * (3. - 2. * t)


def ground_weights(slope_cosine, forest, mountain, desert, moisture, patch):
    """Four nonnegative weights: meadow, litter, damp sediment, exposed rock.

    Moisture/deposition are artistic habitat approximations, not hydrology.
    """
    steep = 1. - smooth(slope_cosine, .57, .88)
    rock = max(steep, max(0., min(1., mountain)) * .52, max(0., min(1., desert)) * .38)
    wet = max(0., min(1., moisture * (.35 + .65 * patch) * smooth(slope_cosine, .65, .96) * (1. - desert * .9)))
    soil = 1. - rock
    litter = soil * (1. - wet) * forest
    meadow = soil * (1. - wet) * (1. - forest)
    return meadow, litter, soil * wet, rock


def texture_phase(anchor, radius_m, tile_m):
    """Keep repeat-map coordinates small without changing geographic phase."""
    return tuple((float(value) * radius_m / tile_m) % 1. for value in anchor)


def optical_depth(origin, direction, distance, radius_m=6371000.,
                  air=1., aerosol=.35, samples=24, outer_height_m=100000.):
    """Normalized spherical ray integral with samples near closest approach.

    Returns scalar extinction used by the shared material approximation. The
    sky itself uses Blender's multiple-scattering model; this is not a full
    spectral/multiple-scattering transport solver for arbitrary planets.
    """
    length = math.sqrt(sum(x*x for x in direction))
    d = tuple(x/length for x in direction)
    dot = sum(origin[i]*d[i] for i in range(3))
    o2 = sum(x*x for x in origin)
    outer = 1. + outer_height_m / radius_m
    discriminant = dot*dot + outer*outer - o2
    if discriminant <= 0:
        return 0.
    root = math.sqrt(discriminant)
    start, end = max(0., -dot-root), min(distance, -dot+root)
    if end <= start:
        return 0.
    closest = max(start, min(end, -dot))
    accum_r = accum_m = 0.
    for endpoint, sign, extent in ((closest, -1., closest-start), (closest, 1., end-closest)):
        for i in range(samples):
            a, b = (i/samples)**2, ((i+1)/samples)**2
            t = endpoint + sign * extent * (a+b) * .5
            point = tuple(origin[j] + d[j]*t for j in range(3))
            height = max(0., (math.sqrt(sum(x*x for x in point))-1.) * radius_m)
            ds = extent * (b-a) * radius_m
            accum_r += math.exp(-height/8000.) * ds
            accum_m += math.exp(-height/1200.) * ds
    return air * 1.75e-5 * accum_r + aerosol * 2.e-5 * accum_m
