# Analýza diskrepancí mezi optimálními řešeními a ASLIB datasety

V **121 instancích** jsme získali důkaz optimality pro rozvrh s horším (vyšším) makespanem, než uvádí ASLIB. 

## Souhrnná statistika

| Metrika | Hodnota |
|---------|---------|
| Celkem instancí s diskrepancí | **121** |
| Průměrný rozdíl makespanu | **6.65** |
| Maximální rozdíl makespanu | **40** |

## Počet diskrepancí podle ASLIB algoritmu

Následující tabulka ukazuje, kolik instancí má lepší makespan v daném ASLIB sloupci než naše prokázané optimum:

| Algoritmus | Počet diskrepancí | Poznámka |
|------------|-------------------|----------|
| **TS** | **0** | ✓ Žádná diskrepance |
| CONH1.1 | 2 | |
| CONH1.2 | 8 | |
| CONH1.3 | 9 | |
| CONH1 | 9 | |
| CONH2 | 69 | |
| GA-WGH1 (10%) | 99 | |
| GA-WGH1 (50%) | 99 | |
| GA-WGH1 (100%) | 99 | |
| GA-WGH2 (10%) | 99 | |
| GA-WGH2 (50%) | 100 | |
| GA-WGH2 (100%) | 104 | |
| GA-POP | 101 | |
| GA | 99 | |
| GA-DYN | 105 | |

### Klíčové pozorování

- **Sloupec TS** (Tabu Search) nemá žádnou diskrepanci - všechny jeho hodnoty jsou ≥ našim optimálním řešením.
- **Konstruktivní heuristiky** (CONH1.x) mají jen málo diskrepancí (2-9).
- **Genetické algoritmy** (GA-*) mají nejvíce diskrepancí (99-105), což naznačuje, že právě tyto algoritmy hlásí podezřele nízké makespany.

## Popis algoritmů

### TS - Tabu Search
Řešení nalezená algoritmem Tabu Search od Servranckx a Vanhoucke (2019a), ukončená po 5 000 rozvrzích.

### CONH1, CONH2 - Konstruktivní heuristiky
Řešení nalezená konstruktivními heuristikami od Nekoueian, Servranckx a Vanhoucke (2023) včetně pravidel pro výběr a plánování:
- **CONH1:** ukončeno po 3 rozvrzích
- **CONH2:** ukončeno po 40 rozvrzích

### GA-WGH1, GA-WGH2 - Genetické algoritmy s váhovým učením
Řešení nalezená genetickým algoritmem s váhovým učením od Nekoueian, Servranckx a Vanhoucke (2023), ukončená po 5 000 rozvrzích s restartem populace po 2 500 rozvrzích. Varianty 10%, 50% a 100%.

### GA-POP - Genetický algoritmus s populačním učením
Řešení nalezená genetickým algoritmem s populačním učením od Nekoueian, Servranckx a Vanhoucke (2023), ukončená po 5 000 rozvrzích s restartem populace po 2 500 rozvrzích.

### GA-DYN - Genetický algoritmus s dynamickým restartem
Řešení nalezená genetickým algoritmem od Nekoueian, Servranckx a Vanhoucke (2023), ukončená po 5 000 rozvrzích s dynamickým schématem restartu.

### GA - Základní genetický algoritmus
Řešení nalezená genetickým algoritmem od Nekoueian, Servranckx a Vanhoucke (2023), ukončená po 5 000 rozvrzích s restartem populace po 2 500 rozvrzích.

## Kompletní tabulka diskrepancí

