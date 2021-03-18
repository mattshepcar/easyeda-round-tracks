const extensionId = 'extension-smoothtracks-id'.split('-')[1]; // this format is needed to set the Extension ID during install
const manifest = easyeda.extension.instances[extensionId].manifest;
var extension = easyeda.extension.instances[extensionId];
const {RoundTracks} = extension.roundtracks;
const {FilletTracks} = extension.fillet;
const {SetTeardrops} = extension.teardrops;
const {Board} = extension.board;

function createCommand(callback) {
	id = 'extension-'+extensionId+'-' + Math.round(Math.random()*1e9);
	cmd=[];
	cmd[id] = callback;
	api('createCommand', cmd);
	return id;
}

var args = {
	radius: 5.0,
	radiusWidthMultiplier: 0.5,
	maxRadius: 100.0,
	minAngle: 5.0,
	minLength: 2.5,
	passes: 3,
	teardropLength: 50,
	teardropWidth: 90,
	teardropSegs: 10,
	smoothnway: false,
	nosubdivide: false,
	nofillet: false,
	noteardrops: false
};

api('createToolbarButton', {
	fordoctype: 'pcb',
	menu:[
		{
			text: "Smooth Tracks",
			cmd: createCommand(()=>{
				board = new Board(api('getSource', {type:'compress'}));
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
				api('applySource',{source: board.save(), createNew: true});
			}),
			title: 'Apply smoothing algorithm to PCB tracks',
		},
		{
			text: "About", 
			cmd: createCommand(()=>{ aboutdlg.dialog('open') })
		},
	]
});

var aboutdlg = api('createDialog', {
	title: `${manifest.name} - About`,
    content : `
    <div style="padding: 8px; text-align: center">
        <h1>${manifest.name}</h1>
		<h2>Version: ${manifest.version}</h2>
		<p>Inspired by <a href="https://mitxela.com/projects/melting_kicad" target="_blank">Mitxela's Melting KiCad article</a></p>
		<p><a href="http://paperjs.org/" target="_blank">paper.js</a> is used for the track filleting option</p>
        <p>Visit <a href="${manifest.homepage}" target="_blank">${manifest.homepage}</a> for updates</p>
    </div>
`,
	width : 320,
	modal : true,
	collapsible: false,
	resizable: false,
	buttons : [{
			text : 'Close',
			cmd : 'dialog-close'
		}
	]
});

