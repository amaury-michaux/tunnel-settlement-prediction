"""Génère un jeu de données synthétique ayant la structure des données réelles du projet.

Les données réelles sont confidentielles. Ce jeu permet d'exécuter les notebooks de bout
en bout. Ses valeurs sont inventées à partir d'ordres de grandeur génériques de
géotechnique et de creusement au tunnelier : elles ne disent rien du vrai tunnel.

Usage : python scripts/make_synthetic_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SORTIE = Path(__file__).resolve().parent.parent / "data" / "synthetic"
rng = np.random.default_rng(2026)

N_ANNEAUX = 4000
LONGUEUR_ANNEAU = 1.5  # m
DIAMETRE = 9.0  # m
pk = np.arange(N_ANNEAUX) * LONGUEUR_ANNEAU


def profil_lisse(amplitude, echelles=(5000, 2300, 1100, 450)):
    """Courbe lisse le long du tracé : sinusoïdes de phases aléatoires, les plus courtes étant
    les plus faibles, ce qui donne un relief irrégulier plutôt qu'une ondulation régulière."""
    poids = 1 / np.arange(1, len(echelles) + 1) ** 1.2
    courbe = sum(
        w * rng.uniform(0.6, 1.0) * np.sin(2 * np.pi * pk / echelle + rng.uniform(0, 2 * np.pi))
        for w, echelle in zip(poids, echelles)
    )
    return amplitude * courbe / poids.sum()


# --- Géométrie ----------------------------------------------------------------
z_tn = 55 + profil_lisse(12)
couverture = np.clip(20 + profil_lisse(10), 10, 35)
z_voute = z_tn - couverture
z_radier = z_voute - DIAMETRE
profondeur_axe = couverture + DIAMETRE / 2

N_SECTEURS = 6
longueur_totale = N_ANNEAUX * LONGUEUR_ANNEAU
tirage = rng.uniform(0.5, 1.5, N_SECTEURS)
bornes = np.round(np.concatenate([[0], np.cumsum(tirage / tirage.sum())]) * longueur_totale)
id_secteur = np.searchsorted(bornes[1:-1], pk, side="right") + 1
secteurs = pd.DataFrame({
    "id_secteur": np.arange(1, N_SECTEURS + 1),
    "nom": [f"Secteur {i}" for i in range(1, N_SECTEURS + 1)],
    "code": [f"S{i}" for i in range(1, N_SECTEURS + 1)],
    "description": ["gare" if i % 2 else "interstation" for i in range(1, N_SECTEURS + 1)],
    "longueur": np.diff(bornes).astype(int),
    "pk_debut": bornes[:-1].astype(int),
    "pk_fin": bornes[1:].astype(int),
})

anneaux = pd.DataFrame({
    "id_anneau": np.arange(1, N_ANNEAUX + 1),
    "id_secteur": id_secteur,
    "pk": pk.round(1),
    "z_tn": z_tn.round(2),
    "z_base_tunnel": z_radier.round(2),
    "z_voute_tunnel": z_voute.round(2),
})

# --- Géologie -------------------------------------------------------------------
# Formations génériques, de haut en bas, avec des paramètres de manuel :
# (code, nom, couleur, épaisseur moyenne en m, gamma_h, E_M, alpha, c', phi', K0)
FORMATIONS = [
    ("R", "Remblais", (150, 150, 150), 3, 18.0, 5, 0.50, 0, 25, 0.60),
    ("L", "Limons", (240, 225, 150), 4, 19.0, 8, 0.50, 5, 25, 0.55),
    ("S", "Sables", (250, 210, 120), 6, 19.5, 20, 0.33, 0, 32, 0.47),
    ("M", "Marnes", (200, 225, 170), 8, 20.0, 40, 0.50, 20, 28, 0.55),
    ("C", "Calcaires", (170, 200, 235), 10, 21.0, 120, 0.50, 40, 35, 0.45),
    ("A", "Argiles plastiques", (205, 170, 225), 7, 19.5, 30, 1.00, 15, 18, 0.70),
    ("K", "Craie", (190, 240, 100), 40, 20.0, 150, 0.50, 30, 35, 0.50),
]
PARAMETRES = ["gamma_h[kN/m3]", "E_M[MPa]", "alpha[]", "c'[kPa]", "phi'[°]", "K0[]"]

