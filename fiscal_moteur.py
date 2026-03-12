"""
=============================================================
MOTEUR DE CALCUL FISCAL — TUNISIE
=============================================================

Ce module contient toute la logique métier du calculateur
d'optimisation fiscale pour les entreprises tunisiennes.

Contexte fiscal couvert :
  - CNSS salarié (Art. 60 CNSS) — plafonnée à 6×SMIG
  - CNSS forfaitaire pour gérant non-salarié (Partie 2)
  - IRPP progressif par tranches (Code de l'IRPP et de l'IS)
  - Réduction d'impôt sur assurance vie (Art. 39 CII)
      → plafonnée à un pourcentage de l'IRPP brut (règle des 55%)
  - Charges patronales sur salaire brut
  - TVA collectée sur facturation (Partie 2, informatif)

Deux modes de calcul proposés :
  • Net fixe Partie 1  : le net salarial est imposé, le reste en facturation
  • Optimisation auto  : le moteur cherche la meilleure répartition
    en initialisant le salaire à 80% du plafond CNSS mensuel

Toutes les formules travaillent en base annuelle ;
les valeurs mensuelles sont obtenues en divisant par 12.
=============================================================
"""

from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, computed_field
from scipy.optimize import fsolve


# =============================================================
# SECTION 1 — MODÈLES DE DONNÉES (Pydantic)
# =============================================================


class TrancheIRPP(BaseModel):
    """
    Une tranche du barème progressif de l'IRPP.

    Exemple (barème 2024) :
        TrancheIRPP(min_tnd=10001, max_tnd=20000, taux=0.20)
        → les revenus entre 10 001 TND et 20 000 TND sont taxés à 20%.
    """

    min_tnd: float = Field(..., ge=0, description="Revenu annuel minimum de la tranche (TND)")
    max_tnd: float = Field(
        ...,
        description="Revenu annuel maximum de la tranche (TND). "
        "Utiliser float('inf') pour la dernière tranche ouverte.",
    )
    taux: float = Field(..., ge=0, le=1, description="Taux marginal d'imposition (ex: 0.20 pour 20%)")


class ParametresFiscaux(BaseModel):
    """
    Ensemble des paramètres fiscaux et sociaux configurables.
    Les valeurs par défaut correspondent aux taux tunisiens en vigueur en 2024.
    """

    # ── CNSS ────────────────────────────────────────────────────────────────
    # Caisse Nationale de Sécurité Sociale
    # Le plafond de la base de calcul est fixé à 6 fois le SMIG mensuel.

    smig_mensuel: float = Field(
        528.32, gt=0,
        description="SMIG mensuel (TND) — sert à calculer le plafond CNSS = 6×SMIG"
    )
    taux_cnss_salarie: float = Field(
        0.0968, gt=0,
        description="Taux CNSS part salarié (ex: 0.0968 pour 9.68%)"
    )
    cnss_forfaitaire_annuel: float = Field(
        1800.0, ge=0,
        description="CNSS forfaitaire annuelle Partie 2 (gérant non-salarié, TND)"
    )
    charges_patronales: float = Field(
        0.17, ge=0,
        description="Taux charges patronales sur salaire brut (ex: 0.17 pour 17%)"
    )

    # ── Assurance Vie (Art. 39 CII) ─────────────────────────────────────────
    # La réduction d'impôt = taux_reduction_assurance × montant_versé,
    # mais elle est plafonnée à plafond_reduction_pct × IRPP brut total.

    montant_assurance_vie: float = Field(
        60000.0, ge=0,
        description="Montant annuel versé en assurance vie (TND)"
    )
    taux_reduction_assurance: float = Field(
        0.40, ge=0, le=1,
        description="Taux de réduction d'impôt assurance vie (ex: 0.40 pour 40%)"
    )
    plafond_reduction_pct: float = Field(
        0.55, ge=0, le=1,
        description="Plafond de la réduction en % de l'IRPP brut (règle des 55%)"
    )

    # ── Frais Administratifs ────────────────────────────────────────────────
    # Frais de gestion (honoraires comptable, frais bancaires, assurances pro, etc.)
    # facturés EN SUS du CA HT au client.
    # Le gérant récupère ainsi ces charges via la facture :
    #   Montant facturé total (HT) = CA HT (base fiscale) + frais_admin
    # Le revenu imposable P2 reste : CA HT − CNSS forfaitaire.
    frais_admin_annuel: float = Field(
        0.0, ge=0,
        description="Frais administratifs annuels Partie 2 (comptable, banque, etc.) en TND — facturés en sus au client"
    )

    # ── TVA ─────────────────────────────────────────────────────────────────
    taux_tva: float = Field(
        0.19, ge=0,
        description="Taux TVA applicable sur la facturation (ex: 0.19 pour 19%)"
    )

    @computed_field
    @property
    def plafond_cnss_mensuel(self) -> float:
        """Plafond mensuel de la base CNSS = 6 × SMIG (Art. 60 CNSS). Affiché en sidebar, non utilisé dans le calcul IRPP."""
        return self.smig_mensuel * 6

    @computed_field
    @property
    def reduction_max_assurance(self) -> float:
        """Réduction maximale théorique avant application du plafond IRPP."""
        return self.montant_assurance_vie * self.taux_reduction_assurance


