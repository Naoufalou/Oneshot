# 📘 Guide Technique & Onboarding Développeur Fullstack — Oneshot

Bienvenue dans l'équipe de développement de **Oneshot** (ex-ADHJob) !  
Ce document a été rédigé pour te permettre de comprendre l'architecture du projet, la stack technique, les flux métiers clés et de devenir autonome immédiatement pour corriger des bugs ou développer de nouvelles fonctionnalités.

---

## 🎯 1. Vision & Objectif du Projet

**Oneshot** est un agent intelligent autonome et une application web conçue pour :
1. **Surveiller en temps réel** les offres d'emploi sur les plateformes majeures (**LinkedIn**, **Indeed**, **France Travail**, et plateformes personnalisées/externes).
2. **Analyser & Scorer par IA** (Google Gemini ou OpenAI) l'adéquation entre le profil du candidat (`config/profile.yaml` / CV PDF) et chaque fiche de poste (calcul du *Match Score* sur 100 et explication détaillée du raisonnement).
3. **Postuler automatiquement en 1 Clic ou en Batch Multi-Plateformes** via Playwright en simulant un comportement humain indétectable (frappes gaussiennes, courbes de Bézier, pauses naturelles, gestion des formulaires et upload du bon CV).
4. **Offrir un Cockpit Zen & Gamifié** permettant de piloter toute sa recherche d'emploi sans stress, avec un suivi précis de chaque candidature.

---

## 💻 2. Stack Technique Globale

| Domaine | Technologies & Outils | Rôle |
|---|---|---|
| **Backend API** | **Python 3.10+**, **FastAPI**, **Uvicorn** | API REST asynchrone, gestion des BackgroundTasks, workers de plateformes |
| **Validation & Modèles** | **Pydantic v2**, **Pydantic-Settings**, **PyYAML** | Schémas de données, validation des payloads et parsing des configs |
| **Persistance** | **SQLite 3** (Mode WAL) | Stockage local léger, rapide et fiable des offres et candidatures |
| **Automatisation Web** | **Playwright (Chromium)**, `playwright-stealth` | Pilotage du navigateur, contournement anti-bot, soumission de formulaires |
| **Moteur Comportemental** | `HumanActions` (moteur interne maison) | Mouvements de souris réalistes (Bézier), délais aléatoires, frappe humaine |
| **Intelligence Artificielle** | **Google GenAI (Gemini 1.5 Flash/Pro)**, OpenAI API, Ollama | Analyse de profil, extraction de compétences, scoring, complétion des formulaires |
| **Traitement Documents** | `pypdf`, `reportlab` | Lecture des CVs PDF, extraction de texte, génération de lettres et CVs adaptés |
| **Frontend** | **Vanilla HTML5 / CSS3 / ES6+**, Jinja2 | Interface fluide, réactive, sans lourdeur de bundler externe |
| **UI Dynamique (TypeScript)** | **TypeScript**, **React 18** & Babel (composants isolés) | Animations visuelles, scènes 3D de particules pendant les batchs |
| **Notifications** | Telegram Bot API, Discord Webhooks | Alertes push instantanées pour les offres à haut score |

---

## 📂 3. Arborescence & Rôle des Répertoires

