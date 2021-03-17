# Matt's easyeda version of:

# Teardrop for pcbnew using filled zones
# (c) Niluje 2019 thewireddoesntexist.org
#
# Based on Teardrops for PCBNEW by svofski, 2014 http://sensi.org/~svo
# Cubic Bezier upgrade by mitxela, 2021 mitxela.com

from math import cos, acos, sin, asin, tan, atan2, sqrt, pi
from line import Vector, normalize, dist, add, sub, scale, dot, kdtree, kdnear
from board import floatToString, pointToStr
from collections import defaultdict
import math

def lookup(p):
    return (int(p.x * 10 + .5), int(p.y * 10 + .5))

def __Bezier(p1, p2, p3, p4, n=20.0):
    pts = []
    h = 1.0 / n
    d0 = (p2 - p1) * (h * 3)
    d1 = (p1 - p2 * 2 + p3) * (h * h * 6)
    d2 = ((p2 - p3) * 3 + p4 - p1) * (h * h * h)
    pts.append(p1)
    for i in range(int(n) - 1):
        p1 += d0 + d1 * .5 + d2
        d0 += d1 + d2 * 3
        d1 += d2 * 6
        pts.append(p1)
    pts.append(p4)
    return pts

def pointsToPath(pts):
    return 'M ' + ' L '.join(pointToStr(p) for p in pts) + ' Z'

def __ComputeCurved(vpercent, w, vec, via, pts, segs):
    """Compute the curves part points"""

    # A and B are points on the track
    # C and E are points on the via
    # D is midpoint behind the via centre

    radius = via.diameter / 2
    minVpercent = float(w * 2) / float(via.diameter)
    weaken = (vpercent / 100.0 - minVpercent) / (1 - minVpercent) / radius

    biasBC = 0.5 * dist(pts[1], pts[2])
    biasAE = 0.5 * dist(pts[4], pts[0])

    vecC = sub(pts[2], via.pos)
    tangentC = Vector(pts[2].x - vecC.y * biasBC * weaken,
                      pts[2].y + vecC.x * biasBC * weaken)
    vecE = sub(pts[4], via.pos)
    tangentE = Vector(pts[4].x + vecE.y * biasAE * weaken,
                      pts[4].y - vecE.x * biasAE * weaken)

    tangentB = sub(pts[1], scale(vec, biasBC))
    tangentA = sub(pts[0], scale(vec, biasAE))

    if 0: # easyeda copper fill doesn't like cubic beziers
        pts = [pointToStr(p) for p in pts]
        path = f'M {pts[3]} '
        path += f'L {pts[4]} C {pointToStr(tangentE)} {pointToStr(tangentA)} {pts[0]} '
        path += f'L {pts[1]} C {pointToStr(tangentB)} {pointToStr(tangentC)} {pts[2]} '
        path += 'Z'
        return path
    else:
        curve1 = __Bezier(pts[1], tangentB, tangentC, pts[2], n=segs)
        curve2 = __Bezier(pts[4], tangentE, tangentA, pts[0], n=segs)
        return pointsToPath(curve1 + [pts[3]] + curve2)

def __FindTouchingTrack(t1, endpoint, trackLookup):
    """Find a track connected to the end of another track"""
    endpoint = lookup(endpoint)
    if endpoint not in trackLookup:
        return None
    touchingTracks = trackLookup[endpoint]
    if len(touchingTracks) > 2 or t1 not in touchingTracks:
        return None
    for t in touchingTracks:
        if t != t1:
            return t
    return None

