extensionId = api('createDialog',{title:'getId'})[0].id.split('-')[2]; // really bad hack to get the extension id ;)
extension = easyeda.extension.instances[extensionId];
const {Point} = extension.paper;

function dot(p0, p1) {
    try {
        return p0.x * p1.x + p0.y * p1.y;
    }
    catch {
        return 0;
    }
}
function cross(p0, p1) {
     return p0.x * p1.y - p0.y * p1.x;
}
function lengthsq(p) {
     return dot(p,p);
}
function clamp(x, minx, maxx) {
    return x < minx ? minx : x > maxx ? maxx : x;
}
function length(p) {
     return Math.sqrt(lengthsq(p));
}
function distsq(p0, p1) {
     return lengthsq(p0.subtract(p1));
}
function dist(p0, p1) {
    return length(p0.subtract(p1));
}
function normalize(v) {
     return v / length(v);
}

class Line {
    constructor(p0, p1) {
        this.start = p0 instanceof Point ? p0 : new Point(p0[0], p0[1]);
        this.end = p1 instanceof Point ? p1 : new Point(p1[0], p1[1]);
        this.update();
    }
    update() {
        const d = this.end.subtract(this.start);
        this.length = d.length;
        if (this.length < 0.0001)
            return false;
        this.dir = d.multiply(1.0 / this.length);
        return true;
    }
    angle() {
        return this.dir.angleInRadians;
        //return math.copysign(1 - this.dir.x / (abs(this.dir.x) + abs(this.dir.y)), this.dir.y)
    }
    reverse() {
        [this.start, this.end] = [this.end, this.start];
        this.dir = this.dir.negate();
    }
    vecToEdge(w) {
        return new Point(-this.dir.y * w * .5, this.dir.x * w * .5);
    }
    testSide(p) {
        return cross(this.dir, p.subtract(this.start));
    }
    //__repr__():
    //    return '%s %s [%s-%s]' % (this.net, this.layer, this.start, this.end)
    pointOnLine(d) {
        return this.start.add(this.dir.multiply(d));
    }
    projectedLength(p, bounded=true) {
        const d = dot(this.dir, p.subtract(this.start));
        return bounded ? clamp(d, 0, this.length) : d;
    }
    closestPoint(p, bounded=true) {
        return this.pointOnLine(this.projectedLength(p, bounded));
    }
    distanceTo(p, bounded=true) {
        try {
            return dist(p, this.closestPoint(p, bounded));
        }
        catch {
            return Infinity;
        }
    }
    split(p) {
        var newTrack = this.clone();
        newTrack.start = p;
        newTrack.update();
        this.end = p;
        this.update();
        return newTrack;
    }
    bounds(expand=0) {
        const w = this.width * .5 + expand;
        return [new Point(Math.min(this.start.x, this.end.x) - w, Math.min(this.start.y, this.end.y) - w),
                new Point(Math.max(this.start.x, this.end.x) + w, Math.max(this.start.y, this.end.y) + w)];
    }
    clone() {
        return Object.assign(Object.create(Object.getPrototypeOf(this)), this);
    }
}

function intersect(t0, t1, bound0=true, bound1=true) {
    const t1perp = new Point(t1.end.y - t1.start.y, t1.start.x - t1.end.x);
    const t0vec = t0.end.subtract(t0.start);
    const t0proj = dot(t0vec, t1perp);
    if (Math.abs(t0proj) < 1e-4)
        return null;
    const t0perp = new Point(t0.end.y - t0.start.y, t0.start.x - t0.end.x);
    const t0t1 = t1.start.subtract(t0.start);
    const d1 = dot(t0t1, t1perp) / t0proj;
    if (bound0 && (d1 < -1e-4 || d1 > 1.0 + 1e-4))
        return null
    if (bound1) {
        const d2 = dot(t0t1, t0perp) / t0proj;
        if (d2 < -1e-4 || d2 > 1.0 + 1e-4)
            return null;
    }
    return t0.start.add(t0vec.multiply(d1));
}

function isParallel(t, t2) {
    return Math.abs(dot(t.dir, t2.dir)) > 0.9999;
}

