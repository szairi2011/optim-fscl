import sys

if sys.version_info < (3, 11):
    raise RuntimeError("Python 3.11 or higher is required. Current version: " + sys.version)

import streamlit as st
import numpy as np
from scipy.optimize import fsolve, minimize_scalar
import pandas as pd

# Configuration de la page
st.set_page_config(
    page_title="Calculateur Fiscal Tunisie",
    page_icon="💰",
    layout="wide"
)

st.title("🧮 Calculateur d'Optimisation Fiscale - Tunisie")
st.markdown("---")

# Sidebar pour les paramètres
st.sidebar.header("⚙️ Paramètres de Configuration")

# Section CNSS
st.sidebar.subheader("📊 CNSS")
smig = st.sidebar.number_input("SMIG mensuel (TND)", value=528.32, step=10.0, format="%.2f")
plafond_cnss = smig * 6
st.sidebar.info(f"Plafond CNSS: {plafond_cnss:.2f} TND")
taux_cnss_salarie = st.sidebar.number_input("Taux CNSS salarié (%)", value=9.68, step=0.1, format="%.2f") / 100
cnss_forfaitaire_annuel = st.sidebar.number_input("CNSS forfaitaire annuel Partie 2 (TND)", value=1800.0, step=100.0, format="%.2f")
charges_patronales = st.sidebar.number_input("Charges patronales (%)", value=17.0, step=0.5, format="%.2f") / 100

# Section Assurance Vie
st.sidebar.subheader("🏦 Assurance Vie")
montant_assurance_vie = st.sidebar.number_input("Montant versé annuel (TND)", value=60000.0, step=1000.0, format="%.2f")
taux_reduction_assurance = st.sidebar.number_input("Taux de réduction (%)", value=40.0, step=1.0, format="%.2f") / 100
reduction_max_assurance = montant_assurance_vie * taux_reduction_assurance
st.sidebar.info(f"Réduction potentielle: {reduction_max_assurance:.2f} TND")
plafond_reduction_pct = st.sidebar.number_input("Plafond réduction (% de l'IRPP brut)", value=55.0, step=1.0, format="%.2f") / 100

# Section TVA
st.sidebar.subheader("💳 TVA")
taux_tva = st.sidebar.number_input("Taux TVA (%)", value=19.0, step=0.5, format="%.2f") / 100

# Section Barème IRPP
st.sidebar.subheader("📈 Barème IRPP")
st.sidebar.markdown("**Tranches d'imposition (annuel)**")

# Créer un DataFrame pour le barème IRPP éditable
if 'bareme_irpp' not in st.session_state:
    st.session_state.bareme_irpp = pd.DataFrame({
        'Min (TND)': [0, 5001, 10001, 20001, 30001, 40001, 50001],
        'Max (TND)': [5000, 10000, 20000, 30000, 40000, 50000, np.inf],
        'Taux (%)': [0, 15, 20, 25, 30, 35, 40]
    })

# Afficher le barème dans la sidebar
edited_bareme = st.sidebar.data_editor(
    st.session_state.bareme_irpp,
    hide_index=True,
    num_rows="dynamic",
    key="bareme_editor"
)
st.session_state.bareme_irpp = edited_bareme

# Fonction de calcul IRPP
def calculer_irpp(revenu_imposable_annuel, bareme):
    """Calcule l'IRPP selon le barème progressif"""
    irpp = 0
    revenu_restant = revenu_imposable_annuel
    
    for idx, row in bareme.iterrows():
        min_tranche = row['Min (TND)']
        max_tranche = row['Max (TND)']
        taux = row['Taux (%)'] / 100
        
        if revenu_restant <= 0:
            break
            
        # Calculer la portion dans cette tranche
        if revenu_imposable_annuel > min_tranche:
            montant_tranche = min(revenu_imposable_annuel, max_tranche) - min_tranche
            montant_tranche = max(0, montant_tranche)
            irpp += montant_tranche * taux
    
    return irpp

# Fonction pour calculer le brut nécessaire pour un net cible (Partie 1)
def calculer_brut_pour_net_partie1(net_cible_mensuel, irpp_mensuel_partie1):
    """Calcule le brut mensuel nécessaire pour obtenir un net cible en Partie 1"""
    net_cible_annuel = net_cible_mensuel * 12
    irpp_annuel_partie1 = irpp_mensuel_partie1 * 12
    
    # Net = Brut * (1 - taux_cnss) - IRPP
    # Brut = (Net + IRPP) / (1 - taux_cnss)
    brut_annuel = (net_cible_annuel + irpp_annuel_partie1) / (1 - taux_cnss_salarie)
    return brut_annuel / 12

