// Matt's easyeda version of:

// Teardrop for pcbnew using filled zones
// (c) Niluje 2019 thewireddoesntexist.org
//
// Based on Teardrops for PCBNEW by svofski, 2014 http://sensi.org/~svo
// Cubic Bezier upgrade by mitxela, 2021 mitxela.com

const {normalize, dist, distsq, dot, kdtree, kdnear, kdtree2, kdnear2} = require('./line');
const {pointToStr} = require('./board');
const {Point} = require('paper');

function lookup(p) {
    return [(p.x * 10 + .5)|0, (p.y * 10 + .5)|0];
}

function __Bezier(p1, p2, p3, p4, n=20) {
    const h = 1.0 / (n - 1);
    var d0 = p2.subtract(p1).multiply(h * 3);
    var d1 = p1.subtract(p2.multiply(2)).add(p3).multiply(h * h * 6);
    var d2 = p2.subtract(p3).multiply(3).add(p4).subtract(p1).multiply(h * h * h);
    var pts = [p1];
    for(var i = 0; i < n - 1; ++i) {
        p1 = new Point(p1.x + d0.x + d1.x * .5 + d2.x,
                       p1.y + d0.y + d1.y * .5 + d2.y);
        d0 = new Point(d0.x + d1.x + d2.x * 3,
                       d0.y + d1.y + d2.y * 3);
        d1 = new Point(d1.x + d2.x * 6,
                       d1.y + d2.y * 6);
        pts.push(p1);
    }
    pts.push(p4);
    return pts;
}

function pointsToPath(pts) {
    return 'M ' + pts.map(pointToStr).join(' L ') + ' Z';
}

function __ComputeCurved(vpercent, w, trackDir, via, pts, segs) {
    // Compute the curves part points

    // A and B are points on the track
    // C and E are points on the via
    // D is midpoint behind the via centre

    const radius = via.diameter * .5;
    const minVpercent = (w * 2) / via.diameter;
    const weaken = (vpercent / 100.0 - minVpercent) / (1 - minVpercent) / radius;

    const biasBC = 0.5 * dist(pts[1], pts[2]);
    const biasAE = 0.5 * dist(pts[4], pts[0]);

    const vecC = pts[2].subtract(via.pos);
    const tangentC = new Point(pts[2].x - vecC.y * biasBC * weaken,
                               pts[2].y + vecC.x * biasBC * weaken);
    const vecE = pts[4].subtract(via.pos);
    const tangentE = new Point(pts[4].x + vecE.y * biasAE * weaken,
                               pts[4].y - vecE.x * biasAE * weaken);
    const tangentB = pts[1].subtract(trackDir.multiply(biasBC));
    const tangentA = pts[0].subtract(trackDir.multiply(biasAE));

    if (0) { // easyeda copper fill doesn't like cubic beziers
        const pts = pts.map(pointToStr);
        var path = `M ${pts[3]} `;
        path += `L ${pts[4]} C ${pointToStr(tangentE)} ${pointToStr(tangentA)} ${pts[0]} `;
        path += `L ${pts[1]} C ${pointToStr(tangentB)} ${pointToStr(tangentC)} ${pts[2]} `;
        path += 'Z';
        return path;
    } else {
        curve1 = __Bezier(pts[1], tangentB, tangentC, pts[2], n=segs);
        curve2 = __Bezier(pts[4], tangentE, tangentA, pts[0], n=segs);
        return pointsToPath(curve1.concat([pts[3]]).concat(curve2));
    }
}

function __FindTouchingTrack(t1, endpoint, trackLookup) {
    // Find a track connected to the end of another track
    endpoint = lookup(endpoint);
    if (!(endpoint in trackLookup))
        return null;
    const touchingTracks = trackLookup[endpoint][1];
    if (touchingTracks.length > 2 || touchingTracks.includes(t1))
        return null;
    for(const t of touchingTracks)
        if (t != t1)
            return t;
    return null;
}