formations = pd.DataFrame({
    "id_formation": [f[0] for f in FORMATIONS],
    "nom": [f[1] for f in FORMATIONS],
    "ordre": np.arange(1, len(FORMATIONS) + 1) * 10,
    "couleur_r": [f[2][0] for f in FORMATIONS],
    "couleur_v": [f[2][1] for f in FORMATIONS],
    "couleur_b": [f[2][2] for f in FORMATIONS],
})

# épaisseur de chaque couche le long du tracé : certaines disparaissent par endroits ;
# la dernière couche s'arrête 8 m sous le radier du tunnel
epaisseurs = np.column_stack([np.clip(f[3] * (1 + profil_lisse(1.6)), 0, None) for f in FORMATIONS[:-1]])
toit_derniere = z_tn - epaisseurs.sum(axis=1)
epaisseurs = np.column_stack([epaisseurs, np.clip(toit_derniere - (z_radier - 8), 3, None)])
toits = z_tn[:, None] - np.concatenate([np.zeros((N_ANNEAUX, 1)), np.cumsum(epaisseurs, axis=1)[:, :-1]], axis=1)
bases = toits - epaisseurs

lignes = []
for j, f in enumerate(FORMATIONS):
    garder = epaisseurs[:, j] > 0.1
    lignes.append(pd.DataFrame({
        "id_anneau": anneaux["id_anneau"][garder],
        "id_formation": f[0],
        "z_base": bases[garder, j].round(2),
        "z_toit": toits[garder, j].round(2),
        "epaisseur": epaisseurs[garder, j].round(2),
    }))
stratigraphie = pd.concat(lignes).sort_values(["id_anneau", "z_toit"], ascending=[True, False])
stratigraphie.insert(0, "id_stratigraphie", np.arange(1, len(stratigraphie) + 1))

# --- Paramètres de sol équivalents par anneau --------------------------------------
# Moyenne des couches situées au-dessus de la voûte, pondérée par (e_i / C) * (h_i / C)
valeurs = np.array([f[4:] for f in FORMATIONS], dtype=float)  # formations x paramètres
variation = 1 + np.column_stack([profil_lisse(0.15) for _ in PARAMETRES])  # anneaux x paramètres
haut = np.minimum(toits, z_tn[:, None])
bas = np.maximum(bases, z_voute[:, None])
e = np.clip(haut - bas, 0, None)
h = z_tn[:, None] - (haut + bas) / 2
poids = (e / couverture[:, None]) * (h / couverture[:, None])
poids /= poids.sum(axis=1, keepdims=True)
sol_eq = (poids @ valeurs) * variation
sol = pd.DataFrame(sol_eq.round(3), columns=PARAMETRES)
sol.insert(0, "id_anneau", anneaux["id_anneau"])
sol.insert(0, "id_strati_homogene", np.arange(1, N_ANNEAUX + 1))
gamma_eq, E_eq, _, c_eq, _, K0_eq = sol_eq.T

# --- Pilotage du tunnelier -------------------------------------------------------------
p_requise = K0_eq * gamma_eq * profondeur_axe / 100  # pression de terre au repos à l'axe, en bar
reglage_secteur = rng.normal(1.0, 0.06, size=N_SECTEURS + 1)[id_secteur]
p_front = p_requise * reglage_secteur * (1 + profil_lisse(0.08)) + rng.normal(0, 0.05, N_ANNEAUX)

