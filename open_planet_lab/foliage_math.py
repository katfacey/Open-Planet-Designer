# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable raster support contours for alpha-aware distant crown geometry."""
import math


def support_loops(mask):
    """Oriented boundaries of a binary pixel union, including interior holes.

    At diagonal contacts choose the left turn, retaining separate leaf islands.
    Coordinates are pixel corners; +Y is up. Filled regions stay on the left.
    """
    edges=set()
    for y,row in enumerate(mask):
        for x,occupied in enumerate(row):
            if not occupied:continue
            for a,b in (((x,y),(x+1,y)),((x+1,y),(x+1,y+1)),((x+1,y+1),(x,y+1)),((x,y+1),(x,y))):
                if (b,a) in edges:edges.remove((b,a))
                else:edges.add((a,b))
    adjacency={}
    for a,b in edges:adjacency.setdefault(a,set()).add(b)
    result=[]
    while edges:
        first=min(edges);start,point=first;previous=start;loop=[start]
        edges.remove(first);adjacency[start].remove(point)
        while point!=start:
            loop.append(point)
            dx,dy=point[0]-previous[0],point[1]-previous[1]
            options=[b for b in adjacency.get(point,()) if (point,b) in edges]
            if not options:raise ValueError('Open alpha-support contour')
            # atan2(cross,dot) orders left, straight, right, reverse.
            next_point=max(options,key=lambda b:math.atan2(dx*(b[1]-point[1])-dy*(b[0]-point[0]),dx*(b[0]-point[0])+dy*(b[1]-point[1])))
            edges.remove((point,next_point));adjacency[point].remove(next_point)
            previous,point=point,next_point
        result.append(loop)
    return result


def area(loop):
    return .5*sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(loop,loop[1:]+loop[:1]))


def simplify_loop(loop):
    """Remove only collinear corners, preserving holes, area and thin branches."""
    return [p for i,p in enumerate(loop) if
        (p[0]-loop[i-1][0])*(loop[(i+1)%len(loop)][1]-p[1]) !=
        (p[1]-loop[i-1][1])*(loop[(i+1)%len(loop)][0]-p[0])]
