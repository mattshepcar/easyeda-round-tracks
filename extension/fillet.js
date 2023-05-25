extensionId = api('createDialog',{title:'getId'})[0].id.split('-')[2]; // really bad hack to get the extension id ;)
extension = easyeda.extension.instances[extensionId];

const { Project, Path } = extension.paper;
const { Line, dot, dist, makePolyLines } = extension.line;
const { floatToString, pointToStr } = extension.board;
const { offsetStroke } = extension.PaperOffset;

function makeTrackPath(track, width) {
    return offsetStroke(new Path(track), width * .5, {join: 'round', cap: 'round'});
}

function FilletTracks(tracks, board, args, teardrops = null) {
    const useArcs = (teardrops == null);
    // combine all the tracks into a minimum set of polygons then 
    // add fillets to any suitable interior corners. 
    // TODO: include pads, arcs & solid regions?
    const [net, layer] = [tracks[0].net, tracks[0].layer];
    var tracksByWidth = {};
    for(const t of tracks) {
        if (t.length > 0.0) {
            if (t.width in tracksByWidth)
                tracksByWidth[t.width].push(t);
            else
                tracksByWidth[t.width] = [t];
        }
    }
    var minWidthAtPoint = {}
    new Project;
    var path = new Path;
    tracksByWidth = Object.entries(tracksByWidth);
    tracksByWidth.sort((a, b) => b[0] - a[0]);
    // start with widest tracks first to ensure that minWidthAtPoint ends up with the minimum widths
    for(const [,tracks] of tracksByWidth) {
        const width = tracks[0].width;
        var trackPath = new Path;
        for(var polyline of makePolyLines(tracks))
            trackPath = trackPath.unite(makeTrackPath(polyline, width), {stroke: true});
        // subtract the combined path
        const intersection = trackPath.subtract(path);
        // store the track width at all these points
        for(const childPath of (intersection.children || [intersection]))
            for(const seg of childPath.segments)
                minWidthAtPoint[seg.point] = width;
        // add to the final combined poly
        path = path.unite(intersection); //trackPath);
    }
    const maxCosTheta = Math.cos(Math.PI / 180 * (args.minAngle + 2));

    const minLength = args.minLength * 0.1;
    const maxCosThetaSq = maxCosTheta * maxCosTheta;
    // check against double the min length because the subdivision algorithm
    // doesn't allow a track to be split below the minimum so we shouldn't
    // add curves on those tracks either
    const min2LengthSq = minLength * minLength * 2 * 2;
    for(const childPath of (path.children || [path])) {
        var numFillets = 0;
        var fillets = [];
        for(const seg of childPath.segments) {
            fillets.push(0);
            // don't process curved segments
            if (seg.hasHandles()) 
                continue;
            const p0 = seg.previous.point.subtract(seg.point)
            const p1 = seg.point.subtract(seg.next.point);
            const side = p0.x * p1.y - p0.y * p1.x;
            // is it an inside corner?
            if (side >= 0)
                continue;
            // long enough tracks?
            const l0sq = p0.x * p0.x + p0.y * p0.y;
            if (l0sq < min2LengthSq)
                continue;
            const l1sq = p1.x * p1.x + p1.y * p1.y;
            if (l1sq < min2LengthSq)
                continue;
            // big enough angle?
            l0dotl1 = p0.x * p1.x + p0.y * p1.y;
            if (l0dotl1 * l0dotl1 >= maxCosThetaSq * l0sq * l1sq)
                continue;

            // extra check to see if this angle+length combo is valid for 
            // subdivision. if not, then don't fillet it either.
            // only need to check if length is less than 4 times the minimum
            // because 4 is the largest 2*cos+2 can reach
            if (Math.min(l0sq, l1sq) < min2LengthSq * 2 * 2) {
                const l0 = Math.sqrt(l0sq);
                const l1 = Math.sqrt(l1sq);
                const cosHalfTheta = Math.sqrt(.5 + .5 * Math.abs(l0dotl1 / (l0 * l1)));
                const amountToShorten = Math.min(l0, l1) / (2 * cosHalfTheta + 2);
                if (amountToShorten < minLength)
                    continue;
            }

            // store the desired fillet size
            const w = minWidthAtPoint[seg.point]
            const fillet = .5 + w * .5;
            fillets[fillets.length - 1] = Math.min(Math.sqrt(l0sq), Math.sqrt(l1sq), fillet);
            numFillets += 1;
        }

        if (numFillets == 0)
            continue;

        // make sure fillets don't overlap
        if (numFillets > 1) {
            for(var i = 0; i < fillets.length; ++i) {
                const f0 = fillets[i];
                if (f0 <= 0.0)
                    continue;
                const j = (i + 1) % fillets.length;
                const f1 = fillets[j];
                if (f1 <= 0.0)
                    continue;
                const len = dist(childPath.segments[i].point, childPath.segments[j].point);
                if (f0 + f1 > len) {
                    // halfway between the two fillet endpoints
                    fillets[i] = (f0 + (len - f1)) * .5;
                    fillets[j] = len - fillets[i];
                }
            }
        }

        // apply fillets
        for(const [i, fillet] of Object.entries(fillets)) {
            if (fillet <= 0.0)
                continue;
            const seg = childPath.segments[i];
            l0 = new Line(seg.point, seg.previous.point);
            l1 = new Line(seg.point, seg.next.point);
            // choose smallest track width at this point for the arc
            var w = useArcs ? minWidthAtPoint[seg.point] : 0;
            // offset into polygon by arc width
            l0.end = l0.pointOnLine(fillet).add(l0.vecToEdge(-w));
            l1.end = l1.pointOnLine(fillet).add(l1.vecToEdge(w));
            // calculate arc radius from fillet length & intersection angle
            const cos2t = .5 + .5 * dot(l0.dir, l1.dir); // half angle formula
            var r = fillet * Math.sqrt(1 / cos2t - 1);
            p0 = pointToStr(l0.end);
            p1 = pointToStr(l1.end);
            // account for the arc width
            if (useArcs) 
                r += w * .5;
            // add the arc
            r = floatToString(r);
            w = floatToString(w)
            var path = `M ${p0} A ${r} ${r} 0 0 0 ${p1}`;
            if (useArcs) {
                board.addShape(`ARC~${w}~${layer}~${net}~${path}~~${board.allocateShapeId()}~0`);
            }
            else {
                path += ` L ${pointToStr(l0.start)} Z`;
                if (teardrops != null)
                {
                    teardrops.push({
                        shapeType: "SOLIDREGION",
                        jsonCache: {
                            layerid: layer,
                            net: net,
                            type: "solid",
                            teardrop: 1,
                            //pointArr: pts,
                            pathStr: path
                        }
                    });
                }
                else
                {
                    pcb.addShape(`SOLIDREGION~${layer}~${net}~${path}~solid~${pcb.allocateShapeId()}~1~~~0`);
                }
            }
        }
    }
}

extension.fillet = {FilletTracks};