tunnelier = pd.DataFrame({
    "id_anneau": anneaux["id_anneau"],
    "Avance_RDC[mm/mn]": np.clip(45 - 0.1 * E_eq + rng.normal(0, 5, N_ANNEAUX), 8, 80),
    "Couple_RDC[kN.m]": np.clip(2500 + 20 * E_eq + profil_lisse(600) + rng.normal(0, 400, N_ANNEAUX), 500, None),
    "PousseeTotale[kN]": 15000 + 250 * profondeur_axe + 30 * E_eq + rng.normal(0, 1500, N_ANNEAUX),
})
for i in range(1, 5):
    tunnelier[f"CapteurPressionsTerreFront{i}[bar]"] = p_front + 0.1 * (i - 1) + rng.normal(0, 0.03, N_ANNEAUX)
for capteur in ("A1", "A2", "A5", "A6"):
    tunnelier[f"PressionInjectionMortier{capteur}[bar]"] = p_front + 0.6 + rng.normal(0, 0.15, N_ANNEAUX)
tunnelier["QuantiteMortierInjecteTotale[m3]"] = np.clip(10 + profil_lisse(0.8) + rng.normal(0, 0.4, N_ANNEAUX), 6, 14)

# quelques enregistrements manquants
manquants = rng.random(N_ANNEAUX) < 0.01
tunnelier.loc[manquants, ["Avance_RDC[mm/mn]", "Couple_RDC[kN.m]", "PousseeTotale[kN]",
                          "CapteurPressionsTerreFront1[bar]"]] = np.nan
tunnelier = tunnelier.round(3)

# --- Tassement mesuré dans des zones instrumentées -----------------------------------------
# Tassement inventé : plus fort en sol mou, en cas de pression de front insuffisante ou de
# mortier en défaut, plus faible en profondeur, avec un effet propre à chaque zone.
deficit_front = np.clip(1 - p_front / p_requise, 0, None)
deficit_mortier = np.clip(10 - tunnelier["QuantiteMortierInjecteTotale[m3]"].to_numpy(), 0, None)
tassement = (1.0 + 4.0 * np.exp(-E_eq / 50) + 0.05 * np.clip(25 - c_eq, 0, None)
             + 12 * deficit_front + 0.8 * deficit_mortier) * (25 / profondeur_axe)

centres = np.sort(rng.choice(np.arange(150, N_ANNEAUX - 150), size=12, replace=False))
mesures = []
for centre in centres:
    effet_zone = rng.normal(0, 0.8)
    demi_largeur = rng.integers(12, 35)
    pas = rng.choice([1, 2])
    for k in range(centre - demi_largeur, centre + demi_largeur + 1, pas):
        mesures.append((k, effet_zone))
mesures = pd.DataFrame(mesures, columns=["indice", "effet_zone"]).drop_duplicates("indice")
idx = mesures["indice"].to_numpy()
smax = -(tassement[idx] + mesures["effet_zone"].to_numpy() + rng.normal(0, 0.15, len(idx)))
smax = np.minimum(smax, -0.2)

calage = pd.DataFrame({
    "id_calage_trans": np.arange(1, len(idx) + 1),
    "id_anneau": anneaux["id_anneau"].to_numpy()[idx],
    "smax": smax.round(2),
    "iy": (0.5 * profondeur_axe[idx] + rng.normal(0, 1, len(idx))).round(2),
    "my": rng.normal(0, 1.5, len(idx)).round(2),
})

# --- Écriture -----------------------------------------------------------------------------------
SORTIE.mkdir(parents=True, exist_ok=True)
tables = {
    "anneau.csv": anneaux,
    "secteur.csv": secteurs,
    "formation_geologique.csv": formations,
    "stratigraphie.csv": stratigraphie,
    "stratigraphie_homogenisee.csv": sol,
    "parametre_tunnelier.csv": tunnelier,
    "smax.csv": calage,
}
for nom, table in tables.items():
    table.to_csv(SORTIE / nom, index=False)
    print(f"{nom:32s} {len(table):6d} lignes")
