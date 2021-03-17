import pyclipper
from board import Board, floatToString, pointToStr
from line import makePolyLines, Line, Vector, dot, add, scale
from collections import defaultdict
import math

def expandTrackToPolygons(track, width):
    # create closed polygon
    poly = track + track[-2::-1] 
    # offset by half track width
    co = pyclipper.PyclipperOffset()
    co.AddPath(poly, pyclipper.JT_ROUND, pyclipper.ET_OPENROUND)
    return co.Execute(width / 2)

def unionPolygons(polys):
    clipper = pyclipper.Pyclipper()
    clipper.AddPaths(polys, pyclipper.PT_SUBJECT)
    return clipper.Execute(pyclipper.CT_UNION, pyclipper.PFT_NONZERO)

def filletTracks(tracks, board, args):
    clipperScale = 100.0
    net, layer = tracks[0].net, tracks[0].layer
    tracksByWidth = defaultdict(list)
    for t in tracks:
        tracksByWidth[t.width].append(t)
    minWidthAtPoint = {}
    combinedPolys = []
    for width, tracks in sorted(tracksByWidth.items(), reverse=True):
        polys = []
        for polyline in makePolyLines(tracks):
            polyline = [(int(p.x * clipperScale + .5), int(p.y * clipperScale + .5)) for p in polyline]
            polys += expandTrackToPolygons(polyline, int(width * clipperScale + .5))
        # subtract all the existing polys
        clipper = pyclipper.Pyclipper()
        clipper.AddPaths(polys, pyclipper.PT_SUBJECT)
        if combinedPolys:
            clipper.AddPaths(combinedPolys, pyclipper.PT_CLIP)
        intersection = clipper.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)
        # store the track width at all these points
        minWidthAtPoint.update(((p[0], p[1]), width) for poly in intersection for p in poly)
        # add to the final combined poly
        combinedPolys = unionPolygons(combinedPolys + intersection)
    maxCosTheta = math.cos(math.radians(args.minAngle))

    #maxCosTheta = math.cos(math.radians(15)) # todo
    minLength = int(args.minLength * 0.1 * clipperScale)
    maxCosThetaSq = maxCosTheta * maxCosTheta
    # check against double the min length because the subdivision algorithm
    # doesn't allow a track to be split below the minimum so we shouldn't
    # add curves on those tracks either
    min2LengthSq = minLength * minLength * 2 * 2 
    for p in combinedPolys:
        fillets = [0.0] * len(p)
        numFillets = 0
        p1 = (p[-2][0] - p[-1][0], p[-2][1] - p[-1][1])
        for i in range(len(p)):
            p0 = p1
            p1 = (p[i-1][0] - p[i][0], p[i-1][1] - p[i][1])
            side = p0[0] * p1[1] - p0[1] * p1[0]
            # is it an inside corner?
            if side >= 0:
                continue
            # long enough tracks?
            l0sq = p0[0] * p0[0] + p0[1] * p0[1]
            if l0sq < min2LengthSq:
                continue
            l1sq = p1[0] * p1[0] + p1[1] * p1[1]
            if l1sq < min2LengthSq:
                continue
            # big enough angle?
            l0dotl1 = p0[0] * p1[0] + p0[1] * p1[1]
            if l0dotl1 * l0dotl1 >= maxCosThetaSq * l0sq * l1sq:
                continue

            # extra check to see if this angle+length combo is valid for 
            # subdivision. if not, then don't fillet it either.
            # only need to check if length is less than 4 times the minimum
            # because 4 is the largest 2*cos+2 can reach
            if min(l0sq, l1sq) < min2LengthSq * 2 * 2:
                l0, l1 = math.sqrt(float(l0sq)), math.sqrt(float(l1sq))
                cosHalfTheta = math.sqrt(.5 + .5 * abs(l0dotl1 / (l0 * l1)))
                amountToShorten = min(l0, l1) / (2 * cosHalfTheta + 2)
                if amountToShorten < minLength:
                    continue

            # store the desired fillet size
            w = minWidthAtPoint[(p[i-1][0], p[i-1][1])]
            fillet = (.5 + w * .5) * clipperScale
            fillets[i] = min(math.sqrt(l0sq), math.sqrt(l1sq), fillet)
            numFillets += 1

        if numFillets == 0:
            continue

        # make sure fillets don't overlap
        if numFillets > 1:
            for i, f1 in enumerate(fillets):
                if f1 > 0.0:
                    f0 = fillets[i - 1]
                    if f0 > 0.0: 
                        l0 = Line(p[i-1], p[i-2])
                        if f0 + f1 > l0.length:
                            # halfway between the two fillet endpoints
                            fillets[i - 1] = (f0 + l0.length - f1) * .5
                            fillets[i] = l0.length - fillets[i - 1]

        # apply fillets
        for i, fillet in enumerate(fillets):
            if fillet <= 0.0:
                continue
            l0 = Line(p[i-1], p[i-2])
            l1 = Line(p[i-1], p[i])
            # choose smallest track width at this point for the arc
            w = minWidthAtPoint[(l0.start.x, l0.start.y)]
            # offset into polygon by arc width
            l0.end = add(l0.pointOnLine(fillet), l0.vecToEdge(-w * clipperScale))
            l1.end = add(l1.pointOnLine(fillet), l1.vecToEdge(w * clipperScale))
            # calculate arc radius from fillet length & intersection angle
            cos2t = .5 + .5 * dot(l0.dir, l1.dir) # half angle formula
            r = math.sqrt(fillet * fillet * (1 - cos2t) / cos2t)
            # account for the arc width
            r += w * clipperScale * .5 
            # add the arc
            r = floatToString(round(r / clipperScale, 5))
            w = floatToString(w)
            p0 = pointToStr(scale(l0.end, 1.0 / clipperScale))
            p1 = pointToStr(scale(l1.end, 1.0 / clipperScale))
            board.addShape(f"ARC~{w}~{layer}~{net}~M {p0} A {r} {r} 0 0 0 {p1}~~{board.getShapeId()}~0")
