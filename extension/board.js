extensionId = api('createDialog',{title:'getId'})[0].id.split('-')[2]; // really bad hack to get the extension id ;)
extension = easyeda.extension.instances[extensionId];

const { Point } = extension.paper;
const { Line, assignIslands, makePolyLines, cleanupColinearTrackPair, splitIntersectingLines } = extension.line;

function floatToString(inputValue) {
    return inputValue;
    //return ('%f' % inputValue).rstrip('0').rstrip('.')
}
function pointToStr(pt) {
    return floatToString(pt.x) + " " + floatToString(pt.y);
    //return "${floatToString(round(pt.x + 4000, 5))} ${floatToString(round(pt.y + 3000, 5))}";
}

class Via {
    constructor(pos, diameter, holeRadius, shapeId) {
        this.pos = pos;
        this.diameter = diameter;
        this.holeRadius = holeRadius;
        this.id = shapeId;
    }
}
class Board {
    constructor(json) {
        console.log("Loading board");
        this.nextTrackId = 0;
        this.board = JSON.parse(json);
        this.loadTracks();
        console.log("Cleaning up overlapping tracks");
        this.cleanupColinearTracks();
        console.log("Splitting intersecting tracks");
        this.splitIntersectingLines();
        console.log("Identifying connected track sections");
        this.assignIslands();
    }

    cleanupColinearTracks() {
        for(const tracks of Object.values(this.tracksByNetAndLayer)) {
            //var trackLookup = kdboxtree(list((t.bounds(), t) for t in tracks))
            for(const t of tracks) {
                for(const t2 of tracks) { // kdboxinside(trackLookup, t.bounds()):
                    if (1) //id(t) < id(t2): doens't work???
                        if (cleanupColinearTrackPair(t, t2, tracks))
                            break;
                }
            }
        }
    }

    splitIntersectingLines() {
        for(const tracks of Object.values(this.tracksByNetAndLayer)) {
            splitIntersectingLines(tracks);
        }
    }
    assignIslands() {
        for(const tracks of Object.values(this.tracksByNetAndLayer)) {
            assignIslands(tracks);
        }
    }

    allocateShapeId() {
        this.highestShapeId += 1;
        return `gge${this.highestShapeId}`;
    }

    addShape(shape) {
        this.board.shape.push(shape);
    }

    addSignalLayers(layers) {
        for(const layer of layers) {
            const fields = layer.split("~");
            // Add layer id only if it's a custom signal layer
            if (fields.pop() == "Signal") {
                this.signalLayers.push(fields[0])
            }
        }
    }

    loadTracks() {
        this.highestShapeId = 0;
        this.tracksByNetAndLayer = {};
        this.viasByNet = {};
        this.teardrops = [];
        this.teardropIndices = [];
        this.signalLayers = ["1", "2"]; // TopLayer & BottomLayer
        this.addSignalLayers(this.board.layers);
        this.loadShapes(this.board.shape);
    }

    loadShapes(shapes) {
        for(const [shapeIndex, shapeStr] of shapes.entries()) {
            const shape = shapeStr.split("~");
            var shapeId;
            if (shape[0] == "LIB") {
                const [, x, y, attributes, rotation, importFlag, _shapeId, , , , locked] = shape;
                shapeId = _shapeId;
                const shapeList = shape.join("~").split("#@$").slice(1);
                this.loadShapes(shapeList);
            } else if (shape[0] == "TRACK") {
                const [, widthStr, layer, net, coordsStr, _shapeId, locked] = shape;
                shapeId = _shapeId;
                if (this.signalLayers.includes(layer)) {
                    const key = net+'~'+layer;
                    if (!(key in this.tracksByNetAndLayer))
                        this.tracksByNetAndLayer[key] = [];
                    const tracks = this.tracksByNetAndLayer[key];
                    const coords = coordsStr.split(' ').map(Number);
                    const width = Number(widthStr);
                    var start = new Point(coords[0], coords[1]);
                    for(var i = 2; i < coords.length; i += 2) {
                        const end = new Point(coords[i], coords[i + 1]);
                        var t = new Line(start, end);
                        t.shapeIndex = shapeIndex;
                        t.id = shapeId;
                        t.width = width;
                        t.layer = layer;
                        t.net = net;
                        t.locked = locked;
                        start = end;
                        if (t.length > 0)
                            tracks.push(t);
                    }
                }
            } else if (shape[0] == 'VIA') {
                const [, x, y, diameter, net, drill, _shapeId, locked] = shape;
                shapeId = _shapeId;
                const pos = new Point(Number(x), Number(y));
                if (!(net in this.viasByNet))
                    this.viasByNet[net] = [];
                this.viasByNet[net].push(new Via(pos, Number(diameter), Number(drill), shapeId));
            } else if (shape[0] == 'PAD') {
                const [, shapeType, x, y, w, h, layer, net, num, holeRadius, points, 
                 rotation, _shapeId, holeLength, holePoints, plated, locked, 
                 pasteExpansion, solderMaskExpansion] = shape;
                shapeId = _shapeId;
                const pos = new Point(Number(x), Number(y));
                if (Number(holeRadius)) {
                    if (!(net in this.viasByNet))
                        this.viasByNet[net] = [];    
                    this.viasByNet[net].push(new Via(pos, Math.min(Number(w), Number(h)), Number(holeRadius), shapeId));
                }
            } else if (shape[0] == 'SOLIDREGION') {
                const [, layer, net, path, type, shapeId, teardrop, targetWire, targetPad] = shape;
                if (teardrop) {
                    this.teardrops.push(shapeId);
                    this.teardropIndices.push(shapeIndex);
                }
            } else {
                for(const field of shape) {
                    if (field.startsWith('gge')) {
                        shapeId = field;
                        break;
                    }
                }
            }
            if (shapeId && shapeId.startsWith('gge') && shape[0] != 'LIB') {
                const numericId = Number(shapeId.substr(3));
                if (numericId > this.highestShapeId)
                    this.highestShapeId = numericId;
            }
        }
    }

    removeTeardrops() {
        while(this.teardropIndices.length) {
            this.board.shape.splice(this.teardropIndices.pop(), 1);
        }
    }

    saveTracks() {
        var tracksByShape = {};
        for(const tracks of Object.values(this.tracksByNetAndLayer)) {
            for(const track of tracks) {
                if (!(track.shapeIndex in tracksByShape))
                    tracksByShape[track.shapeIndex] = [];
                tracksByShape[track.shapeIndex].push(track);
            }
        }
        for(var [shapeIndex, tracks] of Object.entries(tracksByShape)) {
            const track = tracks[0];
            var trackId = track.id;
            for(const coords of makePolyLines(tracks)) {
                if (shapeIndex === null)
                    trackId = this.allocateShapeId();
                const shape = [
                    'TRACK',
                    floatToString(track.width),
                    track.layer,
                    track.net,
                    coords.map(pointToStr).join(' '),
                    trackId,
                    track.locked].join('~');
                if (shapeIndex != null) {
                    this.board['shape'][shapeIndex] = shape;
                    shapeIndex = null;
                } else {
                    this.addShape(shape);
                }
            }
        }
    }
}

extension.board = {Board, pointToStr, floatToString};
