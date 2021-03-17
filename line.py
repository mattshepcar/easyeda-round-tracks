import math
from collections import namedtuple, defaultdict
from copy import copy

class Vector(namedtuple('Vector', 'x y')):
    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)
    def __mul__(self, other):
        return Vector(self.x * other, self.y * other)

def dot(p0, p1):
    return p0.x * p1.x + p0.y * p1.y
def cross(p0, p1):
    return p0.x * p1.y - p0.y * p1.x
def lengthsq(p):
    return dot(p,p)
def length(p):
    return math.sqrt(lengthsq(p))
def clamp(x, minx, maxx):
    return max(minx, min(x, maxx))
def add(p0, p1):
    return Vector(p0.x + p1.x, p0.y + p1.y)
def sub(p0, p1):
    return Vector(p0.x - p1.x, p0.y - p1.y)
def distsq(p0, p1):
    return lengthsq(sub(p0, p1))
def dist(p0, p1):
    return length(sub(p0, p1))
def scale(v, factor):
    return Vector(v.x * factor, v.y * factor)
def normalize(v):
    return scale(v, 1.0 / length(v))

class Line:
    def __init__(self, p0, p1):
        self.start = p0 if isinstance(p0, Vector) else Vector(*p0)
        self.end = p1 if isinstance(p1, Vector) else Vector(*p1)
        self.update()
    def update(self):
        d = sub(self.end, self.start)
        self.length = length(d)
        if self.length < 0.0001:
            return False
        self.dir = scale(d, 1.0 / self.length)
        return True
    def GetWidth(self):
        return self.width
    def angle(self):
        return math.atan2(self.dir.y, self.dir.x)
        #return math.copysign(1 - self.dir.x / (abs(self.dir.x) + abs(self.dir.y)), self.dir.y)
    def reverse(self):
        self.start, self.end = self.end, self.start
        self.dir = Vector(-self.dir.x, -self.dir.y)
    def vecToEdge(self, w):
        return Vector(-self.dir.y * w * .5, self.dir.x * w * .5)
    def testSide(self, p):
        return cross(self.dir, sub(p, self.start))
    def __repr__(self):
        return '%s %s [%s-%s]' % (self.net, self.layer, self.start, self.end)
    def pointOnLine(self, d):
        return Vector(self.start.x + self.dir.x * d, self.start.y + self.dir.y * d)
    def projectedLength(self, p, bounded=True):
        d = dot(self.dir, sub(p, self.start))
        return clamp(d, 0, self.length) if bounded else d
    def closestPoint(self, p, bounded=True):
        return self.pointOnLine(self.projectedLength(p, bounded))
    def distanceTo(self, p, bounded=True):
        return dist(p, self.closestPoint(p, bounded))
    def split(self, p):
        newTrack = copy(self)
        newTrack.start = p
        newTrack.update()
        self.end = p
        self.update()
        return newTrack
    def bounds(self, expand=0):
        w = self.width * .5 + expand
        return (Vector(min(self.start.x, self.end.x) - w, min(self.start.y, self.end.y - w)),
                Vector(max(self.start.x, self.end.x) + w, max(self.start.y, self.end.y) + w))

def intersect(t0, t1, bound0=True, bound1=True):
    t1perp = Vector(t1.end.y - t1.start.y, t1.start.x - t1.end.x)
    t0vec = sub(t0.end, t0.start)
    t0proj = dot(t0vec, t1perp)
    if abs(t0proj) < 1e-4:
        return None
    t0perp = Vector(t0.end.y - t0.start.y, t0.start.x - t0.end.x)
    t0t1 = sub(t1.start, t0.start)
    d1 = dot(t0t1, t1perp) / t0proj
    if bound0 and (d1 < -1e-4 or d1 > 1.0 + 1e-4):
        return None
    if bound1:
        d2 = dot(t0t1, t0perp) / t0proj
        if d2 < -1e-4 or d2 > 1.0 + 1e-4:
            return None
    return Vector(t0.start.x + d1 * t0vec.x, t0.start.y + d1 * t0vec.y)

def isParallel(t, t2):
    return abs(dot(t.dir, t2.dir)) > 0.9999

def isColinear(t, t2):
    ds = sub(t2.start, t.start)
    de = sub(t2.end, t.start)
    return abs(ds.x * de.y - ds.y * de.x) < 0.0001