# Fonction pour calculer la répartition optimale
def calculer_repartition(net_cible_total_mensuel, net_partie1_mensuel=None):
    """
    Calcule la répartition optimale entre Partie 1 et Partie 2
    Si net_partie1_mensuel est None, optimise automatiquement
    """
    net_cible_total_annuel = net_cible_total_mensuel * 12
    
    if net_partie1_mensuel is not None:
        # Net fixe Partie 1
        net_partie1_annuel = net_partie1_mensuel * 12
        net_partie2_annuel = net_cible_total_annuel - net_partie1_annuel
    else:
        # Optimisation automatique - commencer avec salaire au plafond CNSS
        net_partie1_mensuel = plafond_cnss * 0.8  # Estimation initiale
        net_partie1_annuel = net_partie1_mensuel * 12
        net_partie2_annuel = net_cible_total_annuel - net_partie1_annuel
    
    # Résolution itérative
    def equations(vars):
        brut_mensuel_p1, ca_ht_annuel_p2 = vars
        
        # Partie 1
        brut_annuel_p1 = brut_mensuel_p1 * 12
        cnss_annuel_p1 = brut_annuel_p1 * taux_cnss_salarie
        revenu_imposable_p1 = brut_annuel_p1 - cnss_annuel_p1
        
        # Partie 2
        revenu_imposable_p2 = ca_ht_annuel_p2 - cnss_forfaitaire_annuel
        
        # IRPP total
        revenu_imposable_total = revenu_imposable_p1 + revenu_imposable_p2
        irpp_brut_total = calculer_irpp(revenu_imposable_total, st.session_state.bareme_irpp)
        
        # Réduction assurance vie
        reduction_effective = min(reduction_max_assurance, irpp_brut_total * plafond_reduction_pct)
        irpp_net_total = irpp_brut_total - reduction_effective
        
        # Répartition IRPP proportionnelle aux revenus
        if revenu_imposable_total > 0:
            ratio_p1 = revenu_imposable_p1 / revenu_imposable_total
            irpp_net_p1 = irpp_net_total * ratio_p1
            irpp_net_p2 = irpp_net_total * (1 - ratio_p1)
        else:
            irpp_net_p1 = 0
            irpp_net_p2 = 0
        
        # Net réalisé
        net_realise_p1 = revenu_imposable_p1 - irpp_net_p1
        net_realise_p2 = revenu_imposable_p2 - irpp_net_p2
        
        # Équations à résoudre
        eq1 = net_realise_p1 - net_partie1_annuel
        eq2 = net_realise_p2 - net_partie2_annuel
        
        return [eq1, eq2]
    
    # Valeurs initiales
    brut_initial_p1 = net_partie1_mensuel / (1 - taux_cnss_salarie - 0.25)  # Estimation
    ca_initial_p2 = net_partie2_annuel * 1.5  # Estimation
    
    try:
        solution = fsolve(equations, [brut_initial_p1, ca_initial_p2])
        brut_mensuel_p1, ca_ht_annuel_p2 = solution
        
        # Recalculer tous les détails avec la solution
        brut_annuel_p1 = brut_mensuel_p1 * 12
        cnss_annuel_p1 = brut_annuel_p1 * taux_cnss_salarie
        revenu_imposable_p1 = brut_annuel_p1 - cnss_annuel_p1
        
        revenu_imposable_p2 = ca_ht_annuel_p2 - cnss_forfaitaire_annuel
        
        revenu_imposable_total = revenu_imposable_p1 + revenu_imposable_p2
        irpp_brut_total = calculer_irpp(revenu_imposable_total, st.session_state.bareme_irpp)
        
        reduction_effective = min(reduction_max_assurance, irpp_brut_total * plafond_reduction_pct)
        irpp_net_total = irpp_brut_total - reduction_effective
        
        if revenu_imposable_total > 0:
            ratio_p1 = revenu_imposable_p1 / revenu_imposable_total
            irpp_net_p1 = irpp_net_total * ratio_p1
            irpp_net_p2 = irpp_net_total * (1 - ratio_p1)
        else:
            irpp_net_p1 = 0
            irpp_net_p2 = 0
        
        net_realise_p1 = revenu_imposable_p1 - irpp_net_p1
        net_realise_p2 = revenu_imposable_p2 - irpp_net_p2
        net_total_realise = net_realise_p1 + net_realise_p2
        
        # Coûts entreprise
        cout_entreprise_p1 = brut_annuel_p1 * (1 + charges_patronales)
        cout_entreprise_p2 = ca_ht_annuel_p2
        cout_total_entreprise = cout_entreprise_p1 + cout_entreprise_p2
        
        return {
            'brut_mensuel_p1': brut_mensuel_p1,
            'brut_annuel_p1': brut_annuel_p1,
            'cnss_annuel_p1': cnss_annuel_p1,
            'revenu_imposable_p1': revenu_imposable_p1,
            'irpp_net_p1': irpp_net_p1,
            'net_annuel_p1': net_realise_p1,
            'net_mensuel_p1': net_realise_p1 / 12,
            'cout_entreprise_mensuel_p1': cout_entreprise_p1 / 12,
            'ca_ht_annuel_p2': ca_ht_annuel_p2,
            'ca_ht_mensuel_p2': ca_ht_annuel_p2 / 12,
            'cnss_annuel_p2': cnss_forfaitaire_annuel,
            'revenu_imposable_p2': revenu_imposable_p2,
            'irpp_net_p2': irpp_net_p2,
            'net_annuel_p2': net_realise_p2,
            'net_mensuel_p2': net_realise_p2 / 12,
            'cout_entreprise_mensuel_p2': ca_ht_annuel_p2 / 12,
            'revenu_imposable_total': revenu_imposable_total,
            'irpp_brut_total': irpp_brut_total,
            'reduction_effective': reduction_effective,
            'irpp_net_total': irpp_net_total,
            'net_total_annuel': net_total_realise,
            'net_total_mensuel': net_total_realise / 12,
            'cout_total_entreprise_annuel': cout_total_entreprise,
            'cout_total_entreprise_mensuel': cout_total_entreprise / 12
        }
    except Exception as e:
        st.error(f"Erreur de calcul: {e}")
        return None