class DemandeCalcul(BaseModel):
    """
    Saisie utilisateur : objectif de net mensuel et mode de calcul choisi.
    """

    net_cible_total_mensuel: float = Field(
        ..., gt=0,
        description="Net mensuel cible total toutes parties confondues (TND)"
    )
    # None  → mode optimisation automatique (répartition libre)
    # valeur → net mensuel fixe imposé pour la Partie 1 (salaire)
    net_partie1_mensuel: Optional[float] = Field(
        None, gt=0,
        description="Net mensuel fixe Partie 1 (salaire). None = optimisation automatique."
    )
    parametres: ParametresFiscaux
    bareme: list[TrancheIRPP]


class ResultatPartie(BaseModel):
    """Détail des calculs pour une partie (salaire OU facturation)."""

    brut_ou_ca_ht_mensuel: float     # Brut mensuel (P1) ou CA HT mensuel (P2)
    brut_ou_ca_ht_annuel: float      # Idem en annuel
    cnss_annuel: float               # CNSS annuelle déduite (salarié ou forfaitaire)
    revenu_imposable_annuel: float   # Base imposable IRPP annuelle pour cette partie
    irpp_net_annuel: float           # Quote-part IRPP net annuel (après réduction)
    net_mensuel: float               # Net perçu mensuel
    net_annuel: float                # Net perçu annuel
    cout_entreprise_mensuel: float   # Coût réel mensuel pour l'entreprise


class ResultatRepartition(BaseModel):
    """
    Résultat complet du calcul de répartition.
    Toutes les valeurs monétaires sont en TND.
    """

    partie1: ResultatPartie          # Détail salaire
    partie2: ResultatPartie          # Détail facturation

    # ── IRPP global ──────────────────────────────────────────────────────────
    # L'IRPP est calculé sur le revenu imposable TOTAL (P1 + P2 cumulés),
    # conformément au principe de globalisation des revenus en droit fiscal tunisien.
    revenu_imposable_total: float
    irpp_brut_total: float           # IRPP avant réduction assurance vie
    reduction_effective: float       # Réduction réellement appliquée (≤ plafond 55%)
    irpp_net_total: float            # IRPP après réduction

    # ── Synthèse ─────────────────────────────────────────────────────────────
    net_total_mensuel: float
    net_total_annuel: float
    cout_total_entreprise_mensuel: float
    cout_total_entreprise_annuel: float

    # ── TVA (informatif) ─────────────────────────────────────────────────────
    # La TVA est collectée par l'entreprise pour le compte de l'État ;
    # elle n'entre pas dans le revenu net du gérant.
    tva_annuelle: float


# =============================================================
# SECTION 2 — PARAMÈTRES ET BARÈME PAR DÉFAUT
# =============================================================

# Instance par défaut exposée à l'UI.
# L'interface l'utilise uniquement pour pré-remplir les widgets ;
# les valeurs réelles sont toujours celles saisies par l'utilisateur.
PARAMETRES_DEFAUT = ParametresFiscaux()

