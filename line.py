import math
from collections import namedtuple
from copy import copy

Vector = namedtuple('Vector', 'x y')
def dot(p0, p1):
    return p0.x * p1.x + p0.y * p1.y
def length(p):
    return math.sqrt(dot(p,p))
def clamp(x, minx, maxx):
    return max(minx, min(x, maxx))
def add(p0, p1):
    return Vector(p0.x + p1.x, p0.y + p1.y)
def sub(p0, p1):
    return Vector(p0.x - p1.x, p0.y - p1.y)
def dist(p0, p1):
    return length(sub(p0, p1))    

class Line:
    def update(self):
        d = sub(self.end, self.start)
        self.length = length(d)
        if self.length < 0.0001:
            return False
        self.dir = Vector(d.x / self.length, d.y / self.length)
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

def intersect(t0, t1, bounded=True):
    t1perp = Vector(t1.end.y - t1.start.y, t1.start.x - t1.end.x)
    t0vec = sub(t0.end, t0.start)
    t0proj = dot(t0vec, t1perp)
    if abs(t0proj) < 1e-4:
        return None
    t0perp = Vector(t0.end.y - t0.start.y, t0.start.x - t0.end.x)
    t0t1 = sub(t1.start, t0.start)
    d1 = dot(t0t1, t1perp) / t0proj
    if bounded:
        d2 = dot(t0t1, t0perp) / t0proj
        if d1 < 0.0 or d1 > 1.0 or d2 < 0.0 or d2 > 1.0:
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
            print('Merging tracks %s and %s' % (t, t2))
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

def splitIntersectingLines(tracks): 
    i = 0
    while i < len(tracks):
        t = tracks[i]
        i += 1
        for t2 in tracks[i:]:
            ip = intersect(t, t2)
            if ip and (distFromEnd(t, ip) > t.width * .5 and
                       distFromEnd(t2, ip) > t2.width * .5):
                tracks.append(t.split(ip))
                tracks.append(t2.split(ip))
            else:
                newTrack = splitLineIfEndIntersects(t, t2) or splitLineIfEndIntersects(t2, t)
                if newTrack:
                    tracks.append(newTrack)
