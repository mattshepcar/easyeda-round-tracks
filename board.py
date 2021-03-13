import json
from line import Line, Vector, cleanupColinearTrackPair, splitIntersectingLines
from copy import copy
from collections import defaultdict

def floatToString(inputValue):
    return ('%f' % inputValue).rstrip('0').rstrip('.')

class Board:
    def load(self, filename):
        self.nextTrackId = 0
        self.board = json.load(open(filename, encoding='utf-8'))
        self.loadTracks()
        self.cleanupColinearTracks()
        self.splitIntersectingLines()

    def save(self, filename):
        self.saveTracks()
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.board, f, indent=2, sort_keys=False,ensure_ascii=False)

    def cleanupColinearTracks(self):
        for _, tracks in self.tracksByNetAndLayer.items():
            for t in tracks:
                for t2 in tracks:
                    if cleanupColinearTrackPair(t, t2, tracks):
                        break

    def splitIntersectingLines(self):
        for _, tracks in self.tracksByNetAndLayer.items():
            splitIntersectingLines(tracks)

    def getShapeId(self):
        self.highestShapeId += 1
        return 'gge%s' % self.highestShapeId

    def addShape(self, shape):
        self.board['shape'].append(shape)

    def loadTracks(self):
        self.highestShapeId = 0
        self.tracksByNetAndLayer = defaultdict(list)
        for shapeIndex, shape in enumerate(self.board['shape']):
            shape = shape.split('~')
            if shape[0] == 'TRACK':
                width, layer, net, coords, trackId, locked = shape[1:]
                if layer not in ('1', '2'):
                    continue
                tracks = self.tracksByNetAndLayer[net+'~'+layer]
                coords = [float(c) for c in coords.split(' ')]
                width = float(width)
                start = Vector(coords[0], coords[1])
                for i in range(2, len(coords), 2):
                    t = Line()
                    t.shapeIndex = shapeIndex
                    t.id = trackId
                    t.width = width
                    t.layer = layer
                    t.net = net
                    t.start = start
                    t.end = Vector(coords[i], coords[i + 1])
                    t.locked = locked
                    start = copy(t.end)
                    if t.update():
                        tracks.append(t)
            elif shape[0] != 'LIB':
                for field in shape:
                    if field.startswith('gge'):
                        trackId = field
                        break
            if trackId.startswith('gge'):
                numericId = int(trackId[3:])
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
            while tracks:
                coords = [tracks[0].start]
                while tracks:
                    l = len(tracks)
                    for i, t in enumerate(tracks):
                        if t.start.x == coords[-1].x and t.start.y == coords[-1].y:
                            coords.append(t.end)
                            tracks.pop(i)
                            break
                        elif t.end.x == coords[-1].x and t.end.y == coords[-1].y:
                            coords.append(t.start)
                            tracks.pop(i)
                            break
                    if l == len(tracks):
                        for i, t in enumerate(tracks):
                            if t.start.x == coords[0].x and t.start.y == coords[0].y:
                                coords.insert(0, t.end)
                                tracks.pop(i)
                                break
                            elif t.end.x == coords[0].x and t.end.y == coords[0].y:
                                coords.insert(0, t.start)
                                tracks.pop(i)
                                break
                        if l == len(tracks):
                            break
                shape = '~'.join((
                    'TRACK',
                    floatToString(track.width),
                    track.layer,
                    track.net,
                    ' '.join(('%s %s' % (floatToString(round(c.x, 5)), floatToString(round(c.y, 5))) for c in coords)),
                    trackId,
                    track.locked))
                if shapeIndex != None:
                    self.board['shape'][shapeIndex] = shape
                else:
                    self.addShape(shape)
                if tracks:
                    shapeIndex = None
                    trackId = self.getShapeId()
