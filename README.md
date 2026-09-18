# ⚡ Oneshot — Agent Intelligent de Candidatures en 1 Clic & Veille d'Emploi

**Oneshot** (ex-ADHJob) est une application web et un agent autonome conçu pour surveiller les offres d'emploi en temps réel sur les plateformes majeures (**France Travail**, **LinkedIn**, **Indeed**, etc.), analyser l'adéquation avec votre profil via IA, et postuler de manière automatisée et humaine en **1 Clic** ou en **Batch Apply ciblé par plateforme**.

---

## ✨ Fonctionnalités Principales

- 🎮 **Interface Épurée & Mode Zen** : Dashboard anti-distraction, onglets de plateformes colorés, tableau des candidatures à la demande et contrôle total.
- 🌐 **Multi-Plateformes** : Support complet pour France Travail, LinkedIn, Indeed, avec catalogue extensible (WTTJ, Apec, HelloWork, Glassdoor, etc.).
- 🧠 **Analyse & Scoring IA de Profil** : Détection des compétences et calcul en temps réel du taux d'affinité (*Match Score*) à partir de votre CV ou URL LinkedIn/Portfolio.
- ⚡ **Postuler en 1 Clic & Batch Apply par Plateforme** :
  - Mode Playwright simulant un comportement humain (délais naturels, scrolls progressifs, gestion des formulaires).
  - Possibilité de postuler à toutes les offres d'une plateforme spécifique en une seule commande ou à l'ensemble du catalogue.
- 📋 **Suivi des Candidatures Faites** : Onglet et bouton dédié `✨ Postulées` pour consulter l'historique complet des candidatures envoyées et leurs détails.
- 🔒 **Sécurité Locale** : Vos sessions de navigateur et cookies restent 100% stockés localement sur votre machine.

---

## 🚀 Installation & Démarrage Rapide

### 1. Cloner le dépôt
```bash
git clone https://github.com/eliothantute/Oneshot.git
cd Oneshot
```

### 2. Créer et activer l'environnement virtuel Python
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances & les navigateurs Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Lancer l'application web
```bash
./venv/bin/uvicorn ui.web.app:app --reload --port 8000
```
Puis ouvrez votre navigateur sur : **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🛠️ Pour Contribuer / Guide Développeur Fullstack

> 📖 **Guide complet pour les développeurs** : Consultez le document détaillé **[DEV_GUIDE.md](DEV_GUIDE.md)** qui explique toute l'architecture interne (FastAPI, Playwright Stealth, modèle SQLite, intégration LLM Gemini/OpenAI, flux Batch et ajout de nouvelles plateformes).

Pour ajouter de nouvelles fonctionnalités proprement :

1. **Créer une branche de travail** :
   ```bash
   git checkout -b feature/ma-nouvelle-fonctionnalite
   ```
2. **Faire vos modifications et commiter** :
   ```bash
   git add .
   git commit -m "feat: description de la nouvelle fonctionnalité"
   ```
3. **Pousser la branche et ouvrir une Pull Request** :
   ```bash
   git push -u origin feature/ma-nouvelle-fonctionnalite
   ```

---

## 📁 Structure du Projet

```
Oneshot/
├── config/             # Paramètres, profil utilisateur et critères de recherche
├── core/
│   ├── browser/        # Gestionnaire de sessions Playwright & actions humaines
│   ├── llm/            # Évaluation d'adéquation et analyseur de profil IA
│   ├── notifications/  # Alertes Telegram, Discord & In-App
│   ├── storage/        # Gestion de la base de données SQLite
│   └── watcher/        # Scanner temps réel et surveillance d'offres
├── platforms/          # Connecteurs de candidature (France Travail, LinkedIn, Indeed)
├── ui/web/             # Serveur FastAPI, templates HTML, CSS et JavaScript
├── requirements.txt    # Dépendances Python
└── README.md           # Documentation du projet
```