def __ComputePoints(track, via, hpercent, vpercent, segs, follow_tracks,
                    trackLookup):
    """Compute all teardrop points"""
    start = track.start
    end = track.end
    radius = via.diameter/2.0
    w = track.width/2

    if vpercent > 100:
        vpercent = 100

    # ensure that start is at the via/pad end
    if dist(start, via.pos) > dist(end, via.pos):
        start, end = end, start

    vec = normalize(sub(end, start))

    # choose a teardrop length
    targetLength = via.diameter * hpercent / 100.0
    tearDropLength = 0

    while 1:
        d = sub(end, start)
        a = dot(d, d)
        l = math.sqrt(a) # track len
        vecT = scale(d, 1.0 / l) # track dir
        if dist(end, via.pos) >= radius: # end is outside via
            f = sub(start, via.pos)
            c = dot(f, f) - radius * radius
            if tearDropLength == 0 and c < 0:
                # start is inside via, find point on circumference
                b = 2 * dot(f, d)
                t = (math.sqrt(b * b - 4 * a * c) - b) / (2 * a)
                start = add(start, scale(d, t))
                # update length
                l = dist(start, end)
                # direction to the track exit point
                vec = normalize(sub(start, via.pos))
            # find distance along track to place end of teardrop
            n = min(l, targetLength - tearDropLength)
            tearDropLength += n
            if tearDropLength >= targetLength:
                break
        else:
            n = l

        # if not long enough, attempt to walk back along the curved track
        if not follow_tracks:
            break
        t = __FindTouchingTrack(track, end, trackLookup)
        if not t:
            break
        track = t
        # make sure we use the correct end of the track
        if dist(end, t.start) > dist(end, t.end):
            start, end = t.end, t.start
        else:
            start, end = t.start, t.end

    # if shortened, shrink width too
    if tearDropLength < targetLength:
        minVpercent = 100 * float(w) / float(radius)
        vpercent = vpercent * tearDropLength / targetLength + minVpercent * (1 - tearDropLength / targetLength)
        vpercent = min(100, vpercent)

    # find point on the track, sharp end of the teardrop
    start = add(start, scale(vecT, n))
    pointB = add(start, Vector(vecT.y * w, -vecT.x * w))
    pointA = add(start, Vector(-vecT.y * w, vecT.x * w))

    # via side points
    d = asin(vpercent / 100.0)
    vecC = Vector(vec.x * cos(d) + vec.y * sin(d), -vec.x * sin(d) + vec.y * cos(d))
    d = asin(-vpercent / 100.0)
    vecE = Vector(vec.x * cos(d) + vec.y * sin(d), -vec.x * sin(d) + vec.y * cos(d))
    pointC = add(via.pos, scale(vecC, radius))
    pointE = add(via.pos, scale(vecE, radius))

    # Introduce a last point in order to cover the via centre.
    # If not, the zone won't be filled
    pointD = sub(via.pos, scale(vec, radius * 0.5))

    pts = [pointA, pointB, pointC, pointD, pointE]
    if segs > 2:
        return __ComputeCurved(vpercent, w, vecT, via, pts, segs)
    else:
        return pointsToPath(pts)

def SetTeardrops(pcb, tracks, vias, hpercent=50, vpercent=90, segs=10, follow_tracks=True):
    """Set teardrops on a teardrop free board"""
    tracks = [t for t in tracks if t.length > 0]
    trackLookup = defaultdict(list)
    for t in tracks:
        trackLookup[lookup(t.start)].append(t)
        trackLookup[lookup(t.end)].append(t)

    tracks = kdtree(list([t.start, t] for t in tracks) + list([t.end, t] for t in tracks))
    for via in vias:
        r = via.diameter * .5
        nearTracks = set(t for p, t in kdnear(tracks, via.pos, r))
        for t in nearTracks:
            if t.width < via.diameter * .95:
                # is the track entering/leaving the via?
                if (dist(t.start, via.pos) < r) != (dist(t.end, via.pos) < r):
                    path = __ComputePoints(t, via, hpercent, vpercent, segs,
                                follow_tracks, trackLookup)
                    if path:
                        pcb.addShape(f"SOLIDREGION~{t.layer}~{t.net}~{path}~solid~{pcb.getShapeId()}~~~~0")