function isColinear(t, t2) {
    const ds = t2.start.subtract(t.start);
    const de = t2.end.subtract(t.start);
    return Math.abs(ds.x * de.y - ds.y * de.x) < 0.0001;
}

function cleanupColinearTrackPair(t, t2, tracks) {
    if (t == t2)
        return false;
    if (!isParallel(t, t2))
        return false;
    // same width and same direction?
    if (t.width == t2.width) {
        if (!isColinear(t, t2))
            return false;
        var s = t.projectedLength(t2.start, bounded=false);
        var e = t.projectedLength(t2.end, bounded=false);
        if (s > e)
            [s, e] = [e, s];
        // overlapping?
        if (e > 0.0001 && s < t.length - 0.0001) {
            //console.log('Merging tracks ${t} and ${t2}');
            s = Math.min(0, s);
            e = Math.max(t.length, e);
            t2.start = t.pointOnLine(s);
            t2.end  = t.pointOnLine(e);
            t2.update();
            tracks.splice(tracks.indexOf(t), 1);
            return true;
        }
    } else {
        if (t2.width < t.width)
            [t, t2] = [t2, t];
        if (t2.distanceTo(t.start, bounded=false) >= t2.width - t.width + 0.0001)
            return false;
        var s = t2.projectedLength(t.start, bounded=false);
        var e = t2.projectedLength(t.end, bounded=false);
        if (e < s) {
            [s, e] = [e, s];
            t.reverse();
        }
        const overlap = (t2.width - t.width) * .5;
        if (s < -overlap) {
            // we have a line segment before
            if (e > t2.length + overlap) {
                // split the line
                endseg = copy(t);
                endseg.start = t.closestPoint(t2.pointOnLine(t2.length + overlap));
                endseg.end = copy(t.end);
                endseg.update();
                tracks.push(endseg);
            }
            if (e > 0.0) {
                // clip the line to the start of the other line
                t.end = t.closestPoint(t2.pointOnLine(-overlap));
                t.update();
            }
        } else if (e > t2.length + overlap) {
            if (s < t2.length + overlap) {
                // clip the line to the end of the other line
                t.start = t.closestPoint(t2.pointOnLine(t2.length + overlap));
                t.update();
            }
        } else {
            // remove the line segment altogether
            tracks.splice(tracks.indexOf(t), 1);
            return true;
        }
    }
    return false;
}

function distFromEnd(t, p) {
    return Math.min(dist(t.start, p), dist(t.end, p));
}

function splitLineIfEndIntersects(t, t2) {
    // check if ends of t are intersecting t2
    const w = (t.width + t2.width) * .5;
    for(const ip of [t.start, t.end]) 
        if (t2.distanceTo(ip) < w && distFromEnd(t2, ip) > w)
            return t2.split(t2.closestPoint(ip));
    return null;
}

function applySplits(tracks, splits) {
    // split each track at desired split points
    for(const [t, dists] of Object.values(splits)) {
        dists.sort().reverse();
        for(const d of dists) 
            if (d > 0.0 && d < t.length)
                tracks.push(t.split(t.pointOnLine(d)));
    }
}

function splitIntersectingLines(tracks) {
    //var trackLookup = kdboxtree(tracks.map(t=>[t.bounds(), t]));
    var needUpdate = false;
    for(const t2 of tracks) {
        for(const t of tracks) { //kdboxinside(trackLookup, t2.bounds())) {
            if (t == t2)
                continue;
            if (t.width != t2.width)
                continue;
            if (t.start == t2.start || t.start == t2.end ||
                t.end == t2.start || t.end == t2.end) 
                continue;
            const ip = intersect(t, t2, bound0=false);
            if (!ip)
                continue;
            const d2 = t2.projectedLength(ip, bounded=false);
            if (d2 > 0 && d2 < t2.length) {
                const d = t.projectedLength(ip, bounded=false);
                if (d > -t2.width * .5 && d < 0) {
                    needUpdate = true;
                    t.start = ip;
                    t.update();
                } else if (d > t.length && d < t.length + t2.width * .5) {
                    needUpdate = true;
                    t.end = ip;
                    t.update();
                }
            }
        }
    }
    //if (needUpdate)
    //    trackLookup = kdboxtree(tracks.map(t=>[t.bounds(), t]));
    mindist = 0.1

    splits = new Map();
    for(const t of tracks) {
        for(const t2 of tracks) { //kdboxinside(trackLookup, t2.bounds())) {
            if (t == t2)
                continue;
            //if (id(t) <= id(t2))
            //    continue;
            if (t.width != t2.width)
                continue;
            const ip = intersect(t, t2);
            if (ip) {
                for(const s of [t, t2]) {
                    if (dist(s.start, ip) < mindist) {
                        s.start = ip;
                        s.update();
                    } else if (dist(s.end, ip) < mindist) {
                        s.end = ip;
                        s.update();
                    } else {
                        k = s.start+'-'+s.end
                        if (k in splits)
                            splits[k][1].push(s.projectedLength(ip));
                        else
                            splits[k] = [s, [s.projectedLength(ip)]];
                    }
                }
            }
        }
    }
    applySplits(tracks, splits);
}