```text
Oneshot/
├── config/                      # Gestion de la configuration et des profils
│   ├── settings.py              # Configuration Pydantic (chemins, flags, env vars)
│   ├── profile.yaml             # Données du candidat (expériences, compétences, Q/R)
│   └── search_criteria.yaml     # Mots-clés, localisations, quotas, filtres
│
├── core/                        # Cœur métier et logique réutilisable
│   ├── browser/                 # Moteur d'automatisation Playwright
│   │   ├── browser_manager.py   # Gestionnaire de cycle de vie des navigateurs et sessions
│   │   ├── human_actions.py     # Simulation de frappes et mouvements de souris humains
│   │   ├── session_setup.py     # Configuration et persistance des sessions (cookies, localStorage)
│   │   ├── ats_detector.py      # Détection des ATS tiers (Workday, Greenhouse, Lever, Taleo...)
│   │   ├── ats_strategies.py    # Stratégies de remplissage dédiées par ATS
│   │   └── external_form_filler.py # Moteur IA de remplissage de formulaires externes
│   ├── llm/                     # Couche d'interaction avec les modèles d'IA
│   │   ├── llm_client.py        # Client unifié (Gemini / OpenAI / Ollama)
│   │   ├── job_evaluator.py     # Algorithme de scoring d'adéquation candidat/poste (0-100)
│   │   ├── profile_analyzer.py  # Analyseur de CV/Profil et extraction de compétences
│   │   └── form_filler.py       # Génération de réponses intelligentes pour les questionnaires
│   ├── storage/                 # Persistance des données
│   │   └── db.py                # Wrapper SQLite (table job_applications, requêtes, stats)
│   ├── watcher/                 # Veille continue en arrière-plan
│   │   ├── realtime_scanner.py  # Scanner multi-plateformes de détection d'offres
│   │   └── watcher_service.py   # Service planifié de surveillance continue
│   ├── documents/               # Gestion des CV et lettres de motivation
│   │   ├── cv_builder.py        # Génération dynamique de CVs adaptés
│   │   ├── cover_letter_builder.py # Rédaction de lettres ciblées
│   │   └── application_documents.py # Orchestrateur de documents pour une offre
│   ├── notifications/           # Dispatcher de notifications
│   │   ├── dispatcher.py        # Envoi multi-canal
│   │   ├── telegram.py          # Intégration bot Telegram
│   │   └── discord.py           # Intégration Webhook Discord
│   └── rate_limiter.py          # Anti-ban : limitation des requêtes et temporisations
│
├── platforms/                   # Connecteurs spécifiques par plateforme d'emploi
│   ├── base.py                  # Classe abstraite BasePlatform et modèle JobPost
│   ├── linkedin/                # Connecteur LinkedIn (Easy Apply & Search)
│   │   ├── easy_apply.py        # Logique de soumission de formulaire Easy Apply
│   │   └── search.py            # Scraping des résultats de recherche
│   ├── indeed/                  # Connecteur Indeed (Indeed Postuler)
│   │   ├── indeed_apply.py      # Automatisation du flux de candidature Indeed
│   │   └── search.py            # Scraping des offres Indeed
│   └── francetravail/           # Connecteur France Travail (Pôle Emploi)
│       ├── francetravail_apply.py # Flux de candidature FT
│       └── search.py            # Recherche et ingestion des annonces
│
├── ui/web/                      # Interface utilisateur web
│   ├── app.py                   # Serveur FastAPI principal (endpoints REST, workers d'état)
│   ├── templates/
│   │   └── index.html           # Page unique (SPA) avec HUD, onglets, dashboards et modales
│   └── static/
│       ├── app.js               # Logique frontend (appels API, filtres, modales, polling batch)
│       ├── style.css            # Styles CSS3 (design system épuré, thèmes Nintendo/Gaming)
│       ├── three.min.js         # Bibliothèque 3D tierce pour effets visuels
│       └── components/          # Micro-composants React optionnels
│
├── data/                        # Données locales (ignorées par git)
│   ├── browser_sessions/        # Profils Chromium persistants (cookies, tokens)
│   ├── resumes/                 # Fichiers CV (PDF) téléversés
│   ├── screenshots/             # Captures d'écran de vérification ou d'erreur
│   └── generated/               # Documents générés
│
├── scratch/                     # Scripts de test ponctuels et prototypes
├── requirements.txt             # Dépendances Python du projet
└── README.md                    # Documentation utilisateur et installation rapide
```

---

## 🗄️ 4. Modèle de Données & Base SQLite

La base de données principale est gérée via SQLite dans `core/storage/db.py`.  
Elle est configurée en mode **WAL (Write-Ahead Logging)** avec un timeout étendu pour permettre des écritures simultanées entre le serveur FastAPI et les workers asynchrones sans verrouillage (`database is locked`).

### Table `job_applications`

