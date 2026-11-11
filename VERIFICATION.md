# VERIFICATION — oreillette_v1

Date : 2026-11-11 — KiCad **9.0.8** (`kicad-cli version`), bibliothèques `kicad-symbols` / `kicad-footprints` 9.0.8.

## 0. Résumé

| Contrôle | Résultat |
|---|---|
| ERC (`kicad-cli sch erc --severity-all`) | **0 erreur**, 1 avertissement laissé volontairement (§5) |
| DRC (`kicad-cli pcb drc --severity-all --schematic-parity --all-track-errors`) | **0 erreur**, 0 pastille non connectée, 0 écart schéma/PCB, 2 avertissements laissés volontairement (§5) |
| Connectivité schéma ↔ netlist d'origine | identique (49 composants, 28 nets) |
| Brochages U1, U3, U4, Q1, D1, J1 | contrôlés sur les fiches officielles : **conformes**, aucune correction de netlist |
| Brochage U2 (MAX98357A) | **non contrôlé sur la fiche officielle** (téléchargement refusé par analog.com) — voir §6 |

Aucune fiche technique consultée ne contredit la netlist. La netlist d'origine n'a donc pas été modifiée.

**Points à lire avant de commander la carte** (détail au §6) : brochage U2 non confirmé sur la fiche ;
calibre de l'interrupteur SW1 à confirmer ; fiches de SW1 et SW2–SW4 non consultées.

## 1. Environnement — à savoir

- **KiCad n'était pas installé sur la machine** (`kicad-cli` introuvable). Les dépôts KiCad officiels étant
  inaccessibles, KiCad 9.0.8 a été installé depuis l'archive Ubuntu 26.04 dans un environnement isolé (chroot).
  Le dépôt Ubuntu 24.04 de la machine ne propose que KiCad 7.0.11, dont `kicad-cli` n'a ni ERC ni DRC.
  Les fichiers sont donc au format KiCad 9 (schéma `20250114`). Si vous utilisez KiCad 8, ils ne s'ouvriront pas.
- Les fiches techniques ont été téléchargées après ouverture de l'accès réseau aux sites des fabricants.
- Aucun autorouteur n'est disponible hors ligne : les pistes ont été calculées par `tools/route.py`
  (routeur sur grille de 0,05 mm), puis vérifiées par le DRC de KiCad. Le tracé est électriquement correct
  mais pas « dessiné à la main » : quelques pistes de signal sont plus longues que nécessaire (§4.4).

## 2. Brochages contrôlés contre les fiches techniques

