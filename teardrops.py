# Matt's easyeda version of:

# Teardrop for pcbnew using filled zones
# (c) Niluje 2019 thewireddoesntexist.org
#
# Based on Teardrops for PCBNEW by svofski, 2014 http://sensi.org/~svo
# Cubic Bezier upgrade by mitxela, 2021 mitxela.com

from line import Vector, normalize, dist, distsq, dot, kdtree, kdnear
from board import floatToString, pointToStr
from collections import defaultdict
from math import sqrt

def lookup(p):
    return (int(p.x * 10 + .5), int(p.y * 10 + .5))

def __Bezier(p1, p2, p3, p4, n=20):
    h = 1.0 / (n - 1)
    d0 = (p2 - p1) * (h * 3)
    d1 = (p1 - p2 * 2 + p3) * (h * h * 6)
    d2 = ((p2 - p3) * 3 + p4 - p1) * (h * h * h)
    pts = [None] * n
    pts[0] = p1
    for i in range(1, n - 1):
        p1 = Vector(p1.x + d0.x + d1.x * .5 + d2.x,
                    p1.y + d0.y + d1.y * .5 + d2.y)
        d0 = Vector(d0.x + d1.x + d2.x * 3,
                    d0.y + d1.y + d2.y * 3)
        d1 = Vector(d1.x + d2.x * 6,
                    d1.y + d2.y * 6)
        pts[i] = p1
    pts[n - 1] = p4
    return pts

def pointsToPath(pts):
    return 'M ' + ' L '.join(pointToStr(p) for p in pts) + ' Z'

def __ComputeCurved(vpercent, w, trackDir, via, pts, segs):
    """Compute the curves part points"""

    # A and B are points on the track
    # C and E are points on the via
    # D is midpoint behind the via centre

    radius = via.diameter / 2
    minVpercent = float(w * 2) / float(via.diameter)
    weaken = (vpercent / 100.0 - minVpercent) / (1 - minVpercent) / radius

    biasBC = 0.5 * dist(pts[1], pts[2])
    biasAE = 0.5 * dist(pts[4], pts[0])

    vecC = pts[2] - via.pos
    tangentC = Vector(pts[2].x - vecC.y * biasBC * weaken,
                      pts[2].y + vecC.x * biasBC * weaken)
    vecE = pts[4] - via.pos
    tangentE = Vector(pts[4].x + vecE.y * biasAE * weaken,
                      pts[4].y - vecE.x * biasAE * weaken)

    tangentB = pts[1] - trackDir * biasBC
    tangentA = pts[0] - trackDir * biasAE

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

def __ComputePoints(track, via, hpercent, vpercent, segs, trackLookup):
    """Compute all teardrop points"""
    start = track.start
    end = track.end
    radius = via.diameter * .5
    radiusSq = radius * radius
    w = track.width * .5

    if vpercent > 100:
        vpercent = 100

    # ensure that start is at the via/pad end
    if distsq(start, via.pos) > distsq(end, via.pos):
        start, end = end, start

    # choose a teardrop length
    targetLength = via.diameter * hpercent / 100.0
    tearDropLength = 0

    while 1:
        d = end - start
        a = dot(d, d)
        trackLen = sqrt(a)
        trackDir = d / trackLen
        if distsq(end, via.pos) >= radiusSq: # end is outside via
            f = start - via.pos
            c = dot(f, f) - radiusSq
            if tearDropLength == 0 and c < 0:
                # start is inside via, find point on circumference
                b = 2 * dot(f, d)
                t = (sqrt(b * b - 4 * a * c) - b) / (2 * a)
                start += d * t
                # update length
                trackLen = dist(start, end)
                # direction to the track exit point
                tearDropDir = normalize(start - via.pos)
            # find distance along track to place end of teardrop
            posOnTrack = min(trackLen, targetLength - tearDropLength)
            tearDropLength += posOnTrack
            if tearDropLength >= targetLength:
                break
        else:
            posOnTrack = trackLen

        # if not long enough, attempt to walk back along the curved track
        t = __FindTouchingTrack(track, end, trackLookup)
        if not t or t.width != track.width:
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
    start += trackDir * posOnTrack
    pointA = start + Vector(-trackDir.y * w, trackDir.x * w)
    pointB = start + Vector(trackDir.y * w, -trackDir.x * w)

    # via side points
    s = radius * vpercent / 100.0
    c = sqrt(radiusSq - s * s)
    pointC = via.pos + Vector(tearDropDir.x * c + tearDropDir.y * s, 
                             -tearDropDir.x * s + tearDropDir.y * c)
    pointE = via.pos + Vector(tearDropDir.x * c - tearDropDir.y * s, 
                              tearDropDir.x * s + tearDropDir.y * c)

    # Introduce a last point in order to cover the via centre.
    pointD = via.pos - tearDropDir * (radius * 0.5)

    pts = [pointA, pointB, pointC, pointD, pointE]
    if segs > 2:
        return __ComputeCurved(vpercent, w, trackDir, via, pts, segs)
    else:
        return pointsToPath(pts)

def SetTeardrops(pcb, tracks, vias, args):
    """Set teardrops on a teardrop free board"""
    hpercent = args.teardropLength
    vpercent = args.teardropWidth
    segs = args.teardropSegs

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
                    path = __ComputePoints(t, via, hpercent, vpercent, segs, trackLookup)
                    if path:
                        pcb.addShape(f"SOLIDREGION~{t.layer}~{t.net}~{path}~solid~{pcb.getShapeId()}~~~~0")