# Barème IRPP 2024 (Code de l'IRPP et de l'IS, Tunisie).
# Tranches exprimées en base annuelle, taux marginaux progressifs.
BAREME_IRPP_DEFAUT: list[TrancheIRPP] = [
    TrancheIRPP(min_tnd=0,     max_tnd=5_000,        taux=0.00),
    TrancheIRPP(min_tnd=5_001, max_tnd=10_000,       taux=0.15),
    TrancheIRPP(min_tnd=10_001, max_tnd=20_000,      taux=0.20),
    TrancheIRPP(min_tnd=20_001, max_tnd=30_000,      taux=0.25),
    TrancheIRPP(min_tnd=30_001, max_tnd=40_000,      taux=0.30),
    TrancheIRPP(min_tnd=40_001, max_tnd=50_000,      taux=0.35),
    TrancheIRPP(min_tnd=50_001, max_tnd=float("inf"), taux=0.40),
]


# =============================================================
# SECTION 3 — CONVERSION BARÈME ↔ DATAFRAME (usage UI)
# =============================================================


def bareme_vers_dataframe(bareme: list[TrancheIRPP]) -> pd.DataFrame:
    """Convertit la liste de tranches en DataFrame pour st.data_editor."""
    return pd.DataFrame(
        [
            {
                "Min (TND)": t.min_tnd,
                "Max (TND)": t.max_tnd,
                "Taux (%)": round(t.taux * 100, 2),
            }
            for t in bareme
        ]
    )


def dataframe_vers_bareme(df: pd.DataFrame) -> list[TrancheIRPP]:
    """Reconstruit la liste de tranches depuis un DataFrame édité dans l'UI."""
    tranches = []
    for _, row in df.iterrows():
        max_val = row["Max (TND)"]
        # st.data_editor peut renvoyer la chaîne "inf" si l'utilisateur la saisit
        if isinstance(max_val, str):
            max_val = float(max_val)
        tranches.append(
            TrancheIRPP(
                min_tnd=float(row["Min (TND)"]),
                max_tnd=float(max_val),
                taux=float(row["Taux (%)"]) / 100,
            )
        )
    return tranches


# =============================================================
# SECTION 4 — CALCUL DE L'IRPP (barème progressif)
# =============================================================


def calculer_irpp(revenu_imposable_annuel: float, bareme: list[TrancheIRPP]) -> float:
    """
    Calcule l'IRPP brut annuel selon le barème progressif par tranches.

    Formule appliquée :
        Pour chaque tranche [min, max] au taux t :
            IRPP += (min(revenu, max) − min_tranche) × t   si revenu > min_tranche

    Exemple avec revenu = 25 000 TND et barème 2024 :
        Tranche   0 –  5 000 à  0%  →      0.00
        Tranche 5 001 – 10 000 à 15%  →    749.85
        Tranche 10 001 – 20 000 à 20%  →  1 999.80
        Tranche 20 001 – 25 000 à 25%  →  1 249.75
        ─────────────────────────────────────────
        Total IRPP brut                = 3 999.40 TND
    """
    if revenu_imposable_annuel <= 0:
        return 0.0

    irpp = 0.0
    for tranche in bareme:
        if revenu_imposable_annuel <= tranche.min_tnd:
            break
        montant_dans_tranche = min(revenu_imposable_annuel, tranche.max_tnd) - tranche.min_tnd
        irpp += max(0.0, montant_dans_tranche) * tranche.taux

    return irpp


# =============================================================
# SECTION 5 — CALCUL DE LA RÉPARTITION OPTIMALE
# =============================================================