def cleanupColinearTrackPair(t, t2, tracks):
    if t == t2:
        return False
    if not isParallel(t, t2):
        return False
    # same width and same direction?
    if t.width == t2.width and isColinear(t, t2):
        s = t.projectedLength(t2.start, bounded=False)
        e = t.projectedLength(t2.end, bounded=False)
        if s > e:
            s, e = e, s
        # overlapping?
        if e > 0.0001 and s < t.length - 0.0001:
            #print('Merging tracks %s and %s' % (t, t2))
            s = min(0, s)
            e = max(t.length, e)
            t2.start = t.pointOnLine(s)
            t2.end  = t.pointOnLine(e)
            t2.update()
            tracks.remove(t)
            return True
    elif t.width < t2.width:
        if t2.distanceTo(t.start, bounded=False) < t2.width - t.width + 0.0001:
            s = t2.projectedLength(t.start, bounded=False)
            e = t2.projectedLength(t.end, bounded=False)
            if e < s:
                s, e = e, s
                t.reverse()
            overlap = (t2.width - t.width) * .5
            if s < -overlap:
                # we have a line segment before
                if e > t2.length + overlap:
                    # split the line
                    endseg = copy(t)
                    endseg.start = t.closestPoint(t2.pointOnLine(t2.length + overlap))
                    endseg.end = copy(t.end)
                    endseg.update()
                    tracks.append(endseg)
                if e > 0.0:
                    # clip the line to the start of the other line
                    t.end = t.closestPoint(t2.pointOnLine(-overlap))
                    t.update()
            elif e > t2.length + overlap:
                if s < t2.length + overlap:
                    # clip the line to the end of the other line
                    t.start = t.closestPoint(t2.pointOnLine(t2.length + overlap))
                    t.update()
            else:
                # remove the line segment altogether
                tracks.remove(t)
                return True
    return False

def distFromEnd(t, p):
    return min(dist(t.start, p), dist(t.end, p))

def splitLineIfEndIntersects(t, t2):
    # check if ends of t are intersecting t2
    w = (t.width + t2.width) * .5
    for ip in (t.start, t.end):
        if t2.distanceTo(ip) < w and distFromEnd(t2, ip) > w:
            return t2.split(t2.closestPoint(ip))
    return None

def applySplits(tracks, splits):
    # split each track at desired split points
    for t, dists in splits.items():
        dists.sort(reverse=True)
        for d in dists:
            if d > 0.0 and d < t.length:
                tracks.append(t.split(t.pointOnLine(d)))

def splitIntersectingLines(tracks):
    trackLookup = kdboxtree(list((t.bounds(), t) for t in tracks))
    needUpdate = False
    for t2 in tracks:
        for t in kdboxinside(trackLookup, t2.bounds()):
            if t == t2:
                continue
            if t.width != t2.width:
                continue
            if (t.start == t2.start or t.start == t2.end or
                t.end == t2.start or t.end == t2.end):
                continue
            #if distFromEnd(t, t2.start) == 0 or distFromEnd(t, t2.end) == 0:
            #    continue
            ip = intersect(t, t2, bound0=False)
            if not ip:
                continue
            d2 = t2.projectedLength(ip, bounded=False)
            if d2 > 0 and d2 < t2.length:
                d = t.projectedLength(ip, bounded=False)
                if d > -t2.width * .5 and d < 0:
                    needUpdate = True
                    t.start = ip
                    t.update()
                elif d > t.length and d < t.length + t2.width * .5:
                    needUpdate = True
                    t.end = ip
                    t.update()
    if needUpdate:
        trackLookup = kdboxtree(list((t.bounds(), t) for t in tracks))
    mindist = 0.1

    splits = defaultdict(list)
    for t in tracks:
        for t2 in kdboxinside(trackLookup, t2.bounds()):
            if id(t) <= id(t2):
                continue
            if t.width != t2.width:
                continue
            ip = intersect(t, t2)
            if ip:
                for s in (t, t2):
                    if dist(s.start, ip) < mindist:
                        s.start = ip
                        s.update()
                    elif dist(s.end, ip) < mindist:
                        s.end = ip
                        s.update()
                    else:
                        splits[s].append(s.projectedLength(ip))
    applySplits(tracks, splits)

class Island:
    def __init__(self):
        self.id = id(self)
        self.tracks = []
    def add(self, other, islands):
        for t in other.tracks:
            islands[t.start] = self
            islands[t.end] = self
            t.island = self
        self.tracks += other.tracks

