"""
=============================================================
CALCULATEUR D'OPTIMISATION FISCALE — TUNISIE
Interface Streamlit (rendu UI uniquement)
=============================================================
Ce fichier ne contient que le rendu de l'interface utilisateur.
Toute la logique métier et les formules fiscales se trouvent
dans fiscal_moteur.py.
=============================================================
"""

import sys

if sys.version_info < (3, 11):
    raise RuntimeError("Python 3.11 ou supérieur requis. Version actuelle : " + sys.version)

import pandas as pd
import streamlit as st

from fiscal_moteur import (
    BAREME_IRPP_DEFAUT,
    PARAMETRES_DEFAUT,
    DemandeCalcul,
    ParametresFiscaux,
    ResultatRepartition,
    bareme_vers_dataframe,
    calculer_repartition,
    dataframe_vers_bareme,
)

# =============================================================
# SECTION 1 — CONFIGURATION DE LA PAGE
# =============================================================

st.set_page_config(
    page_title="Calculateur Fiscal Tunisie",
    page_icon="💰",
    layout="wide",
)

st.title("🧮 Calculateur d'Optimisation Fiscale - Tunisie")
st.markdown("---")

# =============================================================
# SECTION 2 — PARAMÈTRES (Sidebar)
# =============================================================

st.sidebar.header("⚙️ Paramètres de Configuration")

# ── CNSS ────────────────────────────────────────────────────
st.sidebar.subheader("📊 CNSS")
smig = st.sidebar.number_input("SMIG mensuel (TND)", value=PARAMETRES_DEFAUT.smig_mensuel, step=10.0, format="%.2f")
st.sidebar.info(f"Plafond CNSS: {smig * 6:.2f} TND")
taux_cnss_pct = st.sidebar.number_input("Taux CNSS salarié (%)", value=round(PARAMETRES_DEFAUT.taux_cnss_salarie * 100, 2), step=0.1, format="%.2f")
cnss_forfaitaire = st.sidebar.number_input(
    "CNSS forfaitaire annuel Partie 2 (TND)", value=PARAMETRES_DEFAUT.cnss_forfaitaire_annuel, step=100.0, format="%.2f"
)
charges_patronales_pct = st.sidebar.number_input(
    "Charges patronales (%)", value=round(PARAMETRES_DEFAUT.charges_patronales * 100, 2), step=0.5, format="%.2f"
)

# ── Assurance Vie ────────────────────────────────────────────
st.sidebar.subheader("🏦 Assurance Vie")
montant_av = st.sidebar.number_input(
    "Montant versé annuel (TND)", value=PARAMETRES_DEFAUT.montant_assurance_vie, step=1000.0, format="%.2f"
)
taux_reduction_av_pct = st.sidebar.number_input(
    "Taux de réduction (%)", value=round(PARAMETRES_DEFAUT.taux_reduction_assurance * 100, 2), step=1.0, format="%.2f"
)
st.sidebar.info(f"Réduction potentielle: {montant_av * taux_reduction_av_pct / 100:.2f} TND")
plafond_reduction_pct = st.sidebar.number_input(
    "Plafond réduction (% de l'IRPP brut)", value=round(PARAMETRES_DEFAUT.plafond_reduction_pct * 100, 2), step=1.0, format="%.2f"
)

# ── TVA ──────────────────────────────────────────────────────
st.sidebar.subheader("💳 TVA")
taux_tva_pct = st.sidebar.number_input("Taux TVA (%)", value=round(PARAMETRES_DEFAUT.taux_tva * 100, 2), step=0.5, format="%.2f")

# ── Barème IRPP ──────────────────────────────────────────────
st.sidebar.subheader("📈 Barème IRPP")
st.sidebar.markdown("**Tranches d'imposition (annuel)**")

if "bareme_df" not in st.session_state:
    st.session_state.bareme_df = bareme_vers_dataframe(BAREME_IRPP_DEFAUT)

st.session_state.bareme_df = st.sidebar.data_editor(
    st.session_state.bareme_df,
    hide_index=True,
    num_rows="dynamic",
    key="bareme_editor",
)

# =============================================================
# SECTION 3 — SAISIE DE L'OBJECTIF
# =============================================================