| Repère | Document consulté | Broches de la netlist contrôlées | Résultat |
|---|---|---|---|
| U1 ESP32-WROOM-32E | Espressif, *ESP32-WROOM-32E & WROOM-32UE Datasheet* **v2.1**, tableau 3 | 1 GND, 2 3V3, 3 EN, 7 IO35, 8 IO32, 9 IO33, 10 IO25, 11 IO26, 15 GND, 25 IO0, 31 IO19, 33 IO21, 34 RXD0, 35 TXD0, 36 IO22, 38 GND, 39 GND (pad) | **Conforme**. IO35 = entrée seule + ADC1_CH7 (convient à la mesure batterie) ; IO32 = TOUCH9 (convient au pad tactile). Broches 17–22 et 32 = NC, non utilisées. |
| U3 MCP73831T-2ACI/OT | Microchip **DS20001984H**, tableau 3-1 (SOT-23-5) | 1 STAT, 2 VSS, 3 VBAT, 4 VDD, 5 PROG | **Conforme**. I = 1000 V / R3 = 500 mA avec R3 = 2 kΩ. STAT à l'état bas pendant la charge → D2 câblée entre VBUS et STAT, correct. « -2ACI/OT » = 4,20 V, SOT-23-5. |
| U4 AP2112K-3.3 | Diodes Inc. **DS39724 rév. 2-2**, boîtier SOT25 | 1 VIN, 2 GND, 3 EN, 5 VOUT (4 = NC) | **Conforme**. EN actif à l'état haut, relié à VIN. VIN 2,5–6,0 V, 600 mA mini. |
| Q1 DMG2305UX | Diodes Inc. **DS36196 rév. 8-2** | 1 G, 2 S, 3 D | **Conforme**, avec une réserve : la fiche montre la position des broches (D seul d'un côté, G à gauche, S à droite) sans les numéroter ; la correspondance 1/2/3 repose sur la numérotation SOT-23 normalisée, qui est celle de l'empreinte KiCad. P-MOS −20 V, 52 mΩ à −4,5 V. Diode de corps drain→source : sens correct pour le partage de charge (drain = VBAT, source = VSYS). |
| D1 B5819W | Diodes Inc. **1N5819HW** (ds30217) — équivalent, voir remarque | 1 cathode, 2 anode | **Conforme** : SOD-123, cathode repérée par la bande = pastille 1 de l'empreinte. 40 V, 1 A. |
| J1 USB4125-GF-A | GCT, plan **USB4125 rév. A6** (28/09/2020) | A5 CC1, A9 VBUS, A12 GND, B5 CC2, B9 VBUS, B12 GND, S1 blindage | **Conforme**. L'ordre des pastilles de l'empreinte KiCad (B12 B9 A5 B5 A9 A12) est celui du plan GCT. |
| U2 MAX98357AETE+T | **fiche non obtenue** ; symbole KiCad `Audio:MAX98357A` | 1 DIN, 2 GAIN_SLOT, 3 GND, 4 SD_MODE, 7–8 VDD, 9 OUTP, 10 OUTN, 11 GND, 14 LRCLK, 15 GND, 16 BCLK, 17 pad | **Identique au symbole KiCad**, mais **pas contrôlé sur la fiche Analog Devices** (§6). |

Remarques :

- **D1** : « B5819W » est une référence générique (plusieurs fabricants asiatiques) ; la nomenclature ne précise pas
  le fabricant. La fiche consultée est celle de l'équivalent Diodes Inc. 1N5819HW (même boîtier, même brochage).
  La chute directe à 1 A varie selon le fabricant (0,45 V maxi pour le 1N5819HW).
- **Broches de démarrage** (fiche U1, §« Strapping pins » : IO0, IO2, MTDI = IO12, MTDO = IO15, IO5) :
  IO2, IO5, IO12, IO15 sont laissées non connectées ; IO0 ne va qu'à R8, SW3 et J4, comme dans la netlist.
- **État du produit U1** : la fiche v2.1 ne porte aucun filigrane NRND/EOL. Les autres composants n'ont pas pu
  être contrôlés chez un distributeur (pas d'accès).

## 3. Écarts avec la netlist et la nomenclature d'origine

Connectivité : **aucun écart** (`tools/compare_netlist.py oreillette_v1.net <netlist exportée du schéma>`).

| Écart | Raison |
|---|---|
| Noms d'empreintes | Aucun : les 16 noms d'empreintes de la netlist existent tels quels dans les bibliothèques KiCad 9.0.8. |
| R14 : valeur « 100k » + attribut « Ne pas monter » (au lieu de « 100k NON MONTE ») | L'attribut DNP de KiCad exclut proprement le composant de la pose ; la croix apparaît sur le schéma. |
| Q1 : symbole `Transistor_FET:DMG2301L`, valeur « DMG2305UX » | Le DMG2305UX n'a pas de symbole dans la bibliothèque ; le DMG2301L a le même boîtier et le même brochage (1 G, 2 S, 3 D). |
| D1 : symbole générique `Device:D_Schottky` | Pas de symbole B5819W en SOD-123 dans la bibliothèque. |
| Noms de nets préfixés par « / » dans le PCB (`/CC1`, `/SPK_P`, `/BAT_IN`…) | Nets portés par des labels locaux : KiCad les nomme ainsi. Les nets inter-blocs (VBAT, VSYS, VSW, EN, I2S_*…) utilisent des labels globaux et gardent le nom d'origine. |
| 28 nets `unconnected-(…)` | Broches volontairement libres (drapeaux « non connecté »). |
| 3 symboles `PWR_FLAG` (VBUS, VSW, GND) | Nécessaires à l'ERC ; sans effet sur la carte. |
| Points de test : attribut « exclu de la nomenclature » retiré des empreintes | L'empreinte KiCad l'active par défaut alors que la nomenclature d'origine liste TP1–TP8 ; alignement sur le schéma. |

## 4. PCB

### 4.1 Caractéristiques

- 30 × 50 mm, 1,6 mm, 4 couches : **F.Cu** signal + composants / **In1.Cu** plan GND / **In2.Cu** plan +3V3 / **B.Cu** signal.
- Tous les composants sont sur la face supérieure. 274 segments, 69 vias traversants 0,6 / 0,3 mm.
- Règles (dans `oreillette_v1.kicad_pro`) : isolement mini 0,15 mm (routage fait à 0,20 mm), piste mini 0,15 mm,
  cuivre/bord 0,30 mm, trou mini 0,20 mm (vias thermiques de l'empreinte ESP32).
  **À aligner sur les capacités de votre fabricant.**

### 4.2 Respect des contraintes

| Contrainte | Réalisation |
|---|---|
| Module en bord de carte, antenne sans cuivre | U1 au bord haut, **antenne en débord de 6,2 mm** : il n'y a pas de carte sous l'antenne. Premier cuivre routé à 0,40 mm sous le bord. L'encombrement total est donc 30 × 56,2 mm. |
| Ampli et haut-parleur loin de l'antenne | U2 à 37,5 mm du bord haut, J3 à 46 mm, dans le coin opposé. |
| Pistes haut-parleur courtes et larges | SPK_N 5,7 mm, SPK_P 8,3 mm, en 0,5 mm, sur F.Cu, sans via. Sortie du TQFN en 0,25 mm sur 1,7 mm (pas de 0,5 mm entre broches 9 et 10). |
| Découplage au plus près | Distances entre centres de pastilles : C6→U1.2 2,1 mm ; C5→U1.2 3,9 mm ; C9→U2.7 1,5 mm ; C8→U2.7 2,7 mm ; C3→U4.1 1,8 mm ; C4→U4.5 2,2 mm ; C1→U3.4 2,1 mm ; C2→U3.3 1,9 mm ; C10→U1.7 2,3 mm. |
| VBUS, VBAT, VSYS, VSW pour 1 A | Chemin de puissance en **0,6 mm** (cuivre 35 µm : environ 0,3 mm suffit pour 1 A à +10 °C). BAT_IN en 0,6 mm. |
| Broches de démarrage | Voir §2. |
| Accessibilité, sérigraphie | J4 au bord droit avec le nom de chaque broche et le repère « 1 » ; « + » et « − » de part et d'autre de J2, « BAT » ; nom du signal sous chaque point de test ; RESET / USER / BOOT ; ON / OFF ; HP ; rappel des brochages J4 et J2 au dos. |

Segments plus fins que 0,6 mm sur les nets de puissance — tous en dérivation, aucun dans le chemin principal :

- VBUS → grille de Q1, R5, R4 (0,25 mm) : courant négligeable.
- VBAT → R11 et TP2, VSYS → TP3 (0,25 mm) : mesure seulement.
- VSW → broches 7 et 8 de U2 : deux pistes de 0,25 mm sur 1,3 mm, depuis la pastille de C9 (pas de 0,5 mm du boîtier).

### 4.3 Décisions de conception

- **Antenne en débord plutôt que zone sans cuivre** : c'est la disposition recommandée par Espressif et elle libère
  6 mm de carte, sans quoi les 49 composants ne tenaient pas sur une face en 30 × 50 mm.
- **+3V3 sur un plan entier (In2.Cu)** ; VSW, VSYS, VBAT et VBUS restent en pistes sur les couches externes.
- **Via thermique au centre du pad exposé de U2** (via dans la pastille, non bouché) : la soudure peut y migrer ;
  sans conséquence en prototype, à boucher ou déplacer en série.
- Les autres vias sont hors des pastilles.

### 4.4 Limites du tracé — à reprendre si vous le souhaitez

- **Un seul via par changement de couche sur VBUS, VBAT et VSYS** (1 A dans un via de 0,3 mm : admissible, sans marge).
  Doubler ces vias est une amélioration simple.
- Pistes de signal longues : I2S_LRCLK 52 mm, EN 50 mm, ADC_VBAT 39 mm, I2S_BCLK 37 mm, I2S_DIN 35 mm
  (l'I2S part du côté gauche du module et l'ampli est en bas à droite). Fonctionnel à ces fréquences, mais perfectible.
- Deux pistes de signal passent sur F.Cu sous le corps du module ESP32 (hors antenne).
- 8 références sont sur F.Fab faute de place en sérigraphie : C6, C10, D2, R8, R9, R10, R11, SW3 ;
  les références TP1–TP8 y sont aussi, remplacées par le nom du signal.
- Pas de modèles 3D installés : le rendu 3D ne montre pas les composants.

## 5. Avertissements laissés volontairement

| Outil | Avertissement | Explication |
|---|---|---|
| ERC | `pin_to_pin` : U2 broche 17 (PAD, « non spécifié ») reliée à GND | Type de broche défini ainsi dans le symbole KiCad ; le pad exposé doit bien aller à GND. Modifier le symbole créerait un écart avec la bibliothèque. |
| DRC | 2 × `silk_edge_clearance` : sérigraphie de SW1 coupée par le bord | Dessin du levier de l'interrupteur, qui dépasse volontairement du bord gauche. |

Rapports complets : `docs/erc.rpt`, `docs/drc.rpt`.

## 6. Ce qui n'a pas pu être vérifié

1. **MAX98357A (U2)** : www.analog.com refuse les téléchargements automatisés. Le brochage n'est confirmé que par le
   symbole de la bibliothèque KiCad. Non vérifiés non plus, et cités de mémoire sur le schéma : table de gain
   (GAIN_SLOT libre = 9 dB, 100 kΩ vers GND = 15 dB) et seuils de SD_MODE. **À contrôler sur la fiche avant fabrication.**
   De mémoire également : avec SD_MODE piloté directement à 3,3 V, l'ampli joue le **canal gauche seul**, pas (G+D)/2 ;
   à confirmer selon ce que le firmware envoie.
2. **SW1 PCM12SMTR** : fiche inaccessible (redirection vers un site non autorisé). Non vérifiés : numérotation des
   bornes (2 = commun, d'après l'empreinte KiCad), sens ON/OFF de la sérigraphie, et surtout le **calibre** :
   de mémoire 0,3 A sous 6 V, alors que SW1 porte tout le courant de la carte (pistes prévues pour 1 A).
   Si c'est confirmé, il faudra un autre interrupteur ou une commande par transistor.
3. **SW2–SW4 TL3342** : fiche non obtenue ; brochage repris de l'empreinte KiCad (pastilles 1-1 / 2-2).
4. **J2, J3, J4, passifs, LED** : pas de fiche consultée. La polarité de J2 (1 = BAT+) est celle de la netlist ;
   **elle n'est pas normalisée sur les batteries LiPo à connecteur PH** : à contrôler sur votre batterie.
5. **Disponibilité / obsolescence** des composants : non contrôlée (pas d'accès distributeur).
6. **Ouverture dans l'interface graphique de KiCad** : non testée (machine sans affichage). Les fichiers ont été
   chargés et contrôlés par `kicad-cli` et par l'API `pcbnew` de la même version.
7. Aucune simulation ni vérification RF, thermique ou acoustique.

Observations de conception hors périmètre de la netlist, pour information :

- D3 (bleue) alimentée en 3,3 V à travers 1 kΩ : courant d'environ 0,3 mA, luminosité faible.
- Aucune protection contre l'inversion de batterie ni contre les décharges électrostatiques sur USB.
- J1 est un connecteur d'alimentation seule : la programmation passe uniquement par J4 (adaptateur USB-UART 3,3 V),
  sans circuit de reset automatique (boutons BOOT et RESET).

## 7. Fichiers et régénération

| Fichier | Contenu |
|---|---|
| `oreillette_v1.kicad_pro`, `.kicad_sch`, `.kicad_pcb` | Projet KiCad 9 |
| `docs/oreillette_v1_schema.pdf` | Schéma |
| `docs/oreillette_v1_pcb_rendu_dessus.png`, `_dessous.png` | Rendu de la carte |
| `docs/oreillette_v1_pcb_cuivre_dessus.png`, `_dessous.png` | Cuivre F.Cu + B.Cu + sérigraphie / B.Cu seul |
| `docs/oreillette_v1_pcb_couches.pdf` | F.Cu, In1.Cu, In2.Cu, B.Cu, sérigraphies, F.Fab (7 pages) |
| `docs/erc.rpt`, `docs/drc.rpt` | Rapports ERC et DRC |
| `tools/` | Scripts ayant produit le schéma, le placement et le routage |

Le projet se relit et se modifie normalement dans KiCad ; les scripts ne sont utiles que pour régénérer :

```bash
python3 tools/gen_sch.py /usr/share/kicad/symbols oreillette_v1.kicad_sch
```

```bash
kicad-cli sch export netlist --format kicadsexpr -o out/sch.net oreillette_v1.kicad_sch
```

```bash
python3 tools/gen_pcb.py out/sch.net oreillette_v1.kicad_pcb --route
```

Attention : relancer `gen_sch.py` ou `gen_pcb.py` écrase les modifications faites à la main dans KiCad.