# Interface principale
st.markdown("## 🎯 Objectifs")

col1, col2 = st.columns(2)

with col1:
    net_cible_total = st.number_input(
        "**Net mensuel cible total (TND)**",
        value=10000.0,
        step=100.0,
        format="%.2f"
    )

with col2:
    mode_calcul = st.radio(
        "**Mode de calcul**",
        ["Net fixe Partie 1", "Optimisation automatique"],
        horizontal=True
    )

if mode_calcul == "Net fixe Partie 1":
    net_partie1_fixe = st.number_input(
        "**Net mensuel fixe Partie 1 (TND)**",
        value=3000.0,
        step=100.0,
        format="%.2f"
    )
else:
    net_partie1_fixe = None

# Bouton de calcul
if st.button("🚀 Calculer", type="primary", use_container_width=True):
    with st.spinner("Calcul en cours..."):
        resultat = calculer_repartition(net_cible_total, net_partie1_fixe)
        
        if resultat:
            st.markdown("---")
            st.markdown("## 📊 Résultats")
            
            # Metrics principales
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Net Total Mensuel",
                    f"{resultat['net_total_mensuel']:.2f} TND",
                    delta=f"{resultat['net_total_mensuel'] - net_cible_total:.2f} TND"
                )
            
            with col2:
                st.metric(
                    "Coût Total Entreprise",
                    f"{resultat['cout_total_entreprise_mensuel']:.2f} TND"
                )
            
            with col3:
                st.metric(
                    "IRPP Net Total",
                    f"{resultat['irpp_net_total']:.2f} TND/an"
                )
            
            with col4:
                st.metric(
                    "Réduction Assurance Vie",
                    f"{resultat['reduction_effective']:.2f} TND/an"
                )
            
            st.markdown("---")
            
            # Détails Partie 1 et Partie 2
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 💼 Partie 1 - Salaire")
                st.markdown(f"""
                **Brut mensuel:** {resultat['brut_mensuel_p1']:.2f} TND  
                **Brut annuel:** {resultat['brut_annuel_p1']:.2f} TND  
                **CNSS (9.68%):** -{resultat['cnss_annuel_p1']:.2f} TND/an  
                **Revenu imposable:** {resultat['revenu_imposable_p1']:.2f} TND/an  
                **IRPP net:** -{resultat['irpp_net_p1']:.2f} TND/an ({resultat['irpp_net_p1']/12:.2f} TND/mois)  
                
                ✅ **Net mensuel:** {resultat['net_mensuel_p1']:.2f} TND  
                💰 **Coût entreprise:** {resultat['cout_entreprise_mensuel_p1']:.2f} TND/mois
                """)
            
            with col2:
                st.markdown("### 📄 Partie 2 - Facturation")
                st.markdown(f"""
                **CA HT mensuel:** {resultat['ca_ht_mensuel_p2']:.2f} TND  
                **CA HT annuel:** {resultat['ca_ht_annuel_p2']:.2f} TND  
                **TVA collectée (19%):** {resultat['ca_ht_annuel_p2'] * taux_tva:.2f} TND/an  
                **CNSS forfaitaire:** -{resultat['cnss_annuel_p2']:.2f} TND/an  
                **Revenu imposable:** {resultat['revenu_imposable_p2']:.2f} TND/an  
                **IRPP net:** -{resultat['irpp_net_p2']:.2f} TND/an ({resultat['irpp_net_p2']/12:.2f} TND/mois)  
                
                ✅ **Net mensuel:** {resultat['net_mensuel_p2']:.2f} TND  
                💰 **Montant à facturer HT:** {resultat['ca_ht_mensuel_p2']:.2f} TND/mois
                """)
            
            st.markdown("---")
            
            # Détail IRPP
            st.markdown("### 📈 Détail IRPP")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("IRPP Brut Total", f"{resultat['irpp_brut_total']:.2f} TND/an")
            
            with col2:
                pct_reduction = (resultat['reduction_effective'] / resultat['irpp_brut_total'] * 100) if resultat['irpp_brut_total'] > 0 else 0
                st.metric(
                    "Réduction Appliquée",
                    f"{resultat['reduction_effective']:.2f} TND",
                    delta=f"{pct_reduction:.1f}% de l'IRPP brut"
                )
            
            with col3:
                st.metric("IRPP Net à Payer", f"{resultat['irpp_net_total']:.2f} TND/an")
            
            # Vérification du plafond 55%
            plafond_55 = resultat['irpp_brut_total'] * plafond_reduction_pct
            if resultat['reduction_effective'] < reduction_max_assurance:
                st.warning(f"⚠️ La réduction est limitée par le plafond de {plafond_reduction_pct*100:.0f}% de l'IRPP brut ({plafond_55:.2f} TND). Vous ne bénéficiez que de {resultat['reduction_effective']:.2f} TND sur les {reduction_max_assurance:.2f} TND potentiels.")
            else:
                st.success(f"✅ Vous bénéficiez de la réduction maximale de {reduction_max_assurance:.2f} TND.")
            
            st.markdown("---")
            
            # Tableau récapitulatif
            st.markdown("### 📋 Récapitulatif Annuel")
            
            recap_data = {
                'Catégorie': [
                    'Salaire Brut', 'CNSS Salaire', 'CA HT Facturé', 'CNSS Forfaitaire',
                    'Revenu Imposable Total', 'IRPP Brut', 'Réduction Assurance Vie',
                    'IRPP Net', 'Net Total', 'Coût Total Entreprise'
                ],
                'Montant Annuel (TND)': [
                    f"{resultat['brut_annuel_p1']:.2f}",
                    f"-{resultat['cnss_annuel_p1']:.2f}",
                    f"{resultat['ca_ht_annuel_p2']:.2f}",
                    f"-{resultat['cnss_annuel_p2']:.2f}",
                    f"{resultat['revenu_imposable_total']:.2f}",
                    f"{resultat['irpp_brut_total']:.2f}",
                    f"-{resultat['reduction_effective']:.2f}",
                    f"-{resultat['irpp_net_total']:.2f}",
                    f"{resultat['net_total_annuel']:.2f}",
                    f"{resultat['cout_total_entreprise_annuel']:.2f}"
                ],
                'Montant Mensuel (TND)': [
                    f"{resultat['brut_mensuel_p1']:.2f}",
                    f"-{resultat['cnss_annuel_p1']/12:.2f}",
                    f"{resultat['ca_ht_mensuel_p2']:.2f}",
                    f"-{resultat['cnss_annuel_p2']/12:.2f}",
                    f"{resultat['revenu_imposable_total']/12:.2f}",
                    f"{resultat['irpp_brut_total']/12:.2f}",
                    f"-{resultat['reduction_effective']/12:.2f}",
                    f"-{resultat['irpp_net_total']/12:.2f}",
                    f"{resultat['net_total_mensuel']:.2f}",
                    f"{resultat['cout_total_entreprise_mensuel']:.2f}"
                ]
            }
            
            st.dataframe(pd.DataFrame(recap_data), use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>💡 Cet outil est fourni à titre informatif. Consultez un expert-comptable pour validation.</p>
</div>
""", unsafe_allow_html=True)