class Island {
    constructor() {
        this.tracks = [];
    }
    add(other, islands) {
        for(const t of other.tracks) {
            islands[t.start] = this;
            islands[t.end] = this;
            t.island = this;
        }
        this.tracks = this.tracks.concat(other.tracks);
    }
}

function assignIslands(tracks) {
    var islandsByWidth = new Map();
    for(const t of tracks) {
        if (!(t.width in islandsByWidth))
            islandsByWidth[t.width] = new Map();
        islands = islandsByWidth[t.width]
        const startisland = islands[t.start]
        const endisland = islands[t.end]
        if (startisland && endisland) {
            // join two existing islands
            if (startisland.tracks.length < endisland.tracks.length) {
                endisland.add(startisland, islands);
                t.island = endisland;
            } else {
                startisland.add(endisland, islands);
                t.island = startisland;
            }
        } else {
            t.island = startisland || endisland || new Island();
        }
        islands[t.start] = islands[t.end] = t.island;
        t.island.tracks.push(t);
    }
}

function makePolyLines(lines) {
    var polylines = []
    while (lines.length) {
        var coords = [lines[0].start]
        while (lines.length) {
            const l = lines.length;
            for(const [i, t] of lines.entries()) {
                if (t.start.x == coords[coords.length-1].x && t.start.y == coords[coords.length-1].y) {
                    coords.push(t.end);
                    lines.splice(i, 1);
                    break;
                } else if (t.end.x == coords[coords.length-1].x && t.end.y == coords[coords.length-1].y) {
                    coords.push(t.start);
                    lines.splice(i, 1);
                    break;
                }
            }
            if (l == lines.length) {
                for(const [i, t] of lines.entries()) {
                    if (t.start.x == coords[0].x && t.start.y == coords[0].y) {
                        coords.unshift(t.end);
                        lines.splice(i, 1);
                        break;
                    } else if (t.end.x == coords[0].x && t.end.y == coords[0].y) {
                        coords.unshift(t.start);
                        lines.splice(i, 1);
                        break;
                    }
                }
                if (l == lines.length)
                    break;
            }
        }
        polylines.push(coords);
    }
    return polylines;
}

class KdNode {
    constructor(pos, left, right) {
        this.pos = pos;
        this.left = left;
        this.right = right;
    }
}
function kdtree(points, depth = 0) {
    if (points.length <= 16)
        return points;
    if (depth & 1)
        points.sort((a, b) => a[0].y < b[0].y);
    else
        points.sort((a, b) => a[0].x < b[0].x);
    median = Math.floor(points.length / 2); // | 0;
    return new KdNode(
        depth & 1 ? points[median][0].y : points[median][0].x,
        //pointsByAxis[median][0],
        kdtree(points.slice(0, median), depth + 1),
        kdtree(points.slice(median), depth + 1));
}   

function kdtree2(points, axis = 0) {
    if (points.length <= 8)
        return points;
    points.sort((a, b) => a[axis] < b[axis]);
    median = (points.length / 2) | 0;
    return new KdNode(
        points[median][axis],
        kdtree2(points.slice(0, median), 1 - axis),
        kdtree2(points.slice(median), 1 - axis));
}   