st.markdown("## 🎯 Objectifs")

col1, col2 = st.columns(2)

with col1:
    net_cible_total = st.number_input(
        "**Net mensuel cible total (TND)**",
        value=10000.0,
        step=100.0,
        format="%.2f",
    )

with col2:
    mode_calcul = st.radio(
        "**Mode de calcul**",
        ["Net fixe Partie 1", "Optimisation automatique"],
        horizontal=True,
    )

net_partie1_fixe = None
if mode_calcul == "Net fixe Partie 1":
    net_partie1_fixe = st.number_input(
        "**Net mensuel fixe Partie 1 (TND)**",
        value=3000.0,
        step=100.0,
        format="%.2f",
    )

# =============================================================
# SECTION 4 — CALCUL ET AFFICHAGE DES RÉSULTATS
# =============================================================

if st.button("🚀 Calculer", type="primary", use_container_width=True):
    with st.spinner("Calcul en cours..."):
        try:
            # Construction des paramètres depuis les valeurs de la sidebar
            parametres = ParametresFiscaux(
                smig_mensuel=smig,
                taux_cnss_salarie=taux_cnss_pct / 100,
                cnss_forfaitaire_annuel=cnss_forfaitaire,
                charges_patronales=charges_patronales_pct / 100,
                montant_assurance_vie=montant_av,
                taux_reduction_assurance=taux_reduction_av_pct / 100,
                plafond_reduction_pct=plafond_reduction_pct / 100,
                taux_tva=taux_tva_pct / 100,
            )
            bareme = dataframe_vers_bareme(st.session_state.bareme_df)
            demande = DemandeCalcul(
                net_cible_total_mensuel=net_cible_total,
                net_partie1_mensuel=net_partie1_fixe,
                parametres=parametres,
                bareme=bareme,
            )
            r: ResultatRepartition = calculer_repartition(demande)
        except Exception as exc:
            st.error(f"Erreur de calcul : {exc}")
            st.stop()

    # ── Métriques principales ────────────────────────────────
    st.markdown("---")
    st.markdown("## 📊 Résultats")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Net Total Mensuel",
            f"{r.net_total_mensuel:.2f} TND",
            delta=f"{r.net_total_mensuel - net_cible_total:.2f} TND",
        )
    with col2:
        st.metric("Coût Total Entreprise", f"{r.cout_total_entreprise_mensuel:.2f} TND")
    with col3:
        st.metric("IRPP Net Total", f"{r.irpp_net_total:.2f} TND/an")
    with col4:
        st.metric("Réduction Assurance Vie", f"{r.reduction_effective:.2f} TND/an")

    st.markdown("---")

    # ── Détail Partie 1 & Partie 2 ───────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💼 Partie 1 — Salaire")
        st.markdown(f"""
**Brut mensuel :** {r.partie1.brut_ou_ca_ht_mensuel:.2f} TND  
**Brut annuel :** {r.partie1.brut_ou_ca_ht_annuel:.2f} TND  
**CNSS ({taux_cnss_pct:.2f}%) :** -{r.partie1.cnss_annuel:.2f} TND/an  
**Revenu imposable :** {r.partie1.revenu_imposable_annuel:.2f} TND/an  
**IRPP net :** -{r.partie1.irpp_net_annuel:.2f} TND/an ({r.partie1.irpp_net_annuel / 12:.2f} TND/mois)  

✅ **Net mensuel :** {r.partie1.net_mensuel:.2f} TND  
💰 **Coût entreprise :** {r.partie1.cout_entreprise_mensuel:.2f} TND/mois
""")

    with col2:
        st.markdown("### 📄 Partie 2 — Facturation")
        st.markdown(f"""
**CA HT mensuel :** {r.partie2.brut_ou_ca_ht_mensuel:.2f} TND  
**CA HT annuel :** {r.partie2.brut_ou_ca_ht_annuel:.2f} TND  
**TVA collectée ({taux_tva_pct:.0f}%) :** {r.tva_annuelle:.2f} TND/an  
**CNSS forfaitaire :** -{r.partie2.cnss_annuel:.2f} TND/an  
**Revenu imposable :** {r.partie2.revenu_imposable_annuel:.2f} TND/an  
**IRPP net :** -{r.partie2.irpp_net_annuel:.2f} TND/an ({r.partie2.irpp_net_annuel / 12:.2f} TND/mois)  

✅ **Net mensuel :** {r.partie2.net_mensuel:.2f} TND  
💰 **Montant à facturer HT :** {r.partie2.brut_ou_ca_ht_mensuel:.2f} TND/mois
""")

    st.markdown("---")

    # ── Détail IRPP ──────────────────────────────────────────
    st.markdown("### 📈 Détail IRPP")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("IRPP Brut Total", f"{r.irpp_brut_total:.2f} TND/an")
    with col2:
        pct_reduction = (
            r.reduction_effective / r.irpp_brut_total * 100
            if r.irpp_brut_total > 0
            else 0
        )
        st.metric(
            "Réduction Appliquée",
            f"{r.reduction_effective:.2f} TND",
            delta=f"{pct_reduction:.1f}% de l'IRPP brut",
        )
    with col3:
        st.metric("IRPP Net à Payer", f"{r.irpp_net_total:.2f} TND/an")

    # Comparaison entre la réduction potentielle (moteur) et la réduction effective.
    # Rappel : la réduction est plafonnée par le CA HT généré — voir fiscal_moteur.py.
    if r.reduction_effective < parametres.reduction_max_assurance:
        st.warning(
            f"⚠️ La réduction est limitée par le plafond de {parametres.plafond_reduction_pct * 100:.0f}% "
            f"de l'IRPP brut ({r.irpp_brut_total * parametres.plafond_reduction_pct:.2f} TND). "
            f"Vous ne bénéficiez que de {r.reduction_effective:.2f} TND "
            f"sur les {parametres.reduction_max_assurance:.2f} TND potentiels."
        )
    else:
        st.success(f"✅ Vous bénéficiez de la réduction maximale de {parametres.reduction_max_assurance:.2f} TND.")

    st.markdown("---")

    # ── Tableau récapitulatif ─────────────────────────────────
    st.markdown("### 📋 Récapitulatif")

    recap = {
        "Catégorie": [
            "Salaire Brut",
            "CNSS Salaire",
            "CA HT Facturé",
            "CNSS Forfaitaire",
            "Revenu Imposable Total",
            "IRPP Brut",
            "Réduction Assurance Vie",
            "IRPP Net",
            "Net Total",
            "Coût Total Entreprise",
        ],
        "Montant Annuel (TND)": [
            f"{r.partie1.brut_ou_ca_ht_annuel:.2f}",
            f"-{r.partie1.cnss_annuel:.2f}",
            f"{r.partie2.brut_ou_ca_ht_annuel:.2f}",
            f"-{r.partie2.cnss_annuel:.2f}",
            f"{r.revenu_imposable_total:.2f}",
            f"{r.irpp_brut_total:.2f}",
            f"-{r.reduction_effective:.2f}",
            f"-{r.irpp_net_total:.2f}",
            f"{r.net_total_annuel:.2f}",
            f"{r.cout_total_entreprise_annuel:.2f}",
        ],
        "Montant Mensuel (TND)": [
            f"{r.partie1.brut_ou_ca_ht_mensuel:.2f}",
            f"-{r.partie1.cnss_annuel / 12:.2f}",
            f"{r.partie2.brut_ou_ca_ht_mensuel:.2f}",
            f"-{r.partie2.cnss_annuel / 12:.2f}",
            f"{r.revenu_imposable_total / 12:.2f}",
            f"{r.irpp_brut_total / 12:.2f}",
            f"-{r.reduction_effective / 12:.2f}",
            f"-{r.irpp_net_total / 12:.2f}",
            f"{r.net_total_mensuel:.2f}",
            f"{r.cout_total_entreprise_mensuel:.2f}",
        ],
    }

    st.dataframe(pd.DataFrame(recap), use_container_width=True, hide_index=True)

# =============================================================
# SECTION 5 — FOOTER
# =============================================================

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:gray;'>"
    "<p>💡 Cet outil est fourni à titre informatif. Consultez un expert-comptable pour validation.</p>"
    "</div>",
    unsafe_allow_html=True,
)