def getIslands(tracks):
    islandsByWidth = {}
    for t in tracks:
        islands = islandsByWidth.setdefault(t.width, {})
        startisland = islands.get(t.start)
        endisland = islands.get(t.end)
        if startisland and endisland:
            # join two existing islands
            if len(startisland.tracks) < len(endisland.tracks):
                endisland.add(startisland, islands)
                t.island = endisland
            else:
                startisland.add(endisland, islands)
                t.island = startisland
        else:
            t.island = startisland or endisland or Island()
        islands[t.start] = islands[t.end] = t.island
        t.island.tracks.append(t)
    islands = set()
    for islandsByPosition in islandsByWidth.values():
        islands.update(islandsByPosition.values())
    return islands

def makePolyLines(lines):
    polylines = []
    while lines:
        coords = [lines[0].start]
        while lines:
            l = len(lines)
            for i, t in enumerate(lines):
                if t.start.x == coords[-1].x and t.start.y == coords[-1].y:
                    coords.append(t.end)
                    lines.pop(i)
                    break
                elif t.end.x == coords[-1].x and t.end.y == coords[-1].y:
                    coords.append(t.start)
                    lines.pop(i)
                    break
            if l == len(lines):
                for i, t in enumerate(lines):
                    if t.start.x == coords[0].x and t.start.y == coords[0].y:
                        coords.insert(0, t.end)
                        lines.pop(i)
                        break
                    elif t.end.x == coords[0].x and t.end.y == coords[0].y:
                        coords.insert(0, t.start)
                        lines.pop(i)
                        break
                if l == len(lines):
                    break
        polylines.append(coords)
    return polylines

KdNode = namedtuple("KdNode", "pos left right")
def kdtree(points, depth = 0):
    if len(points) < 4:
        return points
    points.sort(key=lambda p: p[0][depth & 1])
    median = len(points) // 2
    return KdNode(
        pos=points[median][0][depth & 1],
        left=kdtree(points[:median], depth + 1),
        right=kdtree(points[median:], depth + 1))
def kdnear(tree, pos, maxDistance, depth = 0):
    if isinstance(tree, KdNode):
        points = []
        if pos[depth & 1] <= tree.pos + maxDistance:
            points += kdnear(tree.left, pos, maxDistance, depth + 1)
        if pos[depth & 1] >= tree.pos - maxDistance:
            points += kdnear(tree.right, pos, maxDistance, depth + 1)
        return points
    return [p for p in tree if distsq(p[0], pos) < maxDistance * maxDistance]
def kdinside(tree, bounds, depth = 0):
    minpos, maxpos = bounds
    points = []
    pending = [(tree, 0)]
    while pending:
        tree, depth = pending.pop()
        while isinstance(tree, KdNode):
            if minpos[depth & 1] <= tree.pos:
                if maxpos[depth & 1] >= tree.pos:
                    pending.append((tree.right, depth + 1))
                tree = tree.left
            else:
                tree = tree.right
            depth += 1
        points += [p for p in tree 
             if p[0][0] >= minpos[0] and p[0][0] <= maxpos[0] and 
                p[0][1] >= minpos[1] and p[0][1] <= maxpos[1]]
    return points

KdBoxNode = namedtuple("KdBoxNode", "maxleft minright left right")
def kdboxtree(boxes, depth = 0):
    if len(boxes) < 4:
        return boxes
    boxes.sort(key=lambda p: p[0][0][depth & 1] + p[0][1][depth & 1])
    median = len(boxes) // 2
    return KdBoxNode(
        maxleft=max(p[0][1][depth & 1] for p in boxes[:median]),
        minright=min(p[0][0][depth & 1] for p in boxes[median:]),
        left=kdboxtree(boxes[:median], depth + 1),
        right=kdboxtree(boxes[median:], depth + 1))
def kdboxinside(tree, bounds, depth = 0):
    minpos, maxpos = bounds
    if isinstance(tree, KdBoxNode):
        objs = []
        if tree.maxleft > minpos[depth & 1]:
            objs += kdboxinside(tree.left, bounds, depth + 1)
        if tree.minright < maxpos[depth & 1]:
            objs += kdboxinside(tree.right, bounds, depth + 1)
        return objs
    return [obj for (objmin, objmax), obj in tree 
                if objmin[0] <= maxpos[0] and objmax[0] >= minpos[0] and 
                   objmin[1] <= maxpos[1] and objmax[1] >= minpos[1]]


def kdnearest(tree, pos, maxDistance):
    points = kdnear(tree, pos, maxDistance)
    return points[0] if points else None
