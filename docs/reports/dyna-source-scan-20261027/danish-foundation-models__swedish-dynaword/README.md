---
annotations_creators:
- no-annotation
language_creators:
- crowdsourced
language:
- sv
- swe
license: cc0-1.0
multilinguality:
- monolingual
source_datasets:
- original
task_categories:
- text-generation
task_ids:
- language-modeling
tags:
- text-corpus
- continual-development
- community-collaboration
pretty_name: Swedish Dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/*.parquet
- config_name: dalpilen-1860
  data_files:
  - split: train
    path: data/dalpilen-1860/*.parquet
- config_name: lag1800
  data_files:
  - split: train
    path: data/lag1800/*.parquet
- config_name: svensk-tidskrift
  data_files:
  - split: train
    path: data/svensk-tidskrift/*.parquet
- config_name: statens-offentliga-utredningar
  data_files:
  - split: train
    path: data/statens-offentliga-utredningar/*.parquet
- config_name: biblioteksbladet
  data_files:
  - split: train
    path: data/biblioteksbladet/*.parquet
- config_name: riksdagen-forfattningssamling
  data_files:
  - split: train
    path: data/riksdagen-forfattningssamling/*.parquet
- config_name: riksdagen-reglementen
  data_files:
  - split: train
    path: data/riksdagen-reglementen/*.parquet
- config_name: riksdagen-register
  data_files:
  - split: train
    path: data/riksdagen-register/*.parquet
- config_name: riksdagen-skrivelser
  data_files:
  - split: train
    path: data/riksdagen-skrivelser/*.parquet
- config_name: riksdagen-utredningar
  data_files:
  - split: train
    path: data/riksdagen-utredningar/*.parquet
- config_name: riksdagen-berattelser
  data_files:
  - split: train
    path: data/riksdagen-berattelser/*.parquet
- config_name: riksdagen-motioner
  data_files:
  - split: train
    path: data/riksdagen-motioner/*.parquet
- config_name: riksdagen-betankanden
  data_files:
  - split: train
    path: data/riksdagen-betankanden/*.parquet
- config_name: riksdagen-propositioner
  data_files:
  - split: train
    path: data/riksdagen-propositioner/*.parquet
- config_name: riksdagen-protokoll
  data_files:
  - split: train
    path: data/riksdagen-protokoll/*.parquet
- config_name: cellar
  data_files:
  - split: train
    path: data/cellar/*.parquet
- config_name: flashback-dator
  data_files:
  - split: train
    path: data/flashback-dator/*.parquet
- config_name: flashback-droger
  data_files:
  - split: train
    path: data/flashback-droger/*.parquet
- config_name: flashback-ekonomi
  data_files:
  - split: train
    path: data/flashback-ekonomi/*.parquet
- config_name: flashback-fordon
  data_files:
  - split: train
    path: data/flashback-fordon/*.parquet
- config_name: flashback-hem
  data_files:
  - split: train
    path: data/flashback-hem/*.parquet
- config_name: flashback-kultur
  data_files:
  - split: train
    path: data/flashback-kultur/*.parquet
- config_name: flashback-livsstil
  data_files:
  - split: train
    path: data/flashback-livsstil/*.parquet
- config_name: flashback-mat
  data_files:
  - split: train
    path: data/flashback-mat/*.parquet
- config_name: flashback-om-flashback
  data_files:
  - split: train
    path: data/flashback-om-flashback/*.parquet
- config_name: flashback-ovrigt
  data_files:
  - split: train
    path: data/flashback-ovrigt/*.parquet
- config_name: flashback-politik
  data_files:
  - split: train
    path: data/flashback-politik/*.parquet
- config_name: flashback-resor
  data_files:
  - split: train
    path: data/flashback-resor/*.parquet
- config_name: flashback-samhalle
  data_files:
  - split: train
    path: data/flashback-samhalle/*.parquet
- config_name: flashback-sex
  data_files:
  - split: train
    path: data/flashback-sex/*.parquet
- config_name: flashback-sport
  data_files:
  - split: train
    path: data/flashback-sport/*.parquet
- config_name: flashback-vetenskap
  data_files:
  - split: train
    path: data/flashback-vetenskap/*.parquet
- config_name: familjeliv-adoption
  data_files:
  - split: train
    path: data/familjeliv-adoption/*.parquet
- config_name: familjeliv-allmanna-ekonomi
  data_files:
  - split: train
    path: data/familjeliv-allmanna-ekonomi/*.parquet
- config_name: familjeliv-allmanna-familjeliv
  data_files:
  - split: train
    path: data/familjeliv-allmanna-familjeliv/*.parquet
- config_name: familjeliv-allmanna-fritid
  data_files:
  - split: train
    path: data/familjeliv-allmanna-fritid/*.parquet
- config_name: familjeliv-allmanna-husdjur
  data_files:
  - split: train
    path: data/familjeliv-allmanna-husdjur/*.parquet
- config_name: familjeliv-allmanna-hushem
  data_files:
  - split: train
    path: data/familjeliv-allmanna-hushem/*.parquet
- config_name: familjeliv-allmanna-kropp
  data_files:
  - split: train
    path: data/familjeliv-allmanna-kropp/*.parquet
- config_name: familjeliv-allmanna-noje
  data_files:
  - split: train
    path: data/familjeliv-allmanna-noje/*.parquet
- config_name: familjeliv-allmanna-samhalle
  data_files:
  - split: train
    path: data/familjeliv-allmanna-samhalle/*.parquet
- config_name: familjeliv-allmanna-sandladan
  data_files:
  - split: train
    path: data/familjeliv-allmanna-sandladan/*.parquet
- config_name: familjeliv-anglarum
  data_files:
  - split: train
    path: data/familjeliv-anglarum/*.parquet
- config_name: familjeliv-expert
  data_files:
  - split: train
    path: data/familjeliv-expert/*.parquet
- config_name: familjeliv-foralder
  data_files:
  - split: train
    path: data/familjeliv-foralder/*.parquet
- config_name: familjeliv-gravid
  data_files:
  - split: train
    path: data/familjeliv-gravid/*.parquet
- config_name: familjeliv-kansliga
  data_files:
  - split: train
    path: data/familjeliv-kansliga/*.parquet
- config_name: familjeliv-medlem-allmanna
  data_files:
  - split: train
    path: data/familjeliv-medlem-allmanna/*.parquet
- config_name: familjeliv-medlem-foraldrar
  data_files:
  - split: train
    path: data/familjeliv-medlem-foraldrar/*.parquet
- config_name: familjeliv-medlem-planerarbarn
  data_files:
  - split: train
    path: data/familjeliv-medlem-planerarbarn/*.parquet
- config_name: familjeliv-medlem-vantarbarn
  data_files:
  - split: train
    path: data/familjeliv-medlem-vantarbarn/*.parquet
- config_name: familjeliv-pappagrupp
  data_files:
  - split: train
    path: data/familjeliv-pappagrupp/*.parquet
- config_name: familjeliv-planerarbarn
  data_files:
  - split: train
    path: data/familjeliv-planerarbarn/*.parquet
- config_name: familjeliv-sexsamlevnad
  data_files:
  - split: train
    path: data/familjeliv-sexsamlevnad/*.parquet
- config_name: familjeliv-svartattfabarn
  data_files:
  - split: train
    path: data/familjeliv-svartattfabarn/*.parquet
- config_name: lb-open
  data_files:
  - split: train
    path: data/lb-open/*.parquet
- config_name: poeter
  data_files:
  - split: train
    path: data/poeter/*.parquet
- config_name: wikipedia-sv
  data_files:
  - split: train
    path: data/wikipedia-sv/*.parquet
- config_name: europarl-sv
  data_files:
  - split: train
    path: data/europarl-sv/*.parquet
- config_name: laakartidningen
  data_files:
  - split: train
    path: data/laakartidningen/*.parquet
- config_name: fsv-aldrelagar
  data_files:
  - split: train
    path: data/fsv-aldrelagar/*.parquet
- config_name: fsv-aldrereligiosprosa
  data_files:
  - split: train
    path: data/fsv-aldrereligiosprosa/*.parquet
- config_name: fsv-nysvenskbibel
  data_files:
  - split: train
    path: data/fsv-nysvenskbibel/*.parquet
- config_name: fsv-nysvenskdalin
  data_files:
  - split: train
    path: data/fsv-nysvenskdalin/*.parquet
- config_name: fsv-nysvenskkronikor
  data_files:
  - split: train
    path: data/fsv-nysvenskkronikor/*.parquet
- config_name: fsv-nysvensklagar
  data_files:
  - split: train
    path: data/fsv-nysvensklagar/*.parquet
- config_name: fsv-nysvenskovrigt
  data_files:
  - split: train
    path: data/fsv-nysvenskovrigt/*.parquet
- config_name: fsv-profanprosa
  data_files:
  - split: train
    path: data/fsv-profanprosa/*.parquet
- config_name: fsv-verser
  data_files:
  - split: train
    path: data/fsv-verser/*.parquet
- config_name: fsv-yngrelagar
  data_files:
  - split: train
    path: data/fsv-yngrelagar/*.parquet
- config_name: fsv-yngrereligiosprosa
  data_files:
  - split: train
    path: data/fsv-yngrereligiosprosa/*.parquet
- config_name: fsv-yngretankebocker
  data_files:
  - split: train
    path: data/fsv-yngretankebocker/*.parquet
- config_name: standsriksdagen-adelsstandet
  data_files:
  - split: train
    path: data/standsriksdagen-adelsstandet/*.parquet
- config_name: standsriksdagen-bihang
  data_files:
  - split: train
    path: data/standsriksdagen-bihang/*.parquet
- config_name: standsriksdagen-bondestandet
  data_files:
  - split: train
    path: data/standsriksdagen-bondestandet/*.parquet
- config_name: standsriksdagen-borgarstandet
  data_files:
  - split: train
    path: data/standsriksdagen-borgarstandet/*.parquet
- config_name: standsriksdagen-prastestandet
  data_files:
  - split: train
    path: data/standsriksdagen-prastestandet/*.parquet
- config_name: standsriksdagen-riksdagsakter
  data_files:
  - split: train
    path: data/standsriksdagen-riksdagsakter/*.parquet
- config_name: standsriksdagen-riksdagsbeslut
  data_files:
  - split: train
    path: data/standsriksdagen-riksdagsbeslut/*.parquet
- config_name: strindbergromaner
  data_files:
  - split: train
    path: data/strindbergromaner/*.parquet
- config_name: strindbergbrev
  data_files:
  - split: train
    path: data/strindbergbrev/*.parquet
- config_name: dramadialog
  data_files:
  - split: train
    path: data/dramadialog/*.parquet
- config_name: bibel1917
  data_files:
  - split: train
    path: data/bibel1917/*.parquet
- config_name: psalmboken
  data_files:
  - split: train
    path: data/psalmboken/*.parquet
- config_name: akademiliv
  data_files:
  - split: train
    path: data/akademiliv/*.parquet
- config_name: dagens-arena
  data_files:
  - split: train
    path: data/dagens-arena/*.parquet
- config_name: gu-journalen
  data_files:
  - split: train
    path: data/gu-journalen/*.parquet
- config_name: forskning-framsteg
  data_files:
  - split: train
    path: data/forskning-framsteg/*.parquet
- config_name: sv-covid-19
  data_files:
  - split: train
    path: data/sv-covid-19/*.parquet
- config_name: aftonbladet-1830
  data_files:
  - split: train
    path: data/aftonbladet-1830/*.parquet
- config_name: aftonbladet-1840
  data_files:
  - split: train
    path: data/aftonbladet-1840/*.parquet
- config_name: aftonbladet-1850
  data_files:
  - split: train
    path: data/aftonbladet-1850/*.parquet
- config_name: aftonbladet-1860
  data_files:
  - split: train
    path: data/aftonbladet-1860/*.parquet
- config_name: aftonbladet-1870
  data_files:
  - split: train
    path: data/aftonbladet-1870/*.parquet
- config_name: aftonbladet-1880
  data_files:
  - split: train
    path: data/aftonbladet-1880/*.parquet
- config_name: aftonbladet-1890
  data_files:
  - split: train
    path: data/aftonbladet-1890/*.parquet
- config_name: aftonbladet-1900
  data_files:
  - split: train
    path: data/aftonbladet-1900/*.parquet
- config_name: alfwarochskamt-1840
  data_files:
  - split: train
    path: data/alfwarochskamt-1840/*.parquet
- config_name: barometern-1840
  data_files:
  - split: train
    path: data/barometern-1840/*.parquet
- config_name: barometern-1850
  data_files:
  - split: train
    path: data/barometern-1850/*.parquet
- config_name: barometern-1860
  data_files:
  - split: train
    path: data/barometern-1860/*.parquet
- config_name: barometern-1870
  data_files:
  - split: train
    path: data/barometern-1870/*.parquet
- config_name: barometern-1880
  data_files:
  - split: train
    path: data/barometern-1880/*.parquet
- config_name: barometern-1890
  data_files:
  - split: train
    path: data/barometern-1890/*.parquet
- config_name: blekingsposten-1850
  data_files:
  - split: train
    path: data/blekingsposten-1850/*.parquet
- config_name: blekingsposten-1860
  data_files:
  - split: train
    path: data/blekingsposten-1860/*.parquet
- config_name: blekingsposten-1870
  data_files:
  - split: train
    path: data/blekingsposten-1870/*.parquet
- config_name: blekingsposten-1880
  data_files:
  - split: train
    path: data/blekingsposten-1880/*.parquet
- config_name: bollnastidning-1870
  data_files:
  - split: train
    path: data/bollnastidning-1870/*.parquet
- config_name: bollnastidning-1880
  data_files:
  - split: train
    path: data/bollnastidning-1880/*.parquet
- config_name: borastidning-1830
  data_files:
  - split: train
    path: data/borastidning-1830/*.parquet
- config_name: borastidning-1840
  data_files:
  - split: train
    path: data/borastidning-1840/*.parquet
- config_name: borastidning-1850
  data_files:
  - split: train
    path: data/borastidning-1850/*.parquet
- config_name: borastidning-1860
  data_files:
  - split: train
    path: data/borastidning-1860/*.parquet
- config_name: borastidning-1870
  data_files:
  - split: train
    path: data/borastidning-1870/*.parquet
- config_name: borastidning-1880
  data_files:
  - split: train
    path: data/borastidning-1880/*.parquet
- config_name: borastidning-1890
  data_files:
  - split: train
    path: data/borastidning-1890/*.parquet
- config_name: carlscronastidningar-1760
  data_files:
  - split: train
    path: data/carlscronastidningar-1760/*.parquet
- config_name: carlscronaswekoblad-1750
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1750/*.parquet
- config_name: carlscronaswekoblad-1760
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1760/*.parquet
- config_name: carlscronaswekoblad-1770
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1770/*.parquet
- config_name: carlscronaswekoblad-1780
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1780/*.parquet
- config_name: carlscronaswekoblad-1790
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1790/*.parquet
- config_name: carlscronaswekoblad-1800
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1800/*.parquet
- config_name: carlscronaswekoblad-1810
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1810/*.parquet
- config_name: carlscronaswekoblad-1820
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1820/*.parquet
- config_name: carlscronaswekoblad-1830
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1830/*.parquet
- config_name: carlscronaswekoblad-1840
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1840/*.parquet
- config_name: carlscronaswekoblad-1850
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1850/*.parquet
- config_name: carlscronaswekoblad-1860
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1860/*.parquet
- config_name: carlscronaswekoblad-1870
  data_files:
  - split: train
    path: data/carlscronaswekoblad-1870/*.parquet
- config_name: dagligtallehanda-1760
  data_files:
  - split: train
    path: data/dagligtallehanda-1760/*.parquet
- config_name: dagligtallehanda-1770
  data_files:
  - split: train
    path: data/dagligtallehanda-1770/*.parquet
- config_name: dagligtallehanda-1780
  data_files:
  - split: train
    path: data/dagligtallehanda-1780/*.parquet
- config_name: dagligtallehanda-1790
  data_files:
  - split: train
    path: data/dagligtallehanda-1790/*.parquet
- config_name: dagligtallehanda-1800
  data_files:
  - split: train
    path: data/dagligtallehanda-1800/*.parquet
- config_name: dagligtallehanda-1810
  data_files:
  - split: train
    path: data/dagligtallehanda-1810/*.parquet
- config_name: dagligtallehanda-1820
  data_files:
  - split: train
    path: data/dagligtallehanda-1820/*.parquet
- config_name: dagligtallehanda-1830
  data_files:
  - split: train
    path: data/dagligtallehanda-1830/*.parquet
- config_name: dagligtallehanda-1840
  data_files:
  - split: train
    path: data/dagligtallehanda-1840/*.parquet
- config_name: dalpilen-1850
  data_files:
  - split: train
    path: data/dalpilen-1850/*.parquet
- config_name: dalpilen-1870
  data_files:
  - split: train
    path: data/dalpilen-1870/*.parquet
- config_name: dalpilen-1880
  data_files:
  - split: train
    path: data/dalpilen-1880/*.parquet
- config_name: dalpilen-1890
  data_files:
  - split: train
    path: data/dalpilen-1890/*.parquet
- config_name: dalpilen-1900
  data_files:
  - split: train
    path: data/dalpilen-1900/*.parquet
- config_name: fahluweckoblad-1780
  data_files:
  - split: train
    path: data/fahluweckoblad-1780/*.parquet
- config_name: fahluweckoblad-1790
  data_files:
  - split: train
    path: data/fahluweckoblad-1790/*.parquet
- config_name: fahluweckoblad-1800
  data_files:
  - split: train
    path: data/fahluweckoblad-1800/*.parquet
- config_name: fahluweckoblad-1810
  data_files:
  - split: train
    path: data/fahluweckoblad-1810/*.parquet
- config_name: fahluweckoblad-1820
  data_files:
  - split: train
    path: data/fahluweckoblad-1820/*.parquet
- config_name: falkopingstidning-1850
  data_files:
  - split: train
    path: data/falkopingstidning-1850/*.parquet
- config_name: falkopingstidning-1860
  data_files:
  - split: train
    path: data/falkopingstidning-1860/*.parquet
- config_name: falkopingstidning-1870
  data_files:
  - split: train
    path: data/falkopingstidning-1870/*.parquet
- config_name: falkopingstidning-1880
  data_files:
  - split: train
    path: data/falkopingstidning-1880/*.parquet
- config_name: falkopingstidning-1890
  data_files:
  - split: train
    path: data/falkopingstidning-1890/*.parquet
- config_name: faluposten-1860
  data_files:
  - split: train
    path: data/faluposten-1860/*.parquet
- config_name: faluposten-1870
  data_files:
  - split: train
    path: data/faluposten-1870/*.parquet
- config_name: faluposten-1880
  data_files:
  - split: train
    path: data/faluposten-1880/*.parquet
- config_name: faluposten-1890
  data_files:
  - split: train
    path: data/faluposten-1890/*.parquet
- config_name: folketsrost-1840
  data_files:
  - split: train
    path: data/folketsrost-1840/*.parquet
- config_name: folketsrost-1850
  data_files:
  - split: train
    path: data/folketsrost-1850/*.parquet
- config_name: folketsrost-1860
  data_files:
  - split: train
    path: data/folketsrost-1860/*.parquet
- config_name: ghost-1830
  data_files:
  - split: train
    path: data/ghost-1830/*.parquet
- config_name: ghost-1840
  data_files:
  - split: train
    path: data/ghost-1840/*.parquet
- config_name: ghost-1850
  data_files:
  - split: train
    path: data/ghost-1850/*.parquet
- config_name: ghost-1860
  data_files:
  - split: train
    path: data/ghost-1860/*.parquet
- config_name: ghost-1870
  data_files:
  - split: train
    path: data/ghost-1870/*.parquet
- config_name: ghost-1880
  data_files:
  - split: train
    path: data/ghost-1880/*.parquet
- config_name: ghost-1890
  data_files:
  - split: train
    path: data/ghost-1890/*.parquet
- config_name: goteborgsposten-1850
  data_files:
  - split: train
    path: data/goteborgsposten-1850/*.parquet
- config_name: goteborgsposten-1860
  data_files:
  - split: train
    path: data/goteborgsposten-1860/*.parquet
- config_name: goteborgsposten-1870
  data_files:
  - split: train
    path: data/goteborgsposten-1870/*.parquet
- config_name: goteborgsposten-1880
  data_files:
  - split: train
    path: data/goteborgsposten-1880/*.parquet
- config_name: goteborgsposten-1890
  data_files:
  - split: train
    path: data/goteborgsposten-1890/*.parquet
- config_name: goteborgsweckoblad-1870
  data_files:
  - split: train
    path: data/goteborgsweckoblad-1870/*.parquet
- config_name: goteborgsweckoblad-1880
  data_files:
  - split: train
    path: data/goteborgsweckoblad-1880/*.parquet
- config_name: goteborgsweckoblad-1890
  data_files:
  - split: train
    path: data/goteborgsweckoblad-1890/*.parquet
- config_name: gotheborgsallehanda-1770
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1770/*.parquet
- config_name: gotheborgsallehanda-1780
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1780/*.parquet
- config_name: gotheborgsallehanda-1790
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1790/*.parquet
- config_name: gotheborgsallehanda-1800
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1800/*.parquet
- config_name: gotheborgsallehanda-1810
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1810/*.parquet
- config_name: gotheborgsallehanda-1820
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1820/*.parquet
- config_name: gotheborgsallehanda-1830
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1830/*.parquet
- config_name: gotheborgsallehanda-1840
  data_files:
  - split: train
    path: data/gotheborgsallehanda-1840/*.parquet
- config_name: gotheborgskanyheter-1760
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1760/*.parquet
- config_name: gotheborgskanyheter-1770
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1770/*.parquet
- config_name: gotheborgskanyheter-1780
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1780/*.parquet
- config_name: gotheborgskanyheter-1790
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1790/*.parquet
- config_name: gotheborgskanyheter-1800
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1800/*.parquet
- config_name: gotheborgskanyheter-1810
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1810/*.parquet
- config_name: gotheborgskanyheter-1820
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1820/*.parquet
- config_name: gotheborgskanyheter-1830
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1830/*.parquet
- config_name: gotheborgskanyheter-1840
  data_files:
  - split: train
    path: data/gotheborgskanyheter-1840/*.parquet
- config_name: gotheborgsweckolista-1740
  data_files:
  - split: train
    path: data/gotheborgsweckolista-1740/*.parquet
- config_name: gotheborgsweckolista-1750
  data_files:
  - split: train
    path: data/gotheborgsweckolista-1750/*.parquet
- config_name: gotlandstidning-1860
  data_files:
  - split: train
    path: data/gotlandstidning-1860/*.parquet
- config_name: gotlandstidning-1870
  data_files:
  - split: train
    path: data/gotlandstidning-1870/*.parquet
- config_name: gotlandstidning-1880
  data_files:
  - split: train
    path: data/gotlandstidning-1880/*.parquet
- config_name: harnosandsposten-1840
  data_files:
  - split: train
    path: data/harnosandsposten-1840/*.parquet
- config_name: harnosandsposten-1850
  data_files:
  - split: train
    path: data/harnosandsposten-1850/*.parquet
- config_name: harnosandsposten-1860
  data_files:
  - split: train
    path: data/harnosandsposten-1860/*.parquet
- config_name: harnosandsposten-1870
  data_files:
  - split: train
    path: data/harnosandsposten-1870/*.parquet
- config_name: harnosandsposten-1880
  data_files:
  - split: train
    path: data/harnosandsposten-1880/*.parquet
- config_name: harnosandsposten-1890
  data_files:
  - split: train
    path: data/harnosandsposten-1890/*.parquet
- config_name: inrikestidningar-1760
  data_files:
  - split: train
    path: data/inrikestidningar-1760/*.parquet
- config_name: inrikestidningar-1770
  data_files:
  - split: train
    path: data/inrikestidningar-1770/*.parquet
- config_name: inrikestidningar-1780
  data_files:
  - split: train
    path: data/inrikestidningar-1780/*.parquet
- config_name: inrikestidningar-1790
  data_files:
  - split: train
    path: data/inrikestidningar-1790/*.parquet
- config_name: inrikestidningar-1800
  data_files:
  - split: train
    path: data/inrikestidningar-1800/*.parquet
- config_name: inrikestidningar-1810
  data_files:
  - split: train
    path: data/inrikestidningar-1810/*.parquet
- config_name: inrikestidningar-1820
  data_files:
  - split: train
    path: data/inrikestidningar-1820/*.parquet
- config_name: jonkopingsbladet-1840
  data_files:
  - split: train
    path: data/jonkopingsbladet-1840/*.parquet
- config_name: jonkopingsbladet-1850
  data_files:
  - split: train
    path: data/jonkopingsbladet-1850/*.parquet
- config_name: jonkopingsbladet-1860
  data_files:
  - split: train
    path: data/jonkopingsbladet-1860/*.parquet
- config_name: jonkopingsbladet-1870
  data_files:
  - split: train
    path: data/jonkopingsbladet-1870/*.parquet
- config_name: jonkopingsposten-1860
  data_files:
  - split: train
    path: data/jonkopingsposten-1860/*.parquet
- config_name: jonkopingsposten-1870
  data_files:
  - split: train
    path: data/jonkopingsposten-1870/*.parquet
- config_name: jonkopingsposten-1880
  data_files:
  - split: train
    path: data/jonkopingsposten-1880/*.parquet
- config_name: jonkopingsposten-1890
  data_files:
  - split: train
    path: data/jonkopingsposten-1890/*.parquet
- config_name: kalmar-1860
  data_files:
  - split: train
    path: data/kalmar-1860/*.parquet
- config_name: kalmar-1870
  data_files:
  - split: train
    path: data/kalmar-1870/*.parquet
- config_name: kalmar-1880
  data_files:
  - split: train
    path: data/kalmar-1880/*.parquet
- config_name: kalmar-1890
  data_files:
  - split: train
    path: data/kalmar-1890/*.parquet
- config_name: kalmar-1900
  data_files:
  - split: train
    path: data/kalmar-1900/*.parquet
- config_name: karlshamnsallehanda-1840
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1840/*.parquet
- config_name: karlshamnsallehanda-1850
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1850/*.parquet
- config_name: karlshamnsallehanda-1860
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1860/*.parquet
- config_name: karlshamnsallehanda-1870
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1870/*.parquet
- config_name: karlshamnsallehanda-1880
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1880/*.parquet
- config_name: karlshamnsallehanda-1890
  data_files:
  - split: train
    path: data/karlshamnsallehanda-1890/*.parquet
- config_name: karlskronaweckoblad-1870
  data_files:
  - split: train
    path: data/karlskronaweckoblad-1870/*.parquet
- config_name: karlskronaweckoblad-1880
  data_files:
  - split: train
    path: data/karlskronaweckoblad-1880/*.parquet
- config_name: karlskronaweckoblad-1890
  data_files:
  - split: train
    path: data/karlskronaweckoblad-1890/*.parquet
- config_name: kristianstadsbladet-1850
  data_files:
  - split: train
    path: data/kristianstadsbladet-1850/*.parquet
- config_name: kristianstadsbladet-1860
  data_files:
  - split: train
    path: data/kristianstadsbladet-1860/*.parquet
- config_name: kristianstadsbladet-1870
  data_files:
  - split: train
    path: data/kristianstadsbladet-1870/*.parquet
- config_name: kristianstadsbladet-1880
  data_files:
  - split: train
    path: data/kristianstadsbladet-1880/*.parquet
- config_name: kristianstadsbladet-1890
  data_files:
  - split: train
    path: data/kristianstadsbladet-1890/*.parquet
- config_name: lindesbergsallehanda-1870
  data_files:
  - split: train
    path: data/lindesbergsallehanda-1870/*.parquet
- config_name: lindesbergsallehanda-1880
  data_files:
  - split: train
    path: data/lindesbergsallehanda-1880/*.parquet
- config_name: lundsweckoblad-1770
  data_files:
  - split: train
    path: data/lundsweckoblad-1770/*.parquet
- config_name: lundsweckoblad-1780
  data_files:
  - split: train
    path: data/lundsweckoblad-1780/*.parquet
- config_name: lundsweckoblad-1810
  data_files:
  - split: train
    path: data/lundsweckoblad-1810/*.parquet
- config_name: lundsweckoblad-1820
  data_files:
  - split: train
    path: data/lundsweckoblad-1820/*.parquet
- config_name: lundsweckoblad-1830
  data_files:
  - split: train
    path: data/lundsweckoblad-1830/*.parquet
- config_name: lundsweckoblad-1840
  data_files:
  - split: train
    path: data/lundsweckoblad-1840/*.parquet
- config_name: lundsweckoblad-1850
  data_files:
  - split: train
    path: data/lundsweckoblad-1850/*.parquet
- config_name: lundsweckoblad-1860
  data_files:
  - split: train
    path: data/lundsweckoblad-1860/*.parquet
- config_name: lundsweckoblad-1870
  data_files:
  - split: train
    path: data/lundsweckoblad-1870/*.parquet
- config_name: lundsweckoblad-1880
  data_files:
  - split: train
    path: data/lundsweckoblad-1880/*.parquet
- config_name: lundsweckoblad-1890
  data_files:
  - split: train
    path: data/lundsweckoblad-1890/*.parquet
- config_name: malmoallehanda-1820
  data_files:
  - split: train
    path: data/malmoallehanda-1820/*.parquet
- config_name: malmoallehanda-1830
  data_files:
  - split: train
    path: data/malmoallehanda-1830/*.parquet
- config_name: malmoallehanda-1840
  data_files:
  - split: train
    path: data/malmoallehanda-1840/*.parquet
- config_name: malmoallehanda-1850
  data_files:
  - split: train
    path: data/malmoallehanda-1850/*.parquet
- config_name: malmoallehanda-1860
  data_files:
  - split: train
    path: data/malmoallehanda-1860/*.parquet
- config_name: malmoallehanda-1870
  data_files:
  - split: train
    path: data/malmoallehanda-1870/*.parquet
- config_name: malmoallehanda-1880
  data_files:
  - split: train
    path: data/malmoallehanda-1880/*.parquet
- config_name: malmoallehanda-1890
  data_files:
  - split: train
    path: data/malmoallehanda-1890/*.parquet
- config_name: nerikesallehanda-1840
  data_files:
  - split: train
    path: data/nerikesallehanda-1840/*.parquet
- config_name: nerikesallehanda-1850
  data_files:
  - split: train
    path: data/nerikesallehanda-1850/*.parquet
- config_name: nerikesallehanda-1860
  data_files:
  - split: train
    path: data/nerikesallehanda-1860/*.parquet
- config_name: nerikesallehanda-1870
  data_files:
  - split: train
    path: data/nerikesallehanda-1870/*.parquet
- config_name: nerikesallehanda-1880
  data_files:
  - split: train
    path: data/nerikesallehanda-1880/*.parquet
- config_name: nerikesallehanda-1890
  data_files:
  - split: train
    path: data/nerikesallehanda-1890/*.parquet
- config_name: nlk-1850
  data_files:
  - split: train
    path: data/nlk-1850/*.parquet
- config_name: nlk-1860
  data_files:
  - split: train
    path: data/nlk-1860/*.parquet
- config_name: nlk-1870
  data_files:
  - split: train
    path: data/nlk-1870/*.parquet
- config_name: norden-1850
  data_files:
  - split: train
    path: data/norden-1850/*.parquet
- config_name: norden-1860
  data_files:
  - split: train
    path: data/norden-1860/*.parquet
- config_name: norraskane-1880
  data_files:
  - split: train
    path: data/norraskane-1880/*.parquet
- config_name: norraskane-1890
  data_files:
  - split: train
    path: data/norraskane-1890/*.parquet
- config_name: norrbottenskuriren-1860
  data_files:
  - split: train
    path: data/norrbottenskuriren-1860/*.parquet
- config_name: norrbottenskuriren-1870
  data_files:
  - split: train
    path: data/norrbottenskuriren-1870/*.parquet
- config_name: norrbottenskuriren-1880
  data_files:
  - split: train
    path: data/norrbottenskuriren-1880/*.parquet
- config_name: norrbottenskuriren-1890
  data_files:
  - split: train
    path: data/norrbottenskuriren-1890/*.parquet
- config_name: norrbottensposten-1840
  data_files:
  - split: train
    path: data/norrbottensposten-1840/*.parquet
- config_name: norrbottensposten-1850
  data_files:
  - split: train
    path: data/norrbottensposten-1850/*.parquet
- config_name: norrbottensposten-1860
  data_files:
  - split: train
    path: data/norrbottensposten-1860/*.parquet
- config_name: norrbottensposten-1870
  data_files:
  - split: train
    path: data/norrbottensposten-1870/*.parquet
- config_name: norrbottensposten-1880
  data_files:
  - split: train
    path: data/norrbottensposten-1880/*.parquet
- config_name: norrbottensposten-1890
  data_files:
  - split: train
    path: data/norrbottensposten-1890/*.parquet
- config_name: norrkopingskuriren-1850
  data_files:
  - split: train
    path: data/norrkopingskuriren-1850/*.parquet
- config_name: norrkopingskuriren-1860
  data_files:
  - split: train
    path: data/norrkopingskuriren-1860/*.parquet
- config_name: norrkopingstidningar-1780
  data_files:
  - split: train
    path: data/norrkopingstidningar-1780/*.parquet
- config_name: norrkopingstidningar-1790
  data_files:
  - split: train
    path: data/norrkopingstidningar-1790/*.parquet
- config_name: norrkopingstidningar-1800
  data_files:
  - split: train
    path: data/norrkopingstidningar-1800/*.parquet
- config_name: norrkopingstidningar-1810
  data_files:
  - split: train
    path: data/norrkopingstidningar-1810/*.parquet
- config_name: norrkopingstidningar-1820
  data_files:
  - split: train
    path: data/norrkopingstidningar-1820/*.parquet
- config_name: norrkopingstidningar-1830
  data_files:
  - split: train
    path: data/norrkopingstidningar-1830/*.parquet
- config_name: norrkopingstidningar-1840
  data_files:
  - split: train
    path: data/norrkopingstidningar-1840/*.parquet
- config_name: norrkopingstidningar-1850
  data_files:
  - split: train
    path: data/norrkopingstidningar-1850/*.parquet
- config_name: norrkopingstidningar-1860
  data_files:
  - split: train
    path: data/norrkopingstidningar-1860/*.parquet
- config_name: norrkopingstidningar-1870
  data_files:
  - split: train
    path: data/norrkopingstidningar-1870/*.parquet
- config_name: norrkopingstidningar-1880
  data_files:
  - split: train
    path: data/norrkopingstidningar-1880/*.parquet
- config_name: norrkopingstidningar-1890
  data_files:
  - split: train
    path: data/norrkopingstidningar-1890/*.parquet
- config_name: norrkopingsweckotidningar-1750
  data_files:
  - split: train
    path: data/norrkopingsweckotidningar-1750/*.parquet
- config_name: norrkopingsweckotidningar-1760
  data_files:
  - split: train
    path: data/norrkopingsweckotidningar-1760/*.parquet
- config_name: norrkopingsweckotidningar-1770
  data_files:
  - split: train
    path: data/norrkopingsweckotidningar-1770/*.parquet
- config_name: norrkopingsweckotidningar-1780
  data_files:
  - split: train
    path: data/norrkopingsweckotidningar-1780/*.parquet
- config_name: norrlandsposten-1880
  data_files:
  - split: train
    path: data/norrlandsposten-1880/*.parquet
- config_name: nyadagligtallehanda-1850
  data_files:
  - split: train
    path: data/nyadagligtallehanda-1850/*.parquet
- config_name: nyadagligtallehanda-1860
  data_files:
  - split: train
    path: data/nyadagligtallehanda-1860/*.parquet
- config_name: nyadagligtallehanda-1870
  data_files:
  - split: train
    path: data/nyadagligtallehanda-1870/*.parquet
- config_name: nyadagligtallehanda-1880
  data_files:
  - split: train
    path: data/nyadagligtallehanda-1880/*.parquet
- config_name: nyadagligtallehanda-1890
  data_files:
  - split: train
    path: data/nyadagligtallehanda-1890/*.parquet
- config_name: nyakarlskronaweckoblad-1870
  data_files:
  - split: train
    path: data/nyakarlskronaweckoblad-1870/*.parquet
- config_name: nyawermlandstidningen-1850
  data_files:
  - split: train
    path: data/nyawermlandstidningen-1850/*.parquet
- config_name: nyawermlandstidningen-1860
  data_files:
  - split: train
    path: data/nyawermlandstidningen-1860/*.parquet
- config_name: nyawermlandstidningen-1870
  data_files:
  - split: train
    path: data/nyawermlandstidningen-1870/*.parquet
- config_name: nyawermlandstidningen-1880
  data_files:
  - split: train
    path: data/nyawermlandstidningen-1880/*.parquet
- config_name: nyawermlandstidningen-1890
  data_files:
  - split: train
    path: data/nyawermlandstidningen-1890/*.parquet
- config_name: nyawexjobladet-1840
  data_files:
  - split: train
    path: data/nyawexjobladet-1840/*.parquet
- config_name: nyawexjobladet-1850
  data_files:
  - split: train
    path: data/nyawexjobladet-1850/*.parquet
- config_name: nyawexjobladet-1860
  data_files:
  - split: train
    path: data/nyawexjobladet-1860/*.parquet
- config_name: nyawexjobladet-1870
  data_files:
  - split: train
    path: data/nyawexjobladet-1870/*.parquet
- config_name: nyawexjobladet-1880
  data_files:
  - split: train
    path: data/nyawexjobladet-1880/*.parquet
- config_name: nyawexjobladet-1890
  data_files:
  - split: train
    path: data/nyawexjobladet-1890/*.parquet
- config_name: nyttallvarochskamt-1840
  data_files:
  - split: train
    path: data/nyttallvarochskamt-1840/*.parquet
- config_name: nyttallvarochskamt-1850
  data_files:
  - split: train
    path: data/nyttallvarochskamt-1850/*.parquet
- config_name: nyttochgammalt-1780
  data_files:
  - split: train
    path: data/nyttochgammalt-1780/*.parquet
- config_name: nyttochgammalt-1790
  data_files:
  - split: train
    path: data/nyttochgammalt-1790/*.parquet
- config_name: nyttochgammalt-1800
  data_files:
  - split: train
    path: data/nyttochgammalt-1800/*.parquet
- config_name: nyttochgammalt-1810
  data_files:
  - split: train
    path: data/nyttochgammalt-1810/*.parquet
- config_name: ostergotlandsveckoblad-1880
  data_files:
  - split: train
    path: data/ostergotlandsveckoblad-1880/*.parquet
- config_name: ostergotlandsveckoblad-1890
  data_files:
  - split: train
    path: data/ostergotlandsveckoblad-1890/*.parquet
- config_name: ostgotacorrespondenten-1830
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1830/*.parquet
- config_name: ostgotacorrespondenten-1840
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1840/*.parquet
- config_name: ostgotacorrespondenten-1850
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1850/*.parquet
- config_name: ostgotacorrespondenten-1860
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1860/*.parquet
- config_name: ostgotacorrespondenten-1870
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1870/*.parquet
- config_name: ostgotacorrespondenten-1880
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1880/*.parquet
- config_name: ostgotacorrespondenten-1890
  data_files:
  - split: train
    path: data/ostgotacorrespondenten-1890/*.parquet
- config_name: ostgotaposten-1890
  data_files:
  - split: train
    path: data/ostgotaposten-1890/*.parquet
- config_name: ostgotaposten-1900
  data_files:
  - split: train
    path: data/ostgotaposten-1900/*.parquet
- config_name: post-ochinrikestidningar-1820
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1820/*.parquet
- config_name: post-ochinrikestidningar-1830
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1830/*.parquet
- config_name: post-ochinrikestidningar-1840
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1840/*.parquet
- config_name: post-ochinrikestidningar-1850
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1850/*.parquet
- config_name: post-ochinrikestidningar-1860
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1860/*.parquet
- config_name: post-ochinrikestidningar-1870
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1870/*.parquet
- config_name: post-ochinrikestidningar-1880
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1880/*.parquet
- config_name: post-ochinrikestidningar-1890
  data_files:
  - split: train
    path: data/post-ochinrikestidningar-1890/*.parquet
- config_name: posttidningar-1640
  data_files:
  - split: train
    path: data/posttidningar-1640/*.parquet
- config_name: posttidningar-1650
  data_files:
  - split: train
    path: data/posttidningar-1650/*.parquet
- config_name: posttidningar-1660
  data_files:
  - split: train
    path: data/posttidningar-1660/*.parquet
- config_name: posttidningar-1670
  data_files:
  - split: train
    path: data/posttidningar-1670/*.parquet
- config_name: posttidningar-1680
  data_files:
  - split: train
    path: data/posttidningar-1680/*.parquet
- config_name: posttidningar-1690
  data_files:
  - split: train
    path: data/posttidningar-1690/*.parquet
- config_name: posttidningar-1700
  data_files:
  - split: train
    path: data/posttidningar-1700/*.parquet
- config_name: posttidningar-1710
  data_files:
  - split: train
    path: data/posttidningar-1710/*.parquet
- config_name: posttidningar-1720
  data_files:
  - split: train
    path: data/posttidningar-1720/*.parquet
- config_name: posttidningar-1730
  data_files:
  - split: train
    path: data/posttidningar-1730/*.parquet
- config_name: posttidningar-1740
  data_files:
  - split: train
    path: data/posttidningar-1740/*.parquet
- config_name: posttidningar-1750
  data_files:
  - split: train
    path: data/posttidningar-1750/*.parquet
- config_name: posttidningar-1760
  data_files:
  - split: train
    path: data/posttidningar-1760/*.parquet
- config_name: posttidningar-1770
  data_files:
  - split: train
    path: data/posttidningar-1770/*.parquet
- config_name: posttidningar-1780
  data_files:
  - split: train
    path: data/posttidningar-1780/*.parquet
- config_name: posttidningar-1790
  data_files:
  - split: train
    path: data/posttidningar-1790/*.parquet
- config_name: posttidningar-1800
  data_files:
  - split: train
    path: data/posttidningar-1800/*.parquet
- config_name: posttidningar-1810
  data_files:
  - split: train
    path: data/posttidningar-1810/*.parquet
- config_name: posttidningar-1820
  data_files:
  - split: train
    path: data/posttidningar-1820/*.parquet
- config_name: stnlk-1870
  data_files:
  - split: train
    path: data/stnlk-1870/*.parquet
- config_name: stockholmsdagblad-1820
  data_files:
  - split: train
    path: data/stockholmsdagblad-1820/*.parquet
- config_name: stockholmsdagblad-1830
  data_files:
  - split: train
    path: data/stockholmsdagblad-1830/*.parquet
- config_name: stockholmsdagblad-1840
  data_files:
  - split: train
    path: data/stockholmsdagblad-1840/*.parquet
- config_name: stockholmsdagblad-1850
  data_files:
  - split: train
    path: data/stockholmsdagblad-1850/*.parquet
- config_name: stockholmsdagblad-1860
  data_files:
  - split: train
    path: data/stockholmsdagblad-1860/*.parquet
- config_name: stockholmsdagblad-1870
  data_files:
  - split: train
    path: data/stockholmsdagblad-1870/*.parquet
- config_name: stockholmsdagblad-1880
  data_files:
  - split: train
    path: data/stockholmsdagblad-1880/*.parquet
- config_name: stockholmsdagblad-1890
  data_files:
  - split: train
    path: data/stockholmsdagblad-1890/*.parquet
- config_name: stockholmsposten-1770
  data_files:
  - split: train
    path: data/stockholmsposten-1770/*.parquet
- config_name: stockholmsposten-1780
  data_files:
  - split: train
    path: data/stockholmsposten-1780/*.parquet
- config_name: stockholmsposten-1790
  data_files:
  - split: train
    path: data/stockholmsposten-1790/*.parquet
- config_name: stockholmsposten-1800
  data_files:
  - split: train
    path: data/stockholmsposten-1800/*.parquet
- config_name: stockholmsposten-1810
  data_files:
  - split: train
    path: data/stockholmsposten-1810/*.parquet
- config_name: stockholmsposten-1820
  data_files:
  - split: train
    path: data/stockholmsposten-1820/*.parquet
- config_name: stockholmsposten-1830
  data_files:
  - split: train
    path: data/stockholmsposten-1830/*.parquet
- config_name: sundsvallstidning-1880
  data_files:
  - split: train
    path: data/sundsvallstidning-1880/*.parquet
- config_name: sundsvallstidning-1890
  data_files:
  - split: train
    path: data/sundsvallstidning-1890/*.parquet
- config_name: tfwbsol-1840
  data_files:
  - split: train
    path: data/tfwbsol-1840/*.parquet
- config_name: tfwbsol-1850
  data_files:
  - split: train
    path: data/tfwbsol-1850/*.parquet
- config_name: tfwbsol-1860
  data_files:
  - split: train
    path: data/tfwbsol-1860/*.parquet
- config_name: tfwbsol-1870
  data_files:
  - split: train
    path: data/tfwbsol-1870/*.parquet
- config_name: tfwbsol-1880
  data_files:
  - split: train
    path: data/tfwbsol-1880/*.parquet
- config_name: tfwbsol-1890
  data_files:
  - split: train
    path: data/tfwbsol-1890/*.parquet
- config_name: umebladet-1840
  data_files:
  - split: train
    path: data/umebladet-1840/*.parquet
- config_name: umebladet-1850
  data_files:
  - split: train
    path: data/umebladet-1850/*.parquet
- config_name: umebladet-1860
  data_files:
  - split: train
    path: data/umebladet-1860/*.parquet
- config_name: umebladet-1870
  data_files:
  - split: train
    path: data/umebladet-1870/*.parquet
- config_name: umebladet-1880
  data_files:
  - split: train
    path: data/umebladet-1880/*.parquet
- config_name: umebladet-1890
  data_files:
  - split: train
    path: data/umebladet-1890/*.parquet
- config_name: upsala-1840
  data_files:
  - split: train
    path: data/upsala-1840/*.parquet
- config_name: upsala-1850
  data_files:
  - split: train
    path: data/upsala-1850/*.parquet
- config_name: upsala-1860
  data_files:
  - split: train
    path: data/upsala-1860/*.parquet
- config_name: upsala-1870
  data_files:
  - split: train
    path: data/upsala-1870/*.parquet
- config_name: upsala-1880
  data_files:
  - split: train
    path: data/upsala-1880/*.parquet
- config_name: upsala-1890
  data_files:
  - split: train
    path: data/upsala-1890/*.parquet
- config_name: vestmanlandslanstidning-1830
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1830/*.parquet
- config_name: vestmanlandslanstidning-1840
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1840/*.parquet
- config_name: vestmanlandslanstidning-1850
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1850/*.parquet
- config_name: vestmanlandslanstidning-1860
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1860/*.parquet
- config_name: vestmanlandslanstidning-1870
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1870/*.parquet
- config_name: vestmanlandslanstidning-1880
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1880/*.parquet
- config_name: vestmanlandslanstidning-1890
  data_files:
  - split: train
    path: data/vestmanlandslanstidning-1890/*.parquet
- config_name: wermlandslanstidning-1870
  data_files:
  - split: train
    path: data/wermlandslanstidning-1870/*.parquet
- config_name: wermlandstidningen-1840
  data_files:
  - split: train
    path: data/wermlandstidningen-1840/*.parquet
- config_name: wermlandstidningen-1850
  data_files:
  - split: train
    path: data/wermlandstidningen-1850/*.parquet
- config_name: wernamotidning-1870
  data_files:
  - split: train
    path: data/wernamotidning-1870/*.parquet
- config_name: wernamotidning-1880
  data_files:
  - split: train
    path: data/wernamotidning-1880/*.parquet
- config_name: wexjobladet-1810
  data_files:
  - split: train
    path: data/wexjobladet-1810/*.parquet
- config_name: wexjobladet-1820
  data_files:
  - split: train
    path: data/wexjobladet-1820/*.parquet
- config_name: wexjobladet-1830
  data_files:
  - split: train
    path: data/wexjobladet-1830/*.parquet
- config_name: wexjobladet-1840
  data_files:
  - split: train
    path: data/wexjobladet-1840/*.parquet
- config_name: wexjobladet-1850
  data_files:
  - split: train
    path: data/wexjobladet-1850/*.parquet
- config_name: rd-prop
  data_files:
  - split: train
    path: data/rd-prop/*.parquet
- config_name: rd-sou
  data_files:
  - split: train
    path: data/rd-sou/*.parquet
- config_name: rd-prot
  data_files:
  - split: train
    path: data/rd-prot/*.parquet
- config_name: rd-bet
  data_files:
  - split: train
    path: data/rd-bet/*.parquet
- config_name: rd-mot
  data_files:
  - split: train
    path: data/rd-mot/*.parquet
- config_name: rd-ds
  data_files:
  - split: train
    path: data/rd-ds/*.parquet
- config_name: rd-ovr
  data_files:
  - split: train
    path: data/rd-ovr/*.parquet
- config_name: sfs
  data_files:
  - split: train
    path: data/sfs/*.parquet
- config_name: rd-frsrdg
  data_files:
  - split: train
    path: data/rd-frsrdg/*.parquet
- config_name: rd-skfr
  data_files:
  - split: train
    path: data/rd-skfr/*.parquet
- config_name: rd-yttr
  data_files:
  - split: train
    path: data/rd-yttr/*.parquet
- config_name: rd-utsk
  data_files:
  - split: train
    path: data/rd-utsk/*.parquet
- config_name: rd-fpm
  data_files:
  - split: train
    path: data/rd-fpm/*.parquet
- config_name: rd-ip
  data_files:
  - split: train
    path: data/rd-ip/*.parquet
- config_name: rd-kom
  data_files:
  - split: train
    path: data/rd-kom/*.parquet
- config_name: rd-kammakt
  data_files:
  - split: train
    path: data/rd-kammakt/*.parquet
- config_name: rd-utr
  data_files:
  - split: train
    path: data/rd-utr/*.parquet
- config_name: rd-anf-1993-2018
  data_files:
  - split: train
    path: data/rd-anf-1993-2018/*.parquet
- config_name: mosel-voxpopuli
  data_files:
  - split: train
    path: data/mosel-voxpopuli/*.parquet
- config_name: mosel-youtube-commons
  data_files:
  - split: train
    path: data/mosel-youtube-commons/*.parquet
- config_name: kalmar-1910
  data_files:
  - split: train
    path: data/kalmar-1910/*.parquet
- config_name: dalpilen-1910
  data_files:
  - split: train
    path: data/dalpilen-1910/*.parquet
- config_name: dalpilen-1920
  data_files:
  - split: train
    path: data/dalpilen-1920/*.parquet
- config_name: ostgotaposten-1910
  data_files:
  - split: train
    path: data/ostgotaposten-1910/*.parquet
- config_name: sweachum
  data_files:
  - split: train
    path: data/sweachum/*.parquet
- config_name: sweacsam
  data_files:
  - split: train
    path: data/sweacsam/*.parquet
- config_name: bloggmix1998
  data_files:
  - split: train
    path: data/bloggmix1998/*.parquet
- config_name: bloggmix1999
  data_files:
  - split: train
    path: data/bloggmix1999/*.parquet
- config_name: bloggmix2000
  data_files:
  - split: train
    path: data/bloggmix2000/*.parquet
- config_name: bloggmix2001
  data_files:
  - split: train
    path: data/bloggmix2001/*.parquet
- config_name: bloggmix2002
  data_files:
  - split: train
    path: data/bloggmix2002/*.parquet
- config_name: bloggmix2003
  data_files:
  - split: train
    path: data/bloggmix2003/*.parquet
- config_name: bloggmix2004
  data_files:
  - split: train
    path: data/bloggmix2004/*.parquet
- config_name: bloggmix2005
  data_files:
  - split: train
    path: data/bloggmix2005/*.parquet
- config_name: bloggmix2006
  data_files:
  - split: train
    path: data/bloggmix2006/*.parquet
- config_name: bloggmix2007
  data_files:
  - split: train
    path: data/bloggmix2007/*.parquet
- config_name: bloggmix2008
  data_files:
  - split: train
    path: data/bloggmix2008/*.parquet
- config_name: bloggmix2009
  data_files:
  - split: train
    path: data/bloggmix2009/*.parquet
- config_name: bloggmix2010
  data_files:
  - split: train
    path: data/bloggmix2010/*.parquet
- config_name: bloggmix2011
  data_files:
  - split: train
    path: data/bloggmix2011/*.parquet
- config_name: bloggmix2012
  data_files:
  - split: train
    path: data/bloggmix2012/*.parquet
- config_name: bloggmix2013
  data_files:
  - split: train
    path: data/bloggmix2013/*.parquet
- config_name: bloggmix2014
  data_files:
  - split: train
    path: data/bloggmix2014/*.parquet
- config_name: bloggmix2015
  data_files:
  - split: train
    path: data/bloggmix2015/*.parquet
- config_name: bloggmix2016
  data_files:
  - split: train
    path: data/bloggmix2016/*.parquet
- config_name: bloggmix2017
  data_files:
  - split: train
    path: data/bloggmix2017/*.parquet
- config_name: bloggmixodat
  data_files:
  - split: train
    path: data/bloggmixodat/*.parquet
- config_name: press65
  data_files:
  - split: train
    path: data/press65/*.parquet
- config_name: press76
  data_files:
  - split: train
    path: data/press76/*.parquet
- config_name: press95
  data_files:
  - split: train
    path: data/press95/*.parquet
- config_name: press96
  data_files:
  - split: train
    path: data/press96/*.parquet
- config_name: press97
  data_files:
  - split: train
    path: data/press97/*.parquet
- config_name: press98
  data_files:
  - split: train
    path: data/press98/*.parquet
- config_name: gp1994
  data_files:
  - split: train
    path: data/gp1994/*.parquet
- config_name: gp2001
  data_files:
  - split: train
    path: data/gp2001/*.parquet
- config_name: gp2002
  data_files:
  - split: train
    path: data/gp2002/*.parquet
- config_name: gp2003
  data_files:
  - split: train
    path: data/gp2003/*.parquet
- config_name: gp2004
  data_files:
  - split: train
    path: data/gp2004/*.parquet
- config_name: gp2005
  data_files:
  - split: train
    path: data/gp2005/*.parquet
- config_name: gp2006
  data_files:
  - split: train
    path: data/gp2006/*.parquet
- config_name: gp2007
  data_files:
  - split: train
    path: data/gp2007/*.parquet
- config_name: gp2008
  data_files:
  - split: train
    path: data/gp2008/*.parquet
- config_name: gp2009
  data_files:
  - split: train
    path: data/gp2009/*.parquet
- config_name: gp2010
  data_files:
  - split: train
    path: data/gp2010/*.parquet
- config_name: gp2011
  data_files:
  - split: train
    path: data/gp2011/*.parquet
- config_name: gp2012
  data_files:
  - split: train
    path: data/gp2012/*.parquet
- config_name: gp2013
  data_files:
  - split: train
    path: data/gp2013/*.parquet
- config_name: attasidor
  data_files:
  - split: train
    path: data/attasidor/*.parquet
- config_name: svt-2004
  data_files:
  - split: train
    path: data/svt-2004/*.parquet
- config_name: svt-2005
  data_files:
  - split: train
    path: data/svt-2005/*.parquet
- config_name: svt-2006
  data_files:
  - split: train
    path: data/svt-2006/*.parquet
- config_name: svt-2007
  data_files:
  - split: train
    path: data/svt-2007/*.parquet
- config_name: svt-2008
  data_files:
  - split: train
    path: data/svt-2008/*.parquet
- config_name: svt-2009
  data_files:
  - split: train
    path: data/svt-2009/*.parquet
- config_name: svt-2010
  data_files:
  - split: train
    path: data/svt-2010/*.parquet
- config_name: svt-2011
  data_files:
  - split: train
    path: data/svt-2011/*.parquet
- config_name: svt-2012
  data_files:
  - split: train
    path: data/svt-2012/*.parquet
- config_name: svt-2013
  data_files:
  - split: train
    path: data/svt-2013/*.parquet
- config_name: svt-2014
  data_files:
  - split: train
    path: data/svt-2014/*.parquet
- config_name: svt-2015
  data_files:
  - split: train
    path: data/svt-2015/*.parquet
- config_name: svt-2016
  data_files:
  - split: train
    path: data/svt-2016/*.parquet
- config_name: svt-2017
  data_files:
  - split: train
    path: data/svt-2017/*.parquet
- config_name: svt-2018
  data_files:
  - split: train
    path: data/svt-2018/*.parquet
- config_name: svt-2019
  data_files:
  - split: train
    path: data/svt-2019/*.parquet
- config_name: svt-2020
  data_files:
  - split: train
    path: data/svt-2020/*.parquet
- config_name: svt-2021
  data_files:
  - split: train
    path: data/svt-2021/*.parquet
- config_name: svt-2022
  data_files:
  - split: train
    path: data/svt-2022/*.parquet
- config_name: svt-2023
  data_files:
  - split: train
    path: data/svt-2023/*.parquet
- config_name: svt-nodate
  data_files:
  - split: train
    path: data/svt-nodate/*.parquet
- config_name: gutenberg
  data_files:
  - split: train
    path: data/gutenberg/*.parquet
- config_name: runeberg-diverse
  data_files:
  - split: train
    path: data/runeberg-diverse/*.parquet
- config_name: runeberg-folkbbl
  data_files:
  - split: train
    path: data/runeberg-folkbbl/*.parquet
- config_name: runeberg-rost
  data_files:
  - split: train
    path: data/runeberg-rost/*.parquet
- config_name: runeberg-tiden
  data_files:
  - split: train
    path: data/runeberg-tiden/*.parquet
- config_name: runeberg-urdagkron
  data_files:
  - split: train
    path: data/runeberg-urdagkron/*.parquet
- config_name: bellman
  data_files:
  - split: train
    path: data/bellman/*.parquet
- config_name: drama
  data_files:
  - split: train
    path: data/drama/*.parquet
- config_name: lb-restricted
  data_files:
  - split: train
    path: data/lb-restricted/*.parquet
- config_name: swedish-pd
  data_files:
  - split: train
    path: data/swedish-pd/*.parquet
- config_name: riksarkivet-goteborg-lines
  data_files:
  - split: train
    path: data/riksarkivet-goteborg-lines/*.parquet
- config_name: riksarkivet-svea-hovratt-lines
  data_files:
  - split: train
    path: data/riksarkivet-svea-hovratt-lines/*.parquet
- config_name: riksarkivet-krigshovratten-lines
  data_files:
  - split: train
    path: data/riksarkivet-krigshovratten-lines/*.parquet
- config_name: riksarkivet-bergskollegium-lines
  data_files:
  - split: train
    path: data/riksarkivet-bergskollegium-lines/*.parquet
- config_name: riksarkivet-frihetstiden-lines
  data_files:
  - split: train
    path: data/riksarkivet-frihetstiden-lines/*.parquet
- config_name: riksarkivet-pahlman-lines
  data_files:
  - split: train
    path: data/riksarkivet-pahlman-lines/*.parquet
- config_name: riksarkivet-trolldom-lines
  data_files:
  - split: train
    path: data/riksarkivet-trolldom-lines/*.parquet
- config_name: riksarkivet-gota-hovratt-lines
  data_files:
  - split: train
    path: data/riksarkivet-gota-hovratt-lines/*.parquet
- config_name: riksarkivet-bergmastaren-lines
  data_files:
  - split: train
    path: data/riksarkivet-bergmastaren-lines/*.parquet
- config_name: riksarkivet-alvsborgs-losen-lines
  data_files:
  - split: train
    path: data/riksarkivet-alvsborgs-losen-lines/*.parquet
- config_name: riksarkivet-jonkoping-lines
  data_files:
  - split: train
    path: data/riksarkivet-jonkoping-lines/*.parquet
- config_name: wikisource
  data_files:
  - split: train
    path: data/wikisource/*.parquet
language_bcp47:
- swe
---

# 🧨 Swedish Dynaword


<!-- START README TABLE -->
|  |  |
| --- | --- |
| **Version** | 0.0.26 ([Changelog](CHANGELOG.md)) |
| **Language** | Swedish (sv, swe) |
| **License** | Openly Licensed, See the respective dataset |
| **Models** | Currently there is no models trained on this dataset |
| **Contact** | If you have question about this project please create an issue [here](https://huggingface.co/datasets/danish-foundation-models/swedish-dynaword/discussions) |



<!-- END README TABLE -->

## Table of Contents
- [🧨 Swedish Dynaword](#-swedish-dynaword)
  - [Table of Contents](#table-of-contents)
  - [Dataset Description](#dataset-description)
    - [Dataset Summary](#dataset-summary)
    - [Loading the dataset](#loading-the-dataset)
    - [Languages](#languages)
    - [Domains](#domains)
    - [Licensing](#licensing)
  - [Dataset Structure](#dataset-structure)
    - [Data Instances](#data-instances)
    - [Data Fields](#data-fields)
    - [Data Splits](#data-splits)
  - [Dataset Creation](#dataset-creation)
    - [Curation Rationale](#curation-rationale)
    - [Annotations](#annotations)
    - [Source Data](#source-data)
    - [Data Collection and Processing](#data-collection-and-processing)
    - [Dataset Statistics](#dataset-statistics)
    - [Contributing to the dataset](#contributing-to-the-dataset)
  - [Citation Information](#citation-information)
  - [License information](#license-information)
    - [Personal and Sensitive Information](#personal-and-sensitive-information)
    - [Bias, Risks, and Limitations](#bias-risks-and-limitations)
    - [Notice and takedown policy](#notice-and-takedown-policy)

## Dataset Description

<!-- START-DESC-STATS -->
- **Number of samples**: 624.94M
- **Number of tokens (Llama 3)**: 43.51B
- **Average document length in tokens (min, max)**: 69.63 (2, 8.14M)
<!-- END-DESC-STATS -->


### Dataset Summary

The Swedish dynaword is a collection of Swedish free-form text datasets from various domains. All of the datasets in the Swedish Dynaword are openly licensed 
and deemed permissible for training large language models. 

Swedish dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. If you would like to contribute a dataset see the [contribute section](#contributing-to-the-dataset).

### Loading the dataset

```py
from datasets import load_dataset

name = "danish-foundation-models/swedish-dynaword"
ds = load_dataset(name, split = "train")
sample = ds[1] # see "Data Instances" below
```

or load it by streaming the data
```py
ds = load_dataset(name, split = "train", streaming=True)
dataset_iter = iter(ds)
sample = next(iter(dataset_iter))
```

You can also load a single subset at a time:
```py
ds = load_dataset(name, "lag1800", split = "train")
```


As Swedish dynaword is continually expanding and curated you can make sure that you get the same dataset every time by specifying the revision:
You can also load a single subset at a time:
```py
ds = load_dataset(name, revision="{desired revision}")
```

### Languages
This dataset includes the following languages:

- Swedish (swe-Latn) 

In addition it likely contains small amounts of English due to code-switching and Scandinavian languages due to language misclassificaitons due to their similarity.

Language is denoted using [BCP-47](https://en.wikipedia.org/wiki/IETF_language_tag), using the langauge code ISO [639-3](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) and the script code [ISO 15924](https://en.wikipedia.org/wiki/ISO_15924).

<!-- START-LANGUAGE TABLE -->
| Language | Sources | N. Tokens |
| :--- | :--- | :--- |
| sv | [dalpilen-1860], [lag1800], [svensk-tidskrift], [statens-offentliga-utredningar], [biblioteksbladet], [riksdagen-forfattningssamling], [riksdagen-reglementen], [riksdagen-register], [riksdagen-skrivelser], [riksdagen-utredningar], [riksdagen-berattelser], [riksdagen-motioner], [riksdagen-betankanden], [riksdagen-propositioner], [riksdagen-protokoll], [cellar], [flashback-dator], [flashback-droger], [flashback-ekonomi], [flashback-fordon], [flashback-hem], [flashback-kultur], [flashback-livsstil], [flashback-mat], [flashback-om-flashback], [flashback-ovrigt], [flashback-politik], [flashback-resor], [flashback-samhalle], [flashback-sex], [flashback-sport], [flashback-vetenskap], [familjeliv-adoption], [familjeliv-allmanna-ekonomi], [familjeliv-allmanna-familjeliv], [familjeliv-allmanna-fritid], [familjeliv-allmanna-husdjur], [familjeliv-allmanna-hushem], [familjeliv-allmanna-kropp], [familjeliv-allmanna-noje], [familjeliv-allmanna-samhalle], [familjeliv-allmanna-sandladan], [familjeliv-anglarum], [familjeliv-expert], [familjeliv-foralder], [familjeliv-gravid], [familjeliv-kansliga], [familjeliv-medlem-allmanna], [familjeliv-medlem-foraldrar], [familjeliv-medlem-planerarbarn], [familjeliv-medlem-vantarbarn], [familjeliv-pappagrupp], [familjeliv-planerarbarn], [familjeliv-sexsamlevnad], [familjeliv-svartattfabarn], [lb-open], [poeter], [wikipedia-sv], [europarl-sv], [laakartidningen], [fsv-aldrelagar], [fsv-aldrereligiosprosa], [fsv-nysvenskbibel], [fsv-nysvenskdalin], [fsv-nysvenskkronikor], [fsv-nysvensklagar], [fsv-nysvenskovrigt], [fsv-profanprosa], [fsv-verser], [fsv-yngrelagar], [fsv-yngrereligiosprosa], [fsv-yngretankebocker], [standsriksdagen-adelsstandet], [standsriksdagen-bihang], [standsriksdagen-bondestandet], [standsriksdagen-borgarstandet], [standsriksdagen-prastestandet], [standsriksdagen-riksdagsakter], [standsriksdagen-riksdagsbeslut], [strindbergromaner], [strindbergbrev], [dramadialog], [bibel1917], [psalmboken], [akademiliv], [dagens-arena], [gu-journalen], [forskning-framsteg], [sv-covid-19], [aftonbladet-1830], [aftonbladet-1840], [aftonbladet-1850], [aftonbladet-1860], [aftonbladet-1870], [aftonbladet-1880], [aftonbladet-1890], [aftonbladet-1900], [alfwarochskamt-1840], [barometern-1840], [barometern-1850], [barometern-1860], [barometern-1870], [barometern-1880], [barometern-1890], [blekingsposten-1850], [blekingsposten-1860], [blekingsposten-1870], [blekingsposten-1880], [bollnastidning-1870], [bollnastidning-1880], [borastidning-1830], [borastidning-1840], [borastidning-1850], [borastidning-1860], [borastidning-1870], [borastidning-1880], [borastidning-1890], [carlscronastidningar-1760], [carlscronaswekoblad-1750], [carlscronaswekoblad-1760], [carlscronaswekoblad-1770], [carlscronaswekoblad-1780], [carlscronaswekoblad-1790], [carlscronaswekoblad-1800], [carlscronaswekoblad-1810], [carlscronaswekoblad-1820], [carlscronaswekoblad-1830], [carlscronaswekoblad-1840], [carlscronaswekoblad-1850], [carlscronaswekoblad-1860], [carlscronaswekoblad-1870], [dagligtallehanda-1760], [dagligtallehanda-1770], [dagligtallehanda-1780], [dagligtallehanda-1790], [dagligtallehanda-1800], [dagligtallehanda-1810], [dagligtallehanda-1820], [dagligtallehanda-1830], [dagligtallehanda-1840], [dalpilen-1850], [dalpilen-1870], [dalpilen-1880], [dalpilen-1890], [dalpilen-1900], [fahluweckoblad-1780], [fahluweckoblad-1790], [fahluweckoblad-1800], [fahluweckoblad-1810], [fahluweckoblad-1820], [falkopingstidning-1850], [falkopingstidning-1860], [falkopingstidning-1870], [falkopingstidning-1880], [falkopingstidning-1890], [faluposten-1860], [faluposten-1870], [faluposten-1880], [faluposten-1890], [folketsrost-1840], [folketsrost-1850], [folketsrost-1860], [ghost-1830], [ghost-1840], [ghost-1850], [ghost-1860], [ghost-1870], [ghost-1880], [ghost-1890], [goteborgsposten-1850], [goteborgsposten-1860], [goteborgsposten-1870], [goteborgsposten-1880], [goteborgsposten-1890], [goteborgsweckoblad-1870], [goteborgsweckoblad-1880], [goteborgsweckoblad-1890], [gotheborgsallehanda-1770], [gotheborgsallehanda-1780], [gotheborgsallehanda-1790], [gotheborgsallehanda-1800], [gotheborgsallehanda-1810], [gotheborgsallehanda-1820], [gotheborgsallehanda-1830], [gotheborgsallehanda-1840], [gotheborgskanyheter-1760], [gotheborgskanyheter-1770], [gotheborgskanyheter-1780], [gotheborgskanyheter-1790], [gotheborgskanyheter-1800], [gotheborgskanyheter-1810], [gotheborgskanyheter-1820], [gotheborgskanyheter-1830], [gotheborgskanyheter-1840], [gotheborgsweckolista-1740], [gotheborgsweckolista-1750], [gotlandstidning-1860], [gotlandstidning-1870], [gotlandstidning-1880], [harnosandsposten-1840], [harnosandsposten-1850], [harnosandsposten-1860], [harnosandsposten-1870], [harnosandsposten-1880], [harnosandsposten-1890], [inrikestidningar-1760], [inrikestidningar-1770], [inrikestidningar-1780], [inrikestidningar-1790], [inrikestidningar-1800], [inrikestidningar-1810], [inrikestidningar-1820], [jonkopingsbladet-1840], [jonkopingsbladet-1850], [jonkopingsbladet-1860], [jonkopingsbladet-1870], [jonkopingsposten-1860], [jonkopingsposten-1870], [jonkopingsposten-1880], [jonkopingsposten-1890], [kalmar-1860], [kalmar-1870], [kalmar-1880], [kalmar-1890], [kalmar-1900], [karlshamnsallehanda-1840], [karlshamnsallehanda-1850], [karlshamnsallehanda-1860], [karlshamnsallehanda-1870], [karlshamnsallehanda-1880], [karlshamnsallehanda-1890], [karlskronaweckoblad-1870], [karlskronaweckoblad-1880], [karlskronaweckoblad-1890], [kristianstadsbladet-1850], [kristianstadsbladet-1860], [kristianstadsbladet-1870], [kristianstadsbladet-1880], [kristianstadsbladet-1890], [lindesbergsallehanda-1870], [lindesbergsallehanda-1880], [lundsweckoblad-1770], [lundsweckoblad-1780], [lundsweckoblad-1810], [lundsweckoblad-1820], [lundsweckoblad-1830], [lundsweckoblad-1840], [lundsweckoblad-1850], [lundsweckoblad-1860], [lundsweckoblad-1870], [lundsweckoblad-1880], [lundsweckoblad-1890], [malmoallehanda-1820], [malmoallehanda-1830], [malmoallehanda-1840], [malmoallehanda-1850], [malmoallehanda-1860], [malmoallehanda-1870], [malmoallehanda-1880], [malmoallehanda-1890], [nerikesallehanda-1840], [nerikesallehanda-1850], [nerikesallehanda-1860], [nerikesallehanda-1870], [nerikesallehanda-1880], [nerikesallehanda-1890], [nlk-1850], [nlk-1860], [nlk-1870], [norden-1850], [norden-1860], [norraskane-1880], [norraskane-1890], [norrbottenskuriren-1860], [norrbottenskuriren-1870], [norrbottenskuriren-1880], [norrbottenskuriren-1890], [norrbottensposten-1840], [norrbottensposten-1850], [norrbottensposten-1860], [norrbottensposten-1870], [norrbottensposten-1880], [norrbottensposten-1890], [norrkopingskuriren-1850], [norrkopingskuriren-1860], [norrkopingstidningar-1780], [norrkopingstidningar-1790], [norrkopingstidningar-1800], [norrkopingstidningar-1810], [norrkopingstidningar-1820], [norrkopingstidningar-1830], [norrkopingstidningar-1840], [norrkopingstidningar-1850], [norrkopingstidningar-1860], [norrkopingstidningar-1870], [norrkopingstidningar-1880], [norrkopingstidningar-1890], [norrkopingsweckotidningar-1750], [norrkopingsweckotidningar-1760], [norrkopingsweckotidningar-1770], [norrkopingsweckotidningar-1780], [norrlandsposten-1880], [nyadagligtallehanda-1850], [nyadagligtallehanda-1860], [nyadagligtallehanda-1870], [nyadagligtallehanda-1880], [nyadagligtallehanda-1890], [nyakarlskronaweckoblad-1870], [nyawermlandstidningen-1850], [nyawermlandstidningen-1860], [nyawermlandstidningen-1870], [nyawermlandstidningen-1880], [nyawermlandstidningen-1890], [nyawexjobladet-1840], [nyawexjobladet-1850], [nyawexjobladet-1860], [nyawexjobladet-1870], [nyawexjobladet-1880], [nyawexjobladet-1890], [nyttallvarochskamt-1840], [nyttallvarochskamt-1850], [nyttochgammalt-1780], [nyttochgammalt-1790], [nyttochgammalt-1800], [nyttochgammalt-1810], [ostergotlandsveckoblad-1880], [ostergotlandsveckoblad-1890], [ostgotacorrespondenten-1830], [ostgotacorrespondenten-1840], [ostgotacorrespondenten-1850], [ostgotacorrespondenten-1860], [ostgotacorrespondenten-1870], [ostgotacorrespondenten-1880], [ostgotacorrespondenten-1890], [ostgotaposten-1890], [ostgotaposten-1900], [post-ochinrikestidningar-1820], [post-ochinrikestidningar-1830], [post-ochinrikestidningar-1840], [post-ochinrikestidningar-1850], [post-ochinrikestidningar-1860], [post-ochinrikestidningar-1870], [post-ochinrikestidningar-1880], [post-ochinrikestidningar-1890], [posttidningar-1640], [posttidningar-1650], [posttidningar-1660], [posttidningar-1670], [posttidningar-1680], [posttidningar-1690], [posttidningar-1700], [posttidningar-1710], [posttidningar-1720], [posttidningar-1730], [posttidningar-1740], [posttidningar-1750], [posttidningar-1760], [posttidningar-1770], [posttidningar-1780], [posttidningar-1790], [posttidningar-1800], [posttidningar-1810], [posttidningar-1820], [stnlk-1870], [stockholmsdagblad-1820], [stockholmsdagblad-1830], [stockholmsdagblad-1840], [stockholmsdagblad-1850], [stockholmsdagblad-1860], [stockholmsdagblad-1870], [stockholmsdagblad-1880], [stockholmsdagblad-1890], [stockholmsposten-1770], [stockholmsposten-1780], [stockholmsposten-1790], [stockholmsposten-1800], [stockholmsposten-1810], [stockholmsposten-1820], [stockholmsposten-1830], [sundsvallstidning-1880], [sundsvallstidning-1890], [tfwbsol-1840], [tfwbsol-1850], [tfwbsol-1860], [tfwbsol-1870], [tfwbsol-1880], [tfwbsol-1890], [umebladet-1840], [umebladet-1850], [umebladet-1860], [umebladet-1870], [umebladet-1880], [umebladet-1890], [upsala-1840], [upsala-1850], [upsala-1860], [upsala-1870], [upsala-1880], [upsala-1890], [vestmanlandslanstidning-1830], [vestmanlandslanstidning-1840], [vestmanlandslanstidning-1850], [vestmanlandslanstidning-1860], [vestmanlandslanstidning-1870], [vestmanlandslanstidning-1880], [vestmanlandslanstidning-1890], [wermlandslanstidning-1870], [wermlandstidningen-1840], [wermlandstidningen-1850], [wernamotidning-1870], [wernamotidning-1880], [wexjobladet-1810], [wexjobladet-1820], [wexjobladet-1830], [wexjobladet-1840], [wexjobladet-1850], [rd-prop], [rd-sou], [rd-prot], [rd-bet], [rd-mot], [rd-ds], [rd-ovr], [sfs], [rd-frsrdg], [rd-skfr], [rd-yttr], [rd-utsk], [rd-fpm], [rd-ip], [rd-kom], [rd-kammakt], [rd-utr], [rd-anf-1993-2018], [mosel-voxpopuli], [mosel-youtube-commons], [kalmar-1910], [dalpilen-1910], [dalpilen-1920], [ostgotaposten-1910], [sweachum], [sweacsam], [bloggmix1998], [bloggmix1999], [bloggmix2000], [bloggmix2001], [bloggmix2002], [bloggmix2003], [bloggmix2004], [bloggmix2005], [bloggmix2006], [bloggmix2007], [bloggmix2008], [bloggmix2009], [bloggmix2010], [bloggmix2011], [bloggmix2012], [bloggmix2013], [bloggmix2014], [bloggmix2015], [bloggmix2016], [bloggmix2017], [bloggmixodat], [press65], [press76], [press95], [press96], [press97], [press98], [gp1994], [gp2001], [gp2002], [gp2003], [gp2004], [gp2005], [gp2006], [gp2007], [gp2008], [gp2009], [gp2010], [gp2011], [gp2012], [gp2013], [attasidor], [svt-2004], [svt-2005], [svt-2006], [svt-2007], [svt-2008], [svt-2009], [svt-2010], [svt-2011], [svt-2012], [svt-2013], [svt-2014], [svt-2015], [svt-2016], [svt-2017], [svt-2018], [svt-2019], [svt-2020], [svt-2021], [svt-2022], [svt-2023], [svt-nodate], [gutenberg], [runeberg-diverse], [runeberg-folkbbl], [runeberg-rost], [runeberg-tiden], [runeberg-urdagkron], [bellman], [drama], [lb-restricted], [swedish-pd], [riksarkivet-goteborg-lines], [riksarkivet-svea-hovratt-lines], [riksarkivet-krigshovratten-lines], [riksarkivet-bergskollegium-lines], [riksarkivet-frihetstiden-lines], [riksarkivet-pahlman-lines], [riksarkivet-trolldom-lines], [riksarkivet-gota-hovratt-lines], [riksarkivet-bergmastaren-lines], [riksarkivet-alvsborgs-losen-lines], [riksarkivet-jonkoping-lines], [wikisource] | 43.51B |
| **Total** |  | 43.51B |

[dalpilen-1860]: data/dalpilen-1860/dalpilen-1860.md
[lag1800]: data/lag1800/lag1800.md
[svensk-tidskrift]: data/svensk-tidskrift/svensk-tidskrift.md
[statens-offentliga-utredningar]: data/statens-offentliga-utredningar/statens-offentliga-utredningar.md
[biblioteksbladet]: data/biblioteksbladet/biblioteksbladet.md
[riksdagen-forfattningssamling]: data/riksdagen-forfattningssamling/riksdagen-forfattningssamling.md
[riksdagen-reglementen]: data/riksdagen-reglementen/riksdagen-reglementen.md
[riksdagen-register]: data/riksdagen-register/riksdagen-register.md
[riksdagen-skrivelser]: data/riksdagen-skrivelser/riksdagen-skrivelser.md
[riksdagen-utredningar]: data/riksdagen-utredningar/riksdagen-utredningar.md
[riksdagen-berattelser]: data/riksdagen-berattelser/riksdagen-berattelser.md
[riksdagen-motioner]: data/riksdagen-motioner/riksdagen-motioner.md
[riksdagen-betankanden]: data/riksdagen-betankanden/riksdagen-betankanden.md
[riksdagen-propositioner]: data/riksdagen-propositioner/riksdagen-propositioner.md
[riksdagen-protokoll]: data/riksdagen-protokoll/riksdagen-protokoll.md
[cellar]: data/cellar/cellar.md
[flashback-dator]: data/flashback-dator/flashback-dator.md
[flashback-droger]: data/flashback-droger/flashback-droger.md
[flashback-ekonomi]: data/flashback-ekonomi/flashback-ekonomi.md
[flashback-fordon]: data/flashback-fordon/flashback-fordon.md
[flashback-hem]: data/flashback-hem/flashback-hem.md
[flashback-kultur]: data/flashback-kultur/flashback-kultur.md
[flashback-livsstil]: data/flashback-livsstil/flashback-livsstil.md
[flashback-mat]: data/flashback-mat/flashback-mat.md
[flashback-om-flashback]: data/flashback-om-flashback/flashback-om-flashback.md
[flashback-ovrigt]: data/flashback-ovrigt/flashback-ovrigt.md
[flashback-politik]: data/flashback-politik/flashback-politik.md
[flashback-resor]: data/flashback-resor/flashback-resor.md
[flashback-samhalle]: data/flashback-samhalle/flashback-samhalle.md
[flashback-sex]: data/flashback-sex/flashback-sex.md
[flashback-sport]: data/flashback-sport/flashback-sport.md
[flashback-vetenskap]: data/flashback-vetenskap/flashback-vetenskap.md
[familjeliv-adoption]: data/familjeliv-adoption/familjeliv-adoption.md
[familjeliv-allmanna-ekonomi]: data/familjeliv-allmanna-ekonomi/familjeliv-allmanna-ekonomi.md
[familjeliv-allmanna-familjeliv]: data/familjeliv-allmanna-familjeliv/familjeliv-allmanna-familjeliv.md
[familjeliv-allmanna-fritid]: data/familjeliv-allmanna-fritid/familjeliv-allmanna-fritid.md
[familjeliv-allmanna-husdjur]: data/familjeliv-allmanna-husdjur/familjeliv-allmanna-husdjur.md
[familjeliv-allmanna-hushem]: data/familjeliv-allmanna-hushem/familjeliv-allmanna-hushem.md
[familjeliv-allmanna-kropp]: data/familjeliv-allmanna-kropp/familjeliv-allmanna-kropp.md
[familjeliv-allmanna-noje]: data/familjeliv-allmanna-noje/familjeliv-allmanna-noje.md
[familjeliv-allmanna-samhalle]: data/familjeliv-allmanna-samhalle/familjeliv-allmanna-samhalle.md
[familjeliv-allmanna-sandladan]: data/familjeliv-allmanna-sandladan/familjeliv-allmanna-sandladan.md
[familjeliv-anglarum]: data/familjeliv-anglarum/familjeliv-anglarum.md
[familjeliv-expert]: data/familjeliv-expert/familjeliv-expert.md
[familjeliv-foralder]: data/familjeliv-foralder/familjeliv-foralder.md
[familjeliv-gravid]: data/familjeliv-gravid/familjeliv-gravid.md
[familjeliv-kansliga]: data/familjeliv-kansliga/familjeliv-kansliga.md
[familjeliv-medlem-allmanna]: data/familjeliv-medlem-allmanna/familjeliv-medlem-allmanna.md
[familjeliv-medlem-foraldrar]: data/familjeliv-medlem-foraldrar/familjeliv-medlem-foraldrar.md
[familjeliv-medlem-planerarbarn]: data/familjeliv-medlem-planerarbarn/familjeliv-medlem-planerarbarn.md
[familjeliv-medlem-vantarbarn]: data/familjeliv-medlem-vantarbarn/familjeliv-medlem-vantarbarn.md
[familjeliv-pappagrupp]: data/familjeliv-pappagrupp/familjeliv-pappagrupp.md
[familjeliv-planerarbarn]: data/familjeliv-planerarbarn/familjeliv-planerarbarn.md
[familjeliv-sexsamlevnad]: data/familjeliv-sexsamlevnad/familjeliv-sexsamlevnad.md
[familjeliv-svartattfabarn]: data/familjeliv-svartattfabarn/familjeliv-svartattfabarn.md
[lb-open]: data/lb-open/lb-open.md
[poeter]: data/poeter/poeter.md
[wikipedia-sv]: data/wikipedia-sv/wikipedia-sv.md
[europarl-sv]: data/europarl-sv/europarl-sv.md
[laakartidningen]: data/laakartidningen/laakartidningen.md
[fsv-aldrelagar]: data/fsv-aldrelagar/fsv-aldrelagar.md
[fsv-aldrereligiosprosa]: data/fsv-aldrereligiosprosa/fsv-aldrereligiosprosa.md
[fsv-nysvenskbibel]: data/fsv-nysvenskbibel/fsv-nysvenskbibel.md
[fsv-nysvenskdalin]: data/fsv-nysvenskdalin/fsv-nysvenskdalin.md
[fsv-nysvenskkronikor]: data/fsv-nysvenskkronikor/fsv-nysvenskkronikor.md
[fsv-nysvensklagar]: data/fsv-nysvensklagar/fsv-nysvensklagar.md
[fsv-nysvenskovrigt]: data/fsv-nysvenskovrigt/fsv-nysvenskovrigt.md
[fsv-profanprosa]: data/fsv-profanprosa/fsv-profanprosa.md
[fsv-verser]: data/fsv-verser/fsv-verser.md
[fsv-yngrelagar]: data/fsv-yngrelagar/fsv-yngrelagar.md
[fsv-yngrereligiosprosa]: data/fsv-yngrereligiosprosa/fsv-yngrereligiosprosa.md
[fsv-yngretankebocker]: data/fsv-yngretankebocker/fsv-yngretankebocker.md
[standsriksdagen-adelsstandet]: data/standsriksdagen-adelsstandet/standsriksdagen-adelsstandet.md
[standsriksdagen-bihang]: data/standsriksdagen-bihang/standsriksdagen-bihang.md
[standsriksdagen-bondestandet]: data/standsriksdagen-bondestandet/standsriksdagen-bondestandet.md
[standsriksdagen-borgarstandet]: data/standsriksdagen-borgarstandet/standsriksdagen-borgarstandet.md
[standsriksdagen-prastestandet]: data/standsriksdagen-prastestandet/standsriksdagen-prastestandet.md
[standsriksdagen-riksdagsakter]: data/standsriksdagen-riksdagsakter/standsriksdagen-riksdagsakter.md
[standsriksdagen-riksdagsbeslut]: data/standsriksdagen-riksdagsbeslut/standsriksdagen-riksdagsbeslut.md
[strindbergromaner]: data/strindbergromaner/strindbergromaner.md
[strindbergbrev]: data/strindbergbrev/strindbergbrev.md
[dramadialog]: data/dramadialog/dramadialog.md
[bibel1917]: data/bibel1917/bibel1917.md
[psalmboken]: data/psalmboken/psalmboken.md
[akademiliv]: data/akademiliv/akademiliv.md
[dagens-arena]: data/dagens-arena/dagens-arena.md
[gu-journalen]: data/gu-journalen/gu-journalen.md
[forskning-framsteg]: data/forskning-framsteg/forskning-framsteg.md
[sv-covid-19]: data/sv-covid-19/sv-covid-19.md
[aftonbladet-1830]: data/aftonbladet-1830/aftonbladet-1830.md
[aftonbladet-1840]: data/aftonbladet-1840/aftonbladet-1840.md
[aftonbladet-1850]: data/aftonbladet-1850/aftonbladet-1850.md
[aftonbladet-1860]: data/aftonbladet-1860/aftonbladet-1860.md
[aftonbladet-1870]: data/aftonbladet-1870/aftonbladet-1870.md
[aftonbladet-1880]: data/aftonbladet-1880/aftonbladet-1880.md
[aftonbladet-1890]: data/aftonbladet-1890/aftonbladet-1890.md
[aftonbladet-1900]: data/aftonbladet-1900/aftonbladet-1900.md
[alfwarochskamt-1840]: data/alfwarochskamt-1840/alfwarochskamt-1840.md
[barometern-1840]: data/barometern-1840/barometern-1840.md
[barometern-1850]: data/barometern-1850/barometern-1850.md
[barometern-1860]: data/barometern-1860/barometern-1860.md
[barometern-1870]: data/barometern-1870/barometern-1870.md
[barometern-1880]: data/barometern-1880/barometern-1880.md
[barometern-1890]: data/barometern-1890/barometern-1890.md
[blekingsposten-1850]: data/blekingsposten-1850/blekingsposten-1850.md
[blekingsposten-1860]: data/blekingsposten-1860/blekingsposten-1860.md
[blekingsposten-1870]: data/blekingsposten-1870/blekingsposten-1870.md
[blekingsposten-1880]: data/blekingsposten-1880/blekingsposten-1880.md
[bollnastidning-1870]: data/bollnastidning-1870/bollnastidning-1870.md
[bollnastidning-1880]: data/bollnastidning-1880/bollnastidning-1880.md
[borastidning-1830]: data/borastidning-1830/borastidning-1830.md
[borastidning-1840]: data/borastidning-1840/borastidning-1840.md
[borastidning-1850]: data/borastidning-1850/borastidning-1850.md
[borastidning-1860]: data/borastidning-1860/borastidning-1860.md
[borastidning-1870]: data/borastidning-1870/borastidning-1870.md
[borastidning-1880]: data/borastidning-1880/borastidning-1880.md
[borastidning-1890]: data/borastidning-1890/borastidning-1890.md
[carlscronastidningar-1760]: data/carlscronastidningar-1760/carlscronastidningar-1760.md
[carlscronaswekoblad-1750]: data/carlscronaswekoblad-1750/carlscronaswekoblad-1750.md
[carlscronaswekoblad-1760]: data/carlscronaswekoblad-1760/carlscronaswekoblad-1760.md
[carlscronaswekoblad-1770]: data/carlscronaswekoblad-1770/carlscronaswekoblad-1770.md
[carlscronaswekoblad-1780]: data/carlscronaswekoblad-1780/carlscronaswekoblad-1780.md
[carlscronaswekoblad-1790]: data/carlscronaswekoblad-1790/carlscronaswekoblad-1790.md
[carlscronaswekoblad-1800]: data/carlscronaswekoblad-1800/carlscronaswekoblad-1800.md
[carlscronaswekoblad-1810]: data/carlscronaswekoblad-1810/carlscronaswekoblad-1810.md
[carlscronaswekoblad-1820]: data/carlscronaswekoblad-1820/carlscronaswekoblad-1820.md
[carlscronaswekoblad-1830]: data/carlscronaswekoblad-1830/carlscronaswekoblad-1830.md
[carlscronaswekoblad-1840]: data/carlscronaswekoblad-1840/carlscronaswekoblad-1840.md
[carlscronaswekoblad-1850]: data/carlscronaswekoblad-1850/carlscronaswekoblad-1850.md
[carlscronaswekoblad-1860]: data/carlscronaswekoblad-1860/carlscronaswekoblad-1860.md
[carlscronaswekoblad-1870]: data/carlscronaswekoblad-1870/carlscronaswekoblad-1870.md
[dagligtallehanda-1760]: data/dagligtallehanda-1760/dagligtallehanda-1760.md
[dagligtallehanda-1770]: data/dagligtallehanda-1770/dagligtallehanda-1770.md
[dagligtallehanda-1780]: data/dagligtallehanda-1780/dagligtallehanda-1780.md
[dagligtallehanda-1790]: data/dagligtallehanda-1790/dagligtallehanda-1790.md
[dagligtallehanda-1800]: data/dagligtallehanda-1800/dagligtallehanda-1800.md
[dagligtallehanda-1810]: data/dagligtallehanda-1810/dagligtallehanda-1810.md
[dagligtallehanda-1820]: data/dagligtallehanda-1820/dagligtallehanda-1820.md
[dagligtallehanda-1830]: data/dagligtallehanda-1830/dagligtallehanda-1830.md
[dagligtallehanda-1840]: data/dagligtallehanda-1840/dagligtallehanda-1840.md
[dalpilen-1850]: data/dalpilen-1850/dalpilen-1850.md
[dalpilen-1870]: data/dalpilen-1870/dalpilen-1870.md
[dalpilen-1880]: data/dalpilen-1880/dalpilen-1880.md
[dalpilen-1890]: data/dalpilen-1890/dalpilen-1890.md
[dalpilen-1900]: data/dalpilen-1900/dalpilen-1900.md
[fahluweckoblad-1780]: data/fahluweckoblad-1780/fahluweckoblad-1780.md
[fahluweckoblad-1790]: data/fahluweckoblad-1790/fahluweckoblad-1790.md
[fahluweckoblad-1800]: data/fahluweckoblad-1800/fahluweckoblad-1800.md
[fahluweckoblad-1810]: data/fahluweckoblad-1810/fahluweckoblad-1810.md
[fahluweckoblad-1820]: data/fahluweckoblad-1820/fahluweckoblad-1820.md
[falkopingstidning-1850]: data/falkopingstidning-1850/falkopingstidning-1850.md
[falkopingstidning-1860]: data/falkopingstidning-1860/falkopingstidning-1860.md
[falkopingstidning-1870]: data/falkopingstidning-1870/falkopingstidning-1870.md
[falkopingstidning-1880]: data/falkopingstidning-1880/falkopingstidning-1880.md
[falkopingstidning-1890]: data/falkopingstidning-1890/falkopingstidning-1890.md
[faluposten-1860]: data/faluposten-1860/faluposten-1860.md
[faluposten-1870]: data/faluposten-1870/faluposten-1870.md
[faluposten-1880]: data/faluposten-1880/faluposten-1880.md
[faluposten-1890]: data/faluposten-1890/faluposten-1890.md
[folketsrost-1840]: data/folketsrost-1840/folketsrost-1840.md
[folketsrost-1850]: data/folketsrost-1850/folketsrost-1850.md
[folketsrost-1860]: data/folketsrost-1860/folketsrost-1860.md
[ghost-1830]: data/ghost-1830/ghost-1830.md
[ghost-1840]: data/ghost-1840/ghost-1840.md
[ghost-1850]: data/ghost-1850/ghost-1850.md
[ghost-1860]: data/ghost-1860/ghost-1860.md
[ghost-1870]: data/ghost-1870/ghost-1870.md
[ghost-1880]: data/ghost-1880/ghost-1880.md
[ghost-1890]: data/ghost-1890/ghost-1890.md
[goteborgsposten-1850]: data/goteborgsposten-1850/goteborgsposten-1850.md
[goteborgsposten-1860]: data/goteborgsposten-1860/goteborgsposten-1860.md
[goteborgsposten-1870]: data/goteborgsposten-1870/goteborgsposten-1870.md
[goteborgsposten-1880]: data/goteborgsposten-1880/goteborgsposten-1880.md
[goteborgsposten-1890]: data/goteborgsposten-1890/goteborgsposten-1890.md
[goteborgsweckoblad-1870]: data/goteborgsweckoblad-1870/goteborgsweckoblad-1870.md
[goteborgsweckoblad-1880]: data/goteborgsweckoblad-1880/goteborgsweckoblad-1880.md
[goteborgsweckoblad-1890]: data/goteborgsweckoblad-1890/goteborgsweckoblad-1890.md
[gotheborgsallehanda-1770]: data/gotheborgsallehanda-1770/gotheborgsallehanda-1770.md
[gotheborgsallehanda-1780]: data/gotheborgsallehanda-1780/gotheborgsallehanda-1780.md
[gotheborgsallehanda-1790]: data/gotheborgsallehanda-1790/gotheborgsallehanda-1790.md
[gotheborgsallehanda-1800]: data/gotheborgsallehanda-1800/gotheborgsallehanda-1800.md
[gotheborgsallehanda-1810]: data/gotheborgsallehanda-1810/gotheborgsallehanda-1810.md
[gotheborgsallehanda-1820]: data/gotheborgsallehanda-1820/gotheborgsallehanda-1820.md
[gotheborgsallehanda-1830]: data/gotheborgsallehanda-1830/gotheborgsallehanda-1830.md
[gotheborgsallehanda-1840]: data/gotheborgsallehanda-1840/gotheborgsallehanda-1840.md
[gotheborgskanyheter-1760]: data/gotheborgskanyheter-1760/gotheborgskanyheter-1760.md
[gotheborgskanyheter-1770]: data/gotheborgskanyheter-1770/gotheborgskanyheter-1770.md
[gotheborgskanyheter-1780]: data/gotheborgskanyheter-1780/gotheborgskanyheter-1780.md
[gotheborgskanyheter-1790]: data/gotheborgskanyheter-1790/gotheborgskanyheter-1790.md
[gotheborgskanyheter-1800]: data/gotheborgskanyheter-1800/gotheborgskanyheter-1800.md
[gotheborgskanyheter-1810]: data/gotheborgskanyheter-1810/gotheborgskanyheter-1810.md
[gotheborgskanyheter-1820]: data/gotheborgskanyheter-1820/gotheborgskanyheter-1820.md
[gotheborgskanyheter-1830]: data/gotheborgskanyheter-1830/gotheborgskanyheter-1830.md
[gotheborgskanyheter-1840]: data/gotheborgskanyheter-1840/gotheborgskanyheter-1840.md
[gotheborgsweckolista-1740]: data/gotheborgsweckolista-1740/gotheborgsweckolista-1740.md
[gotheborgsweckolista-1750]: data/gotheborgsweckolista-1750/gotheborgsweckolista-1750.md
[gotlandstidning-1860]: data/gotlandstidning-1860/gotlandstidning-1860.md
[gotlandstidning-1870]: data/gotlandstidning-1870/gotlandstidning-1870.md
[gotlandstidning-1880]: data/gotlandstidning-1880/gotlandstidning-1880.md
[harnosandsposten-1840]: data/harnosandsposten-1840/harnosandsposten-1840.md
[harnosandsposten-1850]: data/harnosandsposten-1850/harnosandsposten-1850.md
[harnosandsposten-1860]: data/harnosandsposten-1860/harnosandsposten-1860.md
[harnosandsposten-1870]: data/harnosandsposten-1870/harnosandsposten-1870.md
[harnosandsposten-1880]: data/harnosandsposten-1880/harnosandsposten-1880.md
[harnosandsposten-1890]: data/harnosandsposten-1890/harnosandsposten-1890.md
[inrikestidningar-1760]: data/inrikestidningar-1760/inrikestidningar-1760.md
[inrikestidningar-1770]: data/inrikestidningar-1770/inrikestidningar-1770.md
[inrikestidningar-1780]: data/inrikestidningar-1780/inrikestidningar-1780.md
[inrikestidningar-1790]: data/inrikestidningar-1790/inrikestidningar-1790.md
[inrikestidningar-1800]: data/inrikestidningar-1800/inrikestidningar-1800.md
[inrikestidningar-1810]: data/inrikestidningar-1810/inrikestidningar-1810.md
[inrikestidningar-1820]: data/inrikestidningar-1820/inrikestidningar-1820.md
[jonkopingsbladet-1840]: data/jonkopingsbladet-1840/jonkopingsbladet-1840.md
[jonkopingsbladet-1850]: data/jonkopingsbladet-1850/jonkopingsbladet-1850.md
[jonkopingsbladet-1860]: data/jonkopingsbladet-1860/jonkopingsbladet-1860.md
[jonkopingsbladet-1870]: data/jonkopingsbladet-1870/jonkopingsbladet-1870.md
[jonkopingsposten-1860]: data/jonkopingsposten-1860/jonkopingsposten-1860.md
[jonkopingsposten-1870]: data/jonkopingsposten-1870/jonkopingsposten-1870.md
[jonkopingsposten-1880]: data/jonkopingsposten-1880/jonkopingsposten-1880.md
[jonkopingsposten-1890]: data/jonkopingsposten-1890/jonkopingsposten-1890.md
[kalmar-1860]: data/kalmar-1860/kalmar-1860.md
[kalmar-1870]: data/kalmar-1870/kalmar-1870.md
[kalmar-1880]: data/kalmar-1880/kalmar-1880.md
[kalmar-1890]: data/kalmar-1890/kalmar-1890.md
[kalmar-1900]: data/kalmar-1900/kalmar-1900.md
[karlshamnsallehanda-1840]: data/karlshamnsallehanda-1840/karlshamnsallehanda-1840.md
[karlshamnsallehanda-1850]: data/karlshamnsallehanda-1850/karlshamnsallehanda-1850.md
[karlshamnsallehanda-1860]: data/karlshamnsallehanda-1860/karlshamnsallehanda-1860.md
[karlshamnsallehanda-1870]: data/karlshamnsallehanda-1870/karlshamnsallehanda-1870.md
[karlshamnsallehanda-1880]: data/karlshamnsallehanda-1880/karlshamnsallehanda-1880.md
[karlshamnsallehanda-1890]: data/karlshamnsallehanda-1890/karlshamnsallehanda-1890.md
[karlskronaweckoblad-1870]: data/karlskronaweckoblad-1870/karlskronaweckoblad-1870.md
[karlskronaweckoblad-1880]: data/karlskronaweckoblad-1880/karlskronaweckoblad-1880.md
[karlskronaweckoblad-1890]: data/karlskronaweckoblad-1890/karlskronaweckoblad-1890.md
[kristianstadsbladet-1850]: data/kristianstadsbladet-1850/kristianstadsbladet-1850.md
[kristianstadsbladet-1860]: data/kristianstadsbladet-1860/kristianstadsbladet-1860.md
[kristianstadsbladet-1870]: data/kristianstadsbladet-1870/kristianstadsbladet-1870.md
[kristianstadsbladet-1880]: data/kristianstadsbladet-1880/kristianstadsbladet-1880.md
[kristianstadsbladet-1890]: data/kristianstadsbladet-1890/kristianstadsbladet-1890.md
[lindesbergsallehanda-1870]: data/lindesbergsallehanda-1870/lindesbergsallehanda-1870.md
[lindesbergsallehanda-1880]: data/lindesbergsallehanda-1880/lindesbergsallehanda-1880.md
[lundsweckoblad-1770]: data/lundsweckoblad-1770/lundsweckoblad-1770.md
[lundsweckoblad-1780]: data/lundsweckoblad-1780/lundsweckoblad-1780.md
[lundsweckoblad-1810]: data/lundsweckoblad-1810/lundsweckoblad-1810.md
[lundsweckoblad-1820]: data/lundsweckoblad-1820/lundsweckoblad-1820.md
[lundsweckoblad-1830]: data/lundsweckoblad-1830/lundsweckoblad-1830.md
[lundsweckoblad-1840]: data/lundsweckoblad-1840/lundsweckoblad-1840.md
[lundsweckoblad-1850]: data/lundsweckoblad-1850/lundsweckoblad-1850.md
[lundsweckoblad-1860]: data/lundsweckoblad-1860/lundsweckoblad-1860.md
[lundsweckoblad-1870]: data/lundsweckoblad-1870/lundsweckoblad-1870.md
[lundsweckoblad-1880]: data/lundsweckoblad-1880/lundsweckoblad-1880.md
[lundsweckoblad-1890]: data/lundsweckoblad-1890/lundsweckoblad-1890.md
[malmoallehanda-1820]: data/malmoallehanda-1820/malmoallehanda-1820.md
[malmoallehanda-1830]: data/malmoallehanda-1830/malmoallehanda-1830.md
[malmoallehanda-1840]: data/malmoallehanda-1840/malmoallehanda-1840.md
[malmoallehanda-1850]: data/malmoallehanda-1850/malmoallehanda-1850.md
[malmoallehanda-1860]: data/malmoallehanda-1860/malmoallehanda-1860.md
[malmoallehanda-1870]: data/malmoallehanda-1870/malmoallehanda-1870.md
[malmoallehanda-1880]: data/malmoallehanda-1880/malmoallehanda-1880.md
[malmoallehanda-1890]: data/malmoallehanda-1890/malmoallehanda-1890.md
[nerikesallehanda-1840]: data/nerikesallehanda-1840/nerikesallehanda-1840.md
[nerikesallehanda-1850]: data/nerikesallehanda-1850/nerikesallehanda-1850.md
[nerikesallehanda-1860]: data/nerikesallehanda-1860/nerikesallehanda-1860.md
[nerikesallehanda-1870]: data/nerikesallehanda-1870/nerikesallehanda-1870.md
[nerikesallehanda-1880]: data/nerikesallehanda-1880/nerikesallehanda-1880.md
[nerikesallehanda-1890]: data/nerikesallehanda-1890/nerikesallehanda-1890.md
[nlk-1850]: data/nlk-1850/nlk-1850.md
[nlk-1860]: data/nlk-1860/nlk-1860.md
[nlk-1870]: data/nlk-1870/nlk-1870.md
[norden-1850]: data/norden-1850/norden-1850.md
[norden-1860]: data/norden-1860/norden-1860.md
[norraskane-1880]: data/norraskane-1880/norraskane-1880.md
[norraskane-1890]: data/norraskane-1890/norraskane-1890.md
[norrbottenskuriren-1860]: data/norrbottenskuriren-1860/norrbottenskuriren-1860.md
[norrbottenskuriren-1870]: data/norrbottenskuriren-1870/norrbottenskuriren-1870.md
[norrbottenskuriren-1880]: data/norrbottenskuriren-1880/norrbottenskuriren-1880.md
[norrbottenskuriren-1890]: data/norrbottenskuriren-1890/norrbottenskuriren-1890.md
[norrbottensposten-1840]: data/norrbottensposten-1840/norrbottensposten-1840.md
[norrbottensposten-1850]: data/norrbottensposten-1850/norrbottensposten-1850.md
[norrbottensposten-1860]: data/norrbottensposten-1860/norrbottensposten-1860.md
[norrbottensposten-1870]: data/norrbottensposten-1870/norrbottensposten-1870.md
[norrbottensposten-1880]: data/norrbottensposten-1880/norrbottensposten-1880.md
[norrbottensposten-1890]: data/norrbottensposten-1890/norrbottensposten-1890.md
[norrkopingskuriren-1850]: data/norrkopingskuriren-1850/norrkopingskuriren-1850.md
[norrkopingskuriren-1860]: data/norrkopingskuriren-1860/norrkopingskuriren-1860.md
[norrkopingstidningar-1780]: data/norrkopingstidningar-1780/norrkopingstidningar-1780.md
[norrkopingstidningar-1790]: data/norrkopingstidningar-1790/norrkopingstidningar-1790.md
[norrkopingstidningar-1800]: data/norrkopingstidningar-1800/norrkopingstidningar-1800.md
[norrkopingstidningar-1810]: data/norrkopingstidningar-1810/norrkopingstidningar-1810.md
[norrkopingstidningar-1820]: data/norrkopingstidningar-1820/norrkopingstidningar-1820.md
[norrkopingstidningar-1830]: data/norrkopingstidningar-1830/norrkopingstidningar-1830.md
[norrkopingstidningar-1840]: data/norrkopingstidningar-1840/norrkopingstidningar-1840.md
[norrkopingstidningar-1850]: data/norrkopingstidningar-1850/norrkopingstidningar-1850.md
[norrkopingstidningar-1860]: data/norrkopingstidningar-1860/norrkopingstidningar-1860.md
[norrkopingstidningar-1870]: data/norrkopingstidningar-1870/norrkopingstidningar-1870.md
[norrkopingstidningar-1880]: data/norrkopingstidningar-1880/norrkopingstidningar-1880.md
[norrkopingstidningar-1890]: data/norrkopingstidningar-1890/norrkopingstidningar-1890.md
[norrkopingsweckotidningar-1750]: data/norrkopingsweckotidningar-1750/norrkopingsweckotidningar-1750.md
[norrkopingsweckotidningar-1760]: data/norrkopingsweckotidningar-1760/norrkopingsweckotidningar-1760.md
[norrkopingsweckotidningar-1770]: data/norrkopingsweckotidningar-1770/norrkopingsweckotidningar-1770.md
[norrkopingsweckotidningar-1780]: data/norrkopingsweckotidningar-1780/norrkopingsweckotidningar-1780.md
[norrlandsposten-1880]: data/norrlandsposten-1880/norrlandsposten-1880.md
[nyadagligtallehanda-1850]: data/nyadagligtallehanda-1850/nyadagligtallehanda-1850.md
[nyadagligtallehanda-1860]: data/nyadagligtallehanda-1860/nyadagligtallehanda-1860.md
[nyadagligtallehanda-1870]: data/nyadagligtallehanda-1870/nyadagligtallehanda-1870.md
[nyadagligtallehanda-1880]: data/nyadagligtallehanda-1880/nyadagligtallehanda-1880.md
[nyadagligtallehanda-1890]: data/nyadagligtallehanda-1890/nyadagligtallehanda-1890.md
[nyakarlskronaweckoblad-1870]: data/nyakarlskronaweckoblad-1870/nyakarlskronaweckoblad-1870.md
[nyawermlandstidningen-1850]: data/nyawermlandstidningen-1850/nyawermlandstidningen-1850.md
[nyawermlandstidningen-1860]: data/nyawermlandstidningen-1860/nyawermlandstidningen-1860.md
[nyawermlandstidningen-1870]: data/nyawermlandstidningen-1870/nyawermlandstidningen-1870.md
[nyawermlandstidningen-1880]: data/nyawermlandstidningen-1880/nyawermlandstidningen-1880.md
[nyawermlandstidningen-1890]: data/nyawermlandstidningen-1890/nyawermlandstidningen-1890.md
[nyawexjobladet-1840]: data/nyawexjobladet-1840/nyawexjobladet-1840.md
[nyawexjobladet-1850]: data/nyawexjobladet-1850/nyawexjobladet-1850.md
[nyawexjobladet-1860]: data/nyawexjobladet-1860/nyawexjobladet-1860.md
[nyawexjobladet-1870]: data/nyawexjobladet-1870/nyawexjobladet-1870.md
[nyawexjobladet-1880]: data/nyawexjobladet-1880/nyawexjobladet-1880.md
[nyawexjobladet-1890]: data/nyawexjobladet-1890/nyawexjobladet-1890.md
[nyttallvarochskamt-1840]: data/nyttallvarochskamt-1840/nyttallvarochskamt-1840.md
[nyttallvarochskamt-1850]: data/nyttallvarochskamt-1850/nyttallvarochskamt-1850.md
[nyttochgammalt-1780]: data/nyttochgammalt-1780/nyttochgammalt-1780.md
[nyttochgammalt-1790]: data/nyttochgammalt-1790/nyttochgammalt-1790.md
[nyttochgammalt-1800]: data/nyttochgammalt-1800/nyttochgammalt-1800.md
[nyttochgammalt-1810]: data/nyttochgammalt-1810/nyttochgammalt-1810.md
[ostergotlandsveckoblad-1880]: data/ostergotlandsveckoblad-1880/ostergotlandsveckoblad-1880.md
[ostergotlandsveckoblad-1890]: data/ostergotlandsveckoblad-1890/ostergotlandsveckoblad-1890.md
[ostgotacorrespondenten-1830]: data/ostgotacorrespondenten-1830/ostgotacorrespondenten-1830.md
[ostgotacorrespondenten-1840]: data/ostgotacorrespondenten-1840/ostgotacorrespondenten-1840.md
[ostgotacorrespondenten-1850]: data/ostgotacorrespondenten-1850/ostgotacorrespondenten-1850.md
[ostgotacorrespondenten-1860]: data/ostgotacorrespondenten-1860/ostgotacorrespondenten-1860.md
[ostgotacorrespondenten-1870]: data/ostgotacorrespondenten-1870/ostgotacorrespondenten-1870.md
[ostgotacorrespondenten-1880]: data/ostgotacorrespondenten-1880/ostgotacorrespondenten-1880.md
[ostgotacorrespondenten-1890]: data/ostgotacorrespondenten-1890/ostgotacorrespondenten-1890.md
[ostgotaposten-1890]: data/ostgotaposten-1890/ostgotaposten-1890.md
[ostgotaposten-1900]: data/ostgotaposten-1900/ostgotaposten-1900.md
[post-ochinrikestidningar-1820]: data/post-ochinrikestidningar-1820/post-ochinrikestidningar-1820.md
[post-ochinrikestidningar-1830]: data/post-ochinrikestidningar-1830/post-ochinrikestidningar-1830.md
[post-ochinrikestidningar-1840]: data/post-ochinrikestidningar-1840/post-ochinrikestidningar-1840.md
[post-ochinrikestidningar-1850]: data/post-ochinrikestidningar-1850/post-ochinrikestidningar-1850.md
[post-ochinrikestidningar-1860]: data/post-ochinrikestidningar-1860/post-ochinrikestidningar-1860.md
[post-ochinrikestidningar-1870]: data/post-ochinrikestidningar-1870/post-ochinrikestidningar-1870.md
[post-ochinrikestidningar-1880]: data/post-ochinrikestidningar-1880/post-ochinrikestidningar-1880.md
[post-ochinrikestidningar-1890]: data/post-ochinrikestidningar-1890/post-ochinrikestidningar-1890.md
[posttidningar-1640]: data/posttidningar-1640/posttidningar-1640.md
[posttidningar-1650]: data/posttidningar-1650/posttidningar-1650.md
[posttidningar-1660]: data/posttidningar-1660/posttidningar-1660.md
[posttidningar-1670]: data/posttidningar-1670/posttidningar-1670.md
[posttidningar-1680]: data/posttidningar-1680/posttidningar-1680.md
[posttidningar-1690]: data/posttidningar-1690/posttidningar-1690.md
[posttidningar-1700]: data/posttidningar-1700/posttidningar-1700.md
[posttidningar-1710]: data/posttidningar-1710/posttidningar-1710.md
[posttidningar-1720]: data/posttidningar-1720/posttidningar-1720.md
[posttidningar-1730]: data/posttidningar-1730/posttidningar-1730.md
[posttidningar-1740]: data/posttidningar-1740/posttidningar-1740.md
[posttidningar-1750]: data/posttidningar-1750/posttidningar-1750.md
[posttidningar-1760]: data/posttidningar-1760/posttidningar-1760.md
[posttidningar-1770]: data/posttidningar-1770/posttidningar-1770.md
[posttidningar-1780]: data/posttidningar-1780/posttidningar-1780.md
[posttidningar-1790]: data/posttidningar-1790/posttidningar-1790.md
[posttidningar-1800]: data/posttidningar-1800/posttidningar-1800.md
[posttidningar-1810]: data/posttidningar-1810/posttidningar-1810.md
[posttidningar-1820]: data/posttidningar-1820/posttidningar-1820.md
[stnlk-1870]: data/stnlk-1870/stnlk-1870.md
[stockholmsdagblad-1820]: data/stockholmsdagblad-1820/stockholmsdagblad-1820.md
[stockholmsdagblad-1830]: data/stockholmsdagblad-1830/stockholmsdagblad-1830.md
[stockholmsdagblad-1840]: data/stockholmsdagblad-1840/stockholmsdagblad-1840.md
[stockholmsdagblad-1850]: data/stockholmsdagblad-1850/stockholmsdagblad-1850.md
[stockholmsdagblad-1860]: data/stockholmsdagblad-1860/stockholmsdagblad-1860.md
[stockholmsdagblad-1870]: data/stockholmsdagblad-1870/stockholmsdagblad-1870.md
[stockholmsdagblad-1880]: data/stockholmsdagblad-1880/stockholmsdagblad-1880.md
[stockholmsdagblad-1890]: data/stockholmsdagblad-1890/stockholmsdagblad-1890.md
[stockholmsposten-1770]: data/stockholmsposten-1770/stockholmsposten-1770.md
[stockholmsposten-1780]: data/stockholmsposten-1780/stockholmsposten-1780.md
[stockholmsposten-1790]: data/stockholmsposten-1790/stockholmsposten-1790.md
[stockholmsposten-1800]: data/stockholmsposten-1800/stockholmsposten-1800.md
[stockholmsposten-1810]: data/stockholmsposten-1810/stockholmsposten-1810.md
[stockholmsposten-1820]: data/stockholmsposten-1820/stockholmsposten-1820.md
[stockholmsposten-1830]: data/stockholmsposten-1830/stockholmsposten-1830.md
[sundsvallstidning-1880]: data/sundsvallstidning-1880/sundsvallstidning-1880.md
[sundsvallstidning-1890]: data/sundsvallstidning-1890/sundsvallstidning-1890.md
[tfwbsol-1840]: data/tfwbsol-1840/tfwbsol-1840.md
[tfwbsol-1850]: data/tfwbsol-1850/tfwbsol-1850.md
[tfwbsol-1860]: data/tfwbsol-1860/tfwbsol-1860.md
[tfwbsol-1870]: data/tfwbsol-1870/tfwbsol-1870.md
[tfwbsol-1880]: data/tfwbsol-1880/tfwbsol-1880.md
[tfwbsol-1890]: data/tfwbsol-1890/tfwbsol-1890.md
[umebladet-1840]: data/umebladet-1840/umebladet-1840.md
[umebladet-1850]: data/umebladet-1850/umebladet-1850.md
[umebladet-1860]: data/umebladet-1860/umebladet-1860.md
[umebladet-1870]: data/umebladet-1870/umebladet-1870.md
[umebladet-1880]: data/umebladet-1880/umebladet-1880.md
[umebladet-1890]: data/umebladet-1890/umebladet-1890.md
[upsala-1840]: data/upsala-1840/upsala-1840.md
[upsala-1850]: data/upsala-1850/upsala-1850.md
[upsala-1860]: data/upsala-1860/upsala-1860.md
[upsala-1870]: data/upsala-1870/upsala-1870.md
[upsala-1880]: data/upsala-1880/upsala-1880.md
[upsala-1890]: data/upsala-1890/upsala-1890.md
[vestmanlandslanstidning-1830]: data/vestmanlandslanstidning-1830/vestmanlandslanstidning-1830.md
[vestmanlandslanstidning-1840]: data/vestmanlandslanstidning-1840/vestmanlandslanstidning-1840.md
[vestmanlandslanstidning-1850]: data/vestmanlandslanstidning-1850/vestmanlandslanstidning-1850.md
[vestmanlandslanstidning-1860]: data/vestmanlandslanstidning-1860/vestmanlandslanstidning-1860.md
[vestmanlandslanstidning-1870]: data/vestmanlandslanstidning-1870/vestmanlandslanstidning-1870.md
[vestmanlandslanstidning-1880]: data/vestmanlandslanstidning-1880/vestmanlandslanstidning-1880.md
[vestmanlandslanstidning-1890]: data/vestmanlandslanstidning-1890/vestmanlandslanstidning-1890.md
[wermlandslanstidning-1870]: data/wermlandslanstidning-1870/wermlandslanstidning-1870.md
[wermlandstidningen-1840]: data/wermlandstidningen-1840/wermlandstidningen-1840.md
[wermlandstidningen-1850]: data/wermlandstidningen-1850/wermlandstidningen-1850.md
[wernamotidning-1870]: data/wernamotidning-1870/wernamotidning-1870.md
[wernamotidning-1880]: data/wernamotidning-1880/wernamotidning-1880.md
[wexjobladet-1810]: data/wexjobladet-1810/wexjobladet-1810.md
[wexjobladet-1820]: data/wexjobladet-1820/wexjobladet-1820.md
[wexjobladet-1830]: data/wexjobladet-1830/wexjobladet-1830.md
[wexjobladet-1840]: data/wexjobladet-1840/wexjobladet-1840.md
[wexjobladet-1850]: data/wexjobladet-1850/wexjobladet-1850.md
[rd-prop]: data/rd-prop/rd-prop.md
[rd-sou]: data/rd-sou/rd-sou.md
[rd-prot]: data/rd-prot/rd-prot.md
[rd-bet]: data/rd-bet/rd-bet.md
[rd-mot]: data/rd-mot/rd-mot.md
[rd-ds]: data/rd-ds/rd-ds.md
[rd-ovr]: data/rd-ovr/rd-ovr.md
[sfs]: data/sfs/sfs.md
[rd-frsrdg]: data/rd-frsrdg/rd-frsrdg.md
[rd-skfr]: data/rd-skfr/rd-skfr.md
[rd-yttr]: data/rd-yttr/rd-yttr.md
[rd-utsk]: data/rd-utsk/rd-utsk.md
[rd-fpm]: data/rd-fpm/rd-fpm.md
[rd-ip]: data/rd-ip/rd-ip.md
[rd-kom]: data/rd-kom/rd-kom.md
[rd-kammakt]: data/rd-kammakt/rd-kammakt.md
[rd-utr]: data/rd-utr/rd-utr.md
[rd-anf-1993-2018]: data/rd-anf-1993-2018/rd-anf-1993-2018.md
[mosel-voxpopuli]: data/mosel-voxpopuli/mosel-voxpopuli.md
[mosel-youtube-commons]: data/mosel-youtube-commons/mosel-youtube-commons.md
[kalmar-1910]: data/kalmar-1910/kalmar-1910.md
[dalpilen-1910]: data/dalpilen-1910/dalpilen-1910.md
[dalpilen-1920]: data/dalpilen-1920/dalpilen-1920.md
[ostgotaposten-1910]: data/ostgotaposten-1910/ostgotaposten-1910.md
[sweachum]: data/sweachum/sweachum.md
[sweacsam]: data/sweacsam/sweacsam.md
[bloggmix1998]: data/bloggmix1998/bloggmix1998.md
[bloggmix1999]: data/bloggmix1999/bloggmix1999.md
[bloggmix2000]: data/bloggmix2000/bloggmix2000.md
[bloggmix2001]: data/bloggmix2001/bloggmix2001.md
[bloggmix2002]: data/bloggmix2002/bloggmix2002.md
[bloggmix2003]: data/bloggmix2003/bloggmix2003.md
[bloggmix2004]: data/bloggmix2004/bloggmix2004.md
[bloggmix2005]: data/bloggmix2005/bloggmix2005.md
[bloggmix2006]: data/bloggmix2006/bloggmix2006.md
[bloggmix2007]: data/bloggmix2007/bloggmix2007.md
[bloggmix2008]: data/bloggmix2008/bloggmix2008.md
[bloggmix2009]: data/bloggmix2009/bloggmix2009.md
[bloggmix2010]: data/bloggmix2010/bloggmix2010.md
[bloggmix2011]: data/bloggmix2011/bloggmix2011.md
[bloggmix2012]: data/bloggmix2012/bloggmix2012.md
[bloggmix2013]: data/bloggmix2013/bloggmix2013.md
[bloggmix2014]: data/bloggmix2014/bloggmix2014.md
[bloggmix2015]: data/bloggmix2015/bloggmix2015.md
[bloggmix2016]: data/bloggmix2016/bloggmix2016.md
[bloggmix2017]: data/bloggmix2017/bloggmix2017.md
[bloggmixodat]: data/bloggmixodat/bloggmixodat.md
[press65]: data/press65/press65.md
[press76]: data/press76/press76.md
[press95]: data/press95/press95.md
[press96]: data/press96/press96.md
[press97]: data/press97/press97.md
[press98]: data/press98/press98.md
[gp1994]: data/gp1994/gp1994.md
[gp2001]: data/gp2001/gp2001.md
[gp2002]: data/gp2002/gp2002.md
[gp2003]: data/gp2003/gp2003.md
[gp2004]: data/gp2004/gp2004.md
[gp2005]: data/gp2005/gp2005.md
[gp2006]: data/gp2006/gp2006.md
[gp2007]: data/gp2007/gp2007.md
[gp2008]: data/gp2008/gp2008.md
[gp2009]: data/gp2009/gp2009.md
[gp2010]: data/gp2010/gp2010.md
[gp2011]: data/gp2011/gp2011.md
[gp2012]: data/gp2012/gp2012.md
[gp2013]: data/gp2013/gp2013.md
[attasidor]: data/attasidor/attasidor.md
[svt-2004]: data/svt-2004/svt-2004.md
[svt-2005]: data/svt-2005/svt-2005.md
[svt-2006]: data/svt-2006/svt-2006.md
[svt-2007]: data/svt-2007/svt-2007.md
[svt-2008]: data/svt-2008/svt-2008.md
[svt-2009]: data/svt-2009/svt-2009.md
[svt-2010]: data/svt-2010/svt-2010.md
[svt-2011]: data/svt-2011/svt-2011.md
[svt-2012]: data/svt-2012/svt-2012.md
[svt-2013]: data/svt-2013/svt-2013.md
[svt-2014]: data/svt-2014/svt-2014.md
[svt-2015]: data/svt-2015/svt-2015.md
[svt-2016]: data/svt-2016/svt-2016.md
[svt-2017]: data/svt-2017/svt-2017.md
[svt-2018]: data/svt-2018/svt-2018.md
[svt-2019]: data/svt-2019/svt-2019.md
[svt-2020]: data/svt-2020/svt-2020.md
[svt-2021]: data/svt-2021/svt-2021.md
[svt-2022]: data/svt-2022/svt-2022.md
[svt-2023]: data/svt-2023/svt-2023.md
[svt-nodate]: data/svt-nodate/svt-nodate.md
[gutenberg]: data/gutenberg/gutenberg.md
[runeberg-diverse]: data/runeberg-diverse/runeberg-diverse.md
[runeberg-folkbbl]: data/runeberg-folkbbl/runeberg-folkbbl.md
[runeberg-rost]: data/runeberg-rost/runeberg-rost.md
[runeberg-tiden]: data/runeberg-tiden/runeberg-tiden.md
[runeberg-urdagkron]: data/runeberg-urdagkron/runeberg-urdagkron.md
[bellman]: data/bellman/bellman.md
[drama]: data/drama/drama.md
[lb-restricted]: data/lb-restricted/lb-restricted.md
[swedish-pd]: data/swedish-pd/swedish-pd.md
[riksarkivet-goteborg-lines]: data/riksarkivet-goteborg-lines/riksarkivet-goteborg-lines.md
[riksarkivet-svea-hovratt-lines]: data/riksarkivet-svea-hovratt-lines/riksarkivet-svea-hovratt-lines.md
[riksarkivet-krigshovratten-lines]: data/riksarkivet-krigshovratten-lines/riksarkivet-krigshovratten-lines.md
[riksarkivet-bergskollegium-lines]: data/riksarkivet-bergskollegium-lines/riksarkivet-bergskollegium-lines.md
[riksarkivet-frihetstiden-lines]: data/riksarkivet-frihetstiden-lines/riksarkivet-frihetstiden-lines.md
[riksarkivet-pahlman-lines]: data/riksarkivet-pahlman-lines/riksarkivet-pahlman-lines.md
[riksarkivet-trolldom-lines]: data/riksarkivet-trolldom-lines/riksarkivet-trolldom-lines.md
[riksarkivet-gota-hovratt-lines]: data/riksarkivet-gota-hovratt-lines/riksarkivet-gota-hovratt-lines.md
[riksarkivet-bergmastaren-lines]: data/riksarkivet-bergmastaren-lines/riksarkivet-bergmastaren-lines.md
[riksarkivet-alvsborgs-losen-lines]: data/riksarkivet-alvsborgs-losen-lines/riksarkivet-alvsborgs-losen-lines.md
[riksarkivet-jonkoping-lines]: data/riksarkivet-jonkoping-lines/riksarkivet-jonkoping-lines.md
[wikisource]: data/wikisource/wikisource.md
<!-- END-LANGUAGE TABLE -->

### Domains

This dynaword consist of data from various domains (e.g., legal, books, social media). The following table and figure give an overview of the relative distributions of these domains. To see a full overview of the source check out the [source data section](#source-data)

<div style="display: flex; gap: 20px; align-items: flex-start;">

<div style="flex: 1;">


<!-- START-DOMAIN TABLE -->
| Domain | Sources | N. Tokens |
| :--- | :--- | :--- |
| Social Media | [flashback-dator], [flashback-droger], [flashback-ekonomi], [flashback-fordon], [flashback-hem], [flashback-kultur], [flashback-livsstil], [flashback-mat], [flashback-om-flashback], [flashback-ovrigt], [flashback-politik], [flashback-resor], [flashback-samhalle], [flashback-sex], [flashback-sport], [flashback-vetenskap], [familjeliv-adoption], [familjeliv-allmanna-ekonomi], [familjeliv-allmanna-familjeliv], [familjeliv-allmanna-fritid], [familjeliv-allmanna-husdjur], [familjeliv-allmanna-hushem], [familjeliv-allmanna-kropp], [familjeliv-allmanna-noje], [familjeliv-allmanna-samhalle], [familjeliv-allmanna-sandladan], [familjeliv-anglarum], [familjeliv-expert], [familjeliv-foralder], [familjeliv-gravid], [familjeliv-kansliga], [familjeliv-medlem-allmanna], [familjeliv-medlem-foraldrar], [familjeliv-medlem-planerarbarn], [familjeliv-medlem-vantarbarn], [familjeliv-pappagrupp], [familjeliv-planerarbarn], [familjeliv-sexsamlevnad], [familjeliv-svartattfabarn], [bloggmix1998], [bloggmix1999], [bloggmix2000], [bloggmix2001], [bloggmix2002], [bloggmix2003], [bloggmix2004], [bloggmix2005], [bloggmix2006], [bloggmix2007], [bloggmix2008], [bloggmix2009], [bloggmix2010], [bloggmix2011], [bloggmix2012], [bloggmix2013], [bloggmix2014], [bloggmix2015], [bloggmix2016], [bloggmix2017], [bloggmixodat] | 15.65B |
| News | [dalpilen-1860], [svensk-tidskrift], [biblioteksbladet], [akademiliv], [dagens-arena], [gu-journalen], [forskning-framsteg], [sv-covid-19], [aftonbladet-1830], [aftonbladet-1840], [aftonbladet-1850], [aftonbladet-1860], [aftonbladet-1870], [aftonbladet-1880], [aftonbladet-1890], [aftonbladet-1900], [alfwarochskamt-1840], [barometern-1840], [barometern-1850], [barometern-1860], [barometern-1870], [barometern-1880], [barometern-1890], [blekingsposten-1850], [blekingsposten-1860], [blekingsposten-1870], [blekingsposten-1880], [bollnastidning-1870], [bollnastidning-1880], [borastidning-1830], [borastidning-1840], [borastidning-1850], [borastidning-1860], [borastidning-1870], [borastidning-1880], [borastidning-1890], [carlscronastidningar-1760], [carlscronaswekoblad-1750], [carlscronaswekoblad-1760], [carlscronaswekoblad-1770], [carlscronaswekoblad-1780], [carlscronaswekoblad-1790], [carlscronaswekoblad-1800], [carlscronaswekoblad-1810], [carlscronaswekoblad-1820], [carlscronaswekoblad-1830], [carlscronaswekoblad-1840], [carlscronaswekoblad-1850], [carlscronaswekoblad-1860], [carlscronaswekoblad-1870], [dagligtallehanda-1760], [dagligtallehanda-1770], [dagligtallehanda-1780], [dagligtallehanda-1790], [dagligtallehanda-1800], [dagligtallehanda-1810], [dagligtallehanda-1820], [dagligtallehanda-1830], [dagligtallehanda-1840], [dalpilen-1850], [dalpilen-1870], [dalpilen-1880], [dalpilen-1890], [dalpilen-1900], [fahluweckoblad-1780], [fahluweckoblad-1790], [fahluweckoblad-1800], [fahluweckoblad-1810], [fahluweckoblad-1820], [falkopingstidning-1850], [falkopingstidning-1860], [falkopingstidning-1870], [falkopingstidning-1880], [falkopingstidning-1890], [faluposten-1860], [faluposten-1870], [faluposten-1880], [faluposten-1890], [folketsrost-1840], [folketsrost-1850], [folketsrost-1860], [ghost-1830], [ghost-1840], [ghost-1850], [ghost-1860], [ghost-1870], [ghost-1880], [ghost-1890], [goteborgsposten-1850], [goteborgsposten-1860], [goteborgsposten-1870], [goteborgsposten-1880], [goteborgsposten-1890], [goteborgsweckoblad-1870], [goteborgsweckoblad-1880], [goteborgsweckoblad-1890], [gotheborgsallehanda-1770], [gotheborgsallehanda-1780], [gotheborgsallehanda-1790], [gotheborgsallehanda-1800], [gotheborgsallehanda-1810], [gotheborgsallehanda-1820], [gotheborgsallehanda-1830], [gotheborgsallehanda-1840], [gotheborgskanyheter-1760], [gotheborgskanyheter-1770], [gotheborgskanyheter-1780], [gotheborgskanyheter-1790], [gotheborgskanyheter-1800], [gotheborgskanyheter-1810], [gotheborgskanyheter-1820], [gotheborgskanyheter-1830], [gotheborgskanyheter-1840], [gotheborgsweckolista-1740], [gotheborgsweckolista-1750], [gotlandstidning-1860], [gotlandstidning-1870], [gotlandstidning-1880], [harnosandsposten-1840], [harnosandsposten-1850], [harnosandsposten-1860], [harnosandsposten-1870], [harnosandsposten-1880], [harnosandsposten-1890], [inrikestidningar-1760], [inrikestidningar-1770], [inrikestidningar-1780], [inrikestidningar-1790], [inrikestidningar-1800], [inrikestidningar-1810], [inrikestidningar-1820], [jonkopingsbladet-1840], [jonkopingsbladet-1850], [jonkopingsbladet-1860], [jonkopingsbladet-1870], [jonkopingsposten-1860], [jonkopingsposten-1870], [jonkopingsposten-1880], [jonkopingsposten-1890], [kalmar-1860], [kalmar-1870], [kalmar-1880], [kalmar-1890], [kalmar-1900], [karlshamnsallehanda-1840], [karlshamnsallehanda-1850], [karlshamnsallehanda-1860], [karlshamnsallehanda-1870], [karlshamnsallehanda-1880], [karlshamnsallehanda-1890], [karlskronaweckoblad-1870], [karlskronaweckoblad-1880], [karlskronaweckoblad-1890], [kristianstadsbladet-1850], [kristianstadsbladet-1860], [kristianstadsbladet-1870], [kristianstadsbladet-1880], [kristianstadsbladet-1890], [lindesbergsallehanda-1870], [lindesbergsallehanda-1880], [lundsweckoblad-1770], [lundsweckoblad-1780], [lundsweckoblad-1810], [lundsweckoblad-1820], [lundsweckoblad-1830], [lundsweckoblad-1840], [lundsweckoblad-1850], [lundsweckoblad-1860], [lundsweckoblad-1870], [lundsweckoblad-1880], [lundsweckoblad-1890], [malmoallehanda-1820], [malmoallehanda-1830], [malmoallehanda-1840], [malmoallehanda-1850], [malmoallehanda-1860], [malmoallehanda-1870], [malmoallehanda-1880], [malmoallehanda-1890], [nerikesallehanda-1840], [nerikesallehanda-1850], [nerikesallehanda-1860], [nerikesallehanda-1870], [nerikesallehanda-1880], [nerikesallehanda-1890], [nlk-1850], [nlk-1860], [nlk-1870], [norden-1850], [norden-1860], [norraskane-1880], [norraskane-1890], [norrbottenskuriren-1860], [norrbottenskuriren-1870], [norrbottenskuriren-1880], [norrbottenskuriren-1890], [norrbottensposten-1840], [norrbottensposten-1850], [norrbottensposten-1860], [norrbottensposten-1870], [norrbottensposten-1880], [norrbottensposten-1890], [norrkopingskuriren-1850], [norrkopingskuriren-1860], [norrkopingstidningar-1780], [norrkopingstidningar-1790], [norrkopingstidningar-1800], [norrkopingstidningar-1810], [norrkopingstidningar-1820], [norrkopingstidningar-1830], [norrkopingstidningar-1840], [norrkopingstidningar-1850], [norrkopingstidningar-1860], [norrkopingstidningar-1870], [norrkopingstidningar-1880], [norrkopingstidningar-1890], [norrkopingsweckotidningar-1750], [norrkopingsweckotidningar-1760], [norrkopingsweckotidningar-1770], [norrkopingsweckotidningar-1780], [norrlandsposten-1880], [nyadagligtallehanda-1850], [nyadagligtallehanda-1860], [nyadagligtallehanda-1870], [nyadagligtallehanda-1880], [nyadagligtallehanda-1890], [nyakarlskronaweckoblad-1870], [nyawermlandstidningen-1850], [nyawermlandstidningen-1860], [nyawermlandstidningen-1870], [nyawermlandstidningen-1880], [nyawermlandstidningen-1890], [nyawexjobladet-1840], [nyawexjobladet-1850], [nyawexjobladet-1860], [nyawexjobladet-1870], [nyawexjobladet-1880], [nyawexjobladet-1890], [nyttallvarochskamt-1840], [nyttallvarochskamt-1850], [nyttochgammalt-1780], [nyttochgammalt-1790], [nyttochgammalt-1800], [nyttochgammalt-1810], [ostergotlandsveckoblad-1880], [ostergotlandsveckoblad-1890], [ostgotacorrespondenten-1830], [ostgotacorrespondenten-1840], [ostgotacorrespondenten-1850], [ostgotacorrespondenten-1860], [ostgotacorrespondenten-1870], [ostgotacorrespondenten-1880], [ostgotacorrespondenten-1890], [ostgotaposten-1890], [ostgotaposten-1900], [post-ochinrikestidningar-1820], [post-ochinrikestidningar-1830], [post-ochinrikestidningar-1840], [post-ochinrikestidningar-1850], [post-ochinrikestidningar-1860], [post-ochinrikestidningar-1870], [post-ochinrikestidningar-1880], [post-ochinrikestidningar-1890], [posttidningar-1640], [posttidningar-1650], [posttidningar-1660], [posttidningar-1670], [posttidningar-1680], [posttidningar-1690], [posttidningar-1700], [posttidningar-1710], [posttidningar-1720], [posttidningar-1730], [posttidningar-1740], [posttidningar-1750], [posttidningar-1760], [posttidningar-1770], [posttidningar-1780], [posttidningar-1790], [posttidningar-1800], [posttidningar-1810], [posttidningar-1820], [stnlk-1870], [stockholmsdagblad-1820], [stockholmsdagblad-1830], [stockholmsdagblad-1840], [stockholmsdagblad-1850], [stockholmsdagblad-1860], [stockholmsdagblad-1870], [stockholmsdagblad-1880], [stockholmsdagblad-1890], [stockholmsposten-1770], [stockholmsposten-1780], [stockholmsposten-1790], [stockholmsposten-1800], [stockholmsposten-1810], [stockholmsposten-1820], [stockholmsposten-1830], [sundsvallstidning-1880], [sundsvallstidning-1890], [tfwbsol-1840], [tfwbsol-1850], [tfwbsol-1860], [tfwbsol-1870], [tfwbsol-1880], [tfwbsol-1890], [umebladet-1840], [umebladet-1850], [umebladet-1860], [umebladet-1870], [umebladet-1880], [umebladet-1890], [upsala-1840], [upsala-1850], [upsala-1860], [upsala-1870], [upsala-1880], [upsala-1890], [vestmanlandslanstidning-1830], [vestmanlandslanstidning-1840], [vestmanlandslanstidning-1850], [vestmanlandslanstidning-1860], [vestmanlandslanstidning-1870], [vestmanlandslanstidning-1880], [vestmanlandslanstidning-1890], [wermlandslanstidning-1870], [wermlandstidningen-1840], [wermlandstidningen-1850], [wernamotidning-1870], [wernamotidning-1880], [wexjobladet-1810], [wexjobladet-1820], [wexjobladet-1830], [wexjobladet-1840], [wexjobladet-1850], [kalmar-1910], [dalpilen-1910], [dalpilen-1920], [ostgotaposten-1910], [press65], [press76], [press95], [press96], [press97], [press98], [gp1994], [gp2001], [gp2002], [gp2003], [gp2004], [gp2005], [gp2006], [gp2007], [gp2008], [gp2009], [gp2010], [gp2011], [gp2012], [gp2013], [attasidor], [svt-2004], [svt-2005], [svt-2006], [svt-2007], [svt-2008], [svt-2009], [svt-2010], [svt-2011], [svt-2012], [svt-2013], [svt-2014], [svt-2015], [svt-2016], [svt-2017], [svt-2018], [svt-2019], [svt-2020], [svt-2021], [svt-2022], [svt-2023], [svt-nodate], [runeberg-diverse], [runeberg-folkbbl], [runeberg-rost], [runeberg-tiden], [runeberg-urdagkron] | 13.17B |
| Legal | [lag1800], [riksdagen-forfattningssamling], [riksdagen-reglementen], [cellar], [fsv-aldrelagar], [fsv-nysvensklagar], [fsv-yngrelagar], [standsriksdagen-adelsstandet], [standsriksdagen-bihang], [standsriksdagen-bondestandet], [standsriksdagen-borgarstandet], [standsriksdagen-prastestandet], [standsriksdagen-riksdagsakter], [standsriksdagen-riksdagsbeslut], [rd-prop], [rd-prot], [rd-bet], [rd-mot], [rd-ovr], [sfs], [rd-frsrdg], [rd-skfr], [rd-yttr], [rd-utsk], [rd-fpm], [rd-ip], [rd-kom], [rd-kammakt], [rd-anf-1993-2018], [riksarkivet-goteborg-lines], [riksarkivet-svea-hovratt-lines], [riksarkivet-krigshovratten-lines], [riksarkivet-frihetstiden-lines], [riksarkivet-trolldom-lines], [riksarkivet-gota-hovratt-lines], [riksarkivet-bergmastaren-lines], [riksarkivet-alvsborgs-losen-lines], [riksarkivet-jonkoping-lines] | 7.91B |
| Report | [statens-offentliga-utredningar], [riksdagen-register], [riksdagen-skrivelser], [riksdagen-utredningar], [riksdagen-berattelser], [riksdagen-motioner], [riksdagen-betankanden], [riksdagen-propositioner], [riksdagen-protokoll], [rd-sou], [rd-ds], [rd-utr], [riksarkivet-bergskollegium-lines] | 3.86B |
| Books | [lb-open], [poeter], [fsv-aldrereligiosprosa], [fsv-nysvenskbibel], [fsv-nysvenskdalin], [fsv-nysvenskkronikor], [fsv-nysvenskovrigt], [fsv-profanprosa], [fsv-verser], [fsv-yngrereligiosprosa], [fsv-yngretankebocker], [strindbergromaner], [strindbergbrev], [dramadialog], [bibel1917], [psalmboken], [gutenberg], [bellman], [drama], [lb-restricted], [swedish-pd], [riksarkivet-pahlman-lines], [wikisource] | 2.22B |
| Encyclopedic | [wikipedia-sv] | 362.29M |
| Spoken | [mosel-voxpopuli], [mosel-youtube-commons] | 205.68M |
| Speeches | [europarl-sv] | 63.02M |
| Academic Writing | [sweachum], [sweacsam] | 46.89M |
| Medical | [laakartidningen] | 42.40M |
| **Total** |  | 43.51B |

[dalpilen-1860]: data/dalpilen-1860/dalpilen-1860.md
[lag1800]: data/lag1800/lag1800.md
[svensk-tidskrift]: data/svensk-tidskrift/svensk-tidskrift.md
[statens-offentliga-utredningar]: data/statens-offentliga-utredningar/statens-offentliga-utredningar.md
[biblioteksbladet]: data/biblioteksbladet/biblioteksbladet.md
[riksdagen-forfattningssamling]: data/riksdagen-forfattningssamling/riksdagen-forfattningssamling.md
[riksdagen-reglementen]: data/riksdagen-reglementen/riksdagen-reglementen.md
[riksdagen-register]: data/riksdagen-register/riksdagen-register.md
[riksdagen-skrivelser]: data/riksdagen-skrivelser/riksdagen-skrivelser.md
[riksdagen-utredningar]: data/riksdagen-utredningar/riksdagen-utredningar.md
[riksdagen-berattelser]: data/riksdagen-berattelser/riksdagen-berattelser.md
[riksdagen-motioner]: data/riksdagen-motioner/riksdagen-motioner.md
[riksdagen-betankanden]: data/riksdagen-betankanden/riksdagen-betankanden.md
[riksdagen-propositioner]: data/riksdagen-propositioner/riksdagen-propositioner.md
[riksdagen-protokoll]: data/riksdagen-protokoll/riksdagen-protokoll.md
[cellar]: data/cellar/cellar.md
[flashback-dator]: data/flashback-dator/flashback-dator.md
[flashback-droger]: data/flashback-droger/flashback-droger.md
[flashback-ekonomi]: data/flashback-ekonomi/flashback-ekonomi.md
[flashback-fordon]: data/flashback-fordon/flashback-fordon.md
[flashback-hem]: data/flashback-hem/flashback-hem.md
[flashback-kultur]: data/flashback-kultur/flashback-kultur.md
[flashback-livsstil]: data/flashback-livsstil/flashback-livsstil.md
[flashback-mat]: data/flashback-mat/flashback-mat.md
[flashback-om-flashback]: data/flashback-om-flashback/flashback-om-flashback.md
[flashback-ovrigt]: data/flashback-ovrigt/flashback-ovrigt.md
[flashback-politik]: data/flashback-politik/flashback-politik.md
[flashback-resor]: data/flashback-resor/flashback-resor.md
[flashback-samhalle]: data/flashback-samhalle/flashback-samhalle.md
[flashback-sex]: data/flashback-sex/flashback-sex.md
[flashback-sport]: data/flashback-sport/flashback-sport.md
[flashback-vetenskap]: data/flashback-vetenskap/flashback-vetenskap.md
[familjeliv-adoption]: data/familjeliv-adoption/familjeliv-adoption.md
[familjeliv-allmanna-ekonomi]: data/familjeliv-allmanna-ekonomi/familjeliv-allmanna-ekonomi.md
[familjeliv-allmanna-familjeliv]: data/familjeliv-allmanna-familjeliv/familjeliv-allmanna-familjeliv.md
[familjeliv-allmanna-fritid]: data/familjeliv-allmanna-fritid/familjeliv-allmanna-fritid.md
[familjeliv-allmanna-husdjur]: data/familjeliv-allmanna-husdjur/familjeliv-allmanna-husdjur.md
[familjeliv-allmanna-hushem]: data/familjeliv-allmanna-hushem/familjeliv-allmanna-hushem.md
[familjeliv-allmanna-kropp]: data/familjeliv-allmanna-kropp/familjeliv-allmanna-kropp.md
[familjeliv-allmanna-noje]: data/familjeliv-allmanna-noje/familjeliv-allmanna-noje.md
[familjeliv-allmanna-samhalle]: data/familjeliv-allmanna-samhalle/familjeliv-allmanna-samhalle.md
[familjeliv-allmanna-sandladan]: data/familjeliv-allmanna-sandladan/familjeliv-allmanna-sandladan.md
[familjeliv-anglarum]: data/familjeliv-anglarum/familjeliv-anglarum.md
[familjeliv-expert]: data/familjeliv-expert/familjeliv-expert.md
[familjeliv-foralder]: data/familjeliv-foralder/familjeliv-foralder.md
[familjeliv-gravid]: data/familjeliv-gravid/familjeliv-gravid.md
[familjeliv-kansliga]: data/familjeliv-kansliga/familjeliv-kansliga.md
[familjeliv-medlem-allmanna]: data/familjeliv-medlem-allmanna/familjeliv-medlem-allmanna.md
[familjeliv-medlem-foraldrar]: data/familjeliv-medlem-foraldrar/familjeliv-medlem-foraldrar.md
[familjeliv-medlem-planerarbarn]: data/familjeliv-medlem-planerarbarn/familjeliv-medlem-planerarbarn.md
[familjeliv-medlem-vantarbarn]: data/familjeliv-medlem-vantarbarn/familjeliv-medlem-vantarbarn.md
[familjeliv-pappagrupp]: data/familjeliv-pappagrupp/familjeliv-pappagrupp.md
[familjeliv-planerarbarn]: data/familjeliv-planerarbarn/familjeliv-planerarbarn.md
[familjeliv-sexsamlevnad]: data/familjeliv-sexsamlevnad/familjeliv-sexsamlevnad.md
[familjeliv-svartattfabarn]: data/familjeliv-svartattfabarn/familjeliv-svartattfabarn.md
[lb-open]: data/lb-open/lb-open.md
[poeter]: data/poeter/poeter.md
[wikipedia-sv]: data/wikipedia-sv/wikipedia-sv.md
[europarl-sv]: data/europarl-sv/europarl-sv.md
[laakartidningen]: data/laakartidningen/laakartidningen.md
[fsv-aldrelagar]: data/fsv-aldrelagar/fsv-aldrelagar.md
[fsv-aldrereligiosprosa]: data/fsv-aldrereligiosprosa/fsv-aldrereligiosprosa.md
[fsv-nysvenskbibel]: data/fsv-nysvenskbibel/fsv-nysvenskbibel.md
[fsv-nysvenskdalin]: data/fsv-nysvenskdalin/fsv-nysvenskdalin.md
[fsv-nysvenskkronikor]: data/fsv-nysvenskkronikor/fsv-nysvenskkronikor.md
[fsv-nysvensklagar]: data/fsv-nysvensklagar/fsv-nysvensklagar.md
[fsv-nysvenskovrigt]: data/fsv-nysvenskovrigt/fsv-nysvenskovrigt.md
[fsv-profanprosa]: data/fsv-profanprosa/fsv-profanprosa.md
[fsv-verser]: data/fsv-verser/fsv-verser.md
[fsv-yngrelagar]: data/fsv-yngrelagar/fsv-yngrelagar.md
[fsv-yngrereligiosprosa]: data/fsv-yngrereligiosprosa/fsv-yngrereligiosprosa.md
[fsv-yngretankebocker]: data/fsv-yngretankebocker/fsv-yngretankebocker.md
[standsriksdagen-adelsstandet]: data/standsriksdagen-adelsstandet/standsriksdagen-adelsstandet.md
[standsriksdagen-bihang]: data/standsriksdagen-bihang/standsriksdagen-bihang.md
[standsriksdagen-bondestandet]: data/standsriksdagen-bondestandet/standsriksdagen-bondestandet.md
[standsriksdagen-borgarstandet]: data/standsriksdagen-borgarstandet/standsriksdagen-borgarstandet.md
[standsriksdagen-prastestandet]: data/standsriksdagen-prastestandet/standsriksdagen-prastestandet.md
[standsriksdagen-riksdagsakter]: data/standsriksdagen-riksdagsakter/standsriksdagen-riksdagsakter.md
[standsriksdagen-riksdagsbeslut]: data/standsriksdagen-riksdagsbeslut/standsriksdagen-riksdagsbeslut.md
[strindbergromaner]: data/strindbergromaner/strindbergromaner.md
[strindbergbrev]: data/strindbergbrev/strindbergbrev.md
[dramadialog]: data/dramadialog/dramadialog.md
[bibel1917]: data/bibel1917/bibel1917.md
[psalmboken]: data/psalmboken/psalmboken.md
[akademiliv]: data/akademiliv/akademiliv.md
[dagens-arena]: data/dagens-arena/dagens-arena.md
[gu-journalen]: data/gu-journalen/gu-journalen.md
[forskning-framsteg]: data/forskning-framsteg/forskning-framsteg.md
[sv-covid-19]: data/sv-covid-19/sv-covid-19.md
[aftonbladet-1830]: data/aftonbladet-1830/aftonbladet-1830.md
[aftonbladet-1840]: data/aftonbladet-1840/aftonbladet-1840.md
[aftonbladet-1850]: data/aftonbladet-1850/aftonbladet-1850.md
[aftonbladet-1860]: data/aftonbladet-1860/aftonbladet-1860.md
[aftonbladet-1870]: data/aftonbladet-1870/aftonbladet-1870.md
[aftonbladet-1880]: data/aftonbladet-1880/aftonbladet-1880.md
[aftonbladet-1890]: data/aftonbladet-1890/aftonbladet-1890.md
[aftonbladet-1900]: data/aftonbladet-1900/aftonbladet-1900.md
[alfwarochskamt-1840]: data/alfwarochskamt-1840/alfwarochskamt-1840.md
[barometern-1840]: data/barometern-1840/barometern-1840.md
[barometern-1850]: data/barometern-1850/barometern-1850.md
[barometern-1860]: data/barometern-1860/barometern-1860.md
[barometern-1870]: data/barometern-1870/barometern-1870.md
[barometern-1880]: data/barometern-1880/barometern-1880.md
[barometern-1890]: data/barometern-1890/barometern-1890.md
[blekingsposten-1850]: data/blekingsposten-1850/blekingsposten-1850.md
[blekingsposten-1860]: data/blekingsposten-1860/blekingsposten-1860.md
[blekingsposten-1870]: data/blekingsposten-1870/blekingsposten-1870.md
[blekingsposten-1880]: data/blekingsposten-1880/blekingsposten-1880.md
[bollnastidning-1870]: data/bollnastidning-1870/bollnastidning-1870.md
[bollnastidning-1880]: data/bollnastidning-1880/bollnastidning-1880.md
[borastidning-1830]: data/borastidning-1830/borastidning-1830.md
[borastidning-1840]: data/borastidning-1840/borastidning-1840.md
[borastidning-1850]: data/borastidning-1850/borastidning-1850.md
[borastidning-1860]: data/borastidning-1860/borastidning-1860.md
[borastidning-1870]: data/borastidning-1870/borastidning-1870.md
[borastidning-1880]: data/borastidning-1880/borastidning-1880.md
[borastidning-1890]: data/borastidning-1890/borastidning-1890.md
[carlscronastidningar-1760]: data/carlscronastidningar-1760/carlscronastidningar-1760.md
[carlscronaswekoblad-1750]: data/carlscronaswekoblad-1750/carlscronaswekoblad-1750.md
[carlscronaswekoblad-1760]: data/carlscronaswekoblad-1760/carlscronaswekoblad-1760.md
[carlscronaswekoblad-1770]: data/carlscronaswekoblad-1770/carlscronaswekoblad-1770.md
[carlscronaswekoblad-1780]: data/carlscronaswekoblad-1780/carlscronaswekoblad-1780.md
[carlscronaswekoblad-1790]: data/carlscronaswekoblad-1790/carlscronaswekoblad-1790.md
[carlscronaswekoblad-1800]: data/carlscronaswekoblad-1800/carlscronaswekoblad-1800.md
[carlscronaswekoblad-1810]: data/carlscronaswekoblad-1810/carlscronaswekoblad-1810.md
[carlscronaswekoblad-1820]: data/carlscronaswekoblad-1820/carlscronaswekoblad-1820.md
[carlscronaswekoblad-1830]: data/carlscronaswekoblad-1830/carlscronaswekoblad-1830.md
[carlscronaswekoblad-1840]: data/carlscronaswekoblad-1840/carlscronaswekoblad-1840.md
[carlscronaswekoblad-1850]: data/carlscronaswekoblad-1850/carlscronaswekoblad-1850.md
[carlscronaswekoblad-1860]: data/carlscronaswekoblad-1860/carlscronaswekoblad-1860.md
[carlscronaswekoblad-1870]: data/carlscronaswekoblad-1870/carlscronaswekoblad-1870.md
[dagligtallehanda-1760]: data/dagligtallehanda-1760/dagligtallehanda-1760.md
[dagligtallehanda-1770]: data/dagligtallehanda-1770/dagligtallehanda-1770.md
[dagligtallehanda-1780]: data/dagligtallehanda-1780/dagligtallehanda-1780.md
[dagligtallehanda-1790]: data/dagligtallehanda-1790/dagligtallehanda-1790.md
[dagligtallehanda-1800]: data/dagligtallehanda-1800/dagligtallehanda-1800.md
[dagligtallehanda-1810]: data/dagligtallehanda-1810/dagligtallehanda-1810.md
[dagligtallehanda-1820]: data/dagligtallehanda-1820/dagligtallehanda-1820.md
[dagligtallehanda-1830]: data/dagligtallehanda-1830/dagligtallehanda-1830.md
[dagligtallehanda-1840]: data/dagligtallehanda-1840/dagligtallehanda-1840.md
[dalpilen-1850]: data/dalpilen-1850/dalpilen-1850.md
[dalpilen-1870]: data/dalpilen-1870/dalpilen-1870.md
[dalpilen-1880]: data/dalpilen-1880/dalpilen-1880.md
[dalpilen-1890]: data/dalpilen-1890/dalpilen-1890.md
[dalpilen-1900]: data/dalpilen-1900/dalpilen-1900.md
[fahluweckoblad-1780]: data/fahluweckoblad-1780/fahluweckoblad-1780.md
[fahluweckoblad-1790]: data/fahluweckoblad-1790/fahluweckoblad-1790.md
[fahluweckoblad-1800]: data/fahluweckoblad-1800/fahluweckoblad-1800.md
[fahluweckoblad-1810]: data/fahluweckoblad-1810/fahluweckoblad-1810.md
[fahluweckoblad-1820]: data/fahluweckoblad-1820/fahluweckoblad-1820.md
[falkopingstidning-1850]: data/falkopingstidning-1850/falkopingstidning-1850.md
[falkopingstidning-1860]: data/falkopingstidning-1860/falkopingstidning-1860.md
[falkopingstidning-1870]: data/falkopingstidning-1870/falkopingstidning-1870.md
[falkopingstidning-1880]: data/falkopingstidning-1880/falkopingstidning-1880.md
[falkopingstidning-1890]: data/falkopingstidning-1890/falkopingstidning-1890.md
[faluposten-1860]: data/faluposten-1860/faluposten-1860.md
[faluposten-1870]: data/faluposten-1870/faluposten-1870.md
[faluposten-1880]: data/faluposten-1880/faluposten-1880.md
[faluposten-1890]: data/faluposten-1890/faluposten-1890.md
[folketsrost-1840]: data/folketsrost-1840/folketsrost-1840.md
[folketsrost-1850]: data/folketsrost-1850/folketsrost-1850.md
[folketsrost-1860]: data/folketsrost-1860/folketsrost-1860.md
[ghost-1830]: data/ghost-1830/ghost-1830.md
[ghost-1840]: data/ghost-1840/ghost-1840.md
[ghost-1850]: data/ghost-1850/ghost-1850.md
[ghost-1860]: data/ghost-1860/ghost-1860.md
[ghost-1870]: data/ghost-1870/ghost-1870.md
[ghost-1880]: data/ghost-1880/ghost-1880.md
[ghost-1890]: data/ghost-1890/ghost-1890.md
[goteborgsposten-1850]: data/goteborgsposten-1850/goteborgsposten-1850.md
[goteborgsposten-1860]: data/goteborgsposten-1860/goteborgsposten-1860.md
[goteborgsposten-1870]: data/goteborgsposten-1870/goteborgsposten-1870.md
[goteborgsposten-1880]: data/goteborgsposten-1880/goteborgsposten-1880.md
[goteborgsposten-1890]: data/goteborgsposten-1890/goteborgsposten-1890.md
[goteborgsweckoblad-1870]: data/goteborgsweckoblad-1870/goteborgsweckoblad-1870.md
[goteborgsweckoblad-1880]: data/goteborgsweckoblad-1880/goteborgsweckoblad-1880.md
[goteborgsweckoblad-1890]: data/goteborgsweckoblad-1890/goteborgsweckoblad-1890.md
[gotheborgsallehanda-1770]: data/gotheborgsallehanda-1770/gotheborgsallehanda-1770.md
[gotheborgsallehanda-1780]: data/gotheborgsallehanda-1780/gotheborgsallehanda-1780.md
[gotheborgsallehanda-1790]: data/gotheborgsallehanda-1790/gotheborgsallehanda-1790.md
[gotheborgsallehanda-1800]: data/gotheborgsallehanda-1800/gotheborgsallehanda-1800.md
[gotheborgsallehanda-1810]: data/gotheborgsallehanda-1810/gotheborgsallehanda-1810.md
[gotheborgsallehanda-1820]: data/gotheborgsallehanda-1820/gotheborgsallehanda-1820.md
[gotheborgsallehanda-1830]: data/gotheborgsallehanda-1830/gotheborgsallehanda-1830.md
[gotheborgsallehanda-1840]: data/gotheborgsallehanda-1840/gotheborgsallehanda-1840.md
[gotheborgskanyheter-1760]: data/gotheborgskanyheter-1760/gotheborgskanyheter-1760.md
[gotheborgskanyheter-1770]: data/gotheborgskanyheter-1770/gotheborgskanyheter-1770.md
[gotheborgskanyheter-1780]: data/gotheborgskanyheter-1780/gotheborgskanyheter-1780.md
[gotheborgskanyheter-1790]: data/gotheborgskanyheter-1790/gotheborgskanyheter-1790.md
[gotheborgskanyheter-1800]: data/gotheborgskanyheter-1800/gotheborgskanyheter-1800.md
[gotheborgskanyheter-1810]: data/gotheborgskanyheter-1810/gotheborgskanyheter-1810.md
[gotheborgskanyheter-1820]: data/gotheborgskanyheter-1820/gotheborgskanyheter-1820.md
[gotheborgskanyheter-1830]: data/gotheborgskanyheter-1830/gotheborgskanyheter-1830.md
[gotheborgskanyheter-1840]: data/gotheborgskanyheter-1840/gotheborgskanyheter-1840.md
[gotheborgsweckolista-1740]: data/gotheborgsweckolista-1740/gotheborgsweckolista-1740.md
[gotheborgsweckolista-1750]: data/gotheborgsweckolista-1750/gotheborgsweckolista-1750.md
[gotlandstidning-1860]: data/gotlandstidning-1860/gotlandstidning-1860.md
[gotlandstidning-1870]: data/gotlandstidning-1870/gotlandstidning-1870.md
[gotlandstidning-1880]: data/gotlandstidning-1880/gotlandstidning-1880.md
[harnosandsposten-1840]: data/harnosandsposten-1840/harnosandsposten-1840.md
[harnosandsposten-1850]: data/harnosandsposten-1850/harnosandsposten-1850.md
[harnosandsposten-1860]: data/harnosandsposten-1860/harnosandsposten-1860.md
[harnosandsposten-1870]: data/harnosandsposten-1870/harnosandsposten-1870.md
[harnosandsposten-1880]: data/harnosandsposten-1880/harnosandsposten-1880.md
[harnosandsposten-1890]: data/harnosandsposten-1890/harnosandsposten-1890.md
[inrikestidningar-1760]: data/inrikestidningar-1760/inrikestidningar-1760.md
[inrikestidningar-1770]: data/inrikestidningar-1770/inrikestidningar-1770.md
[inrikestidningar-1780]: data/inrikestidningar-1780/inrikestidningar-1780.md
[inrikestidningar-1790]: data/inrikestidningar-1790/inrikestidningar-1790.md
[inrikestidningar-1800]: data/inrikestidningar-1800/inrikestidningar-1800.md
[inrikestidningar-1810]: data/inrikestidningar-1810/inrikestidningar-1810.md
[inrikestidningar-1820]: data/inrikestidningar-1820/inrikestidningar-1820.md
[jonkopingsbladet-1840]: data/jonkopingsbladet-1840/jonkopingsbladet-1840.md
[jonkopingsbladet-1850]: data/jonkopingsbladet-1850/jonkopingsbladet-1850.md
[jonkopingsbladet-1860]: data/jonkopingsbladet-1860/jonkopingsbladet-1860.md
[jonkopingsbladet-1870]: data/jonkopingsbladet-1870/jonkopingsbladet-1870.md
[jonkopingsposten-1860]: data/jonkopingsposten-1860/jonkopingsposten-1860.md
[jonkopingsposten-1870]: data/jonkopingsposten-1870/jonkopingsposten-1870.md
[jonkopingsposten-1880]: data/jonkopingsposten-1880/jonkopingsposten-1880.md
[jonkopingsposten-1890]: data/jonkopingsposten-1890/jonkopingsposten-1890.md
[kalmar-1860]: data/kalmar-1860/kalmar-1860.md
[kalmar-1870]: data/kalmar-1870/kalmar-1870.md
[kalmar-1880]: data/kalmar-1880/kalmar-1880.md
[kalmar-1890]: data/kalmar-1890/kalmar-1890.md
[kalmar-1900]: data/kalmar-1900/kalmar-1900.md
[karlshamnsallehanda-1840]: data/karlshamnsallehanda-1840/karlshamnsallehanda-1840.md
[karlshamnsallehanda-1850]: data/karlshamnsallehanda-1850/karlshamnsallehanda-1850.md
[karlshamnsallehanda-1860]: data/karlshamnsallehanda-1860/karlshamnsallehanda-1860.md
[karlshamnsallehanda-1870]: data/karlshamnsallehanda-1870/karlshamnsallehanda-1870.md
[karlshamnsallehanda-1880]: data/karlshamnsallehanda-1880/karlshamnsallehanda-1880.md
[karlshamnsallehanda-1890]: data/karlshamnsallehanda-1890/karlshamnsallehanda-1890.md
[karlskronaweckoblad-1870]: data/karlskronaweckoblad-1870/karlskronaweckoblad-1870.md
[karlskronaweckoblad-1880]: data/karlskronaweckoblad-1880/karlskronaweckoblad-1880.md
[karlskronaweckoblad-1890]: data/karlskronaweckoblad-1890/karlskronaweckoblad-1890.md
[kristianstadsbladet-1850]: data/kristianstadsbladet-1850/kristianstadsbladet-1850.md
[kristianstadsbladet-1860]: data/kristianstadsbladet-1860/kristianstadsbladet-1860.md
[kristianstadsbladet-1870]: data/kristianstadsbladet-1870/kristianstadsbladet-1870.md
[kristianstadsbladet-1880]: data/kristianstadsbladet-1880/kristianstadsbladet-1880.md
[kristianstadsbladet-1890]: data/kristianstadsbladet-1890/kristianstadsbladet-1890.md
[lindesbergsallehanda-1870]: data/lindesbergsallehanda-1870/lindesbergsallehanda-1870.md
[lindesbergsallehanda-1880]: data/lindesbergsallehanda-1880/lindesbergsallehanda-1880.md
[lundsweckoblad-1770]: data/lundsweckoblad-1770/lundsweckoblad-1770.md
[lundsweckoblad-1780]: data/lundsweckoblad-1780/lundsweckoblad-1780.md
[lundsweckoblad-1810]: data/lundsweckoblad-1810/lundsweckoblad-1810.md
[lundsweckoblad-1820]: data/lundsweckoblad-1820/lundsweckoblad-1820.md
[lundsweckoblad-1830]: data/lundsweckoblad-1830/lundsweckoblad-1830.md
[lundsweckoblad-1840]: data/lundsweckoblad-1840/lundsweckoblad-1840.md
[lundsweckoblad-1850]: data/lundsweckoblad-1850/lundsweckoblad-1850.md
[lundsweckoblad-1860]: data/lundsweckoblad-1860/lundsweckoblad-1860.md
[lundsweckoblad-1870]: data/lundsweckoblad-1870/lundsweckoblad-1870.md
[lundsweckoblad-1880]: data/lundsweckoblad-1880/lundsweckoblad-1880.md
[lundsweckoblad-1890]: data/lundsweckoblad-1890/lundsweckoblad-1890.md
[malmoallehanda-1820]: data/malmoallehanda-1820/malmoallehanda-1820.md
[malmoallehanda-1830]: data/malmoallehanda-1830/malmoallehanda-1830.md
[malmoallehanda-1840]: data/malmoallehanda-1840/malmoallehanda-1840.md
[malmoallehanda-1850]: data/malmoallehanda-1850/malmoallehanda-1850.md
[malmoallehanda-1860]: data/malmoallehanda-1860/malmoallehanda-1860.md
[malmoallehanda-1870]: data/malmoallehanda-1870/malmoallehanda-1870.md
[malmoallehanda-1880]: data/malmoallehanda-1880/malmoallehanda-1880.md
[malmoallehanda-1890]: data/malmoallehanda-1890/malmoallehanda-1890.md
[nerikesallehanda-1840]: data/nerikesallehanda-1840/nerikesallehanda-1840.md
[nerikesallehanda-1850]: data/nerikesallehanda-1850/nerikesallehanda-1850.md
[nerikesallehanda-1860]: data/nerikesallehanda-1860/nerikesallehanda-1860.md
[nerikesallehanda-1870]: data/nerikesallehanda-1870/nerikesallehanda-1870.md
[nerikesallehanda-1880]: data/nerikesallehanda-1880/nerikesallehanda-1880.md
[nerikesallehanda-1890]: data/nerikesallehanda-1890/nerikesallehanda-1890.md
[nlk-1850]: data/nlk-1850/nlk-1850.md
[nlk-1860]: data/nlk-1860/nlk-1860.md
[nlk-1870]: data/nlk-1870/nlk-1870.md
[norden-1850]: data/norden-1850/norden-1850.md
[norden-1860]: data/norden-1860/norden-1860.md
[norraskane-1880]: data/norraskane-1880/norraskane-1880.md
[norraskane-1890]: data/norraskane-1890/norraskane-1890.md
[norrbottenskuriren-1860]: data/norrbottenskuriren-1860/norrbottenskuriren-1860.md
[norrbottenskuriren-1870]: data/norrbottenskuriren-1870/norrbottenskuriren-1870.md
[norrbottenskuriren-1880]: data/norrbottenskuriren-1880/norrbottenskuriren-1880.md
[norrbottenskuriren-1890]: data/norrbottenskuriren-1890/norrbottenskuriren-1890.md
[norrbottensposten-1840]: data/norrbottensposten-1840/norrbottensposten-1840.md
[norrbottensposten-1850]: data/norrbottensposten-1850/norrbottensposten-1850.md
[norrbottensposten-1860]: data/norrbottensposten-1860/norrbottensposten-1860.md
[norrbottensposten-1870]: data/norrbottensposten-1870/norrbottensposten-1870.md
[norrbottensposten-1880]: data/norrbottensposten-1880/norrbottensposten-1880.md
[norrbottensposten-1890]: data/norrbottensposten-1890/norrbottensposten-1890.md
[norrkopingskuriren-1850]: data/norrkopingskuriren-1850/norrkopingskuriren-1850.md
[norrkopingskuriren-1860]: data/norrkopingskuriren-1860/norrkopingskuriren-1860.md
[norrkopingstidningar-1780]: data/norrkopingstidningar-1780/norrkopingstidningar-1780.md
[norrkopingstidningar-1790]: data/norrkopingstidningar-1790/norrkopingstidningar-1790.md
[norrkopingstidningar-1800]: data/norrkopingstidningar-1800/norrkopingstidningar-1800.md
[norrkopingstidningar-1810]: data/norrkopingstidningar-1810/norrkopingstidningar-1810.md
[norrkopingstidningar-1820]: data/norrkopingstidningar-1820/norrkopingstidningar-1820.md
[norrkopingstidningar-1830]: data/norrkopingstidningar-1830/norrkopingstidningar-1830.md
[norrkopingstidningar-1840]: data/norrkopingstidningar-1840/norrkopingstidningar-1840.md
[norrkopingstidningar-1850]: data/norrkopingstidningar-1850/norrkopingstidningar-1850.md
[norrkopingstidningar-1860]: data/norrkopingstidningar-1860/norrkopingstidningar-1860.md
[norrkopingstidningar-1870]: data/norrkopingstidningar-1870/norrkopingstidningar-1870.md
[norrkopingstidningar-1880]: data/norrkopingstidningar-1880/norrkopingstidningar-1880.md
[norrkopingstidningar-1890]: data/norrkopingstidningar-1890/norrkopingstidningar-1890.md
[norrkopingsweckotidningar-1750]: data/norrkopingsweckotidningar-1750/norrkopingsweckotidningar-1750.md
[norrkopingsweckotidningar-1760]: data/norrkopingsweckotidningar-1760/norrkopingsweckotidningar-1760.md
[norrkopingsweckotidningar-1770]: data/norrkopingsweckotidningar-1770/norrkopingsweckotidningar-1770.md
[norrkopingsweckotidningar-1780]: data/norrkopingsweckotidningar-1780/norrkopingsweckotidningar-1780.md
[norrlandsposten-1880]: data/norrlandsposten-1880/norrlandsposten-1880.md
[nyadagligtallehanda-1850]: data/nyadagligtallehanda-1850/nyadagligtallehanda-1850.md
[nyadagligtallehanda-1860]: data/nyadagligtallehanda-1860/nyadagligtallehanda-1860.md
[nyadagligtallehanda-1870]: data/nyadagligtallehanda-1870/nyadagligtallehanda-1870.md
[nyadagligtallehanda-1880]: data/nyadagligtallehanda-1880/nyadagligtallehanda-1880.md
[nyadagligtallehanda-1890]: data/nyadagligtallehanda-1890/nyadagligtallehanda-1890.md
[nyakarlskronaweckoblad-1870]: data/nyakarlskronaweckoblad-1870/nyakarlskronaweckoblad-1870.md
[nyawermlandstidningen-1850]: data/nyawermlandstidningen-1850/nyawermlandstidningen-1850.md
[nyawermlandstidningen-1860]: data/nyawermlandstidningen-1860/nyawermlandstidningen-1860.md
[nyawermlandstidningen-1870]: data/nyawermlandstidningen-1870/nyawermlandstidningen-1870.md
[nyawermlandstidningen-1880]: data/nyawermlandstidningen-1880/nyawermlandstidningen-1880.md
[nyawermlandstidningen-1890]: data/nyawermlandstidningen-1890/nyawermlandstidningen-1890.md
[nyawexjobladet-1840]: data/nyawexjobladet-1840/nyawexjobladet-1840.md
[nyawexjobladet-1850]: data/nyawexjobladet-1850/nyawexjobladet-1850.md
[nyawexjobladet-1860]: data/nyawexjobladet-1860/nyawexjobladet-1860.md
[nyawexjobladet-1870]: data/nyawexjobladet-1870/nyawexjobladet-1870.md
[nyawexjobladet-1880]: data/nyawexjobladet-1880/nyawexjobladet-1880.md
[nyawexjobladet-1890]: data/nyawexjobladet-1890/nyawexjobladet-1890.md
[nyttallvarochskamt-1840]: data/nyttallvarochskamt-1840/nyttallvarochskamt-1840.md
[nyttallvarochskamt-1850]: data/nyttallvarochskamt-1850/nyttallvarochskamt-1850.md
[nyttochgammalt-1780]: data/nyttochgammalt-1780/nyttochgammalt-1780.md
[nyttochgammalt-1790]: data/nyttochgammalt-1790/nyttochgammalt-1790.md
[nyttochgammalt-1800]: data/nyttochgammalt-1800/nyttochgammalt-1800.md
[nyttochgammalt-1810]: data/nyttochgammalt-1810/nyttochgammalt-1810.md
[ostergotlandsveckoblad-1880]: data/ostergotlandsveckoblad-1880/ostergotlandsveckoblad-1880.md
[ostergotlandsveckoblad-1890]: data/ostergotlandsveckoblad-1890/ostergotlandsveckoblad-1890.md
[ostgotacorrespondenten-1830]: data/ostgotacorrespondenten-1830/ostgotacorrespondenten-1830.md
[ostgotacorrespondenten-1840]: data/ostgotacorrespondenten-1840/ostgotacorrespondenten-1840.md
[ostgotacorrespondenten-1850]: data/ostgotacorrespondenten-1850/ostgotacorrespondenten-1850.md
[ostgotacorrespondenten-1860]: data/ostgotacorrespondenten-1860/ostgotacorrespondenten-1860.md
[ostgotacorrespondenten-1870]: data/ostgotacorrespondenten-1870/ostgotacorrespondenten-1870.md
[ostgotacorrespondenten-1880]: data/ostgotacorrespondenten-1880/ostgotacorrespondenten-1880.md
[ostgotacorrespondenten-1890]: data/ostgotacorrespondenten-1890/ostgotacorrespondenten-1890.md
[ostgotaposten-1890]: data/ostgotaposten-1890/ostgotaposten-1890.md
[ostgotaposten-1900]: data/ostgotaposten-1900/ostgotaposten-1900.md
[post-ochinrikestidningar-1820]: data/post-ochinrikestidningar-1820/post-ochinrikestidningar-1820.md
[post-ochinrikestidningar-1830]: data/post-ochinrikestidningar-1830/post-ochinrikestidningar-1830.md
[post-ochinrikestidningar-1840]: data/post-ochinrikestidningar-1840/post-ochinrikestidningar-1840.md
[post-ochinrikestidningar-1850]: data/post-ochinrikestidningar-1850/post-ochinrikestidningar-1850.md
[post-ochinrikestidningar-1860]: data/post-ochinrikestidningar-1860/post-ochinrikestidningar-1860.md
[post-ochinrikestidningar-1870]: data/post-ochinrikestidningar-1870/post-ochinrikestidningar-1870.md
[post-ochinrikestidningar-1880]: data/post-ochinrikestidningar-1880/post-ochinrikestidningar-1880.md
[post-ochinrikestidningar-1890]: data/post-ochinrikestidningar-1890/post-ochinrikestidningar-1890.md
[posttidningar-1640]: data/posttidningar-1640/posttidningar-1640.md
[posttidningar-1650]: data/posttidningar-1650/posttidningar-1650.md
[posttidningar-1660]: data/posttidningar-1660/posttidningar-1660.md
[posttidningar-1670]: data/posttidningar-1670/posttidningar-1670.md
[posttidningar-1680]: data/posttidningar-1680/posttidningar-1680.md
[posttidningar-1690]: data/posttidningar-1690/posttidningar-1690.md
[posttidningar-1700]: data/posttidningar-1700/posttidningar-1700.md
[posttidningar-1710]: data/posttidningar-1710/posttidningar-1710.md
[posttidningar-1720]: data/posttidningar-1720/posttidningar-1720.md
[posttidningar-1730]: data/posttidningar-1730/posttidningar-1730.md
[posttidningar-1740]: data/posttidningar-1740/posttidningar-1740.md
[posttidningar-1750]: data/posttidningar-1750/posttidningar-1750.md
[posttidningar-1760]: data/posttidningar-1760/posttidningar-1760.md
[posttidningar-1770]: data/posttidningar-1770/posttidningar-1770.md
[posttidningar-1780]: data/posttidningar-1780/posttidningar-1780.md
[posttidningar-1790]: data/posttidningar-1790/posttidningar-1790.md
[posttidningar-1800]: data/posttidningar-1800/posttidningar-1800.md
[posttidningar-1810]: data/posttidningar-1810/posttidningar-1810.md
[posttidningar-1820]: data/posttidningar-1820/posttidningar-1820.md
[stnlk-1870]: data/stnlk-1870/stnlk-1870.md
[stockholmsdagblad-1820]: data/stockholmsdagblad-1820/stockholmsdagblad-1820.md
[stockholmsdagblad-1830]: data/stockholmsdagblad-1830/stockholmsdagblad-1830.md
[stockholmsdagblad-1840]: data/stockholmsdagblad-1840/stockholmsdagblad-1840.md
[stockholmsdagblad-1850]: data/stockholmsdagblad-1850/stockholmsdagblad-1850.md
[stockholmsdagblad-1860]: data/stockholmsdagblad-1860/stockholmsdagblad-1860.md
[stockholmsdagblad-1870]: data/stockholmsdagblad-1870/stockholmsdagblad-1870.md
[stockholmsdagblad-1880]: data/stockholmsdagblad-1880/stockholmsdagblad-1880.md
[stockholmsdagblad-1890]: data/stockholmsdagblad-1890/stockholmsdagblad-1890.md
[stockholmsposten-1770]: data/stockholmsposten-1770/stockholmsposten-1770.md
[stockholmsposten-1780]: data/stockholmsposten-1780/stockholmsposten-1780.md
[stockholmsposten-1790]: data/stockholmsposten-1790/stockholmsposten-1790.md
[stockholmsposten-1800]: data/stockholmsposten-1800/stockholmsposten-1800.md
[stockholmsposten-1810]: data/stockholmsposten-1810/stockholmsposten-1810.md
[stockholmsposten-1820]: data/stockholmsposten-1820/stockholmsposten-1820.md
[stockholmsposten-1830]: data/stockholmsposten-1830/stockholmsposten-1830.md
[sundsvallstidning-1880]: data/sundsvallstidning-1880/sundsvallstidning-1880.md
[sundsvallstidning-1890]: data/sundsvallstidning-1890/sundsvallstidning-1890.md
[tfwbsol-1840]: data/tfwbsol-1840/tfwbsol-1840.md
[tfwbsol-1850]: data/tfwbsol-1850/tfwbsol-1850.md
[tfwbsol-1860]: data/tfwbsol-1860/tfwbsol-1860.md
[tfwbsol-1870]: data/tfwbsol-1870/tfwbsol-1870.md
[tfwbsol-1880]: data/tfwbsol-1880/tfwbsol-1880.md
[tfwbsol-1890]: data/tfwbsol-1890/tfwbsol-1890.md
[umebladet-1840]: data/umebladet-1840/umebladet-1840.md
[umebladet-1850]: data/umebladet-1850/umebladet-1850.md
[umebladet-1860]: data/umebladet-1860/umebladet-1860.md
[umebladet-1870]: data/umebladet-1870/umebladet-1870.md
[umebladet-1880]: data/umebladet-1880/umebladet-1880.md
[umebladet-1890]: data/umebladet-1890/umebladet-1890.md
[upsala-1840]: data/upsala-1840/upsala-1840.md
[upsala-1850]: data/upsala-1850/upsala-1850.md
[upsala-1860]: data/upsala-1860/upsala-1860.md
[upsala-1870]: data/upsala-1870/upsala-1870.md
[upsala-1880]: data/upsala-1880/upsala-1880.md
[upsala-1890]: data/upsala-1890/upsala-1890.md
[vestmanlandslanstidning-1830]: data/vestmanlandslanstidning-1830/vestmanlandslanstidning-1830.md
[vestmanlandslanstidning-1840]: data/vestmanlandslanstidning-1840/vestmanlandslanstidning-1840.md
[vestmanlandslanstidning-1850]: data/vestmanlandslanstidning-1850/vestmanlandslanstidning-1850.md
[vestmanlandslanstidning-1860]: data/vestmanlandslanstidning-1860/vestmanlandslanstidning-1860.md
[vestmanlandslanstidning-1870]: data/vestmanlandslanstidning-1870/vestmanlandslanstidning-1870.md
[vestmanlandslanstidning-1880]: data/vestmanlandslanstidning-1880/vestmanlandslanstidning-1880.md
[vestmanlandslanstidning-1890]: data/vestmanlandslanstidning-1890/vestmanlandslanstidning-1890.md
[wermlandslanstidning-1870]: data/wermlandslanstidning-1870/wermlandslanstidning-1870.md
[wermlandstidningen-1840]: data/wermlandstidningen-1840/wermlandstidningen-1840.md
[wermlandstidningen-1850]: data/wermlandstidningen-1850/wermlandstidningen-1850.md
[wernamotidning-1870]: data/wernamotidning-1870/wernamotidning-1870.md
[wernamotidning-1880]: data/wernamotidning-1880/wernamotidning-1880.md
[wexjobladet-1810]: data/wexjobladet-1810/wexjobladet-1810.md
[wexjobladet-1820]: data/wexjobladet-1820/wexjobladet-1820.md
[wexjobladet-1830]: data/wexjobladet-1830/wexjobladet-1830.md
[wexjobladet-1840]: data/wexjobladet-1840/wexjobladet-1840.md
[wexjobladet-1850]: data/wexjobladet-1850/wexjobladet-1850.md
[rd-prop]: data/rd-prop/rd-prop.md
[rd-sou]: data/rd-sou/rd-sou.md
[rd-prot]: data/rd-prot/rd-prot.md
[rd-bet]: data/rd-bet/rd-bet.md
[rd-mot]: data/rd-mot/rd-mot.md
[rd-ds]: data/rd-ds/rd-ds.md
[rd-ovr]: data/rd-ovr/rd-ovr.md
[sfs]: data/sfs/sfs.md
[rd-frsrdg]: data/rd-frsrdg/rd-frsrdg.md
[rd-skfr]: data/rd-skfr/rd-skfr.md
[rd-yttr]: data/rd-yttr/rd-yttr.md
[rd-utsk]: data/rd-utsk/rd-utsk.md
[rd-fpm]: data/rd-fpm/rd-fpm.md
[rd-ip]: data/rd-ip/rd-ip.md
[rd-kom]: data/rd-kom/rd-kom.md
[rd-kammakt]: data/rd-kammakt/rd-kammakt.md
[rd-utr]: data/rd-utr/rd-utr.md
[rd-anf-1993-2018]: data/rd-anf-1993-2018/rd-anf-1993-2018.md
[mosel-voxpopuli]: data/mosel-voxpopuli/mosel-voxpopuli.md
[mosel-youtube-commons]: data/mosel-youtube-commons/mosel-youtube-commons.md
[kalmar-1910]: data/kalmar-1910/kalmar-1910.md
[dalpilen-1910]: data/dalpilen-1910/dalpilen-1910.md
[dalpilen-1920]: data/dalpilen-1920/dalpilen-1920.md
[ostgotaposten-1910]: data/ostgotaposten-1910/ostgotaposten-1910.md
[sweachum]: data/sweachum/sweachum.md
[sweacsam]: data/sweacsam/sweacsam.md
[bloggmix1998]: data/bloggmix1998/bloggmix1998.md
[bloggmix1999]: data/bloggmix1999/bloggmix1999.md
[bloggmix2000]: data/bloggmix2000/bloggmix2000.md
[bloggmix2001]: data/bloggmix2001/bloggmix2001.md
[bloggmix2002]: data/bloggmix2002/bloggmix2002.md
[bloggmix2003]: data/bloggmix2003/bloggmix2003.md
[bloggmix2004]: data/bloggmix2004/bloggmix2004.md
[bloggmix2005]: data/bloggmix2005/bloggmix2005.md
[bloggmix2006]: data/bloggmix2006/bloggmix2006.md
[bloggmix2007]: data/bloggmix2007/bloggmix2007.md
[bloggmix2008]: data/bloggmix2008/bloggmix2008.md
[bloggmix2009]: data/bloggmix2009/bloggmix2009.md
[bloggmix2010]: data/bloggmix2010/bloggmix2010.md
[bloggmix2011]: data/bloggmix2011/bloggmix2011.md
[bloggmix2012]: data/bloggmix2012/bloggmix2012.md
[bloggmix2013]: data/bloggmix2013/bloggmix2013.md
[bloggmix2014]: data/bloggmix2014/bloggmix2014.md
[bloggmix2015]: data/bloggmix2015/bloggmix2015.md
[bloggmix2016]: data/bloggmix2016/bloggmix2016.md
[bloggmix2017]: data/bloggmix2017/bloggmix2017.md
[bloggmixodat]: data/bloggmixodat/bloggmixodat.md
[press65]: data/press65/press65.md
[press76]: data/press76/press76.md
[press95]: data/press95/press95.md
[press96]: data/press96/press96.md
[press97]: data/press97/press97.md
[press98]: data/press98/press98.md
[gp1994]: data/gp1994/gp1994.md
[gp2001]: data/gp2001/gp2001.md
[gp2002]: data/gp2002/gp2002.md
[gp2003]: data/gp2003/gp2003.md
[gp2004]: data/gp2004/gp2004.md
[gp2005]: data/gp2005/gp2005.md
[gp2006]: data/gp2006/gp2006.md
[gp2007]: data/gp2007/gp2007.md
[gp2008]: data/gp2008/gp2008.md
[gp2009]: data/gp2009/gp2009.md
[gp2010]: data/gp2010/gp2010.md
[gp2011]: data/gp2011/gp2011.md
[gp2012]: data/gp2012/gp2012.md
[gp2013]: data/gp2013/gp2013.md
[attasidor]: data/attasidor/attasidor.md
[svt-2004]: data/svt-2004/svt-2004.md
[svt-2005]: data/svt-2005/svt-2005.md
[svt-2006]: data/svt-2006/svt-2006.md
[svt-2007]: data/svt-2007/svt-2007.md
[svt-2008]: data/svt-2008/svt-2008.md
[svt-2009]: data/svt-2009/svt-2009.md
[svt-2010]: data/svt-2010/svt-2010.md
[svt-2011]: data/svt-2011/svt-2011.md
[svt-2012]: data/svt-2012/svt-2012.md
[svt-2013]: data/svt-2013/svt-2013.md
[svt-2014]: data/svt-2014/svt-2014.md
[svt-2015]: data/svt-2015/svt-2015.md
[svt-2016]: data/svt-2016/svt-2016.md
[svt-2017]: data/svt-2017/svt-2017.md
[svt-2018]: data/svt-2018/svt-2018.md
[svt-2019]: data/svt-2019/svt-2019.md
[svt-2020]: data/svt-2020/svt-2020.md
[svt-2021]: data/svt-2021/svt-2021.md
[svt-2022]: data/svt-2022/svt-2022.md
[svt-2023]: data/svt-2023/svt-2023.md
[svt-nodate]: data/svt-nodate/svt-nodate.md
[gutenberg]: data/gutenberg/gutenberg.md
[runeberg-diverse]: data/runeberg-diverse/runeberg-diverse.md
[runeberg-folkbbl]: data/runeberg-folkbbl/runeberg-folkbbl.md
[runeberg-rost]: data/runeberg-rost/runeberg-rost.md
[runeberg-tiden]: data/runeberg-tiden/runeberg-tiden.md
[runeberg-urdagkron]: data/runeberg-urdagkron/runeberg-urdagkron.md
[bellman]: data/bellman/bellman.md
[drama]: data/drama/drama.md
[lb-restricted]: data/lb-restricted/lb-restricted.md
[swedish-pd]: data/swedish-pd/swedish-pd.md
[riksarkivet-goteborg-lines]: data/riksarkivet-goteborg-lines/riksarkivet-goteborg-lines.md
[riksarkivet-svea-hovratt-lines]: data/riksarkivet-svea-hovratt-lines/riksarkivet-svea-hovratt-lines.md
[riksarkivet-krigshovratten-lines]: data/riksarkivet-krigshovratten-lines/riksarkivet-krigshovratten-lines.md
[riksarkivet-bergskollegium-lines]: data/riksarkivet-bergskollegium-lines/riksarkivet-bergskollegium-lines.md
[riksarkivet-frihetstiden-lines]: data/riksarkivet-frihetstiden-lines/riksarkivet-frihetstiden-lines.md
[riksarkivet-pahlman-lines]: data/riksarkivet-pahlman-lines/riksarkivet-pahlman-lines.md
[riksarkivet-trolldom-lines]: data/riksarkivet-trolldom-lines/riksarkivet-trolldom-lines.md
[riksarkivet-gota-hovratt-lines]: data/riksarkivet-gota-hovratt-lines/riksarkivet-gota-hovratt-lines.md
[riksarkivet-bergmastaren-lines]: data/riksarkivet-bergmastaren-lines/riksarkivet-bergmastaren-lines.md
[riksarkivet-alvsborgs-losen-lines]: data/riksarkivet-alvsborgs-losen-lines/riksarkivet-alvsborgs-losen-lines.md
[riksarkivet-jonkoping-lines]: data/riksarkivet-jonkoping-lines/riksarkivet-jonkoping-lines.md
[wikisource]: data/wikisource/wikisource.md
<!-- END-DOMAIN TABLE -->

</div>

<div style="flex: 1;">

<p align="center">
<img src="./images/domain_distribution.png" width="400" style="margin-right: 10px;" />
</p>

</div>

</div>


### Licensing

The following gives an overview of the licensing in the Dynaword. To get the exact license of the individual datasets check out the [overview table](#source-data).
These license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

<!-- START-LICENSE TABLE -->
| License | Sources | N. Tokens |
| :--- | :--- | :--- |
| CC-BY 4.0 | [dalpilen-1860], [lag1800], [svensk-tidskrift], [statens-offentliga-utredningar], [biblioteksbladet], [riksdagen-forfattningssamling], [riksdagen-reglementen], [riksdagen-register], [riksdagen-skrivelser], [riksdagen-utredningar], [riksdagen-berattelser], [riksdagen-motioner], [riksdagen-betankanden], [riksdagen-propositioner], [riksdagen-protokoll], [flashback-dator], [flashback-droger], [flashback-ekonomi], [flashback-fordon], [flashback-hem], [flashback-kultur], [flashback-livsstil], [flashback-mat], [flashback-om-flashback], [flashback-ovrigt], [flashback-politik], [flashback-resor], [flashback-samhalle], [flashback-sex], [flashback-sport], [flashback-vetenskap], [familjeliv-adoption], [familjeliv-allmanna-ekonomi], [familjeliv-allmanna-familjeliv], [familjeliv-allmanna-fritid], [familjeliv-allmanna-husdjur], [familjeliv-allmanna-hushem], [familjeliv-allmanna-kropp], [familjeliv-allmanna-noje], [familjeliv-allmanna-samhalle], [familjeliv-allmanna-sandladan], [familjeliv-anglarum], [familjeliv-expert], [familjeliv-foralder], [familjeliv-gravid], [familjeliv-kansliga], [familjeliv-medlem-allmanna], [familjeliv-medlem-foraldrar], [familjeliv-medlem-planerarbarn], [familjeliv-medlem-vantarbarn], [familjeliv-pappagrupp], [familjeliv-planerarbarn], [familjeliv-sexsamlevnad], [familjeliv-svartattfabarn], [lb-open], [poeter], [europarl-sv], [laakartidningen], [fsv-aldrelagar], [fsv-aldrereligiosprosa], [fsv-nysvenskbibel], [fsv-nysvenskdalin], [fsv-nysvenskkronikor], [fsv-nysvensklagar], [fsv-nysvenskovrigt], [fsv-profanprosa], [fsv-verser], [fsv-yngrelagar], [fsv-yngrereligiosprosa], [fsv-yngretankebocker], [standsriksdagen-adelsstandet], [standsriksdagen-bihang], [standsriksdagen-bondestandet], [standsriksdagen-borgarstandet], [standsriksdagen-prastestandet], [standsriksdagen-riksdagsakter], [standsriksdagen-riksdagsbeslut], [strindbergromaner], [strindbergbrev], [dramadialog], [bibel1917], [psalmboken], [akademiliv], [dagens-arena], [gu-journalen], [forskning-framsteg], [sv-covid-19], [aftonbladet-1830], [aftonbladet-1840], [aftonbladet-1850], [aftonbladet-1860], [aftonbladet-1870], [aftonbladet-1880], [aftonbladet-1890], [aftonbladet-1900], [alfwarochskamt-1840], [barometern-1840], [barometern-1850], [barometern-1860], [barometern-1870], [barometern-1880], [barometern-1890], [blekingsposten-1850], [blekingsposten-1860], [blekingsposten-1870], [blekingsposten-1880], [bollnastidning-1870], [bollnastidning-1880], [borastidning-1830], [borastidning-1840], [borastidning-1850], [borastidning-1860], [borastidning-1870], [borastidning-1880], [borastidning-1890], [carlscronastidningar-1760], [carlscronaswekoblad-1750], [carlscronaswekoblad-1760], [carlscronaswekoblad-1770], [carlscronaswekoblad-1780], [carlscronaswekoblad-1790], [carlscronaswekoblad-1800], [carlscronaswekoblad-1810], [carlscronaswekoblad-1820], [carlscronaswekoblad-1830], [carlscronaswekoblad-1840], [carlscronaswekoblad-1850], [carlscronaswekoblad-1860], [carlscronaswekoblad-1870], [dagligtallehanda-1760], [dagligtallehanda-1770], [dagligtallehanda-1780], [dagligtallehanda-1790], [dagligtallehanda-1800], [dagligtallehanda-1810], [dagligtallehanda-1820], [dagligtallehanda-1830], [dagligtallehanda-1840], [dalpilen-1850], [dalpilen-1870], [dalpilen-1880], [dalpilen-1890], [dalpilen-1900], [fahluweckoblad-1780], [fahluweckoblad-1790], [fahluweckoblad-1800], [fahluweckoblad-1810], [fahluweckoblad-1820], [falkopingstidning-1850], [falkopingstidning-1860], [falkopingstidning-1870], [falkopingstidning-1880], [falkopingstidning-1890], [faluposten-1860], [faluposten-1870], [faluposten-1880], [faluposten-1890], [folketsrost-1840], [folketsrost-1850], [folketsrost-1860], [ghost-1830], [ghost-1840], [ghost-1850], [ghost-1860], [ghost-1870], [ghost-1880], [ghost-1890], [goteborgsposten-1850], [goteborgsposten-1860], [goteborgsposten-1870], [goteborgsposten-1880], [goteborgsposten-1890], [goteborgsweckoblad-1870], [goteborgsweckoblad-1880], [goteborgsweckoblad-1890], [gotheborgsallehanda-1770], [gotheborgsallehanda-1780], [gotheborgsallehanda-1790], [gotheborgsallehanda-1800], [gotheborgsallehanda-1810], [gotheborgsallehanda-1820], [gotheborgsallehanda-1830], [gotheborgsallehanda-1840], [gotheborgskanyheter-1760], [gotheborgskanyheter-1770], [gotheborgskanyheter-1780], [gotheborgskanyheter-1790], [gotheborgskanyheter-1800], [gotheborgskanyheter-1810], [gotheborgskanyheter-1820], [gotheborgskanyheter-1830], [gotheborgskanyheter-1840], [gotheborgsweckolista-1740], [gotheborgsweckolista-1750], [gotlandstidning-1860], [gotlandstidning-1870], [gotlandstidning-1880], [harnosandsposten-1840], [harnosandsposten-1850], [harnosandsposten-1860], [harnosandsposten-1870], [harnosandsposten-1880], [harnosandsposten-1890], [inrikestidningar-1760], [inrikestidningar-1770], [inrikestidningar-1780], [inrikestidningar-1790], [inrikestidningar-1800], [inrikestidningar-1810], [inrikestidningar-1820], [jonkopingsbladet-1840], [jonkopingsbladet-1850], [jonkopingsbladet-1860], [jonkopingsbladet-1870], [jonkopingsposten-1860], [jonkopingsposten-1870], [jonkopingsposten-1880], [jonkopingsposten-1890], [kalmar-1860], [kalmar-1870], [kalmar-1880], [kalmar-1890], [kalmar-1900], [karlshamnsallehanda-1840], [karlshamnsallehanda-1850], [karlshamnsallehanda-1860], [karlshamnsallehanda-1870], [karlshamnsallehanda-1880], [karlshamnsallehanda-1890], [karlskronaweckoblad-1870], [karlskronaweckoblad-1880], [karlskronaweckoblad-1890], [kristianstadsbladet-1850], [kristianstadsbladet-1860], [kristianstadsbladet-1870], [kristianstadsbladet-1880], [kristianstadsbladet-1890], [lindesbergsallehanda-1870], [lindesbergsallehanda-1880], [lundsweckoblad-1770], [lundsweckoblad-1780], [lundsweckoblad-1810], [lundsweckoblad-1820], [lundsweckoblad-1830], [lundsweckoblad-1840], [lundsweckoblad-1850], [lundsweckoblad-1860], [lundsweckoblad-1870], [lundsweckoblad-1880], [lundsweckoblad-1890], [malmoallehanda-1820], [malmoallehanda-1830], [malmoallehanda-1840], [malmoallehanda-1850], [malmoallehanda-1860], [malmoallehanda-1870], [malmoallehanda-1880], [malmoallehanda-1890], [nerikesallehanda-1840], [nerikesallehanda-1850], [nerikesallehanda-1860], [nerikesallehanda-1870], [nerikesallehanda-1880], [nerikesallehanda-1890], [nlk-1850], [nlk-1860], [nlk-1870], [norden-1850], [norden-1860], [norraskane-1880], [norraskane-1890], [norrbottenskuriren-1860], [norrbottenskuriren-1870], [norrbottenskuriren-1880], [norrbottenskuriren-1890], [norrbottensposten-1840], [norrbottensposten-1850], [norrbottensposten-1860], [norrbottensposten-1870], [norrbottensposten-1880], [norrbottensposten-1890], [norrkopingskuriren-1850], [norrkopingskuriren-1860], [norrkopingstidningar-1780], [norrkopingstidningar-1790], [norrkopingstidningar-1800], [norrkopingstidningar-1810], [norrkopingstidningar-1820], [norrkopingstidningar-1830], [norrkopingstidningar-1840], [norrkopingstidningar-1850], [norrkopingstidningar-1860], [norrkopingstidningar-1870], [norrkopingstidningar-1880], [norrkopingstidningar-1890], [norrkopingsweckotidningar-1750], [norrkopingsweckotidningar-1760], [norrkopingsweckotidningar-1770], [norrkopingsweckotidningar-1780], [norrlandsposten-1880], [nyadagligtallehanda-1850], [nyadagligtallehanda-1860], [nyadagligtallehanda-1870], [nyadagligtallehanda-1880], [nyadagligtallehanda-1890], [nyakarlskronaweckoblad-1870], [nyawermlandstidningen-1850], [nyawermlandstidningen-1860], [nyawermlandstidningen-1870], [nyawermlandstidningen-1880], [nyawermlandstidningen-1890], [nyawexjobladet-1840], [nyawexjobladet-1850], [nyawexjobladet-1860], [nyawexjobladet-1870], [nyawexjobladet-1880], [nyawexjobladet-1890], [nyttallvarochskamt-1840], [nyttallvarochskamt-1850], [nyttochgammalt-1780], [nyttochgammalt-1790], [nyttochgammalt-1800], [nyttochgammalt-1810], [ostergotlandsveckoblad-1880], [ostergotlandsveckoblad-1890], [ostgotacorrespondenten-1830], [ostgotacorrespondenten-1840], [ostgotacorrespondenten-1850], [ostgotacorrespondenten-1860], [ostgotacorrespondenten-1870], [ostgotacorrespondenten-1880], [ostgotacorrespondenten-1890], [ostgotaposten-1890], [ostgotaposten-1900], [post-ochinrikestidningar-1820], [post-ochinrikestidningar-1830], [post-ochinrikestidningar-1840], [post-ochinrikestidningar-1850], [post-ochinrikestidningar-1860], [post-ochinrikestidningar-1870], [post-ochinrikestidningar-1880], [post-ochinrikestidningar-1890], [posttidningar-1640], [posttidningar-1650], [posttidningar-1660], [posttidningar-1670], [posttidningar-1680], [posttidningar-1690], [posttidningar-1700], [posttidningar-1710], [posttidningar-1720], [posttidningar-1730], [posttidningar-1740], [posttidningar-1750], [posttidningar-1760], [posttidningar-1770], [posttidningar-1780], [posttidningar-1790], [posttidningar-1800], [posttidningar-1810], [posttidningar-1820], [stnlk-1870], [stockholmsdagblad-1820], [stockholmsdagblad-1830], [stockholmsdagblad-1840], [stockholmsdagblad-1850], [stockholmsdagblad-1860], [stockholmsdagblad-1870], [stockholmsdagblad-1880], [stockholmsdagblad-1890], [stockholmsposten-1770], [stockholmsposten-1780], [stockholmsposten-1790], [stockholmsposten-1800], [stockholmsposten-1810], [stockholmsposten-1820], [stockholmsposten-1830], [sundsvallstidning-1880], [sundsvallstidning-1890], [tfwbsol-1840], [tfwbsol-1850], [tfwbsol-1860], [tfwbsol-1870], [tfwbsol-1880], [tfwbsol-1890], [umebladet-1840], [umebladet-1850], [umebladet-1860], [umebladet-1870], [umebladet-1880], [umebladet-1890], [upsala-1840], [upsala-1850], [upsala-1860], [upsala-1870], [upsala-1880], [upsala-1890], [vestmanlandslanstidning-1830], [vestmanlandslanstidning-1840], [vestmanlandslanstidning-1850], [vestmanlandslanstidning-1860], [vestmanlandslanstidning-1870], [vestmanlandslanstidning-1880], [vestmanlandslanstidning-1890], [wermlandslanstidning-1870], [wermlandstidningen-1840], [wermlandstidningen-1850], [wernamotidning-1870], [wernamotidning-1880], [wexjobladet-1810], [wexjobladet-1820], [wexjobladet-1830], [wexjobladet-1840], [wexjobladet-1850], [rd-prop], [rd-sou], [rd-prot], [rd-bet], [rd-mot], [rd-ds], [rd-ovr], [sfs], [rd-frsrdg], [rd-skfr], [rd-yttr], [rd-utsk], [rd-fpm], [rd-ip], [rd-kom], [rd-kammakt], [rd-utr], [rd-anf-1993-2018], [mosel-voxpopuli], [mosel-youtube-commons], [kalmar-1910], [dalpilen-1910], [dalpilen-1920], [ostgotaposten-1910], [sweachum], [sweacsam], [bloggmix1998], [bloggmix1999], [bloggmix2000], [bloggmix2001], [bloggmix2002], [bloggmix2003], [bloggmix2004], [bloggmix2005], [bloggmix2006], [bloggmix2007], [bloggmix2008], [bloggmix2009], [bloggmix2010], [bloggmix2011], [bloggmix2012], [bloggmix2013], [bloggmix2014], [bloggmix2015], [bloggmix2016], [bloggmix2017], [bloggmixodat], [press65], [press76], [press95], [press96], [press97], [press98], [gp1994], [gp2001], [gp2002], [gp2003], [gp2004], [gp2005], [gp2006], [gp2007], [gp2008], [gp2009], [gp2010], [gp2011], [gp2012], [gp2013], [attasidor], [svt-2004], [svt-2005], [svt-2006], [svt-2007], [svt-2008], [svt-2009], [svt-2010], [svt-2011], [svt-2012], [svt-2013], [svt-2014], [svt-2015], [svt-2016], [svt-2017], [svt-2018], [svt-2019], [svt-2020], [svt-2021], [svt-2022], [svt-2023], [svt-nodate], [runeberg-diverse], [runeberg-folkbbl], [runeberg-rost], [runeberg-tiden], [runeberg-urdagkron], [bellman], [drama], [lb-restricted] | 37.33B |
| CC-BY-SA 4.0 | [cellar], [wikipedia-sv] | 5.09B |
| Public domain | [swedish-pd] | 1.05B |
| Unrestricted under US copyright law | [gutenberg] | 23.90M |
| CC BY-SA 4.0 | [wikisource] | 10.74M |
| CC0 | [riksarkivet-goteborg-lines], [riksarkivet-svea-hovratt-lines], [riksarkivet-krigshovratten-lines], [riksarkivet-bergskollegium-lines], [riksarkivet-frihetstiden-lines], [riksarkivet-pahlman-lines], [riksarkivet-trolldom-lines], [riksarkivet-gota-hovratt-lines], [riksarkivet-bergmastaren-lines], [riksarkivet-alvsborgs-losen-lines], [riksarkivet-jonkoping-lines] | 7.06M |
| **Total** |  | 43.51B |

[dalpilen-1860]: data/dalpilen-1860/dalpilen-1860.md
[lag1800]: data/lag1800/lag1800.md
[svensk-tidskrift]: data/svensk-tidskrift/svensk-tidskrift.md
[statens-offentliga-utredningar]: data/statens-offentliga-utredningar/statens-offentliga-utredningar.md
[biblioteksbladet]: data/biblioteksbladet/biblioteksbladet.md
[riksdagen-forfattningssamling]: data/riksdagen-forfattningssamling/riksdagen-forfattningssamling.md
[riksdagen-reglementen]: data/riksdagen-reglementen/riksdagen-reglementen.md
[riksdagen-register]: data/riksdagen-register/riksdagen-register.md
[riksdagen-skrivelser]: data/riksdagen-skrivelser/riksdagen-skrivelser.md
[riksdagen-utredningar]: data/riksdagen-utredningar/riksdagen-utredningar.md
[riksdagen-berattelser]: data/riksdagen-berattelser/riksdagen-berattelser.md
[riksdagen-motioner]: data/riksdagen-motioner/riksdagen-motioner.md
[riksdagen-betankanden]: data/riksdagen-betankanden/riksdagen-betankanden.md
[riksdagen-propositioner]: data/riksdagen-propositioner/riksdagen-propositioner.md
[riksdagen-protokoll]: data/riksdagen-protokoll/riksdagen-protokoll.md
[cellar]: data/cellar/cellar.md
[flashback-dator]: data/flashback-dator/flashback-dator.md
[flashback-droger]: data/flashback-droger/flashback-droger.md
[flashback-ekonomi]: data/flashback-ekonomi/flashback-ekonomi.md
[flashback-fordon]: data/flashback-fordon/flashback-fordon.md
[flashback-hem]: data/flashback-hem/flashback-hem.md
[flashback-kultur]: data/flashback-kultur/flashback-kultur.md
[flashback-livsstil]: data/flashback-livsstil/flashback-livsstil.md
[flashback-mat]: data/flashback-mat/flashback-mat.md
[flashback-om-flashback]: data/flashback-om-flashback/flashback-om-flashback.md
[flashback-ovrigt]: data/flashback-ovrigt/flashback-ovrigt.md
[flashback-politik]: data/flashback-politik/flashback-politik.md
[flashback-resor]: data/flashback-resor/flashback-resor.md
[flashback-samhalle]: data/flashback-samhalle/flashback-samhalle.md
[flashback-sex]: data/flashback-sex/flashback-sex.md
[flashback-sport]: data/flashback-sport/flashback-sport.md
[flashback-vetenskap]: data/flashback-vetenskap/flashback-vetenskap.md
[familjeliv-adoption]: data/familjeliv-adoption/familjeliv-adoption.md
[familjeliv-allmanna-ekonomi]: data/familjeliv-allmanna-ekonomi/familjeliv-allmanna-ekonomi.md
[familjeliv-allmanna-familjeliv]: data/familjeliv-allmanna-familjeliv/familjeliv-allmanna-familjeliv.md
[familjeliv-allmanna-fritid]: data/familjeliv-allmanna-fritid/familjeliv-allmanna-fritid.md
[familjeliv-allmanna-husdjur]: data/familjeliv-allmanna-husdjur/familjeliv-allmanna-husdjur.md
[familjeliv-allmanna-hushem]: data/familjeliv-allmanna-hushem/familjeliv-allmanna-hushem.md
[familjeliv-allmanna-kropp]: data/familjeliv-allmanna-kropp/familjeliv-allmanna-kropp.md
[familjeliv-allmanna-noje]: data/familjeliv-allmanna-noje/familjeliv-allmanna-noje.md
[familjeliv-allmanna-samhalle]: data/familjeliv-allmanna-samhalle/familjeliv-allmanna-samhalle.md
[familjeliv-allmanna-sandladan]: data/familjeliv-allmanna-sandladan/familjeliv-allmanna-sandladan.md
[familjeliv-anglarum]: data/familjeliv-anglarum/familjeliv-anglarum.md
[familjeliv-expert]: data/familjeliv-expert/familjeliv-expert.md
[familjeliv-foralder]: data/familjeliv-foralder/familjeliv-foralder.md
[familjeliv-gravid]: data/familjeliv-gravid/familjeliv-gravid.md
[familjeliv-kansliga]: data/familjeliv-kansliga/familjeliv-kansliga.md
[familjeliv-medlem-allmanna]: data/familjeliv-medlem-allmanna/familjeliv-medlem-allmanna.md
[familjeliv-medlem-foraldrar]: data/familjeliv-medlem-foraldrar/familjeliv-medlem-foraldrar.md
[familjeliv-medlem-planerarbarn]: data/familjeliv-medlem-planerarbarn/familjeliv-medlem-planerarbarn.md
[familjeliv-medlem-vantarbarn]: data/familjeliv-medlem-vantarbarn/familjeliv-medlem-vantarbarn.md
[familjeliv-pappagrupp]: data/familjeliv-pappagrupp/familjeliv-pappagrupp.md
[familjeliv-planerarbarn]: data/familjeliv-planerarbarn/familjeliv-planerarbarn.md
[familjeliv-sexsamlevnad]: data/familjeliv-sexsamlevnad/familjeliv-sexsamlevnad.md
[familjeliv-svartattfabarn]: data/familjeliv-svartattfabarn/familjeliv-svartattfabarn.md
[lb-open]: data/lb-open/lb-open.md
[poeter]: data/poeter/poeter.md
[wikipedia-sv]: data/wikipedia-sv/wikipedia-sv.md
[europarl-sv]: data/europarl-sv/europarl-sv.md
[laakartidningen]: data/laakartidningen/laakartidningen.md
[fsv-aldrelagar]: data/fsv-aldrelagar/fsv-aldrelagar.md
[fsv-aldrereligiosprosa]: data/fsv-aldrereligiosprosa/fsv-aldrereligiosprosa.md
[fsv-nysvenskbibel]: data/fsv-nysvenskbibel/fsv-nysvenskbibel.md
[fsv-nysvenskdalin]: data/fsv-nysvenskdalin/fsv-nysvenskdalin.md
[fsv-nysvenskkronikor]: data/fsv-nysvenskkronikor/fsv-nysvenskkronikor.md
[fsv-nysvensklagar]: data/fsv-nysvensklagar/fsv-nysvensklagar.md
[fsv-nysvenskovrigt]: data/fsv-nysvenskovrigt/fsv-nysvenskovrigt.md
[fsv-profanprosa]: data/fsv-profanprosa/fsv-profanprosa.md
[fsv-verser]: data/fsv-verser/fsv-verser.md
[fsv-yngrelagar]: data/fsv-yngrelagar/fsv-yngrelagar.md
[fsv-yngrereligiosprosa]: data/fsv-yngrereligiosprosa/fsv-yngrereligiosprosa.md
[fsv-yngretankebocker]: data/fsv-yngretankebocker/fsv-yngretankebocker.md
[standsriksdagen-adelsstandet]: data/standsriksdagen-adelsstandet/standsriksdagen-adelsstandet.md
[standsriksdagen-bihang]: data/standsriksdagen-bihang/standsriksdagen-bihang.md
[standsriksdagen-bondestandet]: data/standsriksdagen-bondestandet/standsriksdagen-bondestandet.md
[standsriksdagen-borgarstandet]: data/standsriksdagen-borgarstandet/standsriksdagen-borgarstandet.md
[standsriksdagen-prastestandet]: data/standsriksdagen-prastestandet/standsriksdagen-prastestandet.md
[standsriksdagen-riksdagsakter]: data/standsriksdagen-riksdagsakter/standsriksdagen-riksdagsakter.md
[standsriksdagen-riksdagsbeslut]: data/standsriksdagen-riksdagsbeslut/standsriksdagen-riksdagsbeslut.md
[strindbergromaner]: data/strindbergromaner/strindbergromaner.md
[strindbergbrev]: data/strindbergbrev/strindbergbrev.md
[dramadialog]: data/dramadialog/dramadialog.md
[bibel1917]: data/bibel1917/bibel1917.md
[psalmboken]: data/psalmboken/psalmboken.md
[akademiliv]: data/akademiliv/akademiliv.md
[dagens-arena]: data/dagens-arena/dagens-arena.md
[gu-journalen]: data/gu-journalen/gu-journalen.md
[forskning-framsteg]: data/forskning-framsteg/forskning-framsteg.md
[sv-covid-19]: data/sv-covid-19/sv-covid-19.md
[aftonbladet-1830]: data/aftonbladet-1830/aftonbladet-1830.md
[aftonbladet-1840]: data/aftonbladet-1840/aftonbladet-1840.md
[aftonbladet-1850]: data/aftonbladet-1850/aftonbladet-1850.md
[aftonbladet-1860]: data/aftonbladet-1860/aftonbladet-1860.md
[aftonbladet-1870]: data/aftonbladet-1870/aftonbladet-1870.md
[aftonbladet-1880]: data/aftonbladet-1880/aftonbladet-1880.md
[aftonbladet-1890]: data/aftonbladet-1890/aftonbladet-1890.md
[aftonbladet-1900]: data/aftonbladet-1900/aftonbladet-1900.md
[alfwarochskamt-1840]: data/alfwarochskamt-1840/alfwarochskamt-1840.md
[barometern-1840]: data/barometern-1840/barometern-1840.md
[barometern-1850]: data/barometern-1850/barometern-1850.md
[barometern-1860]: data/barometern-1860/barometern-1860.md
[barometern-1870]: data/barometern-1870/barometern-1870.md
[barometern-1880]: data/barometern-1880/barometern-1880.md
[barometern-1890]: data/barometern-1890/barometern-1890.md
[blekingsposten-1850]: data/blekingsposten-1850/blekingsposten-1850.md
[blekingsposten-1860]: data/blekingsposten-1860/blekingsposten-1860.md
[blekingsposten-1870]: data/blekingsposten-1870/blekingsposten-1870.md
[blekingsposten-1880]: data/blekingsposten-1880/blekingsposten-1880.md
[bollnastidning-1870]: data/bollnastidning-1870/bollnastidning-1870.md
[bollnastidning-1880]: data/bollnastidning-1880/bollnastidning-1880.md
[borastidning-1830]: data/borastidning-1830/borastidning-1830.md
[borastidning-1840]: data/borastidning-1840/borastidning-1840.md
[borastidning-1850]: data/borastidning-1850/borastidning-1850.md
[borastidning-1860]: data/borastidning-1860/borastidning-1860.md
[borastidning-1870]: data/borastidning-1870/borastidning-1870.md
[borastidning-1880]: data/borastidning-1880/borastidning-1880.md
[borastidning-1890]: data/borastidning-1890/borastidning-1890.md
[carlscronastidningar-1760]: data/carlscronastidningar-1760/carlscronastidningar-1760.md
[carlscronaswekoblad-1750]: data/carlscronaswekoblad-1750/carlscronaswekoblad-1750.md
[carlscronaswekoblad-1760]: data/carlscronaswekoblad-1760/carlscronaswekoblad-1760.md
[carlscronaswekoblad-1770]: data/carlscronaswekoblad-1770/carlscronaswekoblad-1770.md
[carlscronaswekoblad-1780]: data/carlscronaswekoblad-1780/carlscronaswekoblad-1780.md
[carlscronaswekoblad-1790]: data/carlscronaswekoblad-1790/carlscronaswekoblad-1790.md
[carlscronaswekoblad-1800]: data/carlscronaswekoblad-1800/carlscronaswekoblad-1800.md
[carlscronaswekoblad-1810]: data/carlscronaswekoblad-1810/carlscronaswekoblad-1810.md
[carlscronaswekoblad-1820]: data/carlscronaswekoblad-1820/carlscronaswekoblad-1820.md
[carlscronaswekoblad-1830]: data/carlscronaswekoblad-1830/carlscronaswekoblad-1830.md
[carlscronaswekoblad-1840]: data/carlscronaswekoblad-1840/carlscronaswekoblad-1840.md
[carlscronaswekoblad-1850]: data/carlscronaswekoblad-1850/carlscronaswekoblad-1850.md
[carlscronaswekoblad-1860]: data/carlscronaswekoblad-1860/carlscronaswekoblad-1860.md
[carlscronaswekoblad-1870]: data/carlscronaswekoblad-1870/carlscronaswekoblad-1870.md
[dagligtallehanda-1760]: data/dagligtallehanda-1760/dagligtallehanda-1760.md
[dagligtallehanda-1770]: data/dagligtallehanda-1770/dagligtallehanda-1770.md
[dagligtallehanda-1780]: data/dagligtallehanda-1780/dagligtallehanda-1780.md
[dagligtallehanda-1790]: data/dagligtallehanda-1790/dagligtallehanda-1790.md
[dagligtallehanda-1800]: data/dagligtallehanda-1800/dagligtallehanda-1800.md
[dagligtallehanda-1810]: data/dagligtallehanda-1810/dagligtallehanda-1810.md
[dagligtallehanda-1820]: data/dagligtallehanda-1820/dagligtallehanda-1820.md
[dagligtallehanda-1830]: data/dagligtallehanda-1830/dagligtallehanda-1830.md
[dagligtallehanda-1840]: data/dagligtallehanda-1840/dagligtallehanda-1840.md
[dalpilen-1850]: data/dalpilen-1850/dalpilen-1850.md
[dalpilen-1870]: data/dalpilen-1870/dalpilen-1870.md
[dalpilen-1880]: data/dalpilen-1880/dalpilen-1880.md
[dalpilen-1890]: data/dalpilen-1890/dalpilen-1890.md
[dalpilen-1900]: data/dalpilen-1900/dalpilen-1900.md
[fahluweckoblad-1780]: data/fahluweckoblad-1780/fahluweckoblad-1780.md
[fahluweckoblad-1790]: data/fahluweckoblad-1790/fahluweckoblad-1790.md
[fahluweckoblad-1800]: data/fahluweckoblad-1800/fahluweckoblad-1800.md
[fahluweckoblad-1810]: data/fahluweckoblad-1810/fahluweckoblad-1810.md
[fahluweckoblad-1820]: data/fahluweckoblad-1820/fahluweckoblad-1820.md
[falkopingstidning-1850]: data/falkopingstidning-1850/falkopingstidning-1850.md
[falkopingstidning-1860]: data/falkopingstidning-1860/falkopingstidning-1860.md
[falkopingstidning-1870]: data/falkopingstidning-1870/falkopingstidning-1870.md
[falkopingstidning-1880]: data/falkopingstidning-1880/falkopingstidning-1880.md
[falkopingstidning-1890]: data/falkopingstidning-1890/falkopingstidning-1890.md
[faluposten-1860]: data/faluposten-1860/faluposten-1860.md
[faluposten-1870]: data/faluposten-1870/faluposten-1870.md
[faluposten-1880]: data/faluposten-1880/faluposten-1880.md
[faluposten-1890]: data/faluposten-1890/faluposten-1890.md
[folketsrost-1840]: data/folketsrost-1840/folketsrost-1840.md
[folketsrost-1850]: data/folketsrost-1850/folketsrost-1850.md
[folketsrost-1860]: data/folketsrost-1860/folketsrost-1860.md
[ghost-1830]: data/ghost-1830/ghost-1830.md
[ghost-1840]: data/ghost-1840/ghost-1840.md
[ghost-1850]: data/ghost-1850/ghost-1850.md
[ghost-1860]: data/ghost-1860/ghost-1860.md
[ghost-1870]: data/ghost-1870/ghost-1870.md
[ghost-1880]: data/ghost-1880/ghost-1880.md
[ghost-1890]: data/ghost-1890/ghost-1890.md
[goteborgsposten-1850]: data/goteborgsposten-1850/goteborgsposten-1850.md
[goteborgsposten-1860]: data/goteborgsposten-1860/goteborgsposten-1860.md
[goteborgsposten-1870]: data/goteborgsposten-1870/goteborgsposten-1870.md
[goteborgsposten-1880]: data/goteborgsposten-1880/goteborgsposten-1880.md
[goteborgsposten-1890]: data/goteborgsposten-1890/goteborgsposten-1890.md
[goteborgsweckoblad-1870]: data/goteborgsweckoblad-1870/goteborgsweckoblad-1870.md
[goteborgsweckoblad-1880]: data/goteborgsweckoblad-1880/goteborgsweckoblad-1880.md
[goteborgsweckoblad-1890]: data/goteborgsweckoblad-1890/goteborgsweckoblad-1890.md
[gotheborgsallehanda-1770]: data/gotheborgsallehanda-1770/gotheborgsallehanda-1770.md
[gotheborgsallehanda-1780]: data/gotheborgsallehanda-1780/gotheborgsallehanda-1780.md
[gotheborgsallehanda-1790]: data/gotheborgsallehanda-1790/gotheborgsallehanda-1790.md
[gotheborgsallehanda-1800]: data/gotheborgsallehanda-1800/gotheborgsallehanda-1800.md
[gotheborgsallehanda-1810]: data/gotheborgsallehanda-1810/gotheborgsallehanda-1810.md
[gotheborgsallehanda-1820]: data/gotheborgsallehanda-1820/gotheborgsallehanda-1820.md
[gotheborgsallehanda-1830]: data/gotheborgsallehanda-1830/gotheborgsallehanda-1830.md
[gotheborgsallehanda-1840]: data/gotheborgsallehanda-1840/gotheborgsallehanda-1840.md
[gotheborgskanyheter-1760]: data/gotheborgskanyheter-1760/gotheborgskanyheter-1760.md
[gotheborgskanyheter-1770]: data/gotheborgskanyheter-1770/gotheborgskanyheter-1770.md
[gotheborgskanyheter-1780]: data/gotheborgskanyheter-1780/gotheborgskanyheter-1780.md
[gotheborgskanyheter-1790]: data/gotheborgskanyheter-1790/gotheborgskanyheter-1790.md
[gotheborgskanyheter-1800]: data/gotheborgskanyheter-1800/gotheborgskanyheter-1800.md
[gotheborgskanyheter-1810]: data/gotheborgskanyheter-1810/gotheborgskanyheter-1810.md
[gotheborgskanyheter-1820]: data/gotheborgskanyheter-1820/gotheborgskanyheter-1820.md
[gotheborgskanyheter-1830]: data/gotheborgskanyheter-1830/gotheborgskanyheter-1830.md
[gotheborgskanyheter-1840]: data/gotheborgskanyheter-1840/gotheborgskanyheter-1840.md
[gotheborgsweckolista-1740]: data/gotheborgsweckolista-1740/gotheborgsweckolista-1740.md
[gotheborgsweckolista-1750]: data/gotheborgsweckolista-1750/gotheborgsweckolista-1750.md
[gotlandstidning-1860]: data/gotlandstidning-1860/gotlandstidning-1860.md
[gotlandstidning-1870]: data/gotlandstidning-1870/gotlandstidning-1870.md
[gotlandstidning-1880]: data/gotlandstidning-1880/gotlandstidning-1880.md
[harnosandsposten-1840]: data/harnosandsposten-1840/harnosandsposten-1840.md
[harnosandsposten-1850]: data/harnosandsposten-1850/harnosandsposten-1850.md
[harnosandsposten-1860]: data/harnosandsposten-1860/harnosandsposten-1860.md
[harnosandsposten-1870]: data/harnosandsposten-1870/harnosandsposten-1870.md
[harnosandsposten-1880]: data/harnosandsposten-1880/harnosandsposten-1880.md
[harnosandsposten-1890]: data/harnosandsposten-1890/harnosandsposten-1890.md
[inrikestidningar-1760]: data/inrikestidningar-1760/inrikestidningar-1760.md
[inrikestidningar-1770]: data/inrikestidningar-1770/inrikestidningar-1770.md
[inrikestidningar-1780]: data/inrikestidningar-1780/inrikestidningar-1780.md
[inrikestidningar-1790]: data/inrikestidningar-1790/inrikestidningar-1790.md
[inrikestidningar-1800]: data/inrikestidningar-1800/inrikestidningar-1800.md
[inrikestidningar-1810]: data/inrikestidningar-1810/inrikestidningar-1810.md
[inrikestidningar-1820]: data/inrikestidningar-1820/inrikestidningar-1820.md
[jonkopingsbladet-1840]: data/jonkopingsbladet-1840/jonkopingsbladet-1840.md
[jonkopingsbladet-1850]: data/jonkopingsbladet-1850/jonkopingsbladet-1850.md
[jonkopingsbladet-1860]: data/jonkopingsbladet-1860/jonkopingsbladet-1860.md
[jonkopingsbladet-1870]: data/jonkopingsbladet-1870/jonkopingsbladet-1870.md
[jonkopingsposten-1860]: data/jonkopingsposten-1860/jonkopingsposten-1860.md
[jonkopingsposten-1870]: data/jonkopingsposten-1870/jonkopingsposten-1870.md
[jonkopingsposten-1880]: data/jonkopingsposten-1880/jonkopingsposten-1880.md
[jonkopingsposten-1890]: data/jonkopingsposten-1890/jonkopingsposten-1890.md
[kalmar-1860]: data/kalmar-1860/kalmar-1860.md
[kalmar-1870]: data/kalmar-1870/kalmar-1870.md
[kalmar-1880]: data/kalmar-1880/kalmar-1880.md
[kalmar-1890]: data/kalmar-1890/kalmar-1890.md
[kalmar-1900]: data/kalmar-1900/kalmar-1900.md
[karlshamnsallehanda-1840]: data/karlshamnsallehanda-1840/karlshamnsallehanda-1840.md
[karlshamnsallehanda-1850]: data/karlshamnsallehanda-1850/karlshamnsallehanda-1850.md
[karlshamnsallehanda-1860]: data/karlshamnsallehanda-1860/karlshamnsallehanda-1860.md
[karlshamnsallehanda-1870]: data/karlshamnsallehanda-1870/karlshamnsallehanda-1870.md
[karlshamnsallehanda-1880]: data/karlshamnsallehanda-1880/karlshamnsallehanda-1880.md
[karlshamnsallehanda-1890]: data/karlshamnsallehanda-1890/karlshamnsallehanda-1890.md
[karlskronaweckoblad-1870]: data/karlskronaweckoblad-1870/karlskronaweckoblad-1870.md
[karlskronaweckoblad-1880]: data/karlskronaweckoblad-1880/karlskronaweckoblad-1880.md
[karlskronaweckoblad-1890]: data/karlskronaweckoblad-1890/karlskronaweckoblad-1890.md
[kristianstadsbladet-1850]: data/kristianstadsbladet-1850/kristianstadsbladet-1850.md
[kristianstadsbladet-1860]: data/kristianstadsbladet-1860/kristianstadsbladet-1860.md
[kristianstadsbladet-1870]: data/kristianstadsbladet-1870/kristianstadsbladet-1870.md
[kristianstadsbladet-1880]: data/kristianstadsbladet-1880/kristianstadsbladet-1880.md
[kristianstadsbladet-1890]: data/kristianstadsbladet-1890/kristianstadsbladet-1890.md
[lindesbergsallehanda-1870]: data/lindesbergsallehanda-1870/lindesbergsallehanda-1870.md
[lindesbergsallehanda-1880]: data/lindesbergsallehanda-1880/lindesbergsallehanda-1880.md
[lundsweckoblad-1770]: data/lundsweckoblad-1770/lundsweckoblad-1770.md
[lundsweckoblad-1780]: data/lundsweckoblad-1780/lundsweckoblad-1780.md
[lundsweckoblad-1810]: data/lundsweckoblad-1810/lundsweckoblad-1810.md
[lundsweckoblad-1820]: data/lundsweckoblad-1820/lundsweckoblad-1820.md
[lundsweckoblad-1830]: data/lundsweckoblad-1830/lundsweckoblad-1830.md
[lundsweckoblad-1840]: data/lundsweckoblad-1840/lundsweckoblad-1840.md
[lundsweckoblad-1850]: data/lundsweckoblad-1850/lundsweckoblad-1850.md
[lundsweckoblad-1860]: data/lundsweckoblad-1860/lundsweckoblad-1860.md
[lundsweckoblad-1870]: data/lundsweckoblad-1870/lundsweckoblad-1870.md
[lundsweckoblad-1880]: data/lundsweckoblad-1880/lundsweckoblad-1880.md
[lundsweckoblad-1890]: data/lundsweckoblad-1890/lundsweckoblad-1890.md
[malmoallehanda-1820]: data/malmoallehanda-1820/malmoallehanda-1820.md
[malmoallehanda-1830]: data/malmoallehanda-1830/malmoallehanda-1830.md
[malmoallehanda-1840]: data/malmoallehanda-1840/malmoallehanda-1840.md
[malmoallehanda-1850]: data/malmoallehanda-1850/malmoallehanda-1850.md
[malmoallehanda-1860]: data/malmoallehanda-1860/malmoallehanda-1860.md
[malmoallehanda-1870]: data/malmoallehanda-1870/malmoallehanda-1870.md
[malmoallehanda-1880]: data/malmoallehanda-1880/malmoallehanda-1880.md
[malmoallehanda-1890]: data/malmoallehanda-1890/malmoallehanda-1890.md
[nerikesallehanda-1840]: data/nerikesallehanda-1840/nerikesallehanda-1840.md
[nerikesallehanda-1850]: data/nerikesallehanda-1850/nerikesallehanda-1850.md
[nerikesallehanda-1860]: data/nerikesallehanda-1860/nerikesallehanda-1860.md
[nerikesallehanda-1870]: data/nerikesallehanda-1870/nerikesallehanda-1870.md
[nerikesallehanda-1880]: data/nerikesallehanda-1880/nerikesallehanda-1880.md
[nerikesallehanda-1890]: data/nerikesallehanda-1890/nerikesallehanda-1890.md
[nlk-1850]: data/nlk-1850/nlk-1850.md
[nlk-1860]: data/nlk-1860/nlk-1860.md
[nlk-1870]: data/nlk-1870/nlk-1870.md
[norden-1850]: data/norden-1850/norden-1850.md
[norden-1860]: data/norden-1860/norden-1860.md
[norraskane-1880]: data/norraskane-1880/norraskane-1880.md
[norraskane-1890]: data/norraskane-1890/norraskane-1890.md
[norrbottenskuriren-1860]: data/norrbottenskuriren-1860/norrbottenskuriren-1860.md
[norrbottenskuriren-1870]: data/norrbottenskuriren-1870/norrbottenskuriren-1870.md
[norrbottenskuriren-1880]: data/norrbottenskuriren-1880/norrbottenskuriren-1880.md
[norrbottenskuriren-1890]: data/norrbottenskuriren-1890/norrbottenskuriren-1890.md
[norrbottensposten-1840]: data/norrbottensposten-1840/norrbottensposten-1840.md
[norrbottensposten-1850]: data/norrbottensposten-1850/norrbottensposten-1850.md
[norrbottensposten-1860]: data/norrbottensposten-1860/norrbottensposten-1860.md
[norrbottensposten-1870]: data/norrbottensposten-1870/norrbottensposten-1870.md
[norrbottensposten-1880]: data/norrbottensposten-1880/norrbottensposten-1880.md
[norrbottensposten-1890]: data/norrbottensposten-1890/norrbottensposten-1890.md
[norrkopingskuriren-1850]: data/norrkopingskuriren-1850/norrkopingskuriren-1850.md
[norrkopingskuriren-1860]: data/norrkopingskuriren-1860/norrkopingskuriren-1860.md
[norrkopingstidningar-1780]: data/norrkopingstidningar-1780/norrkopingstidningar-1780.md
[norrkopingstidningar-1790]: data/norrkopingstidningar-1790/norrkopingstidningar-1790.md
[norrkopingstidningar-1800]: data/norrkopingstidningar-1800/norrkopingstidningar-1800.md
[norrkopingstidningar-1810]: data/norrkopingstidningar-1810/norrkopingstidningar-1810.md
[norrkopingstidningar-1820]: data/norrkopingstidningar-1820/norrkopingstidningar-1820.md
[norrkopingstidningar-1830]: data/norrkopingstidningar-1830/norrkopingstidningar-1830.md
[norrkopingstidningar-1840]: data/norrkopingstidningar-1840/norrkopingstidningar-1840.md
[norrkopingstidningar-1850]: data/norrkopingstidningar-1850/norrkopingstidningar-1850.md
[norrkopingstidningar-1860]: data/norrkopingstidningar-1860/norrkopingstidningar-1860.md
[norrkopingstidningar-1870]: data/norrkopingstidningar-1870/norrkopingstidningar-1870.md
[norrkopingstidningar-1880]: data/norrkopingstidningar-1880/norrkopingstidningar-1880.md
[norrkopingstidningar-1890]: data/norrkopingstidningar-1890/norrkopingstidningar-1890.md
[norrkopingsweckotidningar-1750]: data/norrkopingsweckotidningar-1750/norrkopingsweckotidningar-1750.md
[norrkopingsweckotidningar-1760]: data/norrkopingsweckotidningar-1760/norrkopingsweckotidningar-1760.md
[norrkopingsweckotidningar-1770]: data/norrkopingsweckotidningar-1770/norrkopingsweckotidningar-1770.md
[norrkopingsweckotidningar-1780]: data/norrkopingsweckotidningar-1780/norrkopingsweckotidningar-1780.md
[norrlandsposten-1880]: data/norrlandsposten-1880/norrlandsposten-1880.md
[nyadagligtallehanda-1850]: data/nyadagligtallehanda-1850/nyadagligtallehanda-1850.md
[nyadagligtallehanda-1860]: data/nyadagligtallehanda-1860/nyadagligtallehanda-1860.md
[nyadagligtallehanda-1870]: data/nyadagligtallehanda-1870/nyadagligtallehanda-1870.md
[nyadagligtallehanda-1880]: data/nyadagligtallehanda-1880/nyadagligtallehanda-1880.md
[nyadagligtallehanda-1890]: data/nyadagligtallehanda-1890/nyadagligtallehanda-1890.md
[nyakarlskronaweckoblad-1870]: data/nyakarlskronaweckoblad-1870/nyakarlskronaweckoblad-1870.md
[nyawermlandstidningen-1850]: data/nyawermlandstidningen-1850/nyawermlandstidningen-1850.md
[nyawermlandstidningen-1860]: data/nyawermlandstidningen-1860/nyawermlandstidningen-1860.md
[nyawermlandstidningen-1870]: data/nyawermlandstidningen-1870/nyawermlandstidningen-1870.md
[nyawermlandstidningen-1880]: data/nyawermlandstidningen-1880/nyawermlandstidningen-1880.md
[nyawermlandstidningen-1890]: data/nyawermlandstidningen-1890/nyawermlandstidningen-1890.md
[nyawexjobladet-1840]: data/nyawexjobladet-1840/nyawexjobladet-1840.md
[nyawexjobladet-1850]: data/nyawexjobladet-1850/nyawexjobladet-1850.md
[nyawexjobladet-1860]: data/nyawexjobladet-1860/nyawexjobladet-1860.md
[nyawexjobladet-1870]: data/nyawexjobladet-1870/nyawexjobladet-1870.md
[nyawexjobladet-1880]: data/nyawexjobladet-1880/nyawexjobladet-1880.md
[nyawexjobladet-1890]: data/nyawexjobladet-1890/nyawexjobladet-1890.md
[nyttallvarochskamt-1840]: data/nyttallvarochskamt-1840/nyttallvarochskamt-1840.md
[nyttallvarochskamt-1850]: data/nyttallvarochskamt-1850/nyttallvarochskamt-1850.md
[nyttochgammalt-1780]: data/nyttochgammalt-1780/nyttochgammalt-1780.md
[nyttochgammalt-1790]: data/nyttochgammalt-1790/nyttochgammalt-1790.md
[nyttochgammalt-1800]: data/nyttochgammalt-1800/nyttochgammalt-1800.md
[nyttochgammalt-1810]: data/nyttochgammalt-1810/nyttochgammalt-1810.md
[ostergotlandsveckoblad-1880]: data/ostergotlandsveckoblad-1880/ostergotlandsveckoblad-1880.md
[ostergotlandsveckoblad-1890]: data/ostergotlandsveckoblad-1890/ostergotlandsveckoblad-1890.md
[ostgotacorrespondenten-1830]: data/ostgotacorrespondenten-1830/ostgotacorrespondenten-1830.md
[ostgotacorrespondenten-1840]: data/ostgotacorrespondenten-1840/ostgotacorrespondenten-1840.md
[ostgotacorrespondenten-1850]: data/ostgotacorrespondenten-1850/ostgotacorrespondenten-1850.md
[ostgotacorrespondenten-1860]: data/ostgotacorrespondenten-1860/ostgotacorrespondenten-1860.md
[ostgotacorrespondenten-1870]: data/ostgotacorrespondenten-1870/ostgotacorrespondenten-1870.md
[ostgotacorrespondenten-1880]: data/ostgotacorrespondenten-1880/ostgotacorrespondenten-1880.md
[ostgotacorrespondenten-1890]: data/ostgotacorrespondenten-1890/ostgotacorrespondenten-1890.md
[ostgotaposten-1890]: data/ostgotaposten-1890/ostgotaposten-1890.md
[ostgotaposten-1900]: data/ostgotaposten-1900/ostgotaposten-1900.md
[post-ochinrikestidningar-1820]: data/post-ochinrikestidningar-1820/post-ochinrikestidningar-1820.md
[post-ochinrikestidningar-1830]: data/post-ochinrikestidningar-1830/post-ochinrikestidningar-1830.md
[post-ochinrikestidningar-1840]: data/post-ochinrikestidningar-1840/post-ochinrikestidningar-1840.md
[post-ochinrikestidningar-1850]: data/post-ochinrikestidningar-1850/post-ochinrikestidningar-1850.md
[post-ochinrikestidningar-1860]: data/post-ochinrikestidningar-1860/post-ochinrikestidningar-1860.md
[post-ochinrikestidningar-1870]: data/post-ochinrikestidningar-1870/post-ochinrikestidningar-1870.md
[post-ochinrikestidningar-1880]: data/post-ochinrikestidningar-1880/post-ochinrikestidningar-1880.md
[post-ochinrikestidningar-1890]: data/post-ochinrikestidningar-1890/post-ochinrikestidningar-1890.md
[posttidningar-1640]: data/posttidningar-1640/posttidningar-1640.md
[posttidningar-1650]: data/posttidningar-1650/posttidningar-1650.md
[posttidningar-1660]: data/posttidningar-1660/posttidningar-1660.md
[posttidningar-1670]: data/posttidningar-1670/posttidningar-1670.md
[posttidningar-1680]: data/posttidningar-1680/posttidningar-1680.md
[posttidningar-1690]: data/posttidningar-1690/posttidningar-1690.md
[posttidningar-1700]: data/posttidningar-1700/posttidningar-1700.md
[posttidningar-1710]: data/posttidningar-1710/posttidningar-1710.md
[posttidningar-1720]: data/posttidningar-1720/posttidningar-1720.md
[posttidningar-1730]: data/posttidningar-1730/posttidningar-1730.md
[posttidningar-1740]: data/posttidningar-1740/posttidningar-1740.md
[posttidningar-1750]: data/posttidningar-1750/posttidningar-1750.md
[posttidningar-1760]: data/posttidningar-1760/posttidningar-1760.md
[posttidningar-1770]: data/posttidningar-1770/posttidningar-1770.md
[posttidningar-1780]: data/posttidningar-1780/posttidningar-1780.md
[posttidningar-1790]: data/posttidningar-1790/posttidningar-1790.md
[posttidningar-1800]: data/posttidningar-1800/posttidningar-1800.md
[posttidningar-1810]: data/posttidningar-1810/posttidningar-1810.md
[posttidningar-1820]: data/posttidningar-1820/posttidningar-1820.md
[stnlk-1870]: data/stnlk-1870/stnlk-1870.md
[stockholmsdagblad-1820]: data/stockholmsdagblad-1820/stockholmsdagblad-1820.md
[stockholmsdagblad-1830]: data/stockholmsdagblad-1830/stockholmsdagblad-1830.md
[stockholmsdagblad-1840]: data/stockholmsdagblad-1840/stockholmsdagblad-1840.md
[stockholmsdagblad-1850]: data/stockholmsdagblad-1850/stockholmsdagblad-1850.md
[stockholmsdagblad-1860]: data/stockholmsdagblad-1860/stockholmsdagblad-1860.md
[stockholmsdagblad-1870]: data/stockholmsdagblad-1870/stockholmsdagblad-1870.md
[stockholmsdagblad-1880]: data/stockholmsdagblad-1880/stockholmsdagblad-1880.md
[stockholmsdagblad-1890]: data/stockholmsdagblad-1890/stockholmsdagblad-1890.md
[stockholmsposten-1770]: data/stockholmsposten-1770/stockholmsposten-1770.md
[stockholmsposten-1780]: data/stockholmsposten-1780/stockholmsposten-1780.md
[stockholmsposten-1790]: data/stockholmsposten-1790/stockholmsposten-1790.md
[stockholmsposten-1800]: data/stockholmsposten-1800/stockholmsposten-1800.md
[stockholmsposten-1810]: data/stockholmsposten-1810/stockholmsposten-1810.md
[stockholmsposten-1820]: data/stockholmsposten-1820/stockholmsposten-1820.md
[stockholmsposten-1830]: data/stockholmsposten-1830/stockholmsposten-1830.md
[sundsvallstidning-1880]: data/sundsvallstidning-1880/sundsvallstidning-1880.md
[sundsvallstidning-1890]: data/sundsvallstidning-1890/sundsvallstidning-1890.md
[tfwbsol-1840]: data/tfwbsol-1840/tfwbsol-1840.md
[tfwbsol-1850]: data/tfwbsol-1850/tfwbsol-1850.md
[tfwbsol-1860]: data/tfwbsol-1860/tfwbsol-1860.md
[tfwbsol-1870]: data/tfwbsol-1870/tfwbsol-1870.md
[tfwbsol-1880]: data/tfwbsol-1880/tfwbsol-1880.md
[tfwbsol-1890]: data/tfwbsol-1890/tfwbsol-1890.md
[umebladet-1840]: data/umebladet-1840/umebladet-1840.md
[umebladet-1850]: data/umebladet-1850/umebladet-1850.md
[umebladet-1860]: data/umebladet-1860/umebladet-1860.md
[umebladet-1870]: data/umebladet-1870/umebladet-1870.md
[umebladet-1880]: data/umebladet-1880/umebladet-1880.md
[umebladet-1890]: data/umebladet-1890/umebladet-1890.md
[upsala-1840]: data/upsala-1840/upsala-1840.md
[upsala-1850]: data/upsala-1850/upsala-1850.md
[upsala-1860]: data/upsala-1860/upsala-1860.md
[upsala-1870]: data/upsala-1870/upsala-1870.md
[upsala-1880]: data/upsala-1880/upsala-1880.md
[upsala-1890]: data/upsala-1890/upsala-1890.md
[vestmanlandslanstidning-1830]: data/vestmanlandslanstidning-1830/vestmanlandslanstidning-1830.md
[vestmanlandslanstidning-1840]: data/vestmanlandslanstidning-1840/vestmanlandslanstidning-1840.md
[vestmanlandslanstidning-1850]: data/vestmanlandslanstidning-1850/vestmanlandslanstidning-1850.md
[vestmanlandslanstidning-1860]: data/vestmanlandslanstidning-1860/vestmanlandslanstidning-1860.md
[vestmanlandslanstidning-1870]: data/vestmanlandslanstidning-1870/vestmanlandslanstidning-1870.md
[vestmanlandslanstidning-1880]: data/vestmanlandslanstidning-1880/vestmanlandslanstidning-1880.md
[vestmanlandslanstidning-1890]: data/vestmanlandslanstidning-1890/vestmanlandslanstidning-1890.md
[wermlandslanstidning-1870]: data/wermlandslanstidning-1870/wermlandslanstidning-1870.md
[wermlandstidningen-1840]: data/wermlandstidningen-1840/wermlandstidningen-1840.md
[wermlandstidningen-1850]: data/wermlandstidningen-1850/wermlandstidningen-1850.md
[wernamotidning-1870]: data/wernamotidning-1870/wernamotidning-1870.md
[wernamotidning-1880]: data/wernamotidning-1880/wernamotidning-1880.md
[wexjobladet-1810]: data/wexjobladet-1810/wexjobladet-1810.md
[wexjobladet-1820]: data/wexjobladet-1820/wexjobladet-1820.md
[wexjobladet-1830]: data/wexjobladet-1830/wexjobladet-1830.md
[wexjobladet-1840]: data/wexjobladet-1840/wexjobladet-1840.md
[wexjobladet-1850]: data/wexjobladet-1850/wexjobladet-1850.md
[rd-prop]: data/rd-prop/rd-prop.md
[rd-sou]: data/rd-sou/rd-sou.md
[rd-prot]: data/rd-prot/rd-prot.md
[rd-bet]: data/rd-bet/rd-bet.md
[rd-mot]: data/rd-mot/rd-mot.md
[rd-ds]: data/rd-ds/rd-ds.md
[rd-ovr]: data/rd-ovr/rd-ovr.md
[sfs]: data/sfs/sfs.md
[rd-frsrdg]: data/rd-frsrdg/rd-frsrdg.md
[rd-skfr]: data/rd-skfr/rd-skfr.md
[rd-yttr]: data/rd-yttr/rd-yttr.md
[rd-utsk]: data/rd-utsk/rd-utsk.md
[rd-fpm]: data/rd-fpm/rd-fpm.md
[rd-ip]: data/rd-ip/rd-ip.md
[rd-kom]: data/rd-kom/rd-kom.md
[rd-kammakt]: data/rd-kammakt/rd-kammakt.md
[rd-utr]: data/rd-utr/rd-utr.md
[rd-anf-1993-2018]: data/rd-anf-1993-2018/rd-anf-1993-2018.md
[mosel-voxpopuli]: data/mosel-voxpopuli/mosel-voxpopuli.md
[mosel-youtube-commons]: data/mosel-youtube-commons/mosel-youtube-commons.md
[kalmar-1910]: data/kalmar-1910/kalmar-1910.md
[dalpilen-1910]: data/dalpilen-1910/dalpilen-1910.md
[dalpilen-1920]: data/dalpilen-1920/dalpilen-1920.md
[ostgotaposten-1910]: data/ostgotaposten-1910/ostgotaposten-1910.md
[sweachum]: data/sweachum/sweachum.md
[sweacsam]: data/sweacsam/sweacsam.md
[bloggmix1998]: data/bloggmix1998/bloggmix1998.md
[bloggmix1999]: data/bloggmix1999/bloggmix1999.md
[bloggmix2000]: data/bloggmix2000/bloggmix2000.md
[bloggmix2001]: data/bloggmix2001/bloggmix2001.md
[bloggmix2002]: data/bloggmix2002/bloggmix2002.md
[bloggmix2003]: data/bloggmix2003/bloggmix2003.md
[bloggmix2004]: data/bloggmix2004/bloggmix2004.md
[bloggmix2005]: data/bloggmix2005/bloggmix2005.md
[bloggmix2006]: data/bloggmix2006/bloggmix2006.md
[bloggmix2007]: data/bloggmix2007/bloggmix2007.md
[bloggmix2008]: data/bloggmix2008/bloggmix2008.md
[bloggmix2009]: data/bloggmix2009/bloggmix2009.md
[bloggmix2010]: data/bloggmix2010/bloggmix2010.md
[bloggmix2011]: data/bloggmix2011/bloggmix2011.md
[bloggmix2012]: data/bloggmix2012/bloggmix2012.md
[bloggmix2013]: data/bloggmix2013/bloggmix2013.md
[bloggmix2014]: data/bloggmix2014/bloggmix2014.md
[bloggmix2015]: data/bloggmix2015/bloggmix2015.md
[bloggmix2016]: data/bloggmix2016/bloggmix2016.md
[bloggmix2017]: data/bloggmix2017/bloggmix2017.md
[bloggmixodat]: data/bloggmixodat/bloggmixodat.md
[press65]: data/press65/press65.md
[press76]: data/press76/press76.md
[press95]: data/press95/press95.md
[press96]: data/press96/press96.md
[press97]: data/press97/press97.md
[press98]: data/press98/press98.md
[gp1994]: data/gp1994/gp1994.md
[gp2001]: data/gp2001/gp2001.md
[gp2002]: data/gp2002/gp2002.md
[gp2003]: data/gp2003/gp2003.md
[gp2004]: data/gp2004/gp2004.md
[gp2005]: data/gp2005/gp2005.md
[gp2006]: data/gp2006/gp2006.md
[gp2007]: data/gp2007/gp2007.md
[gp2008]: data/gp2008/gp2008.md
[gp2009]: data/gp2009/gp2009.md
[gp2010]: data/gp2010/gp2010.md
[gp2011]: data/gp2011/gp2011.md
[gp2012]: data/gp2012/gp2012.md
[gp2013]: data/gp2013/gp2013.md
[attasidor]: data/attasidor/attasidor.md
[svt-2004]: data/svt-2004/svt-2004.md
[svt-2005]: data/svt-2005/svt-2005.md
[svt-2006]: data/svt-2006/svt-2006.md
[svt-2007]: data/svt-2007/svt-2007.md
[svt-2008]: data/svt-2008/svt-2008.md
[svt-2009]: data/svt-2009/svt-2009.md
[svt-2010]: data/svt-2010/svt-2010.md
[svt-2011]: data/svt-2011/svt-2011.md
[svt-2012]: data/svt-2012/svt-2012.md
[svt-2013]: data/svt-2013/svt-2013.md
[svt-2014]: data/svt-2014/svt-2014.md
[svt-2015]: data/svt-2015/svt-2015.md
[svt-2016]: data/svt-2016/svt-2016.md
[svt-2017]: data/svt-2017/svt-2017.md
[svt-2018]: data/svt-2018/svt-2018.md
[svt-2019]: data/svt-2019/svt-2019.md
[svt-2020]: data/svt-2020/svt-2020.md
[svt-2021]: data/svt-2021/svt-2021.md
[svt-2022]: data/svt-2022/svt-2022.md
[svt-2023]: data/svt-2023/svt-2023.md
[svt-nodate]: data/svt-nodate/svt-nodate.md
[gutenberg]: data/gutenberg/gutenberg.md
[runeberg-diverse]: data/runeberg-diverse/runeberg-diverse.md
[runeberg-folkbbl]: data/runeberg-folkbbl/runeberg-folkbbl.md
[runeberg-rost]: data/runeberg-rost/runeberg-rost.md
[runeberg-tiden]: data/runeberg-tiden/runeberg-tiden.md
[runeberg-urdagkron]: data/runeberg-urdagkron/runeberg-urdagkron.md
[bellman]: data/bellman/bellman.md
[drama]: data/drama/drama.md
[lb-restricted]: data/lb-restricted/lb-restricted.md
[swedish-pd]: data/swedish-pd/swedish-pd.md
[riksarkivet-goteborg-lines]: data/riksarkivet-goteborg-lines/riksarkivet-goteborg-lines.md
[riksarkivet-svea-hovratt-lines]: data/riksarkivet-svea-hovratt-lines/riksarkivet-svea-hovratt-lines.md
[riksarkivet-krigshovratten-lines]: data/riksarkivet-krigshovratten-lines/riksarkivet-krigshovratten-lines.md
[riksarkivet-bergskollegium-lines]: data/riksarkivet-bergskollegium-lines/riksarkivet-bergskollegium-lines.md
[riksarkivet-frihetstiden-lines]: data/riksarkivet-frihetstiden-lines/riksarkivet-frihetstiden-lines.md
[riksarkivet-pahlman-lines]: data/riksarkivet-pahlman-lines/riksarkivet-pahlman-lines.md
[riksarkivet-trolldom-lines]: data/riksarkivet-trolldom-lines/riksarkivet-trolldom-lines.md
[riksarkivet-gota-hovratt-lines]: data/riksarkivet-gota-hovratt-lines/riksarkivet-gota-hovratt-lines.md
[riksarkivet-bergmastaren-lines]: data/riksarkivet-bergmastaren-lines/riksarkivet-bergmastaren-lines.md
[riksarkivet-alvsborgs-losen-lines]: data/riksarkivet-alvsborgs-losen-lines/riksarkivet-alvsborgs-losen-lines.md
[riksarkivet-jonkoping-lines]: data/riksarkivet-jonkoping-lines/riksarkivet-jonkoping-lines.md
[wikisource]: data/wikisource/wikisource.md
<!-- END-LICENSE TABLE -->



## Dataset Structure

The dataset contains text from different sources which are thoroughly defined in [Source Data](#source-data).

### Data Instances

Each entry in the dataset consists of a single text with associated metadata

<!-- START-SAMPLE -->
```py
{
  "id": "standsriksdagen-borgarstandet_00000001",
  "text": "4> PROTOCOL L, HÅLLNA IIOS VÄLLOFLIGA BORGARE-STÅNDET, VID LAGTIMA RIKSDAGEN I STOCKHOLM åren SS56 o[...]",
  "source": "standsriksdagen-borgarstandet",
  "added": "2026-07-27",
  "created": "1856-01-01, 1856-12-31",
  "token_count": 489768
}
```

### Data Fields

An entry in the dataset consists of the following fields:

- `id` (`str`): A unique identifier for each document.
- `text` (`str`): The content of the document.
- `source` (`str`): The source of the document (see [Source Data](#source-data)).
- `added` (`str`): The date when the document was added to this collection.
- `created` (`str`): The date range when the document was originally created.
- `token_count` (`int`): The number of tokens in the sample computed using the Llama 3 tokenizer.
<!-- END-SAMPLE -->

### Data Splits

The entire corpus is provided in the `train` split.

## Dataset Creation

### Curation Rationale

These datasets were collected and curated with the intention of making openly licensed Swedish data available. While this was collected with the intention of developing language models it is likely to have multiple other uses such as examining language development and differences across domains.


### Annotations

This data generally contains no annotation besides the metadata attached to each sample such as what domain it belongs to. 


### Source Data

Below follows a brief overview of the sources in the corpus along with their individual license. To get more information about the individual dataset click the hyperlink in the table.

<details>
<summary><b>Overview Table (click to unfold)</b></summary>

You can learn more about each dataset by pressing the link in the first column.

<!-- START-MAIN TABLE -->
| Source | Description | Domain | N. Tokens | License |
| :--- | :--- | :--- | :--- | :--- |
| [cellar] | The official digital repository for European Union legal documents and open data | Legal | 4.73B | [CC-BY-SA 4.0] |
| [familjeliv-kansliga] | Sentences from the Delicate Room subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 1.55B | [CC-BY 4.0] |
| [flashback-politik] | Sentences from the Politics subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 1.49B | [CC-BY 4.0] |
| [flashback-samhalle] | Sentences from the Society subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 1.45B | [CC-BY 4.0] |
| [swedish-pd] | Public-domain books and periodicals from [PleIAs](https://huggingface.co/datasets/PleIAs/Swedish-PD) | Books | 1.05B | [Public domain] |
| [familjeliv-foralder] | Sentences from the Parents subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 962.66M | [CC-BY 4.0] |
| [statens-offentliga-utredningar] | Historical Swedish government investigation reports ([*Statens offentliga utredningar*](https://spraakbanken.gu.se/en/resources/sou)) from 1922 to 1996 | Report | 909.69M | [CC-BY 4.0] |
| [rd-prop] | Government bills and letters from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-prop) | Legal | 852.65M | [CC-BY 4.0] |
| [flashback-vetenskap] | Sentences from the Science & Technology subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 820.89M | [CC-BY 4.0] |
| [flashback-kultur] | Sentences from the Culture & Entertainment subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 800.01M | [CC-BY 4.0] |
| [familjeliv-gravid] | Sentences from the Pregnant subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 711.06M | [CC-BY 4.0] |
| [riksdagen-propositioner] | Swedish government bills and parliamentary letters from Språkbanken Text's [Bicameral riksdag: Propositions and letters](https://spraakbanken.gu.se/en/resources/tkr-propositioner-skrivelser) | Report | 699.11M | [CC-BY 4.0] |
| [riksdagen-protokoll] | Swedish parliamentary debate protocols from Språkbanken Text's [Bicameral riksdag: Protocols](https://spraakbanken.gu.se/en/resources/tkr-protokoll) | Report | 624.22M | [CC-BY 4.0] |
| [flashback-hem] | Sentences from the Home & Garden subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 617.34M | [CC-BY 4.0] |
| [lb-open] | Literary works from [Litteraturbanken](https://litteraturbanken.se), the Swedish Literature Bank | Books | 592.11M | [CC-BY 4.0] |
| [rd-sou] | Government inquiry reports from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-sou) | Report | 575.76M | [CC-BY 4.0] |
| [flashback-dator] | Sentences from the Computers & IT subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 512.80M | [CC-BY 4.0] |
| [familjeliv-allmanna-samhalle] | Sentences from the Society subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 494.22M | [CC-BY 4.0] |
| [rd-prot] | Parliamentary records from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-prot) | Legal | 492.40M | [CC-BY 4.0] |
| [flashback-sport] | Sentences from the Sports subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 470.50M | [CC-BY 4.0] |
| [rd-bet] | Committee reports from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-bet) | Legal | 459.38M | [CC-BY 4.0] |
| [familjeliv-medlem-foraldrar] | Sentences from the Member Parents subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 442.58M | [CC-BY 4.0] |
| [familjeliv-medlem-allmanna] | Sentences from the Member General subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 431.58M | [CC-BY 4.0] |
| [familjeliv-medlem-vantarbarn] | Sentences from the Member Expecting Children subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 431.54M | [CC-BY 4.0] |
| [riksdagen-betankanden] | Swedish parliamentary committee reports, memorandums and opinions from Språkbanken Text's [Bicameral riksdag: Reports, memorandums and opinions](https://spraakbanken.gu.se/en/resources/tkr-bet-mem-utl) | Report | 423.50M | [CC-BY 4.0] |
| [flashback-droger] | Sentences from the Drugs subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 403.09M | [CC-BY 4.0] |
| [wikipedia-sv] | Articles from the Swedish edition of [Wikipedia](https://sv.wikipedia.org), the free encyclopedia | Encyclopedic | 362.29M | [CC-BY-SA 4.0] |
| [stockholmsdagblad-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1880) | News | 342.05M | [CC-BY 4.0] |
| [rd-mot] | Parliamentary motions from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-mot) | Legal | 326.66M | [CC-BY 4.0] |
| [lb-restricted] | Scrambled sentences from [Litteraturbanken’s protected works](https://sprakbanken.se/resurser/lb-restricted) | Books | 299.45M | [CC-BY 4.0] |
| [flashback-ovrigt] | Sentences from the Other subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 278.09M | [CC-BY 4.0] |
| [familjeliv-planerarbarn] | Sentences from the Planning for Children subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 276.12M | [CC-BY 4.0] |
| [stockholmsdagblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1870) | News | 266.45M | [CC-BY 4.0] |
| [familjeliv-sexsamlevnad] | Sentences from the Sex & Cohabitation subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 260.96M | [CC-BY 4.0] |
| [nyadagligtallehanda-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Dagligt Allehanda 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-nyadagligtallehanda-1880) | News | 253.10M | [CC-BY 4.0] |
| [ghost-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1880) | News | 249.05M | [CC-BY 4.0] |
| [flashback-ekonomi] | Sentences from the Economy subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 248.01M | [CC-BY 4.0] |
| [familjeliv-svartattfabarn] | Sentences from the Difficult to Have Children subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 232.18M | [CC-BY 4.0] |
| [poeter] | Poem lines from [Poeter.se](https://www.poeter.se), a Swedish poetry community website | Books | 220.32M | [CC-BY 4.0] |
| [rd-anf-1993-2018] | Parliamentary speeches from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-anf-1993-2018) | Legal | 220.00M | [CC-BY 4.0] |
| [nyadagligtallehanda-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Dagligt Allehanda 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nyadagligtallehanda-1870) | News | 218.86M | [CC-BY 4.0] |
| [familjeliv-allmanna-kropp] | Sentences from the General Threads – Body subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 218.79M | [CC-BY 4.0] |
| [aftonbladet-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1880) | News | 218.74M | [CC-BY 4.0] |
| [aftonbladet-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1890) | News | 216.96M | [CC-BY 4.0] |
| [stockholmsdagblad-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1860) | News | 216.66M | [CC-BY 4.0] |
| [aftonbladet-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1870) | News | 210.04M | [CC-BY 4.0] |
| [ghost-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1870) | News | 208.44M | [CC-BY 4.0] |
| [goteborgsposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgsposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsposten-1880) | News | 207.22M | [CC-BY 4.0] |
| [stockholmsdagblad-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1890) | News | 205.84M | [CC-BY 4.0] |
| [aftonbladet-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1860) | News | 205.68M | [CC-BY 4.0] |
| [mosel-voxpopuli] | Swedish speech transcripts from [MOSEL VoxPopuli](https://huggingface.co/datasets/FBK-MT/mosel) | Spoken | 205.62M | [CC-BY 4.0] |
| [nyadagligtallehanda-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Dagligt Allehanda 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-nyadagligtallehanda-1860) | News | 204.22M | [CC-BY 4.0] |
| [flashback-livsstil] | Sentences from the Lifestyle subforum of [Flashback](https://www.flashback.org), a large Swedish internet forum | Social Media | 189.25M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1880) | News | 177.57M | [CC-BY 4.0] |
| [aftonbladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1850) | News | 176.76M | [CC-BY 4.0] |
| [stockholmsdagblad-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1850) | News | 173.51M | [CC-BY 4.0] |
| [familjeliv-medlem-planerarbarn] | Sentences from the Member Planning for Children subforum of [Familjeliv](https://www.familjeliv.se), a Swedish parenting forum | Social Media | 170.87M | [CC-BY 4.0] |
| [ghost-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1890) | News | 169.20M | [CC-BY 4.0] |
| [ghost-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1860) | News | 167.72M | [CC-BY 4.0] |
| [nyadagligtallehanda-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Dagligt Allehanda 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-nyadagligtallehanda-1890) | News | 163.94M | [CC-BY 4.0] |
| [flashback-sex] | Sentences from the "Sex" subforum of [Flashback](https://www.flashback.org) | Social Media | 155.59M | [CC-BY 4.0] |
| [stockholmsdagblad-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1840) | News | 153.84M | [CC-BY 4.0] |
| [goteborgsposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgsposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsposten-1870) | News | 150.59M | [CC-BY 4.0] |
| [flashback-fordon] | Sentences from the "Fordon & trafik" (Vehicles & Traffic) subforum of [Flashback](https://www.flashback.org) | Social Media | 150.42M | [CC-BY 4.0] |
| [bloggmix2011] | Swedish blog sentences from [Blog mix 2011](https://spraakbanken.gu.se/en/resources/bloggmix2011) | Social Media | 149.99M | [CC-BY 4.0] |
| [riksdagen-motioner] | Swedish parliamentary motions from Språkbanken Text's [Bicameral riksdag: Motions](https://spraakbanken.gu.se/en/resources/tkr-motioner) | Report | 149.83M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1860) | News | 148.86M | [CC-BY 4.0] |
| [bloggmix2010] | Swedish blog sentences from [Blog mix 2010](https://spraakbanken.gu.se/en/resources/bloggmix2010) | Social Media | 145.61M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1870) | News | 143.94M | [CC-BY 4.0] |
| [standsriksdagen-bihang] | Texts from Ståndsriksdagen: Bihang m.m., part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 139.71M | [CC-BY 4.0] |
| [familjeliv-allmanna-noje] | Sentences from the "Allmänna rubriker – Nöje" (General Threads – Entertainment) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 137.74M | [CC-BY 4.0] |
| [stockholmsdagblad-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1830) | News | 137.41M | [CC-BY 4.0] |
| [flashback-mat] | Sentences from the "Mat, dryck & tobak" (Food, Beverages & Tobacco) subforum of [Flashback](https://www.flashback.org) | Social Media | 137.17M | [CC-BY 4.0] |
| [aftonbladet-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1840) | News | 135.50M | [CC-BY 4.0] |
| [norrkopingstidningar-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1880) | News | 134.12M | [CC-BY 4.0] |
| [riksdagen-berattelser] | Swedish parliamentary narratives and accounts from Språkbanken Text's [Bicameral riksdag: Narratives and accounts](https://spraakbanken.gu.se/en/resources/tkr-berattelser-redogorelser-frsrdg) | Report | 129.77M | [CC-BY 4.0] |
| [goteborgsposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgsposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsposten-1890) | News | 128.67M | [CC-BY 4.0] |
| [standsriksdagen-adelsstandet] | Texts from Ståndsriksdagen: Adelsståndet, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 126.98M | [CC-BY 4.0] |
| [riksdagen-utredningar] | Swedish parliamentary government investigation texts from Språkbanken Text's [Bicameral riksdag: Government official investigations](https://spraakbanken.gu.se/en/resources/tkr-utredningar-kombet-sou) | Report | 125.48M | [CC-BY 4.0] |
| [bloggmix2012] | Swedish blog sentences from [Blog mix 2012](https://spraakbanken.gu.se/en/resources/bloggmix2012) | Social Media | 120.02M | [CC-BY 4.0] |
| [familjeliv-allmanna-hushem] | Sentences from the "Allmänna rubriker – Hus & hem" (General Threads – House & Home) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 117.42M | [CC-BY 4.0] |
| [bloggmix2009] | Swedish blog sentences from [Blog mix 2009](https://spraakbanken.gu.se/en/resources/bloggmix2009) | Social Media | 113.45M | [CC-BY 4.0] |
| [goteborgsposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgsposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsposten-1860) | News | 108.77M | [CC-BY 4.0] |
| [rd-ds] | Ministry reports from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-ds) | Report | 106.37M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1850) | News | 104.30M | [CC-BY 4.0] |
| [ghost-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1850) | News | 101.89M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1880) | News | 101.79M | [CC-BY 4.0] |
| [familjeliv-allmanna-familjeliv] | Sentences from the "Allmänna rubriker – Familjeliv.se" (General Threads – Familjeliv.se) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 98.56M | [CC-BY 4.0] |
| [norrkopingstidningar-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1870) | News | 97.67M | [CC-BY 4.0] |
| [bloggmix2013] | Swedish blog sentences from [Blog mix 2013](https://spraakbanken.gu.se/en/resources/bloggmix2013) | Social Media | 94.34M | [CC-BY 4.0] |
| [kalmar-1910] | Historical newspaper issues from [Kubhist: Kalmar 1910's](https://spraakbanken.gu.se/en/resources/kubhist-kalmar-1910) | News | 93.71M | [CC-BY 4.0] |
| [norrkopingstidningar-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1890) | News | 91.26M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1840) | News | 85.56M | [CC-BY 4.0] |
| [rd-kom] | EU Commission documents from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-kom) | Legal | 82.40M | [CC-BY 4.0] |
| [dagligtallehanda-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1840) | News | 81.86M | [CC-BY 4.0] |
| [familjeliv-allmanna-ekonomi] | Sentences from the "Allmänna rubriker – Ekonomi & juridik" (General Threads – Economics & Law) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 79.97M | [CC-BY 4.0] |
| [nerikesallehanda-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1880) | News | 79.11M | [CC-BY 4.0] |
| [barometern-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1880) | News | 78.14M | [CC-BY 4.0] |
| [kalmar-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Kalmar 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-kalmar-1890) | News | 77.93M | [CC-BY 4.0] |
| [familjeliv-allmanna-husdjur] | Sentences from the "Allmänna rubriker – Husdjur" (General Threads – Pets) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 77.04M | [CC-BY 4.0] |
| [kalmar-1900] | Historical Swedish newspaper issues from Språkbanken Text's [Kalmar 1900's](https://spraakbanken.gu.se/en/resources/kubhist2-kalmar-1900) | News | 76.06M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1890) | News | 75.81M | [CC-BY 4.0] |
| [kalmar-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Kalmar 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-kalmar-1880) | News | 74.51M | [CC-BY 4.0] |
| [dagligtallehanda-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1820) | News | 73.62M | [CC-BY 4.0] |
| [nyawermlandstidningen-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wermlandstidningen 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawermlandstidningen-1880) | News | 73.12M | [CC-BY 4.0] |
| [upsala-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1880) | News | 71.94M | [CC-BY 4.0] |
| [standsriksdagen-borgarstandet] | Texts from Ståndsriksdagen: Borgarståndet, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 71.64M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1870) | News | 70.81M | [CC-BY 4.0] |
| [familjeliv-allmanna-sandladan] | Sentences from the "Allmänna rubriker – Sandlådan" (General Threads – Sandbox) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 68.62M | [CC-BY 4.0] |
| [bloggmix2008] | Swedish blog sentences from [Blog mix 2008](https://spraakbanken.gu.se/en/resources/bloggmix2008) | Social Media | 66.98M | [CC-BY 4.0] |
| [standsriksdagen-bondestandet] | Texts from Ståndsriksdagen: Bondeståndet, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 66.32M | [CC-BY 4.0] |
| [dagligtallehanda-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1810) | News | 65.58M | [CC-BY 4.0] |
| [flashback-resor] | Sentences from the "Resor" (Travel) subforum of [Flashback](https://www.flashback.org) | Social Media | 64.76M | [CC-BY 4.0] |
| [aftonbladet-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1830) | News | 63.05M | [CC-BY 4.0] |
| [europarl-sv] | Texts from the Swedish portion of the [Europarl](https://spraakbanken.gu.se/resurser/europarl-sv) corpus, transcribed proceedings of the European Parliament | Speeches | 63.02M | [CC-BY 4.0] |
| [standsriksdagen-prastestandet] | Texts from Ståndsriksdagen: Prästeståndet, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 62.12M | [CC-BY 4.0] |
| [bloggmix2014] | Swedish blog sentences from [Blog mix 2014](https://spraakbanken.gu.se/en/resources/bloggmix2014) | Social Media | 61.90M | [CC-BY 4.0] |
| [riksdagen-skrivelser] | Swedish parliamentary letters and communications from Språkbanken Text's [Bicameral riksdag: Letters of the Riksdag](https://spraakbanken.gu.se/en/resources/tkr-rskr) | Report | 61.79M | [CC-BY 4.0] |
| [harnosandsposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1880) | News | 61.51M | [CC-BY 4.0] |
| [stockholmsdagblad-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholms Dagblad 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsdagblad-1820) | News | 60.41M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1830) | News | 59.96M | [CC-BY 4.0] |
| [kalmar-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Kalmar 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-kalmar-1870) | News | 59.12M | [CC-BY 4.0] |
| [dagligtallehanda-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1830) | News | 58.54M | [CC-BY 4.0] |
| [flashback-om-flashback] | Sentences from the "Om Flashback" (About Flashback) subforum of [Flashback](https://www.flashback.org) | Social Media | 57.87M | [CC-BY 4.0] |
| [norrkopingstidningar-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1860) | News | 57.40M | [CC-BY 4.0] |
| [sundsvallstidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Sundsvalls Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-sundsvallstidning-1880) | News | 57.13M | [CC-BY 4.0] |
| [barometern-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1890) | News | 55.87M | [CC-BY 4.0] |
| [nerikesallehanda-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1890) | News | 55.71M | [CC-BY 4.0] |
| [nerikesallehanda-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1870) | News | 55.44M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1890) | News | 54.41M | [CC-BY 4.0] |
| [dagligtallehanda-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1800) | News | 54.38M | [CC-BY 4.0] |
| [kristianstadsbladet-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Kristianstadsbladet 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-kristianstadsbladet-1880) | News | 53.76M | [CC-BY 4.0] |
| [familjeliv-allmanna-fritid] | Sentences from the "Allmänna rubriker – Fritid & hobby" (General Threads – Leisure & Hobby) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 52.49M | [CC-BY 4.0] |
| [dalpilen-1910] | Historical newspaper issues from [Kubhist: Dalpilen 1910's](https://spraakbanken.gu.se/en/resources/kubhist-dalpilen-1910) | News | 52.09M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1880) | News | 52.05M | [CC-BY 4.0] |
| [lundsweckoblad-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1880) | News | 51.73M | [CC-BY 4.0] |
| [ghost-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1840) | News | 51.52M | [CC-BY 4.0] |
| [barometern-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1870) | News | 50.60M | [CC-BY 4.0] |
| [sundsvallstidning-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Sundsvalls Tidning 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-sundsvallstidning-1890) | News | 50.41M | [CC-BY 4.0] |
| [jonkopingsposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsposten-1880) | News | 49.86M | [CC-BY 4.0] |
| [borastidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1880) | News | 48.83M | [CC-BY 4.0] |
| [karlskronaweckoblad-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Karlskrona Weckoblad 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-karlskronaweckoblad-1880) | News | 48.68M | [CC-BY 4.0] |
| [bloggmixodat] | Undated blog sentences from Språkbanken’s [Blog mix](https://spraakbanken.gu.se/en/resources/bloggmixodat) | Social Media | 48.48M | [CC-BY 4.0] |
| [folketsrost-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Folkets Röst 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-folketsrost-1850) | News | 48.24M | [CC-BY 4.0] |
| [kristianstadsbladet-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Kristianstadsbladet 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-kristianstadsbladet-1890) | News | 47.96M | [CC-BY 4.0] |
| [rd-ip] | Interpellations from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-ip) | Legal | 47.90M | [CC-BY 4.0] |
| [malmoallehanda-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1880) | News | 47.06M | [CC-BY 4.0] |
| [upsala-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1890) | News | 46.80M | [CC-BY 4.0] |
| [malmoallehanda-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1870) | News | 46.50M | [CC-BY 4.0] |
| [nyawermlandstidningen-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wermlandstidningen 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawermlandstidningen-1890) | News | 46.28M | [CC-BY 4.0] |
| [rd-ovr] | Parliamentary documents from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-ovr) | Legal | 46.27M | [CC-BY 4.0] |
| [upsala-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1870) | News | 44.35M | [CC-BY 4.0] |
| [riksdagen-register] | Swedish parliamentary register texts from Språkbanken Text's [Bicameral riksdag: Register](https://spraakbanken.gu.se/en/resources/tkr-register) | Report | 44.16M | [CC-BY 4.0] |
| [karlshamnsallehanda-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1880) | News | 43.76M | [CC-BY 4.0] |
| [harnosandsposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1890) | News | 43.62M | [CC-BY 4.0] |
| [kristianstadsbladet-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Kristianstadsbladet 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-kristianstadsbladet-1870) | News | 43.46M | [CC-BY 4.0] |
| [bloggmix2015] | Swedish blog sentences from [Blog mix 2015](https://spraakbanken.gu.se/en/resources/bloggmix2015) | Social Media | 43.33M | [CC-BY 4.0] |
| [karlshamnsallehanda-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1890) | News | 43.30M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1890) | News | 42.87M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1860) | News | 42.85M | [CC-BY 4.0] |
| [lundsweckoblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1870) | News | 42.70M | [CC-BY 4.0] |
| [jonkopingsposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsposten-1890) | News | 42.68M | [CC-BY 4.0] |
| [gp2005] | News sentences from [Göteborgs-Posten 2005](https://spraakbanken.gu.se/en/resources/gp2005) | News | 42.48M | [CC-BY 4.0] |
| [laakartidningen] | Sentences from [Läkartidningen](https://lakartidningen.se), the peer-reviewed journal of the Swedish Medical Association, 1996–2006 | Medical | 42.40M | [CC-BY 4.0] |
| [gp2004] | News sentences from [Göteborgs-Posten 2004](https://spraakbanken.gu.se/en/resources/gp2004) | News | 41.79M | [CC-BY 4.0] |
| [sfs] | Swedish statutes from [Svensk författningssamling](https://spraakbanken.gu.se/en/resources/sfs) | Legal | 41.09M | [CC-BY 4.0] |
| [gp1994] | News sentences from [Göteborgs-Posten 1994](https://spraakbanken.gu.se/en/resources/gp1994) | News | 40.60M | [CC-BY 4.0] |
| [svt-2016] | News sentences from [SVT 2016](https://spraakbanken.gu.se/en/resources/svt-2016) | News | 40.58M | [CC-BY 4.0] |
| [gp2006] | News sentences from [Göteborgs-Posten 2006](https://spraakbanken.gu.se/en/resources/gp2006) | News | 40.51M | [CC-BY 4.0] |
| [lundsweckoblad-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1890) | News | 40.49M | [CC-BY 4.0] |
| [dagligtallehanda-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1790) | News | 40.36M | [CC-BY 4.0] |
| [dalpilen-1920] | Historical newspaper issues from [Kubhist: Dalpilen 1920's](https://spraakbanken.gu.se/en/resources/kubhist-dalpilen-1920) | News | 39.51M | [CC-BY 4.0] |
| [svt-2017] | News sentences from [SVT 2017](https://spraakbanken.gu.se/en/resources/svt-2017) | News | 39.50M | [CC-BY 4.0] |
| [nerikesallehanda-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1860) | News | 39.49M | [CC-BY 4.0] |
| [falkopingstidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Falköpings Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-falkopingstidning-1880) | News | 39.22M | [CC-BY 4.0] |
| [dalpilen-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1890) | News | 38.97M | [CC-BY 4.0] |
| [gp2002] | News sentences from [Göteborgs-Posten 2002](https://spraakbanken.gu.se/en/resources/gp2002) | News | 38.94M | [CC-BY 4.0] |
| [post-ochinrikestidningar-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Post- och Inrikes Tidningar 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-post-ochinrikestidningar-1820) | News | 38.22M | [CC-BY 4.0] |
| [tfwbsol-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1880) | News | 38.14M | [CC-BY 4.0] |
| [rd-frsrdg] | Parliamentary reports and proposals from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-frsrdg) | Legal | 38.06M | [CC-BY 4.0] |
| [nyawexjobladet-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1880) | News | 37.77M | [CC-BY 4.0] |
| [tfwbsol-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1890) | News | 37.37M | [CC-BY 4.0] |
| [nyawermlandstidningen-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wermlandstidningen 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawermlandstidningen-1870) | News | 36.71M | [CC-BY 4.0] |
| [malmoallehanda-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1860) | News | 36.48M | [CC-BY 4.0] |
| [karlskronaweckoblad-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Karlskrona Weckoblad 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-karlskronaweckoblad-1890) | News | 35.64M | [CC-BY 4.0] |
| [harnosandsposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1870) | News | 35.62M | [CC-BY 4.0] |
| [jonkopingsposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsposten-1870) | News | 35.53M | [CC-BY 4.0] |
| [svt-2015] | News sentences from [SVT 2015](https://spraakbanken.gu.se/en/resources/svt-2015) | News | 35.48M | [CC-BY 4.0] |
| [svt-2018] | News sentences from [SVT 2018](https://spraakbanken.gu.se/en/resources/svt-2018) | News | 35.35M | [CC-BY 4.0] |
| [gp2003] | News sentences from [Göteborgs-Posten 2003](https://spraakbanken.gu.se/en/resources/gp2003) | News | 35.35M | [CC-BY 4.0] |
| [norrbottenskuriren-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottenskuriren 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottenskuriren-1890) | News | 34.76M | [CC-BY 4.0] |
| [dagligtallehanda-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1780) | News | 34.13M | [CC-BY 4.0] |
| [svt-2019] | News sentences from [SVT 2019](https://spraakbanken.gu.se/en/resources/svt-2019) | News | 33.98M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1870) | News | 33.69M | [CC-BY 4.0] |
| [tfwbsol-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1870) | News | 32.97M | [CC-BY 4.0] |
| [dalpilen-1900] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1900's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1900) | News | 32.52M | [CC-BY 4.0] |
| [gp2007] | News sentences from [Göteborgs-Posten 2007](https://spraakbanken.gu.se/en/resources/gp2007) | News | 32.51M | [CC-BY 4.0] |
| [gp2001] | News sentences from [Göteborgs-Posten 2001](https://spraakbanken.gu.se/en/resources/gp2001) | News | 32.26M | [CC-BY 4.0] |
| [karlshamnsallehanda-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1870) | News | 31.93M | [CC-BY 4.0] |
| [jonkopingsbladet-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsbladet 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsbladet-1860) | News | 31.93M | [CC-BY 4.0] |
| [barometern-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1860) | News | 31.60M | [CC-BY 4.0] |
| [kristianstadsbladet-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Kristianstadsbladet 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-kristianstadsbladet-1860) | News | 31.48M | [CC-BY 4.0] |
| [upsala-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1860) | News | 31.39M | [CC-BY 4.0] |
| [borastidning-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1890) | News | 30.85M | [CC-BY 4.0] |
| [norraskane-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Norra Skåne 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-norraskane-1880) | News | 30.81M | [CC-BY 4.0] |
| [norrkopingstidningar-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1850) | News | 30.46M | [CC-BY 4.0] |
| [gp2009] | News sentences from [Göteborgs-Posten 2009](https://spraakbanken.gu.se/en/resources/gp2009) | News | 30.41M | [CC-BY 4.0] |
| [dalpilen-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1880) | News | 30.05M | [CC-BY 4.0] |
| [bloggmix2007] | Swedish blog sentences from [Blog mix 2007](https://spraakbanken.gu.se/en/resources/bloggmix2007) | Social Media | 30.04M | [CC-BY 4.0] |
| [rd-skfr] | Written parliamentary questions and answers from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-skfr) | Legal | 30.02M | [CC-BY 4.0] |
| [nyawexjobladet-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1870) | News | 29.94M | [CC-BY 4.0] |
| [svt-2020] | News sentences from [SVT 2020](https://spraakbanken.gu.se/en/resources/svt-2020) | News | 29.83M | [CC-BY 4.0] |
| [gp2008] | News sentences from [Göteborgs-Posten 2008](https://spraakbanken.gu.se/en/resources/gp2008) | News | 29.82M | [CC-BY 4.0] |
| [familjeliv-anglarum] | Sentences from the "Änglarum" (Angel Room) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 29.69M | [CC-BY 4.0] |
| [gp2010] | News sentences from [Göteborgs-Posten 2010](https://spraakbanken.gu.se/en/resources/gp2010) | News | 29.65M | [CC-BY 4.0] |
| [svt-2014] | News sentences from [SVT 2014](https://spraakbanken.gu.se/en/resources/svt-2014) | News | 29.59M | [CC-BY 4.0] |
| [gp2011] | News sentences from [Göteborgs-Posten 2011](https://spraakbanken.gu.se/en/resources/gp2011) | News | 29.46M | [CC-BY 4.0] |
| [carlscronaswekoblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1870) | News | 29.41M | [CC-BY 4.0] |
| [norraskane-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Norra Skåne 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-norraskane-1890) | News | 29.31M | [CC-BY 4.0] |
| [nyawexjobladet-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1890) | News | 28.97M | [CC-BY 4.0] |
| [norrbottenskuriren-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottenskuriren 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottenskuriren-1880) | News | 28.52M | [CC-BY 4.0] |
| [bloggmix2016] | Swedish blog sentences from [Blog mix 2016](https://spraakbanken.gu.se/en/resources/bloggmix2016) | Social Media | 28.33M | [CC-BY 4.0] |
| [falkopingstidning-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Falköpings Tidning 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-falkopingstidning-1890) | News | 28.19M | [CC-BY 4.0] |
| [blekingsposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Blekingsposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-blekingsposten-1870) | News | 27.91M | [CC-BY 4.0] |
| [svt-2021] | News sentences from [SVT 2021](https://spraakbanken.gu.se/en/resources/svt-2021) | News | 27.86M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1850) | News | 27.60M | [CC-BY 4.0] |
| [lundsweckoblad-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1860) | News | 27.05M | [CC-BY 4.0] |
| [borastidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1870) | News | 26.86M | [CC-BY 4.0] |
| [sweachum] | Academic sentences in the [humanities](https://spraakbanken.gu.se/en/resources/sweachum) | Academic Writing | 26.83M | [CC-BY 4.0] |
| [gp2012] | News sentences from [Göteborgs-Posten 2012](https://spraakbanken.gu.se/en/resources/gp2012) | News | 26.64M | [CC-BY 4.0] |
| [stnlk-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Sundsvalls Tidning Norrländska Korrespondenten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-stnlk-1870) | News | 26.62M | [CC-BY 4.0] |
| [falkopingstidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Falköpings Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-falkopingstidning-1870) | News | 26.49M | [CC-BY 4.0] |
| [wermlandslanstidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Wermlands läns Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-wermlandslanstidning-1870) | News | 26.34M | [CC-BY 4.0] |
| [svt-2022] | News sentences from [SVT 2022](https://spraakbanken.gu.se/en/resources/svt-2022) | News | 25.99M | [CC-BY 4.0] |
| [umebladet-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1880) | News | 25.73M | [CC-BY 4.0] |
| [svt-2013] | News sentences from [SVT 2013](https://spraakbanken.gu.se/en/resources/svt-2013) | News | 25.72M | [CC-BY 4.0] |
| [nerikesallehanda-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1850) | News | 25.27M | [CC-BY 4.0] |
| [umebladet-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1890) | News | 25.10M | [CC-BY 4.0] |
| [press97] | Swedish newspaper sentences from [Press 1997](https://spraakbanken.gu.se/en/resources/press97) | News | 25.06M | [CC-BY 4.0] |
| [tfwbsol-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1860) | News | 24.62M | [CC-BY 4.0] |
| [gp2013] | News sentences from [Göteborgs-Posten 2013](https://spraakbanken.gu.se/en/resources/gp2013) | News | 24.50M | [CC-BY 4.0] |
| [dagligtallehanda-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1770) | News | 24.23M | [CC-BY 4.0] |
| [ostgotaposten-1900] | Historical Swedish newspaper issues from Språkbanken Text's [Östgötaposten 1900's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotaposten-1900) | News | 23.96M | [CC-BY 4.0] |
| [gutenberg] | Swedish-language books from [Project Gutenberg](https://www.gutenberg.org/) | Books | 23.90M | [Unrestricted under US copyright law] |
| [carlscronaswekoblad-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1860) | News | 23.83M | [CC-BY 4.0] |
| [aftonbladet-1900] | Historical Swedish newspaper issues from Språkbanken Text's [Aftonbladet 1900's](https://spraakbanken.gu.se/en/resources/kubhist2-aftonbladet-1900) | News | 23.79M | [CC-BY 4.0] |
| [nyawermlandstidningen-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wermlandstidningen 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawermlandstidningen-1860) | News | 23.04M | [CC-BY 4.0] |
| [malmoallehanda-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1890) | News | 22.61M | [CC-BY 4.0] |
| [blekingsposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Blekingsposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-blekingsposten-1860) | News | 22.41M | [CC-BY 4.0] |
| [upsala-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1850) | News | 22.29M | [CC-BY 4.0] |
| [nlk-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norrländska Korrespondenten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-nlk-1860) | News | 22.02M | [CC-BY 4.0] |
| [barometern-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1850) | News | 21.97M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1860) | News | 21.44M | [CC-BY 4.0] |
| [nyawexjobladet-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1860) | News | 21.37M | [CC-BY 4.0] |
| [rd-yttr] | Committee opinions from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-yttr) | Legal | 21.00M | [CC-BY 4.0] |
| [jonkopingsbladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsbladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsbladet-1850) | News | 20.80M | [CC-BY 4.0] |
| [karlshamnsallehanda-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1860) | News | 20.60M | [CC-BY 4.0] |
| [norrbottensposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1890) | News | 20.48M | [CC-BY 4.0] |
| [dalpilen-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1870) | News | 20.34M | [CC-BY 4.0] |
| [malmoallehanda-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1850) | News | 20.07M | [CC-BY 4.0] |
| [sweacsam] | Academic sentences in the [social sciences](https://spraakbanken.gu.se/en/resources/sweacsam) | Academic Writing | 20.06M | [CC-BY 4.0] |
| [kalmar-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Kalmar 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-kalmar-1860) | News | 19.85M | [CC-BY 4.0] |
| [press98] | Swedish newspaper sentences from [Press 1998](https://spraakbanken.gu.se/en/resources/press98) | News | 19.26M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1840) | News | 19.11M | [CC-BY 4.0] |
| [norrkopingstidningar-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1840) | News | 18.98M | [CC-BY 4.0] |
| [posttidningar-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1810) | News | 18.67M | [CC-BY 4.0] |
| [faluposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Faluposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-faluposten-1870) | News | 18.53M | [CC-BY 4.0] |
| [svt-2010] | News sentences from [SVT 2010](https://spraakbanken.gu.se/en/resources/svt-2010) | News | 18.48M | [CC-BY 4.0] |
| [falkopingstidning-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Falköpings Tidning 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-falkopingstidning-1860) | News | 18.37M | [CC-BY 4.0] |
| [harnosandsposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1860) | News | 18.15M | [CC-BY 4.0] |
| [gotlandstidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Gotlands Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-gotlandstidning-1870) | News | 18.15M | [CC-BY 4.0] |
| [borastidning-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1860) | News | 18.07M | [CC-BY 4.0] |
| [dagens-arena] | Sentences from Dagens Arena, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/da) | News | 17.80M | [CC-BY 4.0] |
| [carlscronaswekoblad-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1850) | News | 17.70M | [CC-BY 4.0] |
| [svt-2012] | News sentences from [SVT 2012](https://spraakbanken.gu.se/en/resources/svt-2012) | News | 17.61M | [CC-BY 4.0] |
| [dalpilen-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1860) | News | 17.51M | [CC-BY 4.0] |
| [inrikestidningar-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1810) | News | 17.21M | [CC-BY 4.0] |
| [svt-2011] | News sentences from [SVT 2011](https://spraakbanken.gu.se/en/resources/svt-2011) | News | 17.17M | [CC-BY 4.0] |
| [ghost-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Handels- och Sjöfartstidning 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-ghost-1830) | News | 17.15M | [CC-BY 4.0] |
| [svt-2009] | News sentences from [SVT 2009](https://spraakbanken.gu.se/en/resources/svt-2009) | News | 16.90M | [CC-BY 4.0] |
| [familjeliv-adoption] | Sentences from the "Adoption" subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 16.23M | [CC-BY 4.0] |
| [goteborgsweckoblad-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Weckoblad 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsweckoblad-1880) | News | 16.13M | [CC-BY 4.0] |
| [posttidningar-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1800) | News | 15.72M | [CC-BY 4.0] |
| [stockholmsposten-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1780) | News | 15.59M | [CC-BY 4.0] |
| [nyawermlandstidningen-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wermlandstidningen 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawermlandstidningen-1850) | News | 15.20M | [CC-BY 4.0] |
| [sv-covid-19] | Sentences from sv-COVID-19, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/sv-covid-19) | News | 15.05M | [CC-BY 4.0] |
| [umebladet-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1870) | News | 14.96M | [CC-BY 4.0] |
| [svt-2008] | News sentences from [SVT 2008](https://spraakbanken.gu.se/en/resources/svt-2008) | News | 14.93M | [CC-BY 4.0] |
| [blekingsposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Blekingsposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-blekingsposten-1880) | News | 14.89M | [CC-BY 4.0] |
| [nlk-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Norrländska Korrespondenten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nlk-1850) | News | 14.74M | [CC-BY 4.0] |
| [stockholmsposten-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1820) | News | 14.72M | [CC-BY 4.0] |
| [norrbottensposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1880) | News | 14.57M | [CC-BY 4.0] |
| [stockholmsposten-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1810) | News | 14.55M | [CC-BY 4.0] |
| [stockholmsposten-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1800) | News | 14.53M | [CC-BY 4.0] |
| [inrikestidningar-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1800) | News | 14.19M | [CC-BY 4.0] |
| [press95] | Swedish newspaper sentences from [Press 1995](https://spraakbanken.gu.se/en/resources/press95) | News | 14.19M | [CC-BY 4.0] |
| [stockholmsposten-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1790) | News | 14.15M | [CC-BY 4.0] |
| [borastidning-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1850) | News | 14.08M | [CC-BY 4.0] |
| [svt-2023] | News sentences from [SVT 2023](https://spraakbanken.gu.se/en/resources/svt-2023) | News | 14.02M | [CC-BY 4.0] |
| [runeberg-tiden] | [Tiden](https://spraakbanken.gu.se/en/resources/runeberg-tiden) from Project Runeberg | News | 13.99M | [CC-BY 4.0] |
| [svensk-tidskrift] | Historical Swedish conservative journal ([*Svensk Tidskrift*](https://spraakbanken.gu.se/en/resources/runeberg-svtidskr)) covering 27 annual volumes from 1891 to 1940 | News | 13.89M | [CC-BY 4.0] |
| [ostergotlandsveckoblad-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Östergötlands Veckoblad 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-ostergotlandsveckoblad-1890) | News | 13.88M | [CC-BY 4.0] |
| [barometern-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Barometern 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-barometern-1840) | News | 13.07M | [CC-BY 4.0] |
| [karlshamnsallehanda-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1850) | News | 12.97M | [CC-BY 4.0] |
| [bloggmix2006] | Swedish blog sentences from [Blog mix 2006](https://spraakbanken.gu.se/en/resources/bloggmix2006) | Social Media | 12.80M | [CC-BY 4.0] |
| [norrkopingstidningar-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1830) | News | 12.71M | [CC-BY 4.0] |
| [norrbottenskuriren-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottenskuriren 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottenskuriren-1870) | News | 12.64M | [CC-BY 4.0] |
| [familjeliv-expert] | Sentences from the "Fråga experten" (Ask the Expert) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 12.52M | [CC-BY 4.0] |
| [tfwbsol-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1850) | News | 12.42M | [CC-BY 4.0] |
| [press96] | Swedish newspaper sentences from [Press 1996](https://spraakbanken.gu.se/en/resources/press96) | News | 12.41M | [CC-BY 4.0] |
| [nlk-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Norrländska Korrespondenten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nlk-1870) | News | 12.31M | [CC-BY 4.0] |
| [malmoallehanda-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1840) | News | 11.91M | [CC-BY 4.0] |
| [ostgotaposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Östgötaposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotaposten-1890) | News | 11.89M | [CC-BY 4.0] |
| [blekingsposten-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Blekingsposten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-blekingsposten-1850) | News | 11.84M | [CC-BY 4.0] |
| [inrikestidningar-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1790) | News | 11.71M | [CC-BY 4.0] |
| [rd-utsk] | Committee documents from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-utsk) | Legal | 11.65M | [CC-BY 4.0] |
| [gotlandstidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Gotlands Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-gotlandstidning-1880) | News | 11.55M | [CC-BY 4.0] |
| [rd-kammakt] | Chamber records from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-kammakt) | Legal | 11.43M | [CC-BY 4.0] |
| [ostergotlandsveckoblad-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Östergötlands Veckoblad 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-ostergotlandsveckoblad-1880) | News | 11.40M | [CC-BY 4.0] |
| [faluposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Faluposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-faluposten-1880) | News | 11.31M | [CC-BY 4.0] |
| [jonkopingsposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsposten-1860) | News | 10.97M | [CC-BY 4.0] |
| [jonkopingsbladet-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsbladet 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsbladet-1840) | News | 10.90M | [CC-BY 4.0] |
| [carlscronaswekoblad-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1840) | News | 10.80M | [CC-BY 4.0] |
| [svt-2007] | News sentences from [SVT 2007](https://spraakbanken.gu.se/en/resources/svt-2007) | News | 10.76M | [CC-BY 4.0] |
| [wikisource] | Literature and historical documents from [Swedish Wikisource](https://sv.wikisource.org/) | Books | 10.74M | [CC BY-SA 4.0] |
| [umebladet-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1860) | News | 10.70M | [CC-BY 4.0] |
| [attasidor] | Easy-to-read news from [8 Sidor](https://spraakbanken.gu.se/en/resources/attasidor) | News | 10.50M | [CC-BY 4.0] |
| [runeberg-diverse] | [Runeberg periodicals](https://spraakbanken.gu.se/en/resources/runeberg-diverse) from Project Runeberg | News | 10.41M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1850) | News | 10.26M | [CC-BY 4.0] |
| [carlscronaswekoblad-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1830) | News | 9.99M | [CC-BY 4.0] |
| [gotheborgsallehanda-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1810) | News | 9.88M | [CC-BY 4.0] |
| [posttidningar-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1790) | News | 9.87M | [CC-BY 4.0] |
| [lundsweckoblad-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1850) | News | 9.62M | [CC-BY 4.0] |
| [jonkopingsbladet-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Jönköpingsbladet 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-jonkopingsbladet-1870) | News | 9.54M | [CC-BY 4.0] |
| [goteborgsweckoblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Weckoblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsweckoblad-1870) | News | 9.39M | [CC-BY 4.0] |
| [nyawexjobladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1850) | News | 9.24M | [CC-BY 4.0] |
| [harnosandsposten-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1850) | News | 9.03M | [CC-BY 4.0] |
| [gotheborgsallehanda-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1800) | News | 8.87M | [CC-BY 4.0] |
| [gu-journalen] | Texts from GU Journalen, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/gujournalen) | News | 8.85M | [CC-BY 4.0] |
| [biblioteksbladet] | Early volumes of the Swedish library journal *Biblioteksbladet* (1916–1940) | News | 8.71M | [CC-BY 4.0] |
| [gotheborgsallehanda-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1820) | News | 8.46M | [CC-BY 4.0] |
| [inrikestidningar-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1770) | News | 8.43M | [CC-BY 4.0] |
| [posttidningar-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1770) | News | 8.38M | [CC-BY 4.0] |
| [norrkopingskuriren-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpingskuriren 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingskuriren-1860) | News | 8.37M | [CC-BY 4.0] |
| [norrbottensposten-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1870) | News | 8.18M | [CC-BY 4.0] |
| [posttidningar-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1780) | News | 8.12M | [CC-BY 4.0] |
| [nerikesallehanda-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Nerikes Allehanda 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-nerikesallehanda-1840) | News | 8.11M | [CC-BY 4.0] |
| [svt-2006] | News sentences from [SVT 2006](https://spraakbanken.gu.se/en/resources/svt-2006) | News | 8.08M | [CC-BY 4.0] |
| [kristianstadsbladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Kristianstadsbladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-kristianstadsbladet-1850) | News | 8.00M | [CC-BY 4.0] |
| [posttidningar-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1760) | News | 7.80M | [CC-BY 4.0] |
| [inrikestidningar-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1780) | News | 7.79M | [CC-BY 4.0] |
| [standsriksdagen-riksdagsakter] | Texts from Tvåkammarriksdagen: Riksdagsakter, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 7.74M | [CC-BY 4.0] |
| [dalpilen-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Dalpilen 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-dalpilen-1850) | News | 7.70M | [CC-BY 4.0] |
| [carlscronaswekoblad-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1820) | News | 7.63M | [CC-BY 4.0] |
| [bloggmix2005] | Swedish blog sentences from [Blog mix 2005](https://spraakbanken.gu.se/en/resources/bloggmix2005) | Social Media | 7.52M | [CC-BY 4.0] |
| [rd-fpm] | EU fact memoranda from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-fpm) | Legal | 7.46M | [CC-BY 4.0] |
| [strindbergromaner] | Texts from "August Strindbergs romaner" (August Strindberg's novels), distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/strindbergromaner) | Books | 7.31M | [CC-BY 4.0] |
| [umebladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1850) | News | 7.22M | [CC-BY 4.0] |
| [folketsrost-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Folkets Röst 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-folketsrost-1860) | News | 7.18M | [CC-BY 4.0] |
| [posttidningar-1750] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1750's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1750) | News | 7.14M | [CC-BY 4.0] |
| [gotheborgsallehanda-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1830) | News | 6.99M | [CC-BY 4.0] |
| [norrbottenskuriren-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottenskuriren 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottenskuriren-1860) | News | 6.90M | [CC-BY 4.0] |
| [norrkopingstidningar-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1820) | News | 6.87M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1840) | News | 6.84M | [CC-BY 4.0] |
| [upsala-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Upsala 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-upsala-1840) | News | 6.71M | [CC-BY 4.0] |
| [wernamotidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Wernamo Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-wernamotidning-1880) | News | 6.59M | [CC-BY 4.0] |
| [inrikestidningar-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1760) | News | 6.56M | [CC-BY 4.0] |
| [svt-2005] | News sentences from [SVT 2005](https://spraakbanken.gu.se/en/resources/svt-2005) | News | 6.37M | [CC-BY 4.0] |
| [gotheborgsallehanda-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1790) | News | 6.33M | [CC-BY 4.0] |
| [norrkopingstidningar-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1810) | News | 6.21M | [CC-BY 4.0] |
| [posttidningar-1740] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1740's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1740) | News | 6.21M | [CC-BY 4.0] |
| [wermlandstidningen-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Wermlandstidningen 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-wermlandstidningen-1840) | News | 6.00M | [CC-BY 4.0] |
| [norrbottensposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1860) | News | 6.00M | [CC-BY 4.0] |
| [gotheborgsallehanda-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1780) | News | 5.93M | [CC-BY 4.0] |
| [goteborgsweckoblad-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgs Weckoblad 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsweckoblad-1890) | News | 5.75M | [CC-BY 4.0] |
| [carlscronaswekoblad-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1810) | News | 5.69M | [CC-BY 4.0] |
| [riksdagen-reglementen] | Swedish parliamentary regulations from Språkbanken Text's [Bicameral riksdag: Regulations](https://spraakbanken.gu.se/en/resources/tkr-reglementen-sfs) | Legal | 5.69M | [CC-BY 4.0] |
| [lundsweckoblad-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1840) | News | 5.68M | [CC-BY 4.0] |
| [norrkopingstidningar-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1800) | News | 5.65M | [CC-BY 4.0] |
| [bollnastidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Bollnäs Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-bollnastidning-1870) | News | 5.61M | [CC-BY 4.0] |
| [norrbottensposten-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1850) | News | 5.38M | [CC-BY 4.0] |
| [wexjobladet-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Wexjöbladet 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-wexjobladet-1850) | News | 5.37M | [CC-BY 4.0] |
| [lundsweckoblad-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1830) | News | 5.27M | [CC-BY 4.0] |
| [harnosandsposten-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Härnösandsposten 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-harnosandsposten-1840) | News | 5.27M | [CC-BY 4.0] |
| [borastidning-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1840) | News | 5.01M | [CC-BY 4.0] |
| [stockholmsposten-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1830) | News | 4.79M | [CC-BY 4.0] |
| [malmoallehanda-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1830) | News | 4.79M | [CC-BY 4.0] |
| [carlscronaswekoblad-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1800) | News | 4.64M | [CC-BY 4.0] |
| [karlskronaweckoblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Karlskrona Weckoblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-karlskronaweckoblad-1870) | News | 4.62M | [CC-BY 4.0] |
| [rd-utr] | Inquiry documents from [Riksdagens öppna data](https://spraakbanken.gu.se/en/resources/rd-utr) | Report | 4.56M | [CC-BY 4.0] |
| [wexjobladet-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Wexjöbladet 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-wexjobladet-1840) | News | 4.51M | [CC-BY 4.0] |
| [akademiliv] | Sentences from Akademiliv, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/akademiliv) | News | 4.42M | [CC-BY 4.0] |
| [lundsweckoblad-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1820) | News | 4.40M | [CC-BY 4.0] |
| [gotlandstidning-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Gotlands Tidning 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-gotlandstidning-1860) | News | 4.31M | [CC-BY 4.0] |
| [riksarkivet-goteborg-lines] | Police reports from Göteborg from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/goteborgs_poliskammare_fore_1900_lines) | Legal | 4.28M | [CC0] |
| [lindesbergsallehanda-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Lindesbergs Allehanda 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-lindesbergsallehanda-1870) | News | 4.01M | [CC-BY 4.0] |
| [wernamotidning-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Wernamo Tidning 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-wernamotidning-1870) | News | 3.97M | [CC-BY 4.0] |
| [goteborgsposten-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Göteborgsposten 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-goteborgsposten-1850) | News | 3.93M | [CC-BY 4.0] |
| [norrlandsposten-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Norrlandsposten 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-norrlandsposten-1880) | News | 3.87M | [CC-BY 4.0] |
| [vestmanlandslanstidning-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Vestmanlands Läns Tidning 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-vestmanlandslanstidning-1830) | News | 3.84M | [CC-BY 4.0] |
| [nyttallvarochskamt-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt allvar och skämt 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttallvarochskamt-1840) | News | 3.79M | [CC-BY 4.0] |
| [wexjobladet-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Wexjöbladet 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-wexjobladet-1830) | News | 3.77M | [CC-BY 4.0] |
| [runeberg-urdagkron] | [Ur Dagens Krönika](https://spraakbanken.gu.se/en/resources/runeberg-urdagkron) from Project Runeberg | News | 3.73M | [CC-BY 4.0] |
| [norrkopingstidningar-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1790) | News | 3.72M | [CC-BY 4.0] |
| [runeberg-rost] | [Rösträtt för kvinnor](https://spraakbanken.gu.se/en/resources/runeberg-rost) from Project Runeberg | News | 3.61M | [CC-BY 4.0] |
| [familjeliv-pappagrupp] | Sentences from the "Pappagrupp" (Daddy Group) subforum of [Familjeliv](https://www.familjeliv.se) | Social Media | 3.58M | [CC-BY 4.0] |
| [norrkopingskuriren-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpingskuriren 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingskuriren-1850) | News | 3.54M | [CC-BY 4.0] |
| [posttidningar-1730] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1730's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1730) | News | 3.39M | [CC-BY 4.0] |
| [gotheborgskanyheter-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1810) | News | 3.11M | [CC-BY 4.0] |
| [gotheborgsallehanda-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1770) | News | 3.07M | [CC-BY 4.0] |
| [gotheborgskanyheter-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1800) | News | 3.00M | [CC-BY 4.0] |
| [gotheborgskanyheter-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1830) | News | 2.97M | [CC-BY 4.0] |
| [gotheborgskanyheter-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1780) | News | 2.95M | [CC-BY 4.0] |
| [gotheborgskanyheter-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1790) | News | 2.90M | [CC-BY 4.0] |
| [gotheborgskanyheter-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1820) | News | 2.87M | [CC-BY 4.0] |
| [wexjobladet-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Wexjöbladet 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-wexjobladet-1810) | News | 2.87M | [CC-BY 4.0] |
| [norden-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Norden 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-norden-1850) | News | 2.77M | [CC-BY 4.0] |
| [falkopingstidning-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Falköpings Tidning 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-falkopingstidning-1850) | News | 2.75M | [CC-BY 4.0] |
| [bloggmix2017] | Swedish blog sentences from [Blog mix 2017](https://spraakbanken.gu.se/en/resources/bloggmix2017) | Social Media | 2.74M | [CC-BY 4.0] |
| [fsv-yngrereligiosprosa] | Texts from the "Yngre religiös prosa" (Younger Religious Prose) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 2.63M | [CC-BY 4.0] |
| [press76] | Swedish newspaper sentences from [Press 1976](https://spraakbanken.gu.se/en/resources/press76) | News | 2.62M | [CC-BY 4.0] |
| [nyttochgammalt-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt och Gammalt 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttochgammalt-1790) | News | 2.61M | [CC-BY 4.0] |
| [nyttochgammalt-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt och Gammalt 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttochgammalt-1800) | News | 2.60M | [CC-BY 4.0] |
| [wexjobladet-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Wexjöbladet 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-wexjobladet-1820) | News | 2.60M | [CC-BY 4.0] |
| [gotheborgskanyheter-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1770) | News | 2.48M | [CC-BY 4.0] |
| [gotheborgskanyheter-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1840) | News | 2.47M | [CC-BY 4.0] |
| [nyawexjobladet-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Wexjöbladet 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-nyawexjobladet-1840) | News | 2.47M | [CC-BY 4.0] |
| [lundsweckoblad-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1810) | News | 2.46M | [CC-BY 4.0] |
| [posttidningar-1700] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1700's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1700) | News | 2.40M | [CC-BY 4.0] |
| [strindbergbrev] | Texts from "August Strindbergs brev" (August Strindberg's letters), distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/strindbergbrev) | Books | 2.39M | [CC-BY 4.0] |
| [norrkopingsweckotidningar-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Weckotidningar 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingsweckotidningar-1760) | News | 2.21M | [CC-BY 4.0] |
| [press65] | Swedish newspaper sentences from [Press 1965](https://spraakbanken.gu.se/en/resources/press65) | News | 2.18M | [CC-BY 4.0] |
| [fahluweckoblad-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Fahlu Weckoblad 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-fahluweckoblad-1810) | News | 2.12M | [CC-BY 4.0] |
| [norrkopingsweckotidningar-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Weckotidningar 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingsweckotidningar-1770) | News | 2.04M | [CC-BY 4.0] |
| [inrikestidningar-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Inrikes Tidningar 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-inrikestidningar-1820) | News | 2.01M | [CC-BY 4.0] |
| [fahluweckoblad-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Fahlu Weckoblad 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-fahluweckoblad-1790) | News | 1.97M | [CC-BY 4.0] |
| [gotheborgsallehanda-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Allehanda 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsallehanda-1840) | News | 1.95M | [CC-BY 4.0] |
| [posttidningar-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1820) | News | 1.94M | [CC-BY 4.0] |
| [posttidningar-1690] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1690's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1690) | News | 1.92M | [CC-BY 4.0] |
| [nyttallvarochskamt-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt allvar och skämt 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttallvarochskamt-1850) | News | 1.87M | [CC-BY 4.0] |
| [fahluweckoblad-1800] | Historical Swedish newspaper issues from Språkbanken Text's [Fahlu Weckoblad 1800's](https://spraakbanken.gu.se/en/resources/kubhist2-fahluweckoblad-1800) | News | 1.84M | [CC-BY 4.0] |
| [ostgotacorrespondenten-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Östgöta Correspondenten 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-ostgotacorrespondenten-1830) | News | 1.72M | [CC-BY 4.0] |
| [carlscronaswekoblad-1790] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1790's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1790) | News | 1.68M | [CC-BY 4.0] |
| [carlscronaswekoblad-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1770) | News | 1.60M | [CC-BY 4.0] |
| [alfwarochskamt-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Alfwar och Skämt 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-alfwarochskamt-1840) | News | 1.54M | [CC-BY 4.0] |
| [bibel1917] | Texts from Bibeln 1917, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/bibel1917) | Books | 1.48M | [CC-BY 4.0] |
| [nyakarlskronaweckoblad-1870] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Karlskrona Weckoblad 1870's](https://spraakbanken.gu.se/en/resources/kubhist2-nyakarlskronaweckoblad-1870) | News | 1.47M | [CC-BY 4.0] |
| [stockholmsposten-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Stockholmsposten 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-stockholmsposten-1770) | News | 1.46M | [CC-BY 4.0] |
| [dagligtallehanda-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Dagligt Allehanda 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-dagligtallehanda-1760) | News | 1.46M | [CC-BY 4.0] |
| [nyttochgammalt-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt och Gammalt 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttochgammalt-1780) | News | 1.45M | [CC-BY 4.0] |
| [norrbottensposten-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Norrbottensposten 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-norrbottensposten-1840) | News | 1.45M | [CC-BY 4.0] |
| [forskning-framsteg] | Sentences from Forskning & Framsteg, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/fof) | News | 1.44M | [CC-BY 4.0] |
| [posttidningar-1720] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1720's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1720) | News | 1.41M | [CC-BY 4.0] |
| [karlshamnsallehanda-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Karlshamns Allehanda 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-karlshamnsallehanda-1840) | News | 1.40M | [CC-BY 4.0] |
| [umebladet-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Umebladet 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-umebladet-1840) | News | 1.38M | [CC-BY 4.0] |
| [norrkopingstidningar-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Tidningar 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingstidningar-1780) | News | 1.37M | [CC-BY 4.0] |
| [nyadagligtallehanda-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Nya Dagligt Allehanda 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-nyadagligtallehanda-1850) | News | 1.35M | [CC-BY 4.0] |
| [faluposten-1890] | Historical Swedish newspaper issues from Språkbanken Text's [Faluposten 1890's](https://spraakbanken.gu.se/en/resources/kubhist2-faluposten-1890) | News | 1.27M | [CC-BY 4.0] |
| [norden-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Norden 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-norden-1860) | News | 1.26M | [CC-BY 4.0] |
| [drama] | Sentences from Swedish plays in [Dramawebben](https://spraakbanken.gu.se/resurser/drama) | Books | 1.15M | [CC-BY 4.0] |
| [lundsweckoblad-1770] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1770's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1770) | News | 1.08M | [CC-BY 4.0] |
| [ostgotaposten-1910] | Historical newspaper issues from [Kubhist: Östgötaposten 1910's](https://spraakbanken.gu.se/en/resources/kubhist-ostgotaposten-1910) | News | 1.07M | [CC-BY 4.0] |
| [dramadialog] | Texts from Svensk Dramadialog, distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/dramadialog) | Books | 1.06M | [CC-BY 4.0] |
| [lindesbergsallehanda-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Lindesbergs Allehanda 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-lindesbergsallehanda-1880) | News | 1.03M | [CC-BY 4.0] |
| [wermlandstidningen-1850] | Historical Swedish newspaper issues from Språkbanken Text's [Wermlandstidningen 1850's](https://spraakbanken.gu.se/en/resources/kubhist2-wermlandstidningen-1850) | News | 1.03M | [CC-BY 4.0] |
| [posttidningar-1710] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1710's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1710) | News | 1.02M | [CC-BY 4.0] |
| [fsv-aldrelagar] | Texts from the "Äldre lagar" (Older Laws) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Legal | 1.01M | [CC-BY 4.0] |
| [bloggmix2004] | Swedish blog sentences from [Blog mix 2004](https://spraakbanken.gu.se/en/resources/bloggmix2004) | Social Media | 1.01M | [CC-BY 4.0] |
| [bloggmix1999] | Swedish blog sentences from [Blog mix 1999](https://spraakbanken.gu.se/en/resources/bloggmix1999) | Social Media | 1.00M | [CC-BY 4.0] |
| [riksarkivet-bergskollegium-lines] | Reports and correspondence from Bergskollegium from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/bergskollegium_relationer_och_skrivelser_lines) | Report | 979.78K | [CC0] |
| [gotheborgskanyheter-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgska Nyheter 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgskanyheter-1760) | News | 962.75K | [CC-BY 4.0] |
| [carlscronaswekoblad-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1760) | News | 954.50K | [CC-BY 4.0] |
| [gotheborgsweckolista-1750] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Weckolista 1750's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsweckolista-1750) | News | 953.18K | [CC-BY 4.0] |
| [malmoallehanda-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Malmö Allehanda 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-malmoallehanda-1820) | News | 933.65K | [CC-BY 4.0] |
| [lag1800] | Historical Swedish legal texts from Språkbanken Text's [Laws from the 1800's](https://spraakbanken.gu.se/en/resources/lag1800) | Legal | 921.60K | [CC-BY 4.0] |
| [fsv-aldrereligiosprosa] | Texts from the "Äldre religiös prosa" (Older Religious Prose) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 916.75K | [CC-BY 4.0] |
| [tfwbsol-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Tidning för Wenersborgs stad och län 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-tfwbsol-1840) | News | 905.88K | [CC-BY 4.0] |
| [faluposten-1860] | Historical Swedish newspaper issues from Språkbanken Text's [Faluposten 1860's](https://spraakbanken.gu.se/en/resources/kubhist2-faluposten-1860) | News | 897.16K | [CC-BY 4.0] |
| [svt-2004] | News sentences from [SVT 2004](https://spraakbanken.gu.se/en/resources/svt-2004) | News | 853.11K | [CC-BY 4.0] |
| [posttidningar-1680] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1680's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1680) | News | 837.74K | [CC-BY 4.0] |
| [nyttochgammalt-1810] | Historical Swedish newspaper issues from Språkbanken Text's [Nytt och Gammalt 1810's](https://spraakbanken.gu.se/en/resources/kubhist2-nyttochgammalt-1810) | News | 800.62K | [CC-BY 4.0] |
| [runeberg-folkbbl] | [Folkbiblioteksbladet](https://spraakbanken.gu.se/en/resources/runeberg-folkbbl) from Project Runeberg | News | 789.19K | [CC-BY 4.0] |
| [bellman] | Songs, poems and plays from [Bellman’s collected works](https://spraakbanken.gu.se/resurser/bellman) | Books | 774.52K | [CC-BY 4.0] |
| [standsriksdagen-riksdagsbeslut] | Texts from Ståndsriksdagen: Riksdagsbeslut, part of Språkbanken's digitised historical Swedish parliamentary records | Legal | 707.46K | [CC-BY 4.0] |
| [lundsweckoblad-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Lunds Weckoblad 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-lundsweckoblad-1780) | News | 666.75K | [CC-BY 4.0] |
| [fahluweckoblad-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Fahlu Weckoblad 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-fahluweckoblad-1780) | News | 657.79K | [CC-BY 4.0] |
| [norrkopingsweckotidningar-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Weckotidningar 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingsweckotidningar-1780) | News | 638.57K | [CC-BY 4.0] |
| [fsv-nysvenskovrigt] | Texts from the "Nysvenska, övrigt" (Early Modern Swedish, Miscellaneous) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 611.10K | [CC-BY 4.0] |
| [riksarkivet-trolldom-lines] | Records of Swedish witchcraft trials from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/trolldomskommissionen_lines) | Legal | 605.52K | [CC0] |
| [fsv-nysvenskkronikor] | Texts from the "Nysvenska krönikor" (Early Modern Swedish Chronicles) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 598.00K | [CC-BY 4.0] |
| [bollnastidning-1880] | Historical Swedish newspaper issues from Språkbanken Text's [Bollnäs Tidning 1880's](https://spraakbanken.gu.se/en/resources/kubhist2-bollnastidning-1880) | News | 564.03K | [CC-BY 4.0] |
| [bloggmix2001] | Swedish blog sentences from [Blog mix 2001](https://spraakbanken.gu.se/en/resources/bloggmix2001) | Social Media | 543.94K | [CC-BY 4.0] |
| [fsv-nysvenskdalin] | Texts from the "Dalins Then Swänska Argus 1732-1734" (Dalin's Then Swänska Argus) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 449.85K | [CC-BY 4.0] |
| [bloggmix2003] | Swedish blog sentences from [Blog mix 2003](https://spraakbanken.gu.se/en/resources/bloggmix2003) | Social Media | 445.73K | [CC-BY 4.0] |
| [riksarkivet-svea-hovratt-lines] | Court records from Svea hovrätt from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/svea_hovratt_lines) | Legal | 445.24K | [CC0] |
| [fsv-profanprosa] | Texts from the "Profan prosa" (Secular Prose) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 431.01K | [CC-BY 4.0] |
| [carlscronaswekoblad-1780] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1780's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1780) | News | 412.60K | [CC-BY 4.0] |
| [fahluweckoblad-1820] | Historical Swedish newspaper issues from Språkbanken Text's [Fahlu Weckoblad 1820's](https://spraakbanken.gu.se/en/resources/kubhist2-fahluweckoblad-1820) | News | 412.45K | [CC-BY 4.0] |
| [borastidning-1830] | Historical Swedish newspaper issues from Språkbanken Text's [Borås Tidning 1830's](https://spraakbanken.gu.se/en/resources/kubhist2-borastidning-1830) | News | 407.43K | [CC-BY 4.0] |
| [bloggmix2002] | Swedish blog sentences from [Blog mix 2002](https://spraakbanken.gu.se/en/resources/bloggmix2002) | Social Media | 401.43K | [CC-BY 4.0] |
| [fsv-verser] | Texts from the "Verser" (Verse) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 339.94K | [CC-BY 4.0] |
| [bloggmix2000] | Swedish blog sentences from [Blog mix 2000](https://spraakbanken.gu.se/en/resources/bloggmix2000) | Social Media | 316.73K | [CC-BY 4.0] |
| [fsv-yngretankebocker] | Texts from the "Yngre tänkeböcker" (Younger Thought Books) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 296.24K | [CC-BY 4.0] |
| [carlscronastidningar-1760] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Tidningar 1760's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronastidningar-1760) | News | 291.50K | [CC-BY 4.0] |
| [folketsrost-1840] | Historical Swedish newspaper issues from Språkbanken Text's [Folkets Röst 1840's](https://spraakbanken.gu.se/en/resources/kubhist2-folketsrost-1840) | News | 259.93K | [CC-BY 4.0] |
| [norrkopingsweckotidningar-1750] | Historical Swedish newspaper issues from Språkbanken Text's [Norrköpings Weckotidningar 1750's](https://spraakbanken.gu.se/en/resources/kubhist2-norrkopingsweckotidningar-1750) | News | 245.25K | [CC-BY 4.0] |
| [psalmboken] | Sentences from Psalmboken (1937), distributed by [Språkbanken Text](https://spraakbanken.gu.se/resurser/psalmboken) | Books | 241.53K | [CC-BY 4.0] |
| [riksarkivet-krigshovratten-lines] | Military court records from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/krigshovrattens_dombocker_lines) | Legal | 230.76K | [CC0] |
| [fsv-yngrelagar] | Texts from the "Yngre lagar" (Younger Laws) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Legal | 202.68K | [CC-BY 4.0] |
| [carlscronaswekoblad-1750] | Historical Swedish newspaper issues from Språkbanken Text's [Carlscronas Wekoblad 1750's](https://spraakbanken.gu.se/en/resources/kubhist2-carlscronaswekoblad-1750) | News | 192.14K | [CC-BY 4.0] |
| [riksdagen-forfattningssamling] | Swedish parliamentary constitutional texts from Språkbanken Text's [Bicameral riksdag: The constitution of the Riksdag](https://spraakbanken.gu.se/en/resources/tkr-riksdagens-forfattningssamling-rfs) | Legal | 185.96K | [CC-BY 4.0] |
| [riksarkivet-frihetstiden-lines] | Parliamentary committee records from 1765–1766 from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/frihetstidens_utskottshandlingar_lines) | Legal | 171.71K | [CC0] |
| [posttidningar-1640] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1640's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1640) | News | 163.85K | [CC-BY 4.0] |
| [riksarkivet-pahlman-lines] | Travel journals by Carl Fredrik Påhlman from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/carl_fredrik_pahlmans_resejournaler_lines) | Books | 134.63K | [CC0] |
| [riksarkivet-bergmastaren-lines] | Mining court records from Bergmästaren i Nora from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/bergmastaren_i_nora_htr_lines) | Legal | 96.63K | [CC0] |
| [fsv-nysvenskbibel] | Texts from the "Nysvenska bibelböcker" (Early Modern Swedish Bible Books) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Books | 79.17K | [CC-BY 4.0] |
| [svt-nodate] | Undated news sentences from [SVT](https://spraakbanken.gu.se/en/resources/svt-nodate) | News | 68.22K | [CC-BY 4.0] |
| [riksarkivet-alvsborgs-losen-lines] | Tax records for Älvsborgs lösen from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/alvsborgs_losen_lines) | Legal | 64.29K | [CC0] |
| [mosel-youtube-commons] | Swedish speech transcripts from [MOSEL YouTube Commons](https://huggingface.co/datasets/FBK-MT/mosel) | Spoken | 59.85K | [CC-BY 4.0] |
| [bloggmix1998] | Swedish blog sentences from [Blog mix 1998](https://spraakbanken.gu.se/en/resources/bloggmix1998) | Social Media | 53.76K | [CC-BY 4.0] |
| [fsv-nysvensklagar] | Texts from the "Nysvenska lagar" (Early Modern Swedish Laws) collection of [Fornsvenska textbanken](http://project2.sol.lu.se/fornsvenska/), a historical Swedish text archive | Legal | 39.60K | [CC-BY 4.0] |
| [riksarkivet-gota-hovratt-lines] | Court records from Göta hovrätt from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/gota_hovratt_lines) | Legal | 38.09K | [CC0] |
| [posttidningar-1660] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1660's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1660) | News | 33.56K | [CC-BY 4.0] |
| [posttidningar-1650] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1650's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1650) | News | 21.40K | [CC-BY 4.0] |
| [riksarkivet-jonkoping-lines] | Court records from Jönköping from [Riksarkivet](https://huggingface.co/datasets/Riksarkivet/jonkopings_radhusratt_och_magistrat_lines) | Legal | 18.43K | [CC0] |
| [posttidningar-1670] | Historical Swedish newspaper issues from Språkbanken Text's [Posttidningar 1670's](https://spraakbanken.gu.se/en/resources/kubhist2-posttidningar-1670) | News | 11.82K | [CC-BY 4.0] |
| [gotheborgsweckolista-1740] | Historical Swedish newspaper issues from Språkbanken Text's [Götheborgs Weckolista 1740's](https://spraakbanken.gu.se/en/resources/kubhist2-gotheborgsweckolista-1740) | News | 4.65K | [CC-BY 4.0] |
| **Total** |  |  | 43.51B |  |

[dalpilen-1860]: data/dalpilen-1860/dalpilen-1860.md
[lag1800]: data/lag1800/lag1800.md
[svensk-tidskrift]: data/svensk-tidskrift/svensk-tidskrift.md
[statens-offentliga-utredningar]: data/statens-offentliga-utredningar/statens-offentliga-utredningar.md
[biblioteksbladet]: data/biblioteksbladet/biblioteksbladet.md
[riksdagen-forfattningssamling]: data/riksdagen-forfattningssamling/riksdagen-forfattningssamling.md
[riksdagen-reglementen]: data/riksdagen-reglementen/riksdagen-reglementen.md
[riksdagen-register]: data/riksdagen-register/riksdagen-register.md
[riksdagen-skrivelser]: data/riksdagen-skrivelser/riksdagen-skrivelser.md
[riksdagen-utredningar]: data/riksdagen-utredningar/riksdagen-utredningar.md
[riksdagen-berattelser]: data/riksdagen-berattelser/riksdagen-berattelser.md
[riksdagen-motioner]: data/riksdagen-motioner/riksdagen-motioner.md
[riksdagen-betankanden]: data/riksdagen-betankanden/riksdagen-betankanden.md
[riksdagen-propositioner]: data/riksdagen-propositioner/riksdagen-propositioner.md
[riksdagen-protokoll]: data/riksdagen-protokoll/riksdagen-protokoll.md
[cellar]: data/cellar/cellar.md
[flashback-dator]: data/flashback-dator/flashback-dator.md
[flashback-droger]: data/flashback-droger/flashback-droger.md
[flashback-ekonomi]: data/flashback-ekonomi/flashback-ekonomi.md
[flashback-fordon]: data/flashback-fordon/flashback-fordon.md
[flashback-hem]: data/flashback-hem/flashback-hem.md
[flashback-kultur]: data/flashback-kultur/flashback-kultur.md
[flashback-livsstil]: data/flashback-livsstil/flashback-livsstil.md
[flashback-mat]: data/flashback-mat/flashback-mat.md
[flashback-om-flashback]: data/flashback-om-flashback/flashback-om-flashback.md
[flashback-ovrigt]: data/flashback-ovrigt/flashback-ovrigt.md
[flashback-politik]: data/flashback-politik/flashback-politik.md
[flashback-resor]: data/flashback-resor/flashback-resor.md
[flashback-samhalle]: data/flashback-samhalle/flashback-samhalle.md
[flashback-sex]: data/flashback-sex/flashback-sex.md
[flashback-sport]: data/flashback-sport/flashback-sport.md
[flashback-vetenskap]: data/flashback-vetenskap/flashback-vetenskap.md
[familjeliv-adoption]: data/familjeliv-adoption/familjeliv-adoption.md
[familjeliv-allmanna-ekonomi]: data/familjeliv-allmanna-ekonomi/familjeliv-allmanna-ekonomi.md
[familjeliv-allmanna-familjeliv]: data/familjeliv-allmanna-familjeliv/familjeliv-allmanna-familjeliv.md
[familjeliv-allmanna-fritid]: data/familjeliv-allmanna-fritid/familjeliv-allmanna-fritid.md
[familjeliv-allmanna-husdjur]: data/familjeliv-allmanna-husdjur/familjeliv-allmanna-husdjur.md
[familjeliv-allmanna-hushem]: data/familjeliv-allmanna-hushem/familjeliv-allmanna-hushem.md
[familjeliv-allmanna-kropp]: data/familjeliv-allmanna-kropp/familjeliv-allmanna-kropp.md
[familjeliv-allmanna-noje]: data/familjeliv-allmanna-noje/familjeliv-allmanna-noje.md
[familjeliv-allmanna-samhalle]: data/familjeliv-allmanna-samhalle/familjeliv-allmanna-samhalle.md
[familjeliv-allmanna-sandladan]: data/familjeliv-allmanna-sandladan/familjeliv-allmanna-sandladan.md
[familjeliv-anglarum]: data/familjeliv-anglarum/familjeliv-anglarum.md
[familjeliv-expert]: data/familjeliv-expert/familjeliv-expert.md
[familjeliv-foralder]: data/familjeliv-foralder/familjeliv-foralder.md
[familjeliv-gravid]: data/familjeliv-gravid/familjeliv-gravid.md
[familjeliv-kansliga]: data/familjeliv-kansliga/familjeliv-kansliga.md
[familjeliv-medlem-allmanna]: data/familjeliv-medlem-allmanna/familjeliv-medlem-allmanna.md
[familjeliv-medlem-foraldrar]: data/familjeliv-medlem-foraldrar/familjeliv-medlem-foraldrar.md
[familjeliv-medlem-planerarbarn]: data/familjeliv-medlem-planerarbarn/familjeliv-medlem-planerarbarn.md
[familjeliv-medlem-vantarbarn]: data/familjeliv-medlem-vantarbarn/familjeliv-medlem-vantarbarn.md
[familjeliv-pappagrupp]: data/familjeliv-pappagrupp/familjeliv-pappagrupp.md
[familjeliv-planerarbarn]: data/familjeliv-planerarbarn/familjeliv-planerarbarn.md
[familjeliv-sexsamlevnad]: data/familjeliv-sexsamlevnad/familjeliv-sexsamlevnad.md
[familjeliv-svartattfabarn]: data/familjeliv-svartattfabarn/familjeliv-svartattfabarn.md
[lb-open]: data/lb-open/lb-open.md
[poeter]: data/poeter/poeter.md
[wikipedia-sv]: data/wikipedia-sv/wikipedia-sv.md
[europarl-sv]: data/europarl-sv/europarl-sv.md
[laakartidningen]: data/laakartidningen/laakartidningen.md
[fsv-aldrelagar]: data/fsv-aldrelagar/fsv-aldrelagar.md
[fsv-aldrereligiosprosa]: data/fsv-aldrereligiosprosa/fsv-aldrereligiosprosa.md
[fsv-nysvenskbibel]: data/fsv-nysvenskbibel/fsv-nysvenskbibel.md
[fsv-nysvenskdalin]: data/fsv-nysvenskdalin/fsv-nysvenskdalin.md
[fsv-nysvenskkronikor]: data/fsv-nysvenskkronikor/fsv-nysvenskkronikor.md
[fsv-nysvensklagar]: data/fsv-nysvensklagar/fsv-nysvensklagar.md
[fsv-nysvenskovrigt]: data/fsv-nysvenskovrigt/fsv-nysvenskovrigt.md
[fsv-profanprosa]: data/fsv-profanprosa/fsv-profanprosa.md
[fsv-verser]: data/fsv-verser/fsv-verser.md
[fsv-yngrelagar]: data/fsv-yngrelagar/fsv-yngrelagar.md
[fsv-yngrereligiosprosa]: data/fsv-yngrereligiosprosa/fsv-yngrereligiosprosa.md
[fsv-yngretankebocker]: data/fsv-yngretankebocker/fsv-yngretankebocker.md
[standsriksdagen-adelsstandet]: data/standsriksdagen-adelsstandet/standsriksdagen-adelsstandet.md
[standsriksdagen-bihang]: data/standsriksdagen-bihang/standsriksdagen-bihang.md
[standsriksdagen-bondestandet]: data/standsriksdagen-bondestandet/standsriksdagen-bondestandet.md
[standsriksdagen-borgarstandet]: data/standsriksdagen-borgarstandet/standsriksdagen-borgarstandet.md
[standsriksdagen-prastestandet]: data/standsriksdagen-prastestandet/standsriksdagen-prastestandet.md
[standsriksdagen-riksdagsakter]: data/standsriksdagen-riksdagsakter/standsriksdagen-riksdagsakter.md
[standsriksdagen-riksdagsbeslut]: data/standsriksdagen-riksdagsbeslut/standsriksdagen-riksdagsbeslut.md
[strindbergromaner]: data/strindbergromaner/strindbergromaner.md
[strindbergbrev]: data/strindbergbrev/strindbergbrev.md
[dramadialog]: data/dramadialog/dramadialog.md
[bibel1917]: data/bibel1917/bibel1917.md
[psalmboken]: data/psalmboken/psalmboken.md
[akademiliv]: data/akademiliv/akademiliv.md
[dagens-arena]: data/dagens-arena/dagens-arena.md
[gu-journalen]: data/gu-journalen/gu-journalen.md
[forskning-framsteg]: data/forskning-framsteg/forskning-framsteg.md
[sv-covid-19]: data/sv-covid-19/sv-covid-19.md
[aftonbladet-1830]: data/aftonbladet-1830/aftonbladet-1830.md
[aftonbladet-1840]: data/aftonbladet-1840/aftonbladet-1840.md
[aftonbladet-1850]: data/aftonbladet-1850/aftonbladet-1850.md
[aftonbladet-1860]: data/aftonbladet-1860/aftonbladet-1860.md
[aftonbladet-1870]: data/aftonbladet-1870/aftonbladet-1870.md
[aftonbladet-1880]: data/aftonbladet-1880/aftonbladet-1880.md
[aftonbladet-1890]: data/aftonbladet-1890/aftonbladet-1890.md
[aftonbladet-1900]: data/aftonbladet-1900/aftonbladet-1900.md
[alfwarochskamt-1840]: data/alfwarochskamt-1840/alfwarochskamt-1840.md
[barometern-1840]: data/barometern-1840/barometern-1840.md
[barometern-1850]: data/barometern-1850/barometern-1850.md
[barometern-1860]: data/barometern-1860/barometern-1860.md
[barometern-1870]: data/barometern-1870/barometern-1870.md
[barometern-1880]: data/barometern-1880/barometern-1880.md
[barometern-1890]: data/barometern-1890/barometern-1890.md
[blekingsposten-1850]: data/blekingsposten-1850/blekingsposten-1850.md
[blekingsposten-1860]: data/blekingsposten-1860/blekingsposten-1860.md
[blekingsposten-1870]: data/blekingsposten-1870/blekingsposten-1870.md
[blekingsposten-1880]: data/blekingsposten-1880/blekingsposten-1880.md
[bollnastidning-1870]: data/bollnastidning-1870/bollnastidning-1870.md
[bollnastidning-1880]: data/bollnastidning-1880/bollnastidning-1880.md
[borastidning-1830]: data/borastidning-1830/borastidning-1830.md
[borastidning-1840]: data/borastidning-1840/borastidning-1840.md
[borastidning-1850]: data/borastidning-1850/borastidning-1850.md
[borastidning-1860]: data/borastidning-1860/borastidning-1860.md
[borastidning-1870]: data/borastidning-1870/borastidning-1870.md
[borastidning-1880]: data/borastidning-1880/borastidning-1880.md
[borastidning-1890]: data/borastidning-1890/borastidning-1890.md
[carlscronastidningar-1760]: data/carlscronastidningar-1760/carlscronastidningar-1760.md
[carlscronaswekoblad-1750]: data/carlscronaswekoblad-1750/carlscronaswekoblad-1750.md
[carlscronaswekoblad-1760]: data/carlscronaswekoblad-1760/carlscronaswekoblad-1760.md
[carlscronaswekoblad-1770]: data/carlscronaswekoblad-1770/carlscronaswekoblad-1770.md
[carlscronaswekoblad-1780]: data/carlscronaswekoblad-1780/carlscronaswekoblad-1780.md
[carlscronaswekoblad-1790]: data/carlscronaswekoblad-1790/carlscronaswekoblad-1790.md
[carlscronaswekoblad-1800]: data/carlscronaswekoblad-1800/carlscronaswekoblad-1800.md
[carlscronaswekoblad-1810]: data/carlscronaswekoblad-1810/carlscronaswekoblad-1810.md
[carlscronaswekoblad-1820]: data/carlscronaswekoblad-1820/carlscronaswekoblad-1820.md
[carlscronaswekoblad-1830]: data/carlscronaswekoblad-1830/carlscronaswekoblad-1830.md
[carlscronaswekoblad-1840]: data/carlscronaswekoblad-1840/carlscronaswekoblad-1840.md
[carlscronaswekoblad-1850]: data/carlscronaswekoblad-1850/carlscronaswekoblad-1850.md
[carlscronaswekoblad-1860]: data/carlscronaswekoblad-1860/carlscronaswekoblad-1860.md
[carlscronaswekoblad-1870]: data/carlscronaswekoblad-1870/carlscronaswekoblad-1870.md
[dagligtallehanda-1760]: data/dagligtallehanda-1760/dagligtallehanda-1760.md
[dagligtallehanda-1770]: data/dagligtallehanda-1770/dagligtallehanda-1770.md
[dagligtallehanda-1780]: data/dagligtallehanda-1780/dagligtallehanda-1780.md
[dagligtallehanda-1790]: data/dagligtallehanda-1790/dagligtallehanda-1790.md
[dagligtallehanda-1800]: data/dagligtallehanda-1800/dagligtallehanda-1800.md
[dagligtallehanda-1810]: data/dagligtallehanda-1810/dagligtallehanda-1810.md
[dagligtallehanda-1820]: data/dagligtallehanda-1820/dagligtallehanda-1820.md
[dagligtallehanda-1830]: data/dagligtallehanda-1830/dagligtallehanda-1830.md
[dagligtallehanda-1840]: data/dagligtallehanda-1840/dagligtallehanda-1840.md
[dalpilen-1850]: data/dalpilen-1850/dalpilen-1850.md
[dalpilen-1870]: data/dalpilen-1870/dalpilen-1870.md
[dalpilen-1880]: data/dalpilen-1880/dalpilen-1880.md
[dalpilen-1890]: data/dalpilen-1890/dalpilen-1890.md
[dalpilen-1900]: data/dalpilen-1900/dalpilen-1900.md
[fahluweckoblad-1780]: data/fahluweckoblad-1780/fahluweckoblad-1780.md
[fahluweckoblad-1790]: data/fahluweckoblad-1790/fahluweckoblad-1790.md
[fahluweckoblad-1800]: data/fahluweckoblad-1800/fahluweckoblad-1800.md
[fahluweckoblad-1810]: data/fahluweckoblad-1810/fahluweckoblad-1810.md
[fahluweckoblad-1820]: data/fahluweckoblad-1820/fahluweckoblad-1820.md
[falkopingstidning-1850]: data/falkopingstidning-1850/falkopingstidning-1850.md
[falkopingstidning-1860]: data/falkopingstidning-1860/falkopingstidning-1860.md
[falkopingstidning-1870]: data/falkopingstidning-1870/falkopingstidning-1870.md
[falkopingstidning-1880]: data/falkopingstidning-1880/falkopingstidning-1880.md
[falkopingstidning-1890]: data/falkopingstidning-1890/falkopingstidning-1890.md
[faluposten-1860]: data/faluposten-1860/faluposten-1860.md
[faluposten-1870]: data/faluposten-1870/faluposten-1870.md
[faluposten-1880]: data/faluposten-1880/faluposten-1880.md
[faluposten-1890]: data/faluposten-1890/faluposten-1890.md
[folketsrost-1840]: data/folketsrost-1840/folketsrost-1840.md
[folketsrost-1850]: data/folketsrost-1850/folketsrost-1850.md
[folketsrost-1860]: data/folketsrost-1860/folketsrost-1860.md
[ghost-1830]: data/ghost-1830/ghost-1830.md
[ghost-1840]: data/ghost-1840/ghost-1840.md
[ghost-1850]: data/ghost-1850/ghost-1850.md
[ghost-1860]: data/ghost-1860/ghost-1860.md
[ghost-1870]: data/ghost-1870/ghost-1870.md
[ghost-1880]: data/ghost-1880/ghost-1880.md
[ghost-1890]: data/ghost-1890/ghost-1890.md
[goteborgsposten-1850]: data/goteborgsposten-1850/goteborgsposten-1850.md
[goteborgsposten-1860]: data/goteborgsposten-1860/goteborgsposten-1860.md
[goteborgsposten-1870]: data/goteborgsposten-1870/goteborgsposten-1870.md
[goteborgsposten-1880]: data/goteborgsposten-1880/goteborgsposten-1880.md
[goteborgsposten-1890]: data/goteborgsposten-1890/goteborgsposten-1890.md
[goteborgsweckoblad-1870]: data/goteborgsweckoblad-1870/goteborgsweckoblad-1870.md
[goteborgsweckoblad-1880]: data/goteborgsweckoblad-1880/goteborgsweckoblad-1880.md
[goteborgsweckoblad-1890]: data/goteborgsweckoblad-1890/goteborgsweckoblad-1890.md
[gotheborgsallehanda-1770]: data/gotheborgsallehanda-1770/gotheborgsallehanda-1770.md
[gotheborgsallehanda-1780]: data/gotheborgsallehanda-1780/gotheborgsallehanda-1780.md
[gotheborgsallehanda-1790]: data/gotheborgsallehanda-1790/gotheborgsallehanda-1790.md
[gotheborgsallehanda-1800]: data/gotheborgsallehanda-1800/gotheborgsallehanda-1800.md
[gotheborgsallehanda-1810]: data/gotheborgsallehanda-1810/gotheborgsallehanda-1810.md
[gotheborgsallehanda-1820]: data/gotheborgsallehanda-1820/gotheborgsallehanda-1820.md
[gotheborgsallehanda-1830]: data/gotheborgsallehanda-1830/gotheborgsallehanda-1830.md
[gotheborgsallehanda-1840]: data/gotheborgsallehanda-1840/gotheborgsallehanda-1840.md
[gotheborgskanyheter-1760]: data/gotheborgskanyheter-1760/gotheborgskanyheter-1760.md
[gotheborgskanyheter-1770]: data/gotheborgskanyheter-1770/gotheborgskanyheter-1770.md
[gotheborgskanyheter-1780]: data/gotheborgskanyheter-1780/gotheborgskanyheter-1780.md
[gotheborgskanyheter-1790]: data/gotheborgskanyheter-1790/gotheborgskanyheter-1790.md
[gotheborgskanyheter-1800]: data/gotheborgskanyheter-1800/gotheborgskanyheter-1800.md
[gotheborgskanyheter-1810]: data/gotheborgskanyheter-1810/gotheborgskanyheter-1810.md
[gotheborgskanyheter-1820]: data/gotheborgskanyheter-1820/gotheborgskanyheter-1820.md
[gotheborgskanyheter-1830]: data/gotheborgskanyheter-1830/gotheborgskanyheter-1830.md
[gotheborgskanyheter-1840]: data/gotheborgskanyheter-1840/gotheborgskanyheter-1840.md
[gotheborgsweckolista-1740]: data/gotheborgsweckolista-1740/gotheborgsweckolista-1740.md
[gotheborgsweckolista-1750]: data/gotheborgsweckolista-1750/gotheborgsweckolista-1750.md
[gotlandstidning-1860]: data/gotlandstidning-1860/gotlandstidning-1860.md
[gotlandstidning-1870]: data/gotlandstidning-1870/gotlandstidning-1870.md
[gotlandstidning-1880]: data/gotlandstidning-1880/gotlandstidning-1880.md
[harnosandsposten-1840]: data/harnosandsposten-1840/harnosandsposten-1840.md
[harnosandsposten-1850]: data/harnosandsposten-1850/harnosandsposten-1850.md
[harnosandsposten-1860]: data/harnosandsposten-1860/harnosandsposten-1860.md
[harnosandsposten-1870]: data/harnosandsposten-1870/harnosandsposten-1870.md
[harnosandsposten-1880]: data/harnosandsposten-1880/harnosandsposten-1880.md
[harnosandsposten-1890]: data/harnosandsposten-1890/harnosandsposten-1890.md
[inrikestidningar-1760]: data/inrikestidningar-1760/inrikestidningar-1760.md
[inrikestidningar-1770]: data/inrikestidningar-1770/inrikestidningar-1770.md
[inrikestidningar-1780]: data/inrikestidningar-1780/inrikestidningar-1780.md
[inrikestidningar-1790]: data/inrikestidningar-1790/inrikestidningar-1790.md
[inrikestidningar-1800]: data/inrikestidningar-1800/inrikestidningar-1800.md
[inrikestidningar-1810]: data/inrikestidningar-1810/inrikestidningar-1810.md
[inrikestidningar-1820]: data/inrikestidningar-1820/inrikestidningar-1820.md
[jonkopingsbladet-1840]: data/jonkopingsbladet-1840/jonkopingsbladet-1840.md
[jonkopingsbladet-1850]: data/jonkopingsbladet-1850/jonkopingsbladet-1850.md
[jonkopingsbladet-1860]: data/jonkopingsbladet-1860/jonkopingsbladet-1860.md
[jonkopingsbladet-1870]: data/jonkopingsbladet-1870/jonkopingsbladet-1870.md
[jonkopingsposten-1860]: data/jonkopingsposten-1860/jonkopingsposten-1860.md
[jonkopingsposten-1870]: data/jonkopingsposten-1870/jonkopingsposten-1870.md
[jonkopingsposten-1880]: data/jonkopingsposten-1880/jonkopingsposten-1880.md
[jonkopingsposten-1890]: data/jonkopingsposten-1890/jonkopingsposten-1890.md
[kalmar-1860]: data/kalmar-1860/kalmar-1860.md
[kalmar-1870]: data/kalmar-1870/kalmar-1870.md
[kalmar-1880]: data/kalmar-1880/kalmar-1880.md
[kalmar-1890]: data/kalmar-1890/kalmar-1890.md
[kalmar-1900]: data/kalmar-1900/kalmar-1900.md
[karlshamnsallehanda-1840]: data/karlshamnsallehanda-1840/karlshamnsallehanda-1840.md
[karlshamnsallehanda-1850]: data/karlshamnsallehanda-1850/karlshamnsallehanda-1850.md
[karlshamnsallehanda-1860]: data/karlshamnsallehanda-1860/karlshamnsallehanda-1860.md
[karlshamnsallehanda-1870]: data/karlshamnsallehanda-1870/karlshamnsallehanda-1870.md
[karlshamnsallehanda-1880]: data/karlshamnsallehanda-1880/karlshamnsallehanda-1880.md
[karlshamnsallehanda-1890]: data/karlshamnsallehanda-1890/karlshamnsallehanda-1890.md
[karlskronaweckoblad-1870]: data/karlskronaweckoblad-1870/karlskronaweckoblad-1870.md
[karlskronaweckoblad-1880]: data/karlskronaweckoblad-1880/karlskronaweckoblad-1880.md
[karlskronaweckoblad-1890]: data/karlskronaweckoblad-1890/karlskronaweckoblad-1890.md
[kristianstadsbladet-1850]: data/kristianstadsbladet-1850/kristianstadsbladet-1850.md
[kristianstadsbladet-1860]: data/kristianstadsbladet-1860/kristianstadsbladet-1860.md
[kristianstadsbladet-1870]: data/kristianstadsbladet-1870/kristianstadsbladet-1870.md
[kristianstadsbladet-1880]: data/kristianstadsbladet-1880/kristianstadsbladet-1880.md
[kristianstadsbladet-1890]: data/kristianstadsbladet-1890/kristianstadsbladet-1890.md
[lindesbergsallehanda-1870]: data/lindesbergsallehanda-1870/lindesbergsallehanda-1870.md
[lindesbergsallehanda-1880]: data/lindesbergsallehanda-1880/lindesbergsallehanda-1880.md
[lundsweckoblad-1770]: data/lundsweckoblad-1770/lundsweckoblad-1770.md
[lundsweckoblad-1780]: data/lundsweckoblad-1780/lundsweckoblad-1780.md
[lundsweckoblad-1810]: data/lundsweckoblad-1810/lundsweckoblad-1810.md
[lundsweckoblad-1820]: data/lundsweckoblad-1820/lundsweckoblad-1820.md
[lundsweckoblad-1830]: data/lundsweckoblad-1830/lundsweckoblad-1830.md
[lundsweckoblad-1840]: data/lundsweckoblad-1840/lundsweckoblad-1840.md
[lundsweckoblad-1850]: data/lundsweckoblad-1850/lundsweckoblad-1850.md
[lundsweckoblad-1860]: data/lundsweckoblad-1860/lundsweckoblad-1860.md
[lundsweckoblad-1870]: data/lundsweckoblad-1870/lundsweckoblad-1870.md
[lundsweckoblad-1880]: data/lundsweckoblad-1880/lundsweckoblad-1880.md
[lundsweckoblad-1890]: data/lundsweckoblad-1890/lundsweckoblad-1890.md
[malmoallehanda-1820]: data/malmoallehanda-1820/malmoallehanda-1820.md
[malmoallehanda-1830]: data/malmoallehanda-1830/malmoallehanda-1830.md
[malmoallehanda-1840]: data/malmoallehanda-1840/malmoallehanda-1840.md
[malmoallehanda-1850]: data/malmoallehanda-1850/malmoallehanda-1850.md
[malmoallehanda-1860]: data/malmoallehanda-1860/malmoallehanda-1860.md
[malmoallehanda-1870]: data/malmoallehanda-1870/malmoallehanda-1870.md
[malmoallehanda-1880]: data/malmoallehanda-1880/malmoallehanda-1880.md
[malmoallehanda-1890]: data/malmoallehanda-1890/malmoallehanda-1890.md
[nerikesallehanda-1840]: data/nerikesallehanda-1840/nerikesallehanda-1840.md
[nerikesallehanda-1850]: data/nerikesallehanda-1850/nerikesallehanda-1850.md
[nerikesallehanda-1860]: data/nerikesallehanda-1860/nerikesallehanda-1860.md
[nerikesallehanda-1870]: data/nerikesallehanda-1870/nerikesallehanda-1870.md
[nerikesallehanda-1880]: data/nerikesallehanda-1880/nerikesallehanda-1880.md
[nerikesallehanda-1890]: data/nerikesallehanda-1890/nerikesallehanda-1890.md
[nlk-1850]: data/nlk-1850/nlk-1850.md
[nlk-1860]: data/nlk-1860/nlk-1860.md
[nlk-1870]: data/nlk-1870/nlk-1870.md
[norden-1850]: data/norden-1850/norden-1850.md
[norden-1860]: data/norden-1860/norden-1860.md
[norraskane-1880]: data/norraskane-1880/norraskane-1880.md
[norraskane-1890]: data/norraskane-1890/norraskane-1890.md
[norrbottenskuriren-1860]: data/norrbottenskuriren-1860/norrbottenskuriren-1860.md
[norrbottenskuriren-1870]: data/norrbottenskuriren-1870/norrbottenskuriren-1870.md
[norrbottenskuriren-1880]: data/norrbottenskuriren-1880/norrbottenskuriren-1880.md
[norrbottenskuriren-1890]: data/norrbottenskuriren-1890/norrbottenskuriren-1890.md
[norrbottensposten-1840]: data/norrbottensposten-1840/norrbottensposten-1840.md
[norrbottensposten-1850]: data/norrbottensposten-1850/norrbottensposten-1850.md
[norrbottensposten-1860]: data/norrbottensposten-1860/norrbottensposten-1860.md
[norrbottensposten-1870]: data/norrbottensposten-1870/norrbottensposten-1870.md
[norrbottensposten-1880]: data/norrbottensposten-1880/norrbottensposten-1880.md
[norrbottensposten-1890]: data/norrbottensposten-1890/norrbottensposten-1890.md
[norrkopingskuriren-1850]: data/norrkopingskuriren-1850/norrkopingskuriren-1850.md
[norrkopingskuriren-1860]: data/norrkopingskuriren-1860/norrkopingskuriren-1860.md
[norrkopingstidningar-1780]: data/norrkopingstidningar-1780/norrkopingstidningar-1780.md
[norrkopingstidningar-1790]: data/norrkopingstidningar-1790/norrkopingstidningar-1790.md
[norrkopingstidningar-1800]: data/norrkopingstidningar-1800/norrkopingstidningar-1800.md
[norrkopingstidningar-1810]: data/norrkopingstidningar-1810/norrkopingstidningar-1810.md
[norrkopingstidningar-1820]: data/norrkopingstidningar-1820/norrkopingstidningar-1820.md
[norrkopingstidningar-1830]: data/norrkopingstidningar-1830/norrkopingstidningar-1830.md
[norrkopingstidningar-1840]: data/norrkopingstidningar-1840/norrkopingstidningar-1840.md
[norrkopingstidningar-1850]: data/norrkopingstidningar-1850/norrkopingstidningar-1850.md
[norrkopingstidningar-1860]: data/norrkopingstidningar-1860/norrkopingstidningar-1860.md
[norrkopingstidningar-1870]: data/norrkopingstidningar-1870/norrkopingstidningar-1870.md
[norrkopingstidningar-1880]: data/norrkopingstidningar-1880/norrkopingstidningar-1880.md
[norrkopingstidningar-1890]: data/norrkopingstidningar-1890/norrkopingstidningar-1890.md
[norrkopingsweckotidningar-1750]: data/norrkopingsweckotidningar-1750/norrkopingsweckotidningar-1750.md
[norrkopingsweckotidningar-1760]: data/norrkopingsweckotidningar-1760/norrkopingsweckotidningar-1760.md
[norrkopingsweckotidningar-1770]: data/norrkopingsweckotidningar-1770/norrkopingsweckotidningar-1770.md
[norrkopingsweckotidningar-1780]: data/norrkopingsweckotidningar-1780/norrkopingsweckotidningar-1780.md
[norrlandsposten-1880]: data/norrlandsposten-1880/norrlandsposten-1880.md
[nyadagligtallehanda-1850]: data/nyadagligtallehanda-1850/nyadagligtallehanda-1850.md
[nyadagligtallehanda-1860]: data/nyadagligtallehanda-1860/nyadagligtallehanda-1860.md
[nyadagligtallehanda-1870]: data/nyadagligtallehanda-1870/nyadagligtallehanda-1870.md
[nyadagligtallehanda-1880]: data/nyadagligtallehanda-1880/nyadagligtallehanda-1880.md
[nyadagligtallehanda-1890]: data/nyadagligtallehanda-1890/nyadagligtallehanda-1890.md
[nyakarlskronaweckoblad-1870]: data/nyakarlskronaweckoblad-1870/nyakarlskronaweckoblad-1870.md
[nyawermlandstidningen-1850]: data/nyawermlandstidningen-1850/nyawermlandstidningen-1850.md
[nyawermlandstidningen-1860]: data/nyawermlandstidningen-1860/nyawermlandstidningen-1860.md
[nyawermlandstidningen-1870]: data/nyawermlandstidningen-1870/nyawermlandstidningen-1870.md
[nyawermlandstidningen-1880]: data/nyawermlandstidningen-1880/nyawermlandstidningen-1880.md
[nyawermlandstidningen-1890]: data/nyawermlandstidningen-1890/nyawermlandstidningen-1890.md
[nyawexjobladet-1840]: data/nyawexjobladet-1840/nyawexjobladet-1840.md
[nyawexjobladet-1850]: data/nyawexjobladet-1850/nyawexjobladet-1850.md
[nyawexjobladet-1860]: data/nyawexjobladet-1860/nyawexjobladet-1860.md
[nyawexjobladet-1870]: data/nyawexjobladet-1870/nyawexjobladet-1870.md
[nyawexjobladet-1880]: data/nyawexjobladet-1880/nyawexjobladet-1880.md
[nyawexjobladet-1890]: data/nyawexjobladet-1890/nyawexjobladet-1890.md
[nyttallvarochskamt-1840]: data/nyttallvarochskamt-1840/nyttallvarochskamt-1840.md
[nyttallvarochskamt-1850]: data/nyttallvarochskamt-1850/nyttallvarochskamt-1850.md
[nyttochgammalt-1780]: data/nyttochgammalt-1780/nyttochgammalt-1780.md
[nyttochgammalt-1790]: data/nyttochgammalt-1790/nyttochgammalt-1790.md
[nyttochgammalt-1800]: data/nyttochgammalt-1800/nyttochgammalt-1800.md
[nyttochgammalt-1810]: data/nyttochgammalt-1810/nyttochgammalt-1810.md
[ostergotlandsveckoblad-1880]: data/ostergotlandsveckoblad-1880/ostergotlandsveckoblad-1880.md
[ostergotlandsveckoblad-1890]: data/ostergotlandsveckoblad-1890/ostergotlandsveckoblad-1890.md
[ostgotacorrespondenten-1830]: data/ostgotacorrespondenten-1830/ostgotacorrespondenten-1830.md
[ostgotacorrespondenten-1840]: data/ostgotacorrespondenten-1840/ostgotacorrespondenten-1840.md
[ostgotacorrespondenten-1850]: data/ostgotacorrespondenten-1850/ostgotacorrespondenten-1850.md
[ostgotacorrespondenten-1860]: data/ostgotacorrespondenten-1860/ostgotacorrespondenten-1860.md
[ostgotacorrespondenten-1870]: data/ostgotacorrespondenten-1870/ostgotacorrespondenten-1870.md
[ostgotacorrespondenten-1880]: data/ostgotacorrespondenten-1880/ostgotacorrespondenten-1880.md
[ostgotacorrespondenten-1890]: data/ostgotacorrespondenten-1890/ostgotacorrespondenten-1890.md
[ostgotaposten-1890]: data/ostgotaposten-1890/ostgotaposten-1890.md
[ostgotaposten-1900]: data/ostgotaposten-1900/ostgotaposten-1900.md
[post-ochinrikestidningar-1820]: data/post-ochinrikestidningar-1820/post-ochinrikestidningar-1820.md
[post-ochinrikestidningar-1830]: data/post-ochinrikestidningar-1830/post-ochinrikestidningar-1830.md
[post-ochinrikestidningar-1840]: data/post-ochinrikestidningar-1840/post-ochinrikestidningar-1840.md
[post-ochinrikestidningar-1850]: data/post-ochinrikestidningar-1850/post-ochinrikestidningar-1850.md
[post-ochinrikestidningar-1860]: data/post-ochinrikestidningar-1860/post-ochinrikestidningar-1860.md
[post-ochinrikestidningar-1870]: data/post-ochinrikestidningar-1870/post-ochinrikestidningar-1870.md
[post-ochinrikestidningar-1880]: data/post-ochinrikestidningar-1880/post-ochinrikestidningar-1880.md
[post-ochinrikestidningar-1890]: data/post-ochinrikestidningar-1890/post-ochinrikestidningar-1890.md
[posttidningar-1640]: data/posttidningar-1640/posttidningar-1640.md
[posttidningar-1650]: data/posttidningar-1650/posttidningar-1650.md
[posttidningar-1660]: data/posttidningar-1660/posttidningar-1660.md
[posttidningar-1670]: data/posttidningar-1670/posttidningar-1670.md
[posttidningar-1680]: data/posttidningar-1680/posttidningar-1680.md
[posttidningar-1690]: data/posttidningar-1690/posttidningar-1690.md
[posttidningar-1700]: data/posttidningar-1700/posttidningar-1700.md
[posttidningar-1710]: data/posttidningar-1710/posttidningar-1710.md
[posttidningar-1720]: data/posttidningar-1720/posttidningar-1720.md
[posttidningar-1730]: data/posttidningar-1730/posttidningar-1730.md
[posttidningar-1740]: data/posttidningar-1740/posttidningar-1740.md
[posttidningar-1750]: data/posttidningar-1750/posttidningar-1750.md
[posttidningar-1760]: data/posttidningar-1760/posttidningar-1760.md
[posttidningar-1770]: data/posttidningar-1770/posttidningar-1770.md
[posttidningar-1780]: data/posttidningar-1780/posttidningar-1780.md
[posttidningar-1790]: data/posttidningar-1790/posttidningar-1790.md
[posttidningar-1800]: data/posttidningar-1800/posttidningar-1800.md
[posttidningar-1810]: data/posttidningar-1810/posttidningar-1810.md
[posttidningar-1820]: data/posttidningar-1820/posttidningar-1820.md
[stnlk-1870]: data/stnlk-1870/stnlk-1870.md
[stockholmsdagblad-1820]: data/stockholmsdagblad-1820/stockholmsdagblad-1820.md
[stockholmsdagblad-1830]: data/stockholmsdagblad-1830/stockholmsdagblad-1830.md
[stockholmsdagblad-1840]: data/stockholmsdagblad-1840/stockholmsdagblad-1840.md
[stockholmsdagblad-1850]: data/stockholmsdagblad-1850/stockholmsdagblad-1850.md
[stockholmsdagblad-1860]: data/stockholmsdagblad-1860/stockholmsdagblad-1860.md
[stockholmsdagblad-1870]: data/stockholmsdagblad-1870/stockholmsdagblad-1870.md
[stockholmsdagblad-1880]: data/stockholmsdagblad-1880/stockholmsdagblad-1880.md
[stockholmsdagblad-1890]: data/stockholmsdagblad-1890/stockholmsdagblad-1890.md
[stockholmsposten-1770]: data/stockholmsposten-1770/stockholmsposten-1770.md
[stockholmsposten-1780]: data/stockholmsposten-1780/stockholmsposten-1780.md
[stockholmsposten-1790]: data/stockholmsposten-1790/stockholmsposten-1790.md
[stockholmsposten-1800]: data/stockholmsposten-1800/stockholmsposten-1800.md
[stockholmsposten-1810]: data/stockholmsposten-1810/stockholmsposten-1810.md
[stockholmsposten-1820]: data/stockholmsposten-1820/stockholmsposten-1820.md
[stockholmsposten-1830]: data/stockholmsposten-1830/stockholmsposten-1830.md
[sundsvallstidning-1880]: data/sundsvallstidning-1880/sundsvallstidning-1880.md
[sundsvallstidning-1890]: data/sundsvallstidning-1890/sundsvallstidning-1890.md
[tfwbsol-1840]: data/tfwbsol-1840/tfwbsol-1840.md
[tfwbsol-1850]: data/tfwbsol-1850/tfwbsol-1850.md
[tfwbsol-1860]: data/tfwbsol-1860/tfwbsol-1860.md
[tfwbsol-1870]: data/tfwbsol-1870/tfwbsol-1870.md
[tfwbsol-1880]: data/tfwbsol-1880/tfwbsol-1880.md
[tfwbsol-1890]: data/tfwbsol-1890/tfwbsol-1890.md
[umebladet-1840]: data/umebladet-1840/umebladet-1840.md
[umebladet-1850]: data/umebladet-1850/umebladet-1850.md
[umebladet-1860]: data/umebladet-1860/umebladet-1860.md
[umebladet-1870]: data/umebladet-1870/umebladet-1870.md
[umebladet-1880]: data/umebladet-1880/umebladet-1880.md
[umebladet-1890]: data/umebladet-1890/umebladet-1890.md
[upsala-1840]: data/upsala-1840/upsala-1840.md
[upsala-1850]: data/upsala-1850/upsala-1850.md
[upsala-1860]: data/upsala-1860/upsala-1860.md
[upsala-1870]: data/upsala-1870/upsala-1870.md
[upsala-1880]: data/upsala-1880/upsala-1880.md
[upsala-1890]: data/upsala-1890/upsala-1890.md
[vestmanlandslanstidning-1830]: data/vestmanlandslanstidning-1830/vestmanlandslanstidning-1830.md
[vestmanlandslanstidning-1840]: data/vestmanlandslanstidning-1840/vestmanlandslanstidning-1840.md
[vestmanlandslanstidning-1850]: data/vestmanlandslanstidning-1850/vestmanlandslanstidning-1850.md
[vestmanlandslanstidning-1860]: data/vestmanlandslanstidning-1860/vestmanlandslanstidning-1860.md
[vestmanlandslanstidning-1870]: data/vestmanlandslanstidning-1870/vestmanlandslanstidning-1870.md
[vestmanlandslanstidning-1880]: data/vestmanlandslanstidning-1880/vestmanlandslanstidning-1880.md
[vestmanlandslanstidning-1890]: data/vestmanlandslanstidning-1890/vestmanlandslanstidning-1890.md
[wermlandslanstidning-1870]: data/wermlandslanstidning-1870/wermlandslanstidning-1870.md
[wermlandstidningen-1840]: data/wermlandstidningen-1840/wermlandstidningen-1840.md
[wermlandstidningen-1850]: data/wermlandstidningen-1850/wermlandstidningen-1850.md
[wernamotidning-1870]: data/wernamotidning-1870/wernamotidning-1870.md
[wernamotidning-1880]: data/wernamotidning-1880/wernamotidning-1880.md
[wexjobladet-1810]: data/wexjobladet-1810/wexjobladet-1810.md
[wexjobladet-1820]: data/wexjobladet-1820/wexjobladet-1820.md
[wexjobladet-1830]: data/wexjobladet-1830/wexjobladet-1830.md
[wexjobladet-1840]: data/wexjobladet-1840/wexjobladet-1840.md
[wexjobladet-1850]: data/wexjobladet-1850/wexjobladet-1850.md
[rd-prop]: data/rd-prop/rd-prop.md
[rd-sou]: data/rd-sou/rd-sou.md
[rd-prot]: data/rd-prot/rd-prot.md
[rd-bet]: data/rd-bet/rd-bet.md
[rd-mot]: data/rd-mot/rd-mot.md
[rd-ds]: data/rd-ds/rd-ds.md
[rd-ovr]: data/rd-ovr/rd-ovr.md
[sfs]: data/sfs/sfs.md
[rd-frsrdg]: data/rd-frsrdg/rd-frsrdg.md
[rd-skfr]: data/rd-skfr/rd-skfr.md
[rd-yttr]: data/rd-yttr/rd-yttr.md
[rd-utsk]: data/rd-utsk/rd-utsk.md
[rd-fpm]: data/rd-fpm/rd-fpm.md
[rd-ip]: data/rd-ip/rd-ip.md
[rd-kom]: data/rd-kom/rd-kom.md
[rd-kammakt]: data/rd-kammakt/rd-kammakt.md
[rd-utr]: data/rd-utr/rd-utr.md
[rd-anf-1993-2018]: data/rd-anf-1993-2018/rd-anf-1993-2018.md
[mosel-voxpopuli]: data/mosel-voxpopuli/mosel-voxpopuli.md
[mosel-youtube-commons]: data/mosel-youtube-commons/mosel-youtube-commons.md
[kalmar-1910]: data/kalmar-1910/kalmar-1910.md
[dalpilen-1910]: data/dalpilen-1910/dalpilen-1910.md
[dalpilen-1920]: data/dalpilen-1920/dalpilen-1920.md
[ostgotaposten-1910]: data/ostgotaposten-1910/ostgotaposten-1910.md
[sweachum]: data/sweachum/sweachum.md
[sweacsam]: data/sweacsam/sweacsam.md
[bloggmix1998]: data/bloggmix1998/bloggmix1998.md
[bloggmix1999]: data/bloggmix1999/bloggmix1999.md
[bloggmix2000]: data/bloggmix2000/bloggmix2000.md
[bloggmix2001]: data/bloggmix2001/bloggmix2001.md
[bloggmix2002]: data/bloggmix2002/bloggmix2002.md
[bloggmix2003]: data/bloggmix2003/bloggmix2003.md
[bloggmix2004]: data/bloggmix2004/bloggmix2004.md
[bloggmix2005]: data/bloggmix2005/bloggmix2005.md
[bloggmix2006]: data/bloggmix2006/bloggmix2006.md
[bloggmix2007]: data/bloggmix2007/bloggmix2007.md
[bloggmix2008]: data/bloggmix2008/bloggmix2008.md
[bloggmix2009]: data/bloggmix2009/bloggmix2009.md
[bloggmix2010]: data/bloggmix2010/bloggmix2010.md
[bloggmix2011]: data/bloggmix2011/bloggmix2011.md
[bloggmix2012]: data/bloggmix2012/bloggmix2012.md
[bloggmix2013]: data/bloggmix2013/bloggmix2013.md
[bloggmix2014]: data/bloggmix2014/bloggmix2014.md
[bloggmix2015]: data/bloggmix2015/bloggmix2015.md
[bloggmix2016]: data/bloggmix2016/bloggmix2016.md
[bloggmix2017]: data/bloggmix2017/bloggmix2017.md
[bloggmixodat]: data/bloggmixodat/bloggmixodat.md
[press65]: data/press65/press65.md
[press76]: data/press76/press76.md
[press95]: data/press95/press95.md
[press96]: data/press96/press96.md
[press97]: data/press97/press97.md
[press98]: data/press98/press98.md
[gp1994]: data/gp1994/gp1994.md
[gp2001]: data/gp2001/gp2001.md
[gp2002]: data/gp2002/gp2002.md
[gp2003]: data/gp2003/gp2003.md
[gp2004]: data/gp2004/gp2004.md
[gp2005]: data/gp2005/gp2005.md
[gp2006]: data/gp2006/gp2006.md
[gp2007]: data/gp2007/gp2007.md
[gp2008]: data/gp2008/gp2008.md
[gp2009]: data/gp2009/gp2009.md
[gp2010]: data/gp2010/gp2010.md
[gp2011]: data/gp2011/gp2011.md
[gp2012]: data/gp2012/gp2012.md
[gp2013]: data/gp2013/gp2013.md
[attasidor]: data/attasidor/attasidor.md
[svt-2004]: data/svt-2004/svt-2004.md
[svt-2005]: data/svt-2005/svt-2005.md
[svt-2006]: data/svt-2006/svt-2006.md
[svt-2007]: data/svt-2007/svt-2007.md
[svt-2008]: data/svt-2008/svt-2008.md
[svt-2009]: data/svt-2009/svt-2009.md
[svt-2010]: data/svt-2010/svt-2010.md
[svt-2011]: data/svt-2011/svt-2011.md
[svt-2012]: data/svt-2012/svt-2012.md
[svt-2013]: data/svt-2013/svt-2013.md
[svt-2014]: data/svt-2014/svt-2014.md
[svt-2015]: data/svt-2015/svt-2015.md
[svt-2016]: data/svt-2016/svt-2016.md
[svt-2017]: data/svt-2017/svt-2017.md
[svt-2018]: data/svt-2018/svt-2018.md
[svt-2019]: data/svt-2019/svt-2019.md
[svt-2020]: data/svt-2020/svt-2020.md
[svt-2021]: data/svt-2021/svt-2021.md
[svt-2022]: data/svt-2022/svt-2022.md
[svt-2023]: data/svt-2023/svt-2023.md
[svt-nodate]: data/svt-nodate/svt-nodate.md
[gutenberg]: data/gutenberg/gutenberg.md
[runeberg-diverse]: data/runeberg-diverse/runeberg-diverse.md
[runeberg-folkbbl]: data/runeberg-folkbbl/runeberg-folkbbl.md
[runeberg-rost]: data/runeberg-rost/runeberg-rost.md
[runeberg-tiden]: data/runeberg-tiden/runeberg-tiden.md
[runeberg-urdagkron]: data/runeberg-urdagkron/runeberg-urdagkron.md
[bellman]: data/bellman/bellman.md
[drama]: data/drama/drama.md
[lb-restricted]: data/lb-restricted/lb-restricted.md
[swedish-pd]: data/swedish-pd/swedish-pd.md
[riksarkivet-goteborg-lines]: data/riksarkivet-goteborg-lines/riksarkivet-goteborg-lines.md
[riksarkivet-svea-hovratt-lines]: data/riksarkivet-svea-hovratt-lines/riksarkivet-svea-hovratt-lines.md
[riksarkivet-krigshovratten-lines]: data/riksarkivet-krigshovratten-lines/riksarkivet-krigshovratten-lines.md
[riksarkivet-bergskollegium-lines]: data/riksarkivet-bergskollegium-lines/riksarkivet-bergskollegium-lines.md
[riksarkivet-frihetstiden-lines]: data/riksarkivet-frihetstiden-lines/riksarkivet-frihetstiden-lines.md
[riksarkivet-pahlman-lines]: data/riksarkivet-pahlman-lines/riksarkivet-pahlman-lines.md
[riksarkivet-trolldom-lines]: data/riksarkivet-trolldom-lines/riksarkivet-trolldom-lines.md
[riksarkivet-gota-hovratt-lines]: data/riksarkivet-gota-hovratt-lines/riksarkivet-gota-hovratt-lines.md
[riksarkivet-bergmastaren-lines]: data/riksarkivet-bergmastaren-lines/riksarkivet-bergmastaren-lines.md
[riksarkivet-alvsborgs-losen-lines]: data/riksarkivet-alvsborgs-losen-lines/riksarkivet-alvsborgs-losen-lines.md
[riksarkivet-jonkoping-lines]: data/riksarkivet-jonkoping-lines/riksarkivet-jonkoping-lines.md
[wikisource]: data/wikisource/wikisource.md


[CC-0]: https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
[CC-BY-SA 4.0]: https://creativecommons.org/licenses/by-sa/4.0/deed.en
[CC-BY 4.0]: https://creativecommons.org/licenses/by/4.0/deed.en
[Apache 2.0]: https://www.apache.org/licenses/LICENSE-2.0
[Unrestricted under US copyright law]: ./data/gutenberg/gutenberg.md#license-information
[Public domain]: ./data/swedish-pd/swedish-pd.md#license-information
<!-- END-MAIN TABLE -->

</details>


### Data Collection and Processing

This dynaword is continually developed, which means that the dataset will actively be updated as new datasets become available. This means that the size of Dynaword increases over time as seen in the following plot:

<p align="center">
<img src="./images/tokens_over_time.svg" width="600" style="margin-right: 10px;" />
</p>

The data collection and processing varies depending on the dataset and is documentationed the individual datasheets, which is linked in the above table. If possible the collection is documented both in the datasheet and in the reproducible script (`data/{dataset}/create.py`).

In addition to data specific processing we also run a series automated quality checks to ensure formatting (e.g. ensuring correctly formatted columns and unique IDs), quality checks (e.g. duplicate and empty string detection) and datasheet documentation checks. These checks are there to ensure a high quality of documentation and a minimal level of quality. To allow for the development of novel cleaning methodologies we do not provide more extensive cleaning.

### Dataset Statistics
The following plot(s) are intended to give an overview of docuements length in the various sources. 

<p align="center">
<img src="./images/dataset_size_plot.svg" width="600" style="margin-right: 10px;" />
</p>



### Contributing to the dataset

We welcome contributions to the dataset, including new sources, improved data filtering, and other enhancements. To get started on contributing, please see [the contribution guidelines](CONTRIBUTING.md)

## Citation Information

If you use this work, please cite the [scientific article](https://arxiv.org/abs/2508.02271) introducing the Dynaword approach. Many of the sources in this dataset are distributed by [Språkbanken Text](https://spraakbanken.gu.se/en), which should also be cited:

> Enevoldsen, K.C., Jensen, K.N., Kostkan, J., Szab'o, B.I., Kardos, M., Vad, K., Heinsen, J., N'unez, A.B., Barmina, G., Nielsen, J., Larsen, R., Vahlstrup, P.B., Dalum, P.M., Elliott, D., Galke, L., Schneider-Kamp, P., & Nielbo, K.L. (2025). Dynaword: From One-shot to Continuously Developed Datasets.
>
> Forsberg, M., Dannélls, D., Borin, L., & Berdicevskis, A. (2025). Background: Språkbanken Text. In D. Dannélls, K. Blensenius & L. Borin (Eds.), *Sixty years of Swedish computational lexicography* (pp. 161–173).

```bibtex
@article{enevoldsen2025dynaword,
  title={Dynaword: From One-shot to Continuously Developed Datasets},
  author={Enevoldsen, Kenneth and Jensen, Kristian N{\o}rgaard and Kostkan, Jan and Szab{\'o}, Bal{\'a}zs and Kardos, M{\'a}rton and Vad, Kirten and N{\'u}{\~n}ez, Andrea Blasi and Barmina, Gianluca and Nielsen, Jacob and Larsen, Rasmus and others},
  journal={arXiv preprint arXiv:2508.02271},
  year={2025}
}
@incollection{forsberg2025spraakbanken,
  title={Background: {S}pr{\aa}kbanken {T}ext},
  author={Forsberg, Markus and Dann{\'e}lls, Dana and Borin, Lars and Berdicevskis, Aleksandrs},
  booktitle={Sixty years of {S}wedish computational lexicography},
  editor={Dann{\'e}lls, Dana and Blensenius, Kristian and Borin, Lars},
  pages={161--173},
  year={2025}
}
```

Additionally, we recommend citing the relevant source datasets as well. See the individual datasheets for more information.

## License information

The license for each constituent dataset is supplied in the [Source data](#source-data) table. This license is applied to the constituent data, i.e., the text. The collection of datasets (metadata, quality control, etc.) is licensed under [CC-0](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en).

### Personal and Sensitive Information

As far as we are aware the dataset does not contain information identifying sexual orientation, political beliefs, religion, or health connected along with a personal identifier of any non-public or non-historic figures.


### Bias, Risks, and Limitations

Certain works in this collection are historical works and thus reflect the linguistic, cultural, and ideological norms of their time.
As such, it includes perspectives, assumptions, and biases characteristic of the period, which may be considered offensive or exclusionary by contemporary standards.


### Notice and takedown policy
We redistribute files shared with us under a license permitting such redistribution. If you have concerns about the licensing of these files, please [contact us](https://huggingface.co/datasets/danish-foundation-models/swedish-dynaword/discussions/new). If you consider that the data contains material that infringe your copyright, please:
- Clearly identify yourself with detailed contact information such as an address, a telephone number, or an email address at which you can be contacted.
- Clearly reference the original work claimed to be infringed
- Clearly identify the material claimed to be infringing and information reasonably sufficient to allow us to locate the material.
You can contact us through this channel.
We will comply with legitimate requests by removing the affected sources from the next release of the corpus

---

<h3 style="display: flex; align-items: center;">
  <a href="https://www.foundationmodels.dk">
    <img src="./docs/icon.png" width="30" style="margin-right: 10px;" />
  </a>
  A&nbsp;<a href=https://www.foundationmodels.dk>Danish Foundation Models</a>&nbsp;dataset
</h3>