| # | Instance | Naše optimum | ASLIB best | Rozdíl | Nejlepší ASLIB algoritmy |
|---|----------|-------------|------------|--------|--------------------------|
| 1 | aslib0_12968 | 121 | 120 | 1 | GA-WGH2 (100%), GA, GA-DYN |
| 2 | aslib0_12975 | 136 | 127 | 9 | GA-POP |
| 3 | aslib0_13146 | 155 | 138 | 17 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 4 | aslib0_1315 | 80 | 79 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 5 | aslib0_1362 | 79 | 77 | 2 | GA-WGH1 (10%) |
| 6 | aslib0_13668 | 130 | 129 | 1 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 7 | aslib0_13674 | 125 | 123 | 2 | GA-WGH1 (100%), GA-WGH2, GA-POP, GA, GA-DYN |
| 8 | aslib0_13916 | 136 | 135 | 1 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 9 | aslib0_15189 | 140 | 137 | 3 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 10 | aslib0_15236 | 170 | 147 | 23 | GA-WGH2 (10%) |
| 11 | aslib0_15379 | 133 | 131 | 2 | CONH2, GA-WGH1 (10%), GA-WGH2 (100%), GA-DYN |
| 12 | aslib0_15730 | 122 | 119 | 3 | GA-WGH2 (50%) |
| 13 | aslib0_1594 | 80 | 79 | 1 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 14 | aslib0_1683 | 83 | 81 | 2 | GA-WGH2 (50%) |
| 15 | aslib0_17571 | 168 | 166 | 2 | GA-WGH2 (100%), GA-DYN |
| 16 | aslib0_18737 | 171 | 166 | 5 | GA-WGH2 (100%), GA-DYN |
| 17 | aslib0_19092 | 165 | 161 | 4 | GA-WGH1 (100%), GA-WGH2 (50%) |
| 18 | aslib0_19197 | 210 | 201 | 9 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 19 | aslib0_19228 | 199 | 197 | 2 | GA-WGH1 (50%), GA-WGH2 (10%) |
| 20 | aslib0_20614 | 222 | 213 | 9 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 21 | aslib0_20665 | 217 | 214 | 3 | GA-WGH1 (100%), GA-WGH2 (50%), GA |
| 22 | aslib0_20871 | 223 | 221 | 2 | CONH2 |
| 23 | aslib0_20948 | 228 | 219 | 9 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 24 | aslib0_21847 | 196 | 195 | 1 | GA-WGH1 (50%), GA-WGH2 (10%) |
| 25 | aslib0_22372 | 246 | 241 | 5 | GA-WGH1, GA-WGH2 (100%), GA-DYN |
| 26 | aslib0_22415 | 240 | 235 | 5 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 27 | aslib0_22748 | 262 | 225 | 37 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 28 | aslib0_23127 | 248 | 242 | 6 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 29 | aslib0_23181 | 238 | 226 | 12 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 30 | aslib0_23183 | 271 | 254 | 17 | GA-WGH1 (100%), GA-WGH2 (50%) |
| 31 | aslib0_23197 | 261 | 247 | 14 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 32 | aslib0_23975 | 238 | 235 | 3 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 33 | aslib0_24384 | 182 | 181 | 1 | GA-WGH2, GA-POP, GA-DYN |
| 34 | aslib0_24449 | 173 | 171 | 2 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 35 | aslib0_24641 | 163 | 156 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 36 | aslib0_24981 | 197 | 194 | 3 | GA-WGH1, GA |
| 37 | aslib0_25575 | 176 | 168 | 8 | CONH2, GA-WGH1, GA |
| 38 | aslib0_25678 | 193 | 176 | 17 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 39 | aslib0_25691 | 170 | 162 | 8 | GA-WGH2 (10%) |
| 40 | aslib0_25744 | 204 | 203 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 41 | aslib0_26936 | 173 | 163 | 10 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 42 | aslib0_26973 | 191 | 177 | 14 | GA-WGH1 (100%), GA-WGH2 (100%), GA-POP, GA, GA-DYN |
| 43 | aslib0_27236 | 274 | 234 | 40 | GA-WGH1, GA-WGH2 (50%), GA-POP |
| 44 | aslib0_27420 | 195 | 191 | 4 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 45 | aslib0_2747 | 80 | 79 | 1 | GA-POP, GA-DYN |
| 46 | aslib0_27644 | 157 | 155 | 2 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 47 | aslib0_2847 | 79 | 77 | 2 | GA-POP |
| 48 | aslib0_28496 | 218 | 214 | 4 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 49 | aslib0_2880 | 93 | 91 | 2 | GA-WGH2, GA-DYN |
| 50 | aslib0_28893 | 213 | 206 | 7 | GA-WGH2, GA-DYN |
| 51 | aslib0_29082 | 182 | 180 | 2 | GA-WGH1 (50%) |
| 52 | aslib0_29399 | 225 | 219 | 6 | GA-WGH2 (100%), GA-DYN |
| 53 | aslib0_29446 | 198 | 197 | 1 | GA-WGH1 (100%) |
| 54 | aslib0_29680 | 204 | 187 | 17 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 55 | aslib0_29738 | 201 | 196 | 5 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 56 | aslib0_29896 | 218 | 214 | 4 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 57 | aslib0_30748 | 239 | 232 | 7 | GA-WGH1 (100%), GA-WGH2 (100%), GA-POP, GA-DYN |
| 58 | aslib0_30968 | 217 | 202 | 15 | GA-WGH1 (100%), GA-WGH2, GA-DYN |
| 59 | aslib0_31160 | 187 | 184 | 3 | CONH1, CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 60 | aslib0_31181 | 214 | 207 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 61 | aslib0_31187 | 199 | 189 | 10 | GA-WGH2 (100%), GA-DYN |
| 62 | aslib0_31196 | 202 | 196 | 6 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 63 | aslib0_31321 | 182 | 177 | 5 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 64 | aslib0_31460 | 198 | 189 | 9 | GA-WGH1, GA-WGH2 (100%), GA, GA-DYN |
| 65 | aslib0_31636 | 202 | 201 | 1 | GA-WGH1 (50%) |
| 66 | aslib0_3175 | 89 | 85 | 4 | GA-POP |
| 67 | aslib0_3187 | 92 | 91 | 1 | GA-WGH1 (50%), GA-WGH2, GA-POP, GA-DYN |
| 68 | aslib0_31963 | 210 | 196 | 14 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 69 | aslib0_32566 | 234 | 231 | 3 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 70 | aslib0_32578 | 212 | 201 | 11 | GA-WGH1 (50%) |
| 71 | aslib0_32589 | 205 | 176 | 29 | GA-WGH1 (10%), GA-WGH2, GA-POP, GA, GA-DYN |
| 72 | aslib0_32623 | 241 | 233 | 8 | CONH2, GA-WGH1 (10%), GA-WGH2, GA-POP, GA-DYN |
| 73 | aslib0_32634 | 262 | 261 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA-DYN |
| 74 | aslib0_32635 | 231 | 224 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 75 | aslib0_32641 | 258 | 254 | 4 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 76 | aslib0_32673 | 228 | 223 | 5 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 77 | aslib0_32737 | 245 | 240 | 5 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 78 | aslib0_32827 | 236 | 227 | 9 | GA-WGH2 (50%), GA |
| 79 | aslib0_32899 | 252 | 251 | 1 | GA-WGH1, GA-WGH2, GA, GA-DYN |
| 80 | aslib0_32938 | 260 | 254 | 6 | GA-WGH1 (50%), GA-WGH2 |
| 81 | aslib0_32968 | 249 | 242 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 82 | aslib0_33098 | 297 | 290 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 83 | aslib0_33321 | 244 | 239 | 5 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 84 | aslib0_33326 | 258 | 251 | 7 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 85 | aslib0_33471 | 254 | 251 | 3 | CONH1, CONH2, GA-WGH1, GA-WGH2 (10%), GA-POP, GA |
| 86 | aslib0_33641 | 226 | 225 | 1 | GA-WGH1 (100%) |
| 87 | aslib0_33668 | 249 | 245 | 4 | CONH1, CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 88 | aslib0_33669 | 259 | 248 | 11 | GA-POP, GA |
| 89 | aslib0_33680 | 273 | 269 | 4 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 90 | aslib0_33845 | 257 | 252 | 5 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 91 | aslib0_33989 | 293 | 287 | 6 | CONH1, CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 92 | aslib0_34376 | 246 | 244 | 2 | GA-WGH1 (50%), GA-WGH2 |
| 93 | aslib0_34397 | 243 | 242 | 1 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 94 | aslib0_34484 | 251 | 250 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 95 | aslib0_34875 | 225 | 219 | 6 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 96 | aslib0_34892 | 218 | 208 | 10 | GA-POP |
| 97 | aslib0_34968 | 253 | 247 | 6 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 98 | aslib0_35124 | 245 | 242 | 3 | CONH1, CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 99 | aslib0_35167 | 259 | 254 | 5 | CONH1, CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 100 | aslib0_35174 | 259 | 244 | 15 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 101 | aslib0_35212 | 279 | 271 | 8 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 102 | aslib0_35220 | 247 | 239 | 8 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 103 | aslib0_35224 | 274 | 256 | 18 | GA-WGH1 (50%), GA-WGH2, GA-DYN |
| 104 | aslib0_35247 | 240 | 236 | 4 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 105 | aslib0_35373 | 249 | 236 | 13 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA-DYN |
| 106 | aslib0_35433 | 258 | 257 | 1 | GA-WGH1 (50%), GA-WGH2 (50%) |
| 107 | aslib0_35438 | 260 | 259 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 108 | aslib0_35577 | 203 | 191 | 12 | GA-WGH1 (50%) |
| 109 | aslib0_35676 | 265 | 251 | 14 | GA-POP |
| 110 | aslib0_35690 | 255 | 246 | 9 | GA-WGH1 (10%), GA-WGH2, GA, GA-DYN |
| 111 | aslib0_35963 | 259 | 256 | 3 | GA |
| 112 | aslib0_35976 | 271 | 261 | 10 | CONH2, GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 113 | aslib0_35995 | 257 | 254 | 3 | GA-WGH1, GA-WGH2 (100%), GA, GA-DYN |
| 114 | aslib0_3913 | 85 | 82 | 3 | GA-WGH1 (50%), GA-WGH2 (100%), GA-DYN |
| 115 | aslib0_398 | 100 | 84 | 16 | GA-POP |
| 116 | aslib0_476 | 101 | 94 | 7 | GA-WGH2 (50%) |
| 117 | aslib0_5098 | 183 | 180 | 3 | GA-WGH1 (100%), GA |
| 118 | aslib0_610 | 78 | 76 | 2 | GA-POP |
| 119 | aslib0_8341 | 245 | 239 | 6 | GA-WGH2 (50%) |
| 120 | aslib0_893 | 84 | 83 | 1 | GA-WGH1, GA-WGH2, GA-POP, GA, GA-DYN |
| 121 | aslib0_940 | 75 | 73 | 2 | GA-WGH1, GA-WGH2 (100%), GA-POP, GA-DYN |

