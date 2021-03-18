const yargs = require("yargs");
const fs = require('fs');
const { Board } = require('./board');
const { SetTeardrops } = require('./teardrops');
const { FilletTracks } = require('./fillet');
const { RoundTracks } = require('./roundtracks');
const path = require('path');

const args = yargs
    .usage("Usage: <infile> [outfile]")
    .demandCommand(1, 2)
    .option('radius', { describe: "Radius to round 90 degree corners to (in mils)", type: "number", default: 5.0})
    .option('radiusWidthMultiplier', { describe: "Corner radius is expanded by the width of the track multiplied by this value", type: "number", default: 0.5})
    .option('maxRadius', { describe: "Maximum corner radius (in mils)", type: "number", default: 100.0})
    .option('minAngle', { describe: "Stop rounding when angle between two tracks is smaller than this", type: "number", default: 5.0})
    .option('minLength', { describe: "Stop rounding when track segments are shorter than this (mils)", type: "number", default: 2.5})
    .option('passes', { describe: "Number of passes to make over each track during smoothing", type: "number", default: 3})
    .option('teardropLength', { describe: "Length of teardrops as a percentage of pad diameter", type: "number", default: 50})
    .option('teardropWidth', { describe: "Width of teardrops as a percentage", type: "number", default: 90})
    .option('teardropSegs', { describe: "Number of curve segments to create for teardrops", type: "number", default: 10})
    .option('smoothnway', { describe: "Apply rounding on n-way junctions (fillets will normally work better)", type: "boolean"})
    .option('nosubdivide', { describe: "Don't run track smoothing subdivision algorithm", type: "boolean"})
    .option('nofillet', { describe: "Don't add fillets on any corners that couldn't be rounded", type: "boolean"})
    .option('noteardrops', { describe: "Don't add teardrops", type: "boolean"})
    .argv;

const infile = args._[0];
console.log(`Loading board "${infile}"`);
fs.readFile(infile, 'utf8', function (err, json) {
    if (err) {
      return console.log(err);
    }
    board = new Board(json);
    if (!args.nosubdivide) {
        console.log("Subdividing tracks");
        for(const tracks of Object.values(board.tracksByNetAndLayer)) {
            const net = tracks[0].net;
            const vias = board.viasByNet[net] || [];
            RoundTracks(tracks, vias, board, args);
        }
    }
    if (!args.nofillet) {
        console.log("Applying fillets");
        for(const tracks of Object.values(board.tracksByNetAndLayer)) {
            FilletTracks(tracks, board, args);
        }
    }
    if (!args.noteardrops) {
        console.log("Applying teardrops");
        for(const tracks of Object.values(board.tracksByNetAndLayer)) {
            const net = tracks[0].net;
            const vias = board.viasByNet[net] || [];
            SetTeardrops(board, tracks, vias, args);
        }
    }
    var outname = args._[1];
    if (!outname) {
        const en = path.extname(infile);
        const basename = path.basename(infile, en);
        outname = path.join(path.dirname(infile), basename + "_smoothed" + en);
    }
    console.log(`Saving board "${outname}"`);
    board.save(outname);
  });
  