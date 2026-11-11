#!/bin/bash
# Trace des vues de relecture (cuivre dessus/dessous) en PNG. Usage : tools/plot.sh <prefixe sortie>
set -e
kicad-cli pcb export pdf --mode-single -l B.Cu,F.Cu,F.SilkS,Edge.Cuts -o "$1_top.pdf" oreillette_v1.kicad_pcb >/dev/null
kicad-cli pcb export pdf --mode-single -l B.Cu,Edge.Cuts -o "$1_bot.pdf" oreillette_v1.kicad_pcb >/dev/null
for s in top bot; do pdftoppm -r 600 -x 2330 -y 1380 -W 780 -H 1240 -png "$1_$s.pdf" "$1_$s"; done