## Reference

### Dataset ASLIB0
- Servranckx, T., and Vanhoucke, M. (2019a). *A tabu search procedure for the resource-constrained project scheduling problem with alternative subgraphs.* European Journal of Operational Research, 273(3), 841-860. https://doi.org/10.1016/j.ejor.2018.09.005

### Dataset ASLIB1-5
- Servranckx, T., Coelho, J., and Vanhoucke, M. (2022). *Various extensions in resource-constrained project scheduling with alternative subgraphs.* International Journal of Production Research, 60(11), 3501–3520. https://doi.org/10.1080/00207543.2021.1924411

### Algoritmus TS (Tabu Search)
- Servranckx, T., and Vanhoucke, M. (2019a). *A tabu search procedure for the resource-constrained project scheduling problem with alternative subgraphs.* European Journal of Operational Research, 273(3), 841-860. https://doi.org/10.1016/j.ejor.2018.09.005

### Algoritmy CONH (Konstruktivní heuristiky)
- Nekoueian, R., Servranckx, T., and Vanhoucke, M. (2023). *Constructive heuristics for selecting and scheduling alternative subgraphs in resource-constrained projects.* Computers & Industrial Engineering, Article 109399.

### Algoritmy GA (Genetické algoritmy)
- Nekoueian, R., Servranckx, T., and Vanhoucke, M. (2024). *A dynamic learning-based genetic algorithm for scheduling resource-constrained projects with alternative subgraphs.* (under submission)

### Síťové indikátory
- Vanhoucke, M., Coelho, J., Debels, D., Maenhout, B., and Tavares, L. V. (2008). *An evaluation of the adequacy of project network generators with systematically sampled networks.* European Journal of Operational Research, 187(2), 511–524. https://doi.org/10.1016/j.ejor.2007.03.032

## Kontakt

- **Mario Vanhoucke:** mario.vanhoucke@ugent.be
- **José Coelho:** jose.coelho@uab.pt
- **Tom Servranckx:** tom.servranckx@ugent.be

## Závěr

Možné vysvětlení diskrepancí:
1. Chyby v publikovaných ASLIB výsledcích
2. Odlišná interpretace problému nebo omezení
3. Chyby při záznamu/přepisu výsledků

Jelikož ASLIB nepublikoval kompletní rozvrhy, ale pouze hodnoty makespanu, není možné jednoznačně určit zdroj těchto nesrovnalostí.