```sql
CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,         -- 'linkedin', 'indeed', 'francetravail', ou plateforme custom
    job_id TEXT NOT NULL,           -- Identifiant unique de l'offre sur la plateforme
    job_title TEXT NOT NULL,        -- Titre du poste
    company TEXT NOT NULL,          -- Nom de l'entreprise
    location TEXT,                  -- Ville / Télétravail / Région
    job_url TEXT NOT NULL,          -- URL directe vers l'annonce
    match_score INTEGER,            -- Score d'affinité IA calculé (0 à 100)
    match_reason TEXT,              -- Justification textuelle détaillée de l'IA
    status TEXT NOT NULL,           -- Statut dans le pipeline (voir ci-dessous)
    applied_at TEXT,                -- Horodatage ISO de la candidature
    error_message TEXT,             -- Détail de l'erreur si échec ou redirection externe
    screenshot_path TEXT,           -- Chemin de la preuve de candidature ou de l'erreur
    form_answers TEXT,              -- JSON des réponses apportées au formulaire
    is_easy_apply INTEGER DEFAULT 1,-- 1 si candidature directe/simple, 0 si formulaire externe
    created_at TEXT NOT NULL,       -- Date de découverte de l'offre
    posted_at TEXT,                 -- Date de publication originale
    posted_relative TEXT,           -- Mention relative (ex: "Il y a 2 heures", "Récent")
    UNIQUE(platform, job_id)
);
```

