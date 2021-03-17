import json
from line import Line, Vector, cleanupColinearTrackPair, splitIntersectingLines, getIslands, makePolyLines, dist, kdboxtree, kdboxinside
from copy import copy
from collections import defaultdict, namedtuple
import math

def floatToString(inputValue):
    return ('%f' % inputValue).rstrip('0').rstrip('.')
def pointToStr(pt):
    return f"{floatToString(round(pt.x + 4000, 5))} {floatToString(round(pt.y + 3000, 5))}"

Transform = namedtuple('Transform', 'pos angle')
Via = namedtuple('Via', 'pos diameter drill')

def Pos(x, y, tx):
    return Vector(float(x) - 4000, float(y) - 3000)

class Board:
    def load(self, filename):
        self.nextTrackId = 0
        self.board = json.load(open(filename, encoding='utf-8'))
        self.loadTracks()
        print("Cleaning up overlapping tracks")
        self.cleanupColinearTracks()
        print("Splitting intersecting tracks")
        self.splitIntersectingLines()
        print("Identifying connected track sections")
        self.assignIslands()

    def save(self, filename):
        self.saveTracks()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.board, f, indent=2, sort_keys=False, ensure_ascii=False)

    def cleanupColinearTracks(self):
        for tracks in self.tracksByNetAndLayer.values():
            #trackLookup = kdboxtree(list((t.bounds(), t) for t in tracks))
            for t in tracks:
                for t2 in tracks: #kdboxinside(trackLookup, t.bounds()):
                    if 1: #id(t) < id(t2): doens't work???
                        if cleanupColinearTrackPair(t, t2, tracks):
                            break

    def splitIntersectingLines(self):
        for tracks in self.tracksByNetAndLayer.values():
            splitIntersectingLines(tracks)

    def assignIslands(self):
        for tracks in self.tracksByNetAndLayer.values():
            getIslands(tracks)

    def getShapeId(self):
        self.highestShapeId += 1
        return 'gge%s' % self.highestShapeId

    def addShape(self, shape):
        self.board['shape'].append(shape)

    def loadTracks(self):
        self.highestShapeId = 0
        self.tracksByNetAndLayer = defaultdict(list)
        self.viasByNet = defaultdict(list)
        self.loadShapes(self.board['shape'])

    def loadShapes(self, shapes, tx=Transform(Vector(0, 0), 0)):
        for shapeIndex, shape in enumerate(shapes):
            shape = shape.split('~')
            if shape[0] == 'LIB':
                x, y, attributes, rotation, importFlag, shapeId, _, _, _, locked = shape[1:11]
                shapeList = '~'.join(shape).split('#@$')[1:]
                rotation = float(rotation or 0)
                self.loadShapes(shapeList, Transform(Pos(x, y, tx), rotation + tx.angle))
            elif shape[0] == 'TRACK':
                width, layer, net, coords, shapeId, locked = shape[1:]
                if layer not in ('1', '2'):
                    continue
                tracks = self.tracksByNetAndLayer[net+'~'+layer]
                coords = [float(c) for c in coords.split(' ')]
                width = float(width)
                start = Pos(coords[0], coords[1], tx)
                for i in range(2, len(coords), 2):
                    end = Pos(coords[i], coords[i + 1], tx)
                    t = Line(start, end)
                    t.shapeIndex = shapeIndex
                    t.id = shapeId
                    t.width = width
                    t.layer = layer
                    t.net = net
                    t.locked = locked
                    start = copy(end)
                    if t.update():
                        tracks.append(t)
            elif shape[0] == 'VIA':
                x, y, diameter, net, drill, shapeId, locked = shape[1:]
                pos = Pos(x, y, tx)
                self.viasByNet[net].append(Via(pos, float(diameter), float(drill)))
            elif shape[0] == 'PAD':
                (shapeType, x, y, w, h, layer, net, num, holeRadius, points, 
                 rotation, shapeId, holeLength, holePoints, plated, locked, 
                 pasteExpansion, solderMaskExpansion, _) = shape[1:]
                pos = Pos(x, y, tx)
                if float(holeRadius):
                    self.viasByNet[net].append(Via(pos, min(float(w), float(h)), float(holeRadius)))
            else:
                for field in shape:
                    if field.startswith('gge'):
                        shapeId = field
                        break
            if shapeId.startswith('gge') and shape[0] != 'LIB':
                numericId = int(shapeId[3:])
                if numericId > self.highestShapeId:
                    self.highestShapeId = numericId

    def saveTracks(self):
        tracksByShape = {}
        for tracks in self.tracksByNetAndLayer.values():
            for track in tracks:
                tracksByShape.setdefault(track.shapeIndex, []).append(track)
        for shapeIndex, tracks in tracksByShape.items():
            track = tracks[0]
            trackId = track.id
            for coords in makePolyLines(tracks):
                if shapeIndex is None:
                    trackId = self.getShapeId()
                shape = '~'.join((
                    'TRACK',
                    floatToString(track.width),
                    track.layer,
                    track.net,
                    ' '.join((pointToStr(c) for c in coords)),
                    trackId,
                    track.locked))
                if shapeIndex != None:
                    self.board['shape'][shapeIndex] = shape
                    shapeIndex = None
                else:
                    self.addShape(shape)
