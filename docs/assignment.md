# Assignment

The original text of the team project assignment (topic 22, STU FEI, 2026/2027), verbatim in
Slovak as published, tab-separated columns included: topic number, team, supervisor, faculty,
supervisor's e-mail, title, assignment.

<!-- markdownlint-disable MD010 -- the original is tab-separated -->
```text
22	"Arsen Labovich,
Mykhailo Adamenko,
Vladyslav Shudiehov,
Bohdan Lynnyk,
Tymur Tkach
"	Filip Hodoň	FEI	filip.hodon@stuba.sk	Konfigurovateľná pipeline pre analýzu vzorov vo finančných časových radoch	"Cieľom projektu je navrhnúť a implementovať modulárne experimentálne prostredie, ktoré umožní systematicky skladať a porovnávať celý experiment spracovania finančných časových radov. Od reprezentácie a predspracovania dát, cez model hlbokého učenia, až po následné spracovanie predikcií a ich pretavenie do obchodného rozhodnutia. V rámci tímového projektu sa budete sústreďovať na návrh jednotnej konfigurovateľnej pipeline, v ktorej si používateľ cez webové rozhranie zvolí formu predspracovania dát (napr. Renko, Kagi, časové okná, ..), nahrá alebo vyberie natrénovaný model a zvolí spôsob post-processingu predikcie (prahovanie, vyhladzovanie, k-means, ..). Výsledkom každého behu bude experiment s jednotnou sadou metrík a vizualizácií, pričom prostredie umožní jednotlivé experimenty vzájomne porovnávať a vyhodnocovať, ktorá kombinácia reprezentácie dát, architektúry a post-processingu prináša najstabilnejšie výsledky.

Vaše úlohy:
Riešenie projektu bude zamerané na návrh a implementáciu konfigurovateľného experimentálneho prostredia rozdeleného do troch vymeniteľných vrstiev:
1. Vrstva predspracovania a reprezentácie dát. Implementácia transformácie cenových radov (Renko, Kagi, ..), spolu s normalizáciou, segmentáciou a tvorbou vstupných okien pre modely.
2. Modelová vrstva - jednotné rozhranie umožňujúce nahranie a spustenie natrénovaných modelov vo formáte .keras, vrátane validácie nahraného modelu (kontrola tvaru vstupu a výstupu voči zvolenej konfigurácii predspracovania). Súčasťou bude implementácia a vyhodnotenie porovnania existujúcich architektúr pre časové ready (napr. TSMixer, StockMixer,..) z hľadiska ich schopnosti zachytávať hlboké vzory a generalizovať na rôzne trhové podmienky.
3. Vrstva post-processingu a rozhodovania - konfigurovateľné spracovanie surovej predikcie modelu do obchodného signálu: prahy a kalibrácia, vyhladzovanie a filtrovanie signálu, minimálna doba držania pozície, určovanie veľkosti pozície a rizikové obmedzenia."
```
