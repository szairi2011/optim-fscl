# 🧮 Calculateur d'Optimisation Fiscale - Tunisie

Application Streamlit pour calculer la répartition optimale entre salaire et facturation en Tunisie.

## 📋 Fonctionnalités

- **Calcul inverse automatique** : Partez du net cible et obtenez le brut nécessaire
- **Deux modes** : Net fixe Partie 1 ou optimisation automatique
- **Tous les paramètres configurables** : CNSS, barème IRPP, assurance vie, TVA
- **Respect de la règle fiscale** : Plafond de 55% sur la réduction d'impôt assurance vie
- **Interface intuitive** en français

## 🚀 Installation

### Prérequis
- Python 3.8 ou supérieur
- [uv](https://docs.astral.sh/uv/) (gestionnaire de dépendances)

### Étapes

1. **Créer et activer l'environnement virtuel `alical`** :
```bash
uv venv alical
alical\Scripts\activate   # Windows
# ou
source alical/bin/activate  # Linux / macOS
```

2. **Installer les dépendances** :
```bash
uv pip install -r requirements.txt
```

3. **Lancer l'application** (sans activation manuelle) :
```bash
uv run streamlit run calculateur_fiscal_tunisie.py
```

> Alternatively, activate the venv first then run streamlit directly:
> ```bash
> alical\Scripts\activate   # Windows
> source alical/bin/activate  # Linux / macOS
> streamlit run calculateur_fiscal_tunisie.py
> ```

4. L'application s'ouvrira automatiquement dans votre navigateur à l'adresse `http://localhost:8501`

## 📖 Mode d'emploi

### Configuration des paramètres (Sidebar)

1. **CNSS** :
   - SMIG mensuel (défaut: 528.32 TND)
   - Taux CNSS salarié (défaut: 9.68%)
   - CNSS forfaitaire Partie 2 (défaut: 1,800 TND/an)

2. **Charges patronales** : 17% (modifiable)

3. **Assurance vie** :
   - Montant versé annuel (défaut: 60,000 TND)
   - Taux de réduction (défaut: 40%)
   - Plafond réduction (défaut: 55% de l'IRPP brut)

4. **TVA** : 19% (modifiable)

5. **Barème IRPP** : Tableau éditable avec les tranches d'imposition

### Calcul

1. **Choisir le mode** :
   - **Net fixe Partie 1** : Vous fixez le net mensuel du salaire, l'outil calcule le reste
   - **Optimisation automatique** : L'outil trouve la meilleure répartition

2. **Entrer l'objectif** :
   - Net mensuel cible total (ex: 10,000 TND)
   - Si mode "Net fixe", entrer le net mensuel Partie 1 (ex: 3,000 TND)

3. **Cliquer sur "Calculer"**

### Résultats affichés

- **Métriques principales** : Net total, Coût entreprise, IRPP, Réduction
- **Détail Partie 1** : Salaire brut, CNSS, IRPP, Net, Coût entreprise
- **Détail Partie 2** : CA HT à facturer, TVA, CNSS, IRPP, Net
- **Détail IRPP** : IRPP brut, Réduction appliquée, IRPP net
- **Tableau récapitulatif** : Vue d'ensemble annuelle et mensuelle

## 🔍 Exemple d'utilisation

**Objectif** : Obtenir 10,000 TND net/mois avec un salaire fixe de 3,000 TND net/mois

**Résultats** :
- Salaire brut nécessaire : ~4,550 TND/mois
- CA HT à facturer : ~9,450 TND/mois
- IRPP total : Calculé automatiquement avec réduction assurance vie
- Coût total entreprise : ~14,400 TND/mois

## ⚠️ Notes importantes

1. **Règle des 55%** : La réduction d'impôt pour assurance vie est plafonnée à 55% de l'IRPP brut total
2. **CNSS plafonnée** : La CNSS sur salaire est calculée sur maximum 6× SMIG
3. **Barème IRPP progressif** : L'impôt est calculé par tranches
4. **Calcul simultané** : L'IRPP total prend en compte les deux parties (salaire + facturation)

## 🛠️ Personnalisation

Vous pouvez modifier directement dans la sidebar :
- Le barème IRPP (ajouter/supprimer des tranches)
- Tous les taux (CNSS, charges patronales, TVA)
- Les montants d'assurance vie

## 📞 Support

Pour toute question ou amélioration, n'hésitez pas à me contacter.

---

💡 **Disclaimer** : Cet outil est fourni à titre informatif uniquement. Consultez toujours un expert-comptable agréé pour valider vos calculs fiscaux.
