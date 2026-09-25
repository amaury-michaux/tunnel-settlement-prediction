# Data

The project's real data is confidential and is never stored in this repository: `.gitignore` excludes everything in `data/` except this file and `synthetic/`.

`synthetic/` holds a synthetic dataset with the same tables and columns, built by `scripts/make_synthetic_data.py`. Its values are invented.

| File | One row per | Main columns |
|---|---|---|
| `anneau.csv` | lining ring | `id_anneau`, `id_secteur`, `pk`, `z_tn`, `z_voute_tunnel`, `z_base_tunnel` |
| `stratigraphie.csv` | ring × geological layer | `id_anneau`, `id_formation`, `z_base`, `z_toit`, `epaisseur` |
| `formation_geologique.csv` | geological formation | `id_formation`, `nom`, `ordre`, `couleur_r`, `couleur_v`, `couleur_b` |
| `secteur.csv` | sector of the alignment | `id_secteur`, `code`, `pk_debut`, `pk_fin` |
| `parametre_tunnelier.csv` | ring | TBM parameters: `Avance_RDC[mm/mn]`, `Couple_RDC[kN.m]`, `PousseeTotale[kN]`, `CapteurPressionsTerreFront1[bar]`, `PressionInjectionMortierA1…A6[bar]`, `QuantiteMortierInjecteTotale[m3]` |
| `stratigraphie_homogenisee.csv` | ring | equivalent soil parameters: `gamma_h[kN/m3]`, `E_M[MPa]`, `alpha[]`, `c'[kPa]`, `phi'[°]`, `K0[]` |
| `smax.csv` | instrumented cross-section | `id_anneau`, `smax` (maximum surface settlement, mm) |

`id_anneau` is the join key between all tables.