### Cycle de vie d'une offre (`status`)
1. **`found`** : Découverte par le scanner ou ajoutée manuellement, en attente d'évaluation ou de candidature.
2. **`evaluated`** : Le LLM a analysé la fiche et calculé le `match_score` et `match_reason`.
3. **`applied`** : Candidature soumise avec succès (horodatée dans `applied_at`).
4. **`skipped`** : Offre ignorée (soit par l'utilisateur, soit nécessitant une redirection externe complexe, soit profil hors critères).
5. **`failed`** : Échec lors du remplissage du formulaire (ex: question bloquante non résolue, captcha, timeout réseau).
6. **`requires_review`** : Le formulaire nécessite une intervention humaine directe.

---

## ⚙️ 5. Flux Métiers Clés (Workflows)

### 🔄 Flux 1 : Veille continue & Ingestion des offres (Watcher / Scanner)
1. Le service `WatcherService` tourne en arrière-plan ou est déclenché à la demande via `/api/jobs/sync-realtime`.
2. Pour chaque plateforme activée, le scraper recherche les annonces correspondant aux critères de `config/search_criteria.yaml`.
3. Pour chaque annonce non présente en base :
   - Ingestion dans `job_applications` avec statut `found`.
   - Si activé, appel à `JobEvaluator.evaluate()` : le LLM compare le texte de l'annonce au profil `profile.yaml`.
   - Mise à jour du `match_score` (ex: 88%) et du `match_reason`.
   - Si le score dépasse le seuil `min_alert_score`, une notification Discord ou Telegram est expédiée.

### ⚡ Flux 2 : Postuler en 1 Clic & Batch Multi-Plateformes
C'est le cœur réacteur de Oneshot :
1. **Déclenchement** : L'utilisateur clique sur *Postuler en 1 Clic* (global) ou sur le bouton d'une plateforme spécifique (ou d'une offre unitaire via `/api/jobs/{id}/apply`).
2. **Orchestration** : Dans `ui/web/app.py`, la fonction `apply_all_jobs_endpoint` initialise le dictionnaire global `PLATFORM_WORKERS` :
   - Chaque plateforme active reçoit un worker dédié fonctionnant de façon concurrente et sécurisée.
   - Les offres éligibles sont sélectionnées (`status != 'applied'` et `match_score >= min_match_score`).
3. **Exécution Playwright Stealth** :
   - Chargement du profil de session Chromium persistant (`data/browser_sessions/<platform>`).
   - Navigation vers l'URL de l'offre avec injection de `playwright-stealth` et de scripts anti-détection.
   - Remplissage progressif des formulaires avec `HumanActions` (délais aléatoires entre 80ms et 350ms par touche, mouvements naturels de souris).
   - Sélection et upload du CV actif configuré dans `data/resumes/`.
   - Résolution des questions posées via `FormFiller` (LLM basé sur le profil candidat).
   - Envoi de la candidature, capture d'écran de confirmation et mise à jour en base (`status = 'applied'`).
4. **Retour Temps Réel** : Le frontend interroge `/api/jobs/batch-status` toutes les secondes et met à jour dynamiquement la barre de progression, les compteurs de succès/erreurs, et la carte de statut de chaque worker.

### 🔑 Flux 3 : Authentification & Gestion des Sessions
Pour éviter de stocker les identifiants ou mots de passe en clair, l'application utilise une approche **Local-First** :
- **Méthode 1 : Ouverture de fenêtre navigateur (`/api/platforms/{platform}/login-window`)**  
  Un Chromium s'ouvre sur l'écran de l'utilisateur. Il se connecte normalement (avec 2FA/SMS si nécessaire). Une fois connecté, il clique sur "Valider la connexion" : les cookies et le contexte sont enregistrés dans `data/browser_sessions/<platform>`.
- **Méthode 2 : Cookie direct (LinkedIn `li_at`)**  
  Pour LinkedIn, l'utilisateur peut simplement coller son cookie `li_at` extrait de son navigateur habituel via `/api/platforms/linkedin/set-cookie`.

---

## 🛠️ 6. Guide d'Installation & Prise en Main (Dev Setup)

### 1. Prérequis
- **Python 3.10** ou supérieur installé.
- **Git**.
- Clé API **Google Gemini** (recommandée, gratuite sur Google AI Studio) ou **OpenAI**.

### 2. Clonage et environnement virtuel
```bash
# Cloner le projet
git clone https://github.com/Naoufalou/Oneshot.git
cd Oneshot

# Créer l'environnement virtuel Python
python3 -m venv venv

# Activer l'environnement virtuel
# Sur macOS / Linux :
source venv/bin/activate
# Sur Windows (cmd / PowerShell) :
# .\venv\Scripts\activate
```

### 3. Installation des dépendances et de Playwright
```bash
pip install --upgrade pip
pip install -r requirements.txt

# Installer les binaires Chromium nécessaires à Playwright
playwright install chromium
```

### 4. Configuration de l'environnement (`.env`)
Copie le fichier d'exemple et renseigne ta clé API IA :
```bash
cp .env.example .env
```
Édite `.env` :
```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...votre_cle_ici
HEADLESS_BROWSER=false
HUMAN_IN_THE_LOOP=true
```

### 5. Personnalisation du Profil & des Critères
Vérifie ou adapte les fichiers YAML dans `config/` :
- `config/profile.yaml` : Tes coordonnées, compétences, liens LinkedIn/GitHub, réponses types.
- `config/search_criteria.yaml` : Tes mots-clés cibles (*"Développeur Full Stack"*, *"Python"*...), villes, et score minimum.

### 6. Lancement du Serveur de Développement
```bash
uvicorn ui.web.app:app --reload --port 8000
```
L'application est immédiatement accessible sur **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.  
Le mode `--reload` redémarre automatiquement le serveur à chaque modification des fichiers Python.

---

## 🧩 7. Comment Ajouter une Nouvelle Plateforme d'Emploi ?

L'architecture est pensée pour être modulaire grâce au pattern Strategy / Template Method. Pour intégrer une nouvelle plateforme (par exemple **Welcome to the Jungle** `wttj`) :

### Étape 1 : Créer le sous-dossier dans `platforms/`
Créer `platforms/wttj/__init__.py`, `platforms/wttj/search.py` et `platforms/wttj/wttj_apply.py`.

### Étape 2 : Hériter de `BasePlatform`
Dans `platforms/wttj/__init__.py` :
```python
from platforms.base import BasePlatform, JobPost
from core.storage.db import ApplicationRecord
from typing import List

class WTTJPlatform(BasePlatform):
    def __init__(self):
        super().__init__(platform_name="wttj")

    async def is_logged_in(self) -> bool:
        # Vérifier présence d'un cookie ou sélecteur d'avatar connecté
        ...

    async def search_jobs(self, query: str, location: str, limit: int = 15) -> List[JobPost]:
        # Scraper les offres de l'URL de recherche WTTJ
        ...

    async def apply(self, job: JobPost, dry_run: bool = False) -> ApplicationRecord:
        # Remplir le formulaire WTTJ avec HumanActions
        ...
```

### Étape 3 : Déclarer la plateforme dans le backend (`ui/web/app.py`)
- Ajouter la plateforme dans le statut des plateformes (`/api/platforms/status`).
- Déclarer son worker dans le dictionnaire `PLATFORM_WORKERS`.
- L'ajouter dans `execute_platform_batch_worker`.

### Étape 4 : Ajouter la carte et les filtres dans le frontend
- Ajouter un bouton filtre dans `index.html` sous `zen-platform-hub`.
- Définir sa couleur et son icône dans `style.css` (variables CSS `--color-wttj`, etc.).

---

## ⚠️ 8. Bonnes Pratiques & Pièges Courants (Gotchas)

1. **Sélecteurs CSS/XPath fragiles** :
   - Les sites d'emploi (notamment LinkedIn et Indeed) font régulièrement des A/B tests et modifient leurs classes CSS générées aléatoirement.
   - **Règle d'or** : Utilise toujours des sélecteurs robustes basés sur l'accessibilité (`page.get_by_role()`, `page.get_by_label()`, `aria-label`, ou attributs stables de données comme `data-test-*`), ou des fallbacks en cascade.
2. **Anti-Bot & Délais Humains** :
   - Ne jamais court-circuiter les pauses de `HumanActions` (`human.sleep_gaussian()` et `human.random_mouse_jitter()`) en mode réel.
   - Un envoi de formulaire instantané sans frappe progressive entraîne des captchas ou le blocage temporaire du compte.
3. **Gestion de la concurrence SQLite** :
   - Toujours utiliser `with db._get_connection() as conn:` pour manipuler la base.
   - Ne jamais garder une connexion ou un curseur ouvert indéfiniment pendant des opérations réseau lentes ou du scraping Playwright.
4. **Gestion de la mémoire Playwright** :
   - Toujours appeler `await browser.close()` ou réutiliser le `BrowserManager` au lieu d'instancier 50 instances de Chromium simultanées qui satureraient la RAM.
5. **Frontend sans build-step (No-Webpack/Vite)** :
   - Le frontend tourne en JavaScript natif ES6+.
   - Si tu ajoutes des scripts ou modifications dans `static/app.js` ou `static/style.css`, pense à incrémenter le paramètre de version dans `index.html` (ex: `style.css?v=4.1`) pour éviter les soucis de cache navigateur lors des tests.

---

## 🎯 9. Roadmap & Pistes d'Amélioration pour l'Équipe

Voici les chantiers prioritaires sur lesquels tu peux apporter une forte valeur ajoutée :
- [ ] **ATS Pipeline (Vue Kanban)** : Ajouter un onglet Kanban pour suivre l'avancement post-candidature (*Postulée* -> *Entretien RH* -> *Test technique* -> *Offre*).
- [ ] **Nouveaux Connecteurs** : Finaliser les connecteurs natifs pour *Welcome to the Jungle*, *Apec*, et *HelloWork*.
- [ ] **Tests E2E Automatisés** : Mettre en place une suite de tests automatisés via `pytest-asyncio` pour valider les routes d'API et les parseurs sans lancer de vraies candidatures.
- [ ] **Génération personnalisée de lettres de motivation** : Améliorer le prompt de `cover_letter_builder.py` pour intégrer des éléments spécifiques tirés des actualités récentes de l'entreprise cible.
- [ ] **Packaging Desktop** : Évaluer l'intégration avec Tauri ou Electron pour distribuer l'application sous forme de binaire natif macOS/Windows prêt à l'emploi.

---

## 🤝 10. Besoin d'aide ou questions ?
- Fichiers de configuration utilisateur : `config/profile.yaml` & `config/search_criteria.yaml`
- Logs d'exécution : consultables en direct dans le terminal ou via l'endpoint `/api/logs`
- Données persistées : `applications.db` (consultable avec n'importe quel visualiseur SQLite comme *DB Browser for SQLite*)

**Bon dev et bienvenue dans le projet Oneshot ! 🚀**