function kdnear2(tree, pos, maxDistance, axis = 0) {
    if (tree instanceof KdNode) {
        var points = [];
        const coord = pos[axis];
        if (coord <= tree.pos + maxDistance)
            points = points.concat(kdnear2(tree.left, pos, maxDistance, 1 - axis));
        if (coord >= tree.pos - maxDistance)
            points = points.concat(kdnear2(tree.right, pos, maxDistance, 1 - axis));
        return points;
    }
    return tree.filter(p => (p[0]-pos[0])*(p[0]-pos[0])+(p[1]-pos[1])*(p[1]-pos[1]) < maxDistance * maxDistance);
}
function kdnear(tree, pos, maxDistance, depth = 0) {
    if (tree instanceof KdNode) {
        var points = [];
        const coord = depth & 1 ? pos.y : pos.x;
        if (coord <= tree.pos + maxDistance)
            points = points.concat(kdnear(tree.left, pos, maxDistance, depth + 1));
        if (coord >= tree.pos - maxDistance)
            points = points.concat(kdnear(tree.right, pos, maxDistance, depth + 1));
        return points;
    }
    return tree.filter(p => distsq(p[0], pos) < maxDistance * maxDistance);
}
function kdinside(tree, bounds, depth = 0) {
    const [minpos, maxpos] = bounds;
    var points = [];
    var pending = [[tree, 0]];
    while (pending.length > 0) {
        var [tree, depth] = pending.pop();
        while (tree instanceof KdNode) {
            const mincoord = depth & 1 ? minpos.y : minpos.x;
            if (mincoord <= tree.pos) {
                const maxcoord = depth & 1 ? maxpos.y : maxpos.x;
                if (maxcoord >= tree.pos)
                    pending.push([tree.right, depth + 1]);
                tree = tree.left;
            } else {
                tree = tree.right;
            }
            depth += 1;
        }
        points = points.concat(tree.filter(p => 
            p[0].x >= minpos.x && p[0].x <= maxpos.x && 
            p[0].y >= minpos.y && p[0].y <= maxpos.y));
    }
    return points;
}

class KdBoxNode {
    constructor(maxleft, minright, left, right) {
        this.maxleft = maxleft;
        this.minright = minright;
        this.left = left;
        this.right = right;
    }
}
function kdboxtree(boxes, depth = 0) {
    if (boxes.length <= 4)
        return boxes;
    if (depth & 1) 
        boxes.sort((a, b) => a[0][0].y + a[0][1].y < b[0][0].y + b[0][1].y);
    else
        boxes.sort((a, b) => a[0][0].y + a[0][1].x < b[0][0].y + b[0][1].x);
    const median = boxes.length / 2 | 0;
    const leftboxes = boxes.slice(0, median);
    const rightboxes = boxes.slice(median);
    var maxleft, minright;
    if (depth & 1) {
        maxleft = Math.max(...leftboxes.map(p => p[0][1].y));
        minright = Math.min(...rightboxes.map(p => p[0][0].y));
    } else {
        maxleft = Math.max(...leftboxes.map(p => p[0][1].x));
        minright = Math.min(...rightboxes.map(p => p[0][0].x));
    }
    return new KdBoxNode(maxleft, minright,
        kdboxtree(leftboxes, depth + 1),
        kdboxtree(rightboxes, depth + 1));
}
        
function kdboxinside(tree, bounds, depth = 0) {
    const [minpos, maxpos] = bounds;
    if (tree instanceof KdBoxNode) {
        var objs = [];
        const mincoord = depth & 1 ? minpos.y : minpos.x;
        if (tree.maxleft > mincoord)
            objs = objs.concat(kdboxinside(tree.left, bounds, depth + 1));
        const maxcoord = depth & 1 ? maxpos.y : maxpos.x;
        if (tree.minright < maxcoord)
            objs = objs.concat(kdboxinside(tree.right, bounds, depth + 1));
        return objs;
    }
    return tree.filter(([objmin, objmax], obj) => 
                objmin.x <= maxpos.x && objmax.x >= minpos.x && 
                objmin.y <= maxpos.y && objmax.y >= minpos.y)
                .map(([, obj]) => obj);
}

extension.line = {dot, Line, dist, distsq, assignIslands, makePolyLines, splitIntersectingLines, cleanupColinearTrackPair, kdtree, kdnear, kdtree2, kdnear2, kdinside, kdboxtree, kdboxinside};