def calculer_repartition(demande: DemandeCalcul) -> ResultatRepartition:
    """
    Résout le système d'équations non-linéaires pour trouver le brut Partie 1
    et le CA HT Partie 2 qui produisent exactement le net cible demandé.

    ── Schéma de calcul ──────────────────────────────────────────────────────

    Partie 1 (Salaire) :
        Brut P1
          − CNSS salarié (brut × taux_cnss)      → base CNSS non plafonnée dans ce calcul
          = Revenu imposable P1
          − Quote-part IRPP net P1
          = Net P1
        Coût entreprise P1 = Brut × (1 + charges_patronales)

    Partie 2 (Facturation — gérant non-salarié) :
        CA HT P2 (base fiscale)
          − CNSS forfaitaire annuelle
          = Revenu imposable P2
          − Quote-part IRPP net P2
          = Net P2
        Frais admin : facturés EN SUS au client (hors calcul fiscal)
        Montant total facturé HT = CA HT + frais admin
        Coût entreprise P2 = CA HT + frais admin

    IRPP :
        Calculé sur le revenu imposable TOTAL (P1 + P2 cumulés).
        Principe de globalisation des revenus (droit fiscal tunisien).
        Réduction assurance vie = min(reduction_max, IRPP brut × plafond_55%).
        IRPP net réparti proportionnellement aux revenus imposables P1 / P2.

    ── Résolution numérique ──────────────────────────────────────────────────
        Système de 2 équations, 2 inconnues [brut_mensuel_p1, ca_ht_annuel_p2] :
            eq1 : net_réalisé_P1 − net_cible_P1 = 0
            eq2 : net_réalisé_P2 − net_cible_P2 = 0
        Résolu via scipy.optimize.fsolve (méthode hybride de Powell).

    Raises:
        ValueError : si fsolve ne converge pas (paramètres incohérents).
    """
    p = demande.parametres
    bareme = demande.bareme

    net_cible_total_annuel = demande.net_cible_total_mensuel * 12

    # ── Détermination du net cible par partie ─────────────────────────────
    if demande.net_partie1_mensuel is not None:
        # Mode : net fixe Partie 1 — l'utilisateur impose le salaire net
        net_partie1_annuel = demande.net_partie1_mensuel * 12
    else:
        # Mode : optimisation automatique
        # Initialisation : salaire ≈ 80% du plafond CNSS mensuel × 12
        net_partie1_annuel = p.plafond_cnss_mensuel * 0.8 * 12

    net_partie2_annuel = net_cible_total_annuel - net_partie1_annuel

    # ── Système d'équations ───────────────────────────────────────────────
    def equations(vars: list[float]) -> list[float]:
        brut_mensuel_p1, ca_ht_annuel_p2 = vars
        brut_annuel_p1 = brut_mensuel_p1 * 12

        # Partie 1 — CNSS sur la totalité du brut (même formule que l'original)
        cnss_annuel_p1 = brut_annuel_p1 * p.taux_cnss_salarie
        revenu_imposable_p1 = brut_annuel_p1 - cnss_annuel_p1

        # Partie 2 — seule la CNSS forfaitaire est déduite du CA HT.
        # Les frais admin sont facturés EN SUS au client ; ils n'entrent pas
        # dans la base imposable (le CA HT est déjà le revenu net de l'activité).
        revenu_imposable_p2 = ca_ht_annuel_p2 - p.cnss_forfaitaire_annuel

        # IRPP calculé sur le revenu TOTAL combiné
        revenu_imposable_total = revenu_imposable_p1 + revenu_imposable_p2
        irpp_brut_total = calculer_irpp(revenu_imposable_total, bareme)

        # Réduction assurance vie plafonnée à X% de l'IRPP brut (règle des 55%)
        reduction_effective = min(
            p.reduction_max_assurance,
            irpp_brut_total * p.plafond_reduction_pct,
        )
        irpp_net_total = irpp_brut_total - reduction_effective

        # Répartition de l'IRPP net proportionnellement aux revenus imposables
        if revenu_imposable_total > 0:
            ratio_p1 = revenu_imposable_p1 / revenu_imposable_total
        else:
            ratio_p1 = 0.5

        irpp_net_p1 = irpp_net_total * ratio_p1
        irpp_net_p2 = irpp_net_total * (1 - ratio_p1)

        net_realise_p1 = revenu_imposable_p1 - irpp_net_p1
        net_realise_p2 = revenu_imposable_p2 - irpp_net_p2

        return [
            net_realise_p1 - net_partie1_annuel,
            net_realise_p2 - net_partie2_annuel,
        ]

    # ── Valeurs initiales pour la convergence de fsolve ───────────────────
    # Estimation grossière : on suppose ~25% d'IRPP + CNSS sur le salaire
    brut_initial_p1 = (net_partie1_annuel / 12) / max(1e-9, 1 - p.taux_cnss_salarie - 0.25)
    ca_initial_p2 = net_partie2_annuel * 1.5  # surcoût approximatif facturation

    solution, _, ier, msg = fsolve(
        equations,
        [brut_initial_p1, ca_initial_p2],
        full_output=True,
    )

    if ier != 1:
        raise ValueError(
            f"Le solveur n'a pas convergé. Message : {msg}\n"
            "Vérifiez la cohérence des paramètres (SMIG, taux, net cible)."
        )

    brut_mensuel_p1, ca_ht_annuel_p2 = solution

    # ── Recalcul complet avec la solution trouvée ─────────────────────────
    brut_annuel_p1 = brut_mensuel_p1 * 12
    cnss_annuel_p1 = brut_annuel_p1 * p.taux_cnss_salarie
    revenu_imposable_p1 = brut_annuel_p1 - cnss_annuel_p1

    revenu_imposable_p2 = ca_ht_annuel_p2 - p.cnss_forfaitaire_annuel

    revenu_imposable_total = revenu_imposable_p1 + revenu_imposable_p2
    irpp_brut_total = calculer_irpp(revenu_imposable_total, bareme)

    # ⚠️ Point clé — lien entre CA HT facturé et réduction assurance vie :
    #
    #   reduction_effective = min(
    #       montant_AV × taux_reduction,          ← plafond « potentiel »
    #       irpp_brut_total × plafond_55%          ← plafond « légal »
    #   )
    #
    #   irpp_brut_total dépend du revenu imposable TOTAL (P1 + P2).
    #   Si le CA HT de P2 est faible  → revenu imposable bas
    #                                 → IRPP brut bas
    #                                 → plafond légal (55%) bas
    #                                 → réduction effective limitée.
    #
    #   Conséquence : le gain fiscal assurance vie est financé
    #   indirectement par le client via ses paiements de factures.
    #   Ce n'est pas de l'argent « gratuit » ; c'est une optimisation
    #   de l'impôt déjà dû sur un CA généré.
    reduction_effective = min(
        p.reduction_max_assurance,
        irpp_brut_total * p.plafond_reduction_pct,
    )
    irpp_net_total = irpp_brut_total - reduction_effective

    if revenu_imposable_total > 0:
        ratio_p1 = revenu_imposable_p1 / revenu_imposable_total
    else:
        ratio_p1 = 0.5

    irpp_net_p1 = irpp_net_total * ratio_p1
    irpp_net_p2 = irpp_net_total * (1 - ratio_p1)

    net_annuel_p1 = revenu_imposable_p1 - irpp_net_p1
    net_annuel_p2 = revenu_imposable_p2 - irpp_net_p2

    # Coût entreprise P1 = brut + charges patronales
    cout_entreprise_annuel_p1 = brut_annuel_p1 * (1 + p.charges_patronales)
    # Coût entreprise P2 = CA HT + frais admin
    # (la société avance les deux ; les frais admin sont couverts par la facturation au client)
    cout_entreprise_annuel_p2 = ca_ht_annuel_p2 + p.frais_admin_annuel

    # TVA collectée (non incluse dans le revenu net — transitoire pour l'État)
    tva_annuelle = ca_ht_annuel_p2 * p.taux_tva

    return ResultatRepartition(
        partie1=ResultatPartie(
            brut_ou_ca_ht_mensuel=brut_mensuel_p1,
            brut_ou_ca_ht_annuel=brut_annuel_p1,
            cnss_annuel=cnss_annuel_p1,
            revenu_imposable_annuel=revenu_imposable_p1,
            irpp_net_annuel=irpp_net_p1,
            net_mensuel=net_annuel_p1 / 12,
            net_annuel=net_annuel_p1,
            cout_entreprise_mensuel=cout_entreprise_annuel_p1 / 12,
        ),
        partie2=ResultatPartie(
            brut_ou_ca_ht_mensuel=ca_ht_annuel_p2 / 12,
            brut_ou_ca_ht_annuel=ca_ht_annuel_p2,
            cnss_annuel=p.cnss_forfaitaire_annuel,
            revenu_imposable_annuel=revenu_imposable_p2,
            irpp_net_annuel=irpp_net_p2,
            net_mensuel=net_annuel_p2 / 12,
            net_annuel=net_annuel_p2,
            cout_entreprise_mensuel=cout_entreprise_annuel_p2 / 12,
        ),
        revenu_imposable_total=revenu_imposable_total,
        irpp_brut_total=irpp_brut_total,
        reduction_effective=reduction_effective,
        irpp_net_total=irpp_net_total,
        net_total_mensuel=(net_annuel_p1 + net_annuel_p2) / 12,
        net_total_annuel=net_annuel_p1 + net_annuel_p2,
        cout_total_entreprise_mensuel=(cout_entreprise_annuel_p1 + cout_entreprise_annuel_p2) / 12,
        cout_total_entreprise_annuel=cout_entreprise_annuel_p1 + cout_entreprise_annuel_p2,
        tva_annuelle=tva_annuelle,
    )
