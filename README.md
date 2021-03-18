# easyeda-round-tracks

Based on https://github.com/mitxela/kicad-round-tracks this extension applies rounding to the copper traces on a PCB in EasyEDA.

## Installation
1) Download/clone this repository
1) Open [EasyEDA](https://easyeda.com/editor) in Browser or Desktop
1) In EasyEDA go to "Advanced" > "Extensions" > "Extensions Settings ..." > "Load Extension..." > "Select Files ..."
1) Select all files from the "extension" directory of your extracted download and hit "Load Extension"
1) You're done, close the dialog (you can delete the files from your harddisk)

## Using

Current there are just two menu options under the "Smooth Tracks" menu at the top:
1) Smooth Tracks.  This will apply smoothing to all the tracks on the top & bottom layers. Then it will create arcs on any t-junctions or areas where track smoothing could not be applied (e.g. where traces of differing widths intersect).  Finally it will add teardrops to vias and through hole pads.  The resultant board will be opened as a new document because the smoothing process is not reversible.
2) Add Teardrops.  Any existing teardrops will be removed from the board and new ones added.  These can be removed by using the normal EasyEDA teardrops dialog if required.

## Example

This is the result of running "Smooth Tracks":
![output](docs/example1-smoothed.PNG)
on this input board:
![input](docs/example1-input.PNG) 