function __ComputePoints(track, via, hpercent, vpercent, segs, trackLookup) {
    // Compute all teardrop points
    var start = track.start;
    var end = track.end;
    const radius = via.diameter * .5;
    const radiusSq = radius * radius;
    const w = track.width * .5;

    if (vpercent > 100)
        vpercent = 100;

    // ensure that start is at the via/pad end
    if (distsq(start, via.pos) > distsq(end, via.pos))
        [start, end] = [end, start];

    // choose a teardrop length
    const targetLength = via.diameter * hpercent / 100.0;
    var tearDropLength = 0.0;
    var posOnTrack = 0.0;
    var trackDir;
    for(;;) {
        const d = end.subtract(start);
        const a = dot(d, d);
        var trackLen = Math.sqrt(a);
        trackDir = d.multiply(1.0 / trackLen);
        if (distsq(end, via.pos) >= radiusSq) {
            // track end is outside via
            const f = start.subtract(via.pos);
            const c = dot(f, f) - radiusSq;
            if (tearDropLength == 0 && c < 0) {
                // start is inside via, find point on circumference
                const b = 2 * dot(f, d);
                const t = (Math.sqrt(b * b - 4 * a * c) - b) / (2 * a);
                start = start.add(d.multiply(t));
                // update length
                trackLen = dist(start, end);
                // direction to the track exit point
                tearDropDir = start.subtract(via.pos).normalize();
            }
            // find distance along track to place end of teardrop
            posOnTrack = Math.min(trackLen, targetLength - tearDropLength);
            tearDropLength += posOnTrack;
            if (tearDropLength >= targetLength)
                break;
        } else {
            posOnTrack = trackLen;
        }
        // if not long enough, attempt to walk back along the curved track
        const t = __FindTouchingTrack(track, end, trackLookup);
        if (t === null || t.width != track.width)
            break;
        track = t;
        // make sure we use the correct end of the track
        if (distsq(end, t.start) > distsq(end, t.end))
            [start, end] = [t.end, t.start];
        else
            [start, end] = [t.start, t.end];
    }

    // if shortened, shrink width too
    if (tearDropLength < targetLength) {
        const minVpercent = 100.0 * w / radius;
        vpercent = vpercent * tearDropLength / targetLength + minVpercent * (1 - tearDropLength / targetLength);
        vpercent = Math.min(100, vpercent);
    }

    // find point on the track, sharp end of the teardrop
    start = start.add(trackDir.multiply(posOnTrack));
    const pointA = new Point(start.x - trackDir.y * w, start.y + trackDir.x * w);
    const pointB = new Point(start.x + trackDir.y * w, start.y - trackDir.x * w);

    // via side points
    const s = radius * vpercent / 100.0;
    const c = Math.sqrt(radiusSq - s * s);
    const pointC = new Point(via.pos.x + tearDropDir.x * c + tearDropDir.y * s, 
                             via.pos.y - tearDropDir.x * s + tearDropDir.y * c);
    const pointE = new Point(via.pos.x + tearDropDir.x * c - tearDropDir.y * s, 
                             via.pos.y + tearDropDir.x * s + tearDropDir.y * c);

    // Introduce a last point in order to cover the via centre.
    const pointD = via.pos.subtract(tearDropDir.multiply(radius * 0.5));

    const pts = [pointA, pointB, pointC, pointD, pointE];
    if (segs > 2)
        return __ComputeCurved(vpercent, w, trackDir, via, pts, segs);
    else
        return pointsToPath(pts);
}

function SetTeardrops(pcb, tracks, vias, args) {
    // Set teardrops on a teardrop free board
    const hpercent = args.teardropLength;
    const vpercent = args.teardropWidth;
    const segs = args.teardropSegs;

    tracks = tracks.filter(t => t.length > 0);
    const trackLookup = {}
    for(const t of tracks) {
        for(var p of [t.start, t.end]) {
            p = lookup(p);
            if (p in trackLookup)
                trackLookup[p][1].push(t);
            else
                trackLookup[p] = [p, [t]];
        }
    }

    // todo: kd-tree slow/broken
    //var endpoints = Object.values(trackLookup).map(p => p[0]);
    //endpoints = kdtree2(endpoints);

    //tracks = tracks.map(t => [t.start, t]).concat(tracks.map(t => [t.end, t]));
    //tracks = kdtree(tracks);
    for(const via of vias) {
        const r = via.diameter * .5;
        const rsq = r * r;
        //for(const p of kdnear2(endpoints, lookup(via.pos), (r*10.0+.5)|0)) {
        //    const nearTracks = trackLookup[p][1];
        const nearTracks = tracks;
        {
            for(const t of nearTracks) {
                if (t.width < via.diameter * .95) {
                    // is the track entering/leaving the via?
                    if ((distsq(t.start, via.pos) < rsq) != (distsq(t.end, via.pos) < rsq)) {
                        const path = __ComputePoints(t, via, hpercent, vpercent, segs, trackLookup);
                        if (path != null)
                            pcb.addShape(`SOLIDREGION~${t.layer}~${t.net}~${path}~solid~${pcb.allocateShapeId()}~~~~0`);
                    }
                }
            }
        }
    }
}

module.exports = {SetTeardrops};
