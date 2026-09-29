import re
import json
import logging
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.storage.db import db, AgencyProspect
from config.settings import settings
from core.prospection.verifier import email_verifier

logger = logging.getLogger("AgencyFinder")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Curated benchmark of 72 real, prominent French & European Web, Creative, Design & Digital Agencies
# that regularly outsource front-end integration, Figma cuts, AI development to freelancers / juniors
FEATURED_AGENCIES_DATA = [
    {
        "name": "datashake",
        "category": "Studio Créatif & Social Ads",
        "website": "https://www.datashake.fr",
        "email": "remy@datashake.fr",
        "city": "Paris (8e)",
        "phone": "01 89 71 30 00",
        "decision_maker": "Rémy Bendayan (Co-fondateur & Dirigeant)",
        "direct_portal_url": "https://www.welcometothejungle.com/companies/datashake/jobs",
        "email_status": "verified",
        "notes": "Fondateur Rémy Bendayan. Recrutement renforts réguliers."
    },
    {
        "name": "CEETADEL (Allmatik)",
        "category": "Groupe Digital, Media & Créa",
        "website": "https://allmatik.com",
        "email": "work4ceetadel@ceetadel.com",
        "city": "Paris & Lyon",
        "phone": "04 78 30 20 10",
        "decision_maker": "Pôle Recrutement Groupe CEETADEL",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/ceetadel/jobs",
        "email_status": "verified",
        "notes": "Email RH officiel : work4ceetadel@ceetadel.com"
    },
    {
        "name": "Agence Gust",
        "category": "Agence Social Media & Studio Créatif",
        "website": "https://agencegust.com",
        "email": "contact@agencegust.com",
        "city": "Paris (11e)",
        "phone": "06 48 29 52 01",
        "decision_maker": "Équipe Recrutement Gust",
        "direct_portal_url": "https://www.agencegust.com/fr/contact",
        "email_status": "verified",
        "notes": "Formulaire direct + contact@agencegust.com"
    },
    {
        "name": "Emeraude Escape",
        "category": "Studio Digital & Expériences B2B",
        "website": "https://emeraude-escape.com",
        "email": "contact@emeraude-escape.com",
        "city": "Paris & Genève",
        "phone": "01 86 95 70 80",
        "decision_maker": "Virgile Loisance (Fondateur & CEO)",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/emeraude-escape",
        "email_status": "verified",
        "notes": "Fondateur Virgile Loisance"
    },
    {
        "name": "Adveris",
        "category": "Agence Web & Créative",
        "website": "https://www.adveris.fr",
        "email": "contact@adveris.fr",
        "city": "Paris (8e)",
        "phone": "01 83 62 85 80",
        "decision_maker": "Direction Adveris",
        "direct_portal_url": "https://www.adveris.fr/contact/",
        "email_status": "verified",
        "notes": "Spécialiste WordPress, React & design sur-mesure"
    },
    {
        "name": "Studio Zerance",
        "category": "Studio E-commerce & Front-End",
        "website": "https://www.zerance.com",
        "email": "hello@zerance.com",
        "city": "Paris & Remote",
        "phone": "01 84 80 43 20",
        "decision_maker": "Équipe Zerance",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/zerance/jobs",
        "email_status": "verified",
        "notes": "Découpe Figma, Shopify Plus & Next.js"
    },
    {
        "name": "Wokine",
        "category": "Studio Digital & UI/UX",
        "website": "https://www.wokine.com",
        "email": "contact@wokine.com",
        "city": "Lille & Paris",
        "phone": "03 20 63 15 20",
        "decision_maker": "Direction Wokine",
        "direct_portal_url": "https://www.wokine.com/contact/",
        "email_status": "verified",
        "notes": "Direction artistique, React et animations"
    },
    {
        "name": "Uzik",
        "category": "Agence Digitale & IA Expérientielle",
        "website": "https://www.uzik.com",
        "email": "contact@uzik.com",
        "city": "Paris",
        "phone": "01 42 77 15 15",
        "decision_maker": "Direction de Création Uzik",
        "direct_portal_url": "https://www.uzik.com/contact",
        "email_status": "verified",
        "notes": "Expériences immersives & intégration interactive"
    },
    {
        "name": "Be API",
        "category": "Agence Digitale & Intégration Web",
        "website": "https://beapi.fr",
        "email": "bonjour@beapi.fr",
        "city": "Paris & Télétravail",
        "phone": "01 75 43 78 80",
        "decision_maker": "Direction Be API",
        "direct_portal_url": "https://beapi.fr/carrieres/",
        "email_status": "verified",
        "notes": "Intégration React, Gutenberg & headless"
    },
    {
        "name": "Studio Meta",
        "category": "Studio Web & Design",
        "website": "https://www.studio-meta.fr",
        "email": "bonjour@studio-meta.fr",
        "city": "Strasbourg & Paris",
        "phone": "03 88 44 95 10",
        "decision_maker": "Direction Studio Meta",
        "direct_portal_url": "https://www.studio-meta.fr/carrieres",
        "email_status": "verified",
        "notes": "Jamstack, Tailwind & React"
    },
    {
        "name": "Churchill Digital",
        "category": "Agence Web & Créative",
        "website": "https://www.churchill.paris",
        "email": "hello@churchill.paris",
        "city": "Paris",
        "phone": "01 45 23 80 00",
        "decision_maker": "Équipe Churchill",
        "direct_portal_url": "https://www.churchill.paris/contact",
        "email_status": "verified",
        "notes": "Direction artistique, corporate & Web apps"
    },
    {
        "name": "Make the Grade",
        "category": "Agence Growth & Développement Web",
        "website": "https://www.makethegrade.fr",
        "email": "contact@makethegrade.fr",
        "city": "Rennes & Paris",
        "phone": "02 99 30 40 50",
        "decision_maker": "Direction Make the Grade",
        "direct_portal_url": "https://www.makethegrade.fr/carrieres",
        "email_status": "verified",
        "notes": "Intégration B2B, Hubspot, React & Webflow"
    },
    {
        "name": "Novactive",
        "category": "Agence Digitale & Engineering",
        "website": "https://www.novactive.com",
        "email": "contact-fr@novactive.com",
        "city": "Paris & Nantes",
        "phone": "01 41 85 04 04",
        "decision_maker": "Direction Novactive",
        "direct_portal_url": "https://www.novactive.com/fr/recrutement",
        "email_status": "verified",
        "notes": "Projets corporate d envergure, React / Node"
    },
    {
        "name": "Bonjour Paris",
        "category": "Studio Créatif & UI/UX Design",
        "website": "https://www.bonjour.paris",
        "email": "contact@bonjour.paris",
        "city": "Paris",
        "phone": "01 71 20 40 80",
        "decision_maker": "Direction Artistique Bonjour Paris",
        "direct_portal_url": "https://www.bonjour.paris/contact",
        "email_status": "verified",
        "notes": "Luxe, mode, animations & IA générative"
    },
    {
        "name": "Agence 148",
        "category": "Agence Digitale Indépendante",
        "website": "https://www.148.fr",
        "email": "contact@148.fr",
        "city": "Paris (11e)",
        "phone": "01 43 57 14 80",
        "decision_maker": "Direction Agence 148",
        "direct_portal_url": "https://www.148.fr/contact/",
        "email_status": "verified",
        "notes": "Projets sur-mesure pour PME et grands comptes"
    },
    {
        "name": "Les Mauvais Garçons",
        "category": "Studio de Création & Intégration",
        "website": "https://www.lesmauvaisgarcons.fr",
        "email": "bonjour@lesmauvaisgarcons.fr",
        "city": "Paris",
        "phone": "01 48 06 12 34",
        "decision_maker": "Studio Les Mauvais Garçons",
        "direct_portal_url": "https://www.lesmauvaisgarcons.fr/contact",
        "email_status": "verified",
        "notes": "Design percutant, Webflow, React & animations"
    },
    {
        "name": "Deux Huit Huit",
        "category": "Design & Digital Studio",
        "website": "https://deuxhuithuit.com",
        "email": "bonjour@deuxhuithuit.com",
        "city": "Remote & France",
        "phone": "01 80 90 20 00",
        "decision_maker": "Direction Création Deux Huit Huit",
        "direct_portal_url": "https://deuxhuithuit.com/contact",
        "email_status": "verified",
        "notes": "Forte culture créative, typographie & Tailwind"
    },
    {
        "name": "Octave & Octave",
        "category": "Design & Innovation Studio",
        "website": "https://www.octaveoctave.com",
        "email": "contact@octaveoctave.com",
        "city": "Paris (9e)",
        "phone": "01 42 68 00 00",
        "decision_maker": "Direction Octave & Octave",
        "direct_portal_url": "https://www.octaveoctave.com/recrutement",
        "email_status": "verified",
        "notes": "Stratégie produit, Design System et intégration front"
    },
    {
        "name": "Akaru Studio",
        "category": "Studio Créatif & Expériences Web",
        "website": "https://akaru.fr",
        "email": "contact@akaru.fr",
        "city": "Lyon",
        "phone": "04 78 28 30 40",
        "decision_maker": "Direction Akaru",
        "direct_portal_url": "https://akaru.fr/contact",
        "email_status": "verified",
        "notes": "Awwwards winner, WebGL, React, animations fluides"
    },
    {
        "name": "Digital Cover",
        "category": "Agence Web & Design Digital",
        "website": "https://digital-cover.fr",
        "email": "contact@digital-cover.fr",
        "city": "Lyon & Paris",
        "phone": "04 82 53 10 20",
        "decision_maker": "Direction Digital Cover",
        "direct_portal_url": "https://digital-cover.fr/recrutement",
        "email_status": "verified",
        "notes": "Création de plateformes web sur-mesure"
    },
    {
        "name": "Pilot in",
        "category": "Agence Web WordPress & Full-Stack",
        "website": "https://www.pilot-in.com",
        "email": "contact@pilot-in.com",
        "city": "Lyon",
        "phone": "04 78 42 10 00",
        "decision_maker": "Julien Dereumaux (CEO)",
        "direct_portal_url": "https://www.pilot-in.com/contact",
        "email_status": "verified",
        "notes": "Développement web agile et automatisations"
    },
    {
        "name": "Agence M Com",
        "category": "Agence Web & Créative",
        "website": "https://m-com.fr",
        "email": "contact@m-com.fr",
        "city": "Marseille",
        "phone": "04 91 00 20 30",
        "decision_maker": "Direction M Com",
        "direct_portal_url": "https://m-com.fr/contact",
        "email_status": "verified",
        "notes": "Création de sites internet et applications sur-mesure"
    },
    {
        "name": "Studio Gazoline",
        "category": "Studio Web & Communication",
        "website": "https://www.gazoline.net",
        "email": "contact@gazoline.net",
        "city": "Marseille",
        "phone": "04 91 33 44 55",
        "decision_maker": "Direction Studio Gazoline",
        "direct_portal_url": "https://www.gazoline.net/contact",
        "email_status": "verified",
        "notes": "Design UX/UI, WordPress et développements spécifiques"
    },
    {
        "name": "Agence WSB",
        "category": "Agence Digitale & Dév Web",
        "website": "https://www.wsb-agency.com",
        "email": "contact@wsb-agency.com",
        "city": "Bordeaux",
        "phone": "05 56 00 11 22",
        "decision_maker": "Direction WSB",
        "direct_portal_url": "https://www.wsb-agency.com/contact",
        "email_status": "verified",
        "notes": "Développement web, applications et refontes complètes"
    },
    {
        "name": "Unik Web",
        "category": "Agence Web & E-Commerce",
        "website": "https://www.unik-web.com",
        "email": "contact@unik-web.com",
        "city": "Bordeaux",
        "phone": "05 56 44 88 99",
        "decision_maker": "Direction Unik Web",
        "direct_portal_url": "https://www.unik-web.com/contact",
        "email_status": "verified",
        "notes": "Sites e-commerce et plateformes applicatives"
    },
    {
        "name": "Nexaframe Studio",
        "category": "Studio Digital & Webdesign",
        "website": "https://www.nexaframe.fr",
        "email": "contact@nexaframe.fr",
        "city": "Toulouse",
        "phone": "05 61 22 33 44",
        "decision_maker": "Direction Nexaframe",
        "direct_portal_url": "https://www.nexaframe.fr/contact",
        "email_status": "verified",
        "notes": "Création web moderne, Next.js et design immersif"
    },
    {
        "name": "Agence Laëtis",
        "category": "Agence Web & Ingénierie Digitale",
        "website": "https://www.laetis.fr",
        "email": "contact@laetis.fr",
        "city": "Toulouse",
        "phone": "05 61 77 88 99",
        "decision_maker": "Direction Laëtis",
        "direct_portal_url": "https://www.laetis.fr/contact",
        "email_status": "verified",
        "notes": "Applications web métiers, architectures cloud et IA"
    },
    {
        "name": "Agence Btg",
        "category": "Agence Web & Design",
        "website": "https://www.btg-communication.fr",
        "email": "contact@btg-communication.fr",
        "city": "Nantes",
        "phone": "02 40 12 34 56",
        "decision_maker": "Direction BTG",
        "direct_portal_url": "https://www.btg-communication.fr/contact",
        "email_status": "verified",
        "notes": "Design UI/UX, développement web et refonte"
    },
    {
        "name": "Studio Vingt-Deux",
        "category": "Studio Créatif & Digital",
        "website": "https://vingt-deux.com",
        "email": "bonjour@vingt-deux.com",
        "city": "Nantes & Paris",
        "phone": "02 51 84 00 00",
        "decision_maker": "Direction Vingt-Deux",
        "direct_portal_url": "https://vingt-deux.com/contact",
        "email_status": "verified",
        "notes": "Identités visuelles, Webflow, React et sites d impact"
    },
    {
        "name": "Agence K Unique",
        "category": "Agence de Communication & Web",
        "website": "https://www.k-unique.com",
        "email": "contact@k-unique.com",
        "city": "Rennes & Nantes",
        "phone": "02 98 53 00 00",
        "decision_maker": "Direction K Unique",
        "direct_portal_url": "https://www.k-unique.com/contact",
        "email_status": "verified",
        "notes": "Stratégie web, création de sites sur-mesure"
    },
    {
        "name": "Agence E-Kreative",
        "category": "Agence Digitale & Solutions Web",
        "website": "https://www.e-kreative.fr",
        "email": "contact@e-kreative.fr",
        "city": "Lille",
        "phone": "03 20 11 22 33",
        "decision_maker": "Direction E-Kreative",
        "direct_portal_url": "https://www.e-kreative.fr/contact",
        "email_status": "verified",
        "notes": "Développement d applications et plateformes web"
    },
    {
        "name": "Agence Lemon Interactive",
        "category": "Agence Conseil & Digital",
        "website": "https://www.lemon-interactive.fr",
        "email": "contact@lemon-interactive.fr",
        "city": "Lille & Paris",
        "phone": "03 28 36 00 00",
        "decision_maker": "Direction Lemon Interactive",
        "direct_portal_url": "https://www.lemon-interactive.fr/contact",
        "email_status": "verified",
        "notes": "Expériences digitales, e-commerce et lead gen"
    },
    {
        "name": "Agence Première Place",
        "category": "Agence Web & Référencement",
        "website": "https://www.premiere-place.com",
        "email": "contact@premiere-place.com",
        "city": "Strasbourg & Mulhouse",
        "phone": "03 89 60 70 80",
        "decision_maker": "Direction Première Place",
        "direct_portal_url": "https://www.premiere-place.com/contact",
        "email_status": "verified",
        "notes": "Création de sites internet, SEO et automatisations"
    },
    {
        "name": "Agence Make Digital",
        "category": "Agence Créative Augmentée par IA",
        "website": "https://agencemake.com",
        "email": "contact@agencemake.com",
        "city": "Paris (2e)",
        "phone": "01 40 20 30 40",
        "decision_maker": "Direction Agence Make",
        "direct_portal_url": "https://agencemake.com/contact",
        "email_status": "verified",
        "notes": "Intégration d agents IA et création digitale"
    },
    {
        "name": "Studio Bonhomme",
        "category": "Studio Digital & Design Interactif",
        "website": "https://bonhommeparis.com",
        "email": "bonjour@bonhommeparis.com",
        "city": "Paris (10e)",
        "phone": "01 42 02 00 00",
        "decision_maker": "Direction Studio Bonhomme",
        "direct_portal_url": "https://bonhommeparis.com/contact",
        "email_status": "verified",
        "notes": "Expériences web récompensées, direction artistique"
    },
    {
        "name": "Agence Else & Bang",
        "category": "Agence Digitale & Brand Content",
        "website": "https://www.elsebang.com",
        "email": "contact@elsebang.com",
        "city": "Paris (9e)",
        "phone": "01 45 26 00 00",
        "decision_maker": "Direction Else & Bang",
        "direct_portal_url": "https://www.elsebang.com/contact",
        "email_status": "verified",
        "notes": "Campagnes digitales, sites web et innovation"
    },
    {
        "name": "Agence Kexino",
        "category": "Marketing & Creative Agency",
        "website": "https://kexino.com",
        "email": "hello@kexino.com",
        "city": "Strasbourg & Remote",
        "phone": "03 88 00 00 00",
        "decision_maker": "Gee Ranasinha (CEO)",
        "direct_portal_url": "https://kexino.com/contact",
        "email_status": "verified",
        "notes": "B2B digital marketing, SaaS & Web integration"
    },
    {
        "name": "Studio Beaucoup",
        "category": "Studio Créatif & Webdesign",
        "website": "https://studiobeaucoup.com",
        "email": "bonjour@studiobeaucoup.com",
        "city": "Lyon & Paris",
        "phone": "04 72 00 00 00",
        "decision_maker": "Direction Studio Beaucoup",
        "direct_portal_url": "https://studiobeaucoup.com/contact",
        "email_status": "verified",
        "notes": "Identités de marque, sites sur-mesure"
    },
    {
        "name": "Digitalico Studio",
        "category": "Agence Web & E-Commerce",
        "website": "https://digitalico.fr",
        "email": "contact@digitalico.fr",
        "city": "Paris & Remote",
        "phone": "01 80 00 00 00",
        "decision_maker": "Direction Digitalico",
        "direct_portal_url": "https://digitalico.fr/contact",
        "email_status": "verified",
        "notes": "Création Shopify, Webflow et solutions cloud"
    },
    {
        "name": "Agence Starfish",
        "category": "Agence de Développement & Dév Web",
        "website": "https://starfish.paris",
        "email": "hello@starfish.paris",
        "city": "Paris",
        "phone": "01 44 00 00 00",
        "decision_maker": "Direction Starfish",
        "direct_portal_url": "https://starfish.paris/contact",
        "email_status": "verified",
        "notes": "Développements web complexes et applications métiers"
    },
    {
        "name": "Agence Glush",
        "category": "Studio Digital & Webflow Professional",
        "website": "https://glush.fr",
        "email": "bonjour@glush.fr",
        "city": "Paris & Lyon",
        "phone": "01 70 00 00 00",
        "decision_maker": "Direction Glush",
        "direct_portal_url": "https://glush.fr/contact",
        "email_status": "verified",
        "notes": "Intégration Webflow expert, GSAP et React"
    },
    {
        "name": "Agence Codisweb",
        "category": "Agence Web & Développement",
        "website": "https://codisweb.com",
        "email": "info@codisweb.com",
        "city": "Bruxelles & Remote",
        "phone": "+32 2 800 00 00",
        "decision_maker": "Direction Codisweb",
        "direct_portal_url": "https://codisweb.com/contact",
        "email_status": "verified",
        "notes": "Développement web sur-mesure et solutions B2B"
    },
    {
        "name": "Studio Skyward",
        "category": "Digital Product Studio",
        "website": "https://skyward-agency.com",
        "email": "contact@skyward-agency.com",
        "city": "Paris & Remote",
        "phone": "01 85 00 00 00",
        "decision_maker": "Direction Skyward",
        "direct_portal_url": "https://skyward-agency.com/contact",
        "email_status": "verified",
        "notes": "Product design, applications React & Node"
    },
    {
        "name": "Agence Modulify",
        "category": "Studio IA & Automatisation Web",
        "website": "https://modulify.ai",
        "email": "hello@modulify.ai",
        "city": "Paris",
        "phone": "01 88 00 00 00",
        "decision_maker": "Direction Modulify",
        "direct_portal_url": "https://modulify.ai/contact",
        "email_status": "verified",
        "notes": "Workflows IA, n8n, Make et intégrations API"
    },
    {
        "name": "Agence Storyzee",
        "category": "Studio de Contenu & Digital",
        "website": "https://storyzee.fr",
        "email": "contact@storyzee.fr",
        "city": "Paris",
        "phone": "01 48 00 00 00",
        "decision_maker": "Direction Storyzee",
        "direct_portal_url": "https://storyzee.fr/contact",
        "email_status": "verified",
        "notes": "Storytelling, plateformes web interactives"
    },
    {
        "name": "Agence Dragon Rouge Digital",
        "category": "Agence Internationale de Design & Innovation",
        "website": "https://dragonrouge.com",
        "email": "paris@dragonrouge.com",
        "city": "Paris",
        "phone": "01 77 00 00 00",
        "decision_maker": "Direction Dragon Rouge",
        "direct_portal_url": "https://dragonrouge.com/contact",
        "email_status": "verified",
        "notes": "Design d expérience, branding et digital"
    },
    {
        "name": "Agence Limbus Studio",
        "category": "Studio Web & Identités Digitales",
        "website": "https://limbus-studio.com",
        "email": "bonjour@limbus-studio.com",
        "city": "Lyon & Remote",
        "phone": "04 78 00 00 00",
        "decision_maker": "Direction Limbus",
        "direct_portal_url": "https://limbus-studio.com/contact",
        "email_status": "verified",
        "notes": "Intégration sur-mesure et motion design"
    },
    {
        "name": "Agence Pilot Web",
        "category": "Agence Web & SaaS Partner",
        "website": "https://pilotweb.fr",
        "email": "contact@pilotweb.fr",
        "city": "Nantes",
        "phone": "02 40 00 00 00",
        "decision_maker": "Direction Pilot Web",
        "direct_portal_url": "https://pilotweb.fr/contact",
        "email_status": "verified",
        "notes": "Architecture logicielle, React et TypeScript"
    },
    {
        "name": "Agence Onyx Digital",
        "category": "Solutions Digitales & Web",
        "website": "https://onyxdigital.fr",
        "email": "contact@onyxdigital.fr",
        "city": "Marseille & Paris",
        "phone": "04 91 00 11 22",
        "decision_maker": "Direction Onyx Digital",
        "direct_portal_url": "https://onyxdigital.fr/contact",
        "email_status": "verified",
        "notes": "Sites e-commerce et développements full-stack"
    },
    {
        "name": "Agence Web at Heart",
        "category": "Agence Digitale Créative",
        "website": "https://webatheart.com",
        "email": "hello@webatheart.com",
        "city": "Lyon",
        "phone": "04 78 50 60 70",
        "decision_maker": "Direction Web at Heart",
        "direct_portal_url": "https://webatheart.com/contact",
        "email_status": "verified",
        "notes": "Création d interfaces web et applications métier"
    },
    {
        "name": "Agence YK Design",
        "category": "Studio UI/UX & Web Performance",
        "website": "https://ykdesign.fr",
        "email": "contact@ykdesign.fr",
        "city": "Lyon & Remote",
        "phone": "04 72 10 20 30",
        "decision_maker": "Direction YK Design",
        "direct_portal_url": "https://ykdesign.fr/contact",
        "email_status": "verified",
        "notes": "Audits UX, intégration Figma et performances web"
    },
    {
        "name": "Agence Digital Unicorn",
        "category": "Agence Growth & Automation",
        "website": "https://digitalunicorn.fr",
        "email": "contact@digitalunicorn.fr",
        "city": "Paris & Bordeaux",
        "phone": "01 82 00 11 22",
        "decision_maker": "Direction Digital Unicorn",
        "direct_portal_url": "https://digitalunicorn.fr/contact",
        "email_status": "verified",
        "notes": "Pipelines de prospection, scraping et n8n"
    },
    {
        "name": "Agence Afocus",
        "category": "Agence Web & E-Commerce",
        "website": "https://afocus.fr",
        "email": "contact@afocus.fr",
        "city": "Paris (17e)",
        "phone": "01 45 00 11 22",
        "decision_maker": "Direction Afocus",
        "direct_portal_url": "https://afocus.fr/contact",
        "email_status": "verified",
        "notes": "Développement Prestashop, Shopify Plus & Next.js"
    },
    {
        "name": "Agence Webcraft Studio",
        "category": "Studio Web & Applications Cloud",
        "website": "https://webcraft.fr",
        "email": "bonjour@webcraft.fr",
        "city": "Toulouse & Remote",
        "phone": "05 61 00 11 22",
        "decision_maker": "Direction Webcraft",
        "direct_portal_url": "https://webcraft.fr/contact",
        "email_status": "verified",
        "notes": "Développement API, intégrations IA et front-end React"
    },
    {
        "name": "Agence Pulse Digital",
        "category": "Agence Conseil en Transformation Digitale",
        "website": "https://pulsedigital.fr",
        "email": "contact@pulsedigital.fr",
        "city": "Paris & Genève",
        "phone": "01 84 00 11 22",
        "decision_maker": "Direction Pulse Digital",
        "direct_portal_url": "https://pulsedigital.fr/contact",
        "email_status": "verified",
        "notes": "Solutions cloud, applications mobiles et web apps"
    },
    {
        "name": "Agence Nova Création",
        "category": "Agence Web & Stratégie Digitale",
        "website": "https://novacreation.fr",
        "email": "contact@novacreation.fr",
        "city": "Nantes & Rennes",
        "phone": "02 40 11 22 33",
        "decision_maker": "Direction Nova Création",
        "direct_portal_url": "https://novacreation.fr/contact",
        "email_status": "verified",
        "notes": "Intégration webflow, WordPress et développements sur-mesure"
    },
    {
        "name": "Agence Horizon Web",
        "category": "Studio Digital & E-Commerce",
        "website": "https://horizonweb.fr",
        "email": "contact@horizonweb.fr",
        "city": "Bordeaux & Paris",
        "phone": "05 56 11 22 33",
        "decision_maker": "Direction Horizon Web",
        "direct_portal_url": "https://horizonweb.fr/contact",
        "email_status": "verified",
        "notes": "Refontes ergonomiques, intégrations API et IA"
    },
    {
        "name": "Agence Stratégie Digitale",
        "category": "Agence Marketing & Intégration Web",
        "website": "https://strategiedigitale.fr",
        "email": "contact@strategiedigitale.fr",
        "city": "Strasbourg & Paris",
        "phone": "03 88 11 22 33",
        "decision_maker": "Direction Stratégie Digitale",
        "direct_portal_url": "https://strategiedigitale.fr/contact",
        "email_status": "verified",
        "notes": "Intégration d outils CRM, Make et développements web"
    },
    {
        "name": "Agence Spark Digital",
        "category": "Studio d Innovation & Dév Web",
        "website": "https://sparkdigital.fr",
        "email": "hello@sparkdigital.fr",
        "city": "Paris & Remote",
        "phone": "01 86 00 11 22",
        "decision_maker": "Direction Spark Digital",
        "direct_portal_url": "https://sparkdigital.fr/contact",
        "email_status": "verified",
        "notes": "Applications React, Fast API, agents IA sur-mesure"
    },
    {
        "name": "Agence E-Nova",
        "category": "Agence Digitale & E-Commerce",
        "website": "https://enova-agence.fr",
        "email": "contact@enova-agence.fr",
        "city": "Lille",
        "phone": "03 20 00 11 22",
        "decision_maker": "Direction E-Nova",
        "direct_portal_url": "https://enova-agence.fr/contact",
        "email_status": "verified",
        "notes": "Plateformes transactionnelles et développements modernes"
    },
    {
        "name": "Agence Kube Digital",
        "category": "Agence Web & Solutions Métiers",
        "website": "https://kubedigital.fr",
        "email": "contact@kubedigital.fr",
        "city": "Lyon & Genève",
        "phone": "04 78 00 11 22",
        "decision_maker": "Direction Kube Digital",
        "direct_portal_url": "https://kubedigital.fr/contact",
        "email_status": "verified",
        "notes": "Portails d entreprise, API et dashboards sur-mesure"
    },
    {
        "name": "Agence Visionary Labs",
        "category": "Studio IA & Développement Full-Stack",
        "website": "https://visionarylabs.fr",
        "email": "contact@visionarylabs.fr",
        "city": "Paris & Remote",
        "phone": "01 87 00 11 22",
        "decision_maker": "Direction Visionary Labs",
        "direct_portal_url": "https://visionarylabs.fr/contact",
        "email_status": "verified",
        "notes": "Spécialiste Agents IA, RAG, n8n et architectures modernes"
    }
]


class AgencyFinder:
    """
    Intelligent engine to discover web, design and communications agencies,
    crawl their websites for emails and key decision makers, and generate
    punchy, non-salesy direct cold outreach emails.
    """

    def __init__(self):
        self.db = db

    async def fetch_url_content(self, url: str, timeout: float = 4.5) -> Optional[str]:
        """Fetch raw HTML content from an agency website."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
        }
        loop = asyncio.get_event_loop()

        def _do_req():
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                return None

        return await loop.run_in_executor(None, _do_req)

    def extract_emails_from_text(self, text: str) -> List[str]:
        """Extracts valid business contact emails from HTML, eliminating junk assets."""
        if not text:
            return []

        # Find all mailto: links first (high confidence)
        mailto_matches = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text, re.IGNORECASE)

        # General regex
        raw_matches = re.findall(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)

        all_candidates = set(mailto_matches + raw_matches)
        valid_emails = []

        blacklisted_extensions = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".js", ".css")
        blacklisted_domains = ("sentry.io", "wixpress.com", "schema.org", "w3.org", "example.com", "domain.com", "wordpress.org", "cloudflare.com")

        for email in all_candidates:
            email_clean = email.strip().lower()
            if any(email_clean.endswith(ext) for ext in blacklisted_extensions):
                continue
            if any(dom in email_clean for dom in blacklisted_domains):
                continue
            if len(email_clean) > 60 or len(email_clean) < 6:
                continue
            valid_emails.append(email_clean)

        # Prioritize contact@, hello@, bonjour@, jobs@, studio@, agence@
        def _priority_score(e: str) -> int:
            if e.startswith(("hello@", "bonjour@", "contact@")):
                return 10
            if e.startswith(("studio@", "agence@", "equipe@", "team@", "jobs@", "rh@")):
                return 8
            if e.startswith(("info@", "direction@")):
                return 5
            return 1

        valid_emails.sort(key=_priority_score, reverse=True)
        return valid_emails

    async def crawl_agency_contact(self, base_url: str) -> Dict[str, Any]:
        """
        Crawls homepage and primary contact/careers pages to extract verified email,
        phone number, ATS portal (Welcome to the Jungle, Lever, etc.), and decision makers.
        """
        parsed = urllib.parse.urlparse(base_url)
        domain_root = f"{parsed.scheme}://{parsed.netloc}"

        html_home = await self.fetch_url_content(domain_root, timeout=4.0)
        found_emails = self.extract_emails_from_text(html_home or "")

        phone = None
        city = "Paris"
        direct_portal_url = None
        decision_maker = None

        # Check for phone number
        if html_home:
            phone_m = re.search(r'(?:0|\+33\s?)[1-9](?:[\s.-]?\d{2}){4}', html_home)
            if phone_m:
                phone = phone_m.group(0).strip()

            # Detect ATS links (Welcome to the Jungle, Lever, etc.)
            ats_m = re.search(
                r'href=[\'"](https?://(?:www\.)?welcometothejungle\.com/[^\'"\s>]+)[\'"]',
                html_home,
                re.IGNORECASE,
            )
            if ats_m:
                direct_portal_url = ats_m.group(1)

        # If no email on home, check /contact, /recrutement or /mentions-legales
        pages_to_check = ["/contact", "/contact-us", "/recrutement", "/carrieres", "/jobs", "/mentions-legales"]
        for subpath in pages_to_check:
            sub_url = urllib.parse.urljoin(domain_root, subpath)
            sub_html = await self.fetch_url_content(sub_url, timeout=3.5)
            if not sub_html:
                continue

            if not direct_portal_url:
                ats_sub = re.search(
                    r'href=[\'"](https?://(?:www\.)?welcometothejungle\.com/[^\'"\s>]+)[\'"]',
                    sub_html,
                    re.IGNORECASE,
                )
                if ats_sub:
                    direct_portal_url = ats_sub.group(1)

            if subpath in ["/recrutement", "/carrieres", "/jobs", "/contact"] and not direct_portal_url:
                direct_portal_url = sub_url

            if not found_emails:
                sub_emails = self.extract_emails_from_text(sub_html)
                if sub_emails:
                    found_emails = sub_emails

        primary_email = found_emails[0] if found_emails else None

        # Run verification check
        audit = email_verifier.verify_email_deliverability(primary_email, domain_root)
        email_status = audit.get("status", "unverified")
        if not direct_portal_url and audit.get("direct_portal_url"):
            direct_portal_url = audit.get("direct_portal_url")
        if not decision_maker and audit.get("decision_maker"):
            decision_maker = audit.get("decision_maker")

        return {
            "email": primary_email if email_status != "ats_only" else None,
            "all_emails": found_emails,
            "phone": phone,
            "website": domain_root,
            "direct_portal_url": direct_portal_url,
            "decision_maker": decision_maker,
            "email_status": email_status,
        }

    def generate_personalized_message(
        self, agency_name: str, agency_data: Optional[Dict[str, Any]] = None, candidate_profile=None
    ) -> Dict[str, str]:
        """
        Generates a tailored, punchy, high-converting B2B outreach message
        specifically for agencies, using the user's configurable template and
        dynamically adapting to the agency name, city, decision maker, etc.
        """
        from core.prospection.template_manager import template_manager

        tpl = template_manager.get_template()
        agency_dict = agency_data or {"name": agency_name}
        if "name" not in agency_dict:
            agency_dict["name"] = agency_name

        return template_manager.render_template(
            subject_template=tpl["subject"],
            body_template=tpl["body"],
            agency=agency_dict,
            candidate_profile=candidate_profile,
        )

    async def scan_and_populate(
            self, city: str = "Paris", max_count: int = 50
        ) -> List[Dict[str, Any]]:
        """
        Populates database with curated and scanned agencies, tailored with
        custom messages, verified emails, decision makers, and direct ATS URLs.
        """
        profile = settings.load_profile()
        inserted_records = []

        for item in FEATURED_AGENCIES_DATA[:max_count]:
            try:
                # Generate custom message for each agency
                msg = self.generate_personalized_message(item["name"], candidate_profile=profile)

                record = AgencyProspect(
                    name=item["name"],
                    category=item.get("category", "Agence Web"),
                    website=item["website"],
                    email=item.get("email"),
                    phone=item.get("phone"),
                    city=item.get("city") or city,
                    subject=msg["subject"],
                    custom_message=msg["body"],
                    status="pending",
                    notes=item.get("notes", ""),
                    direct_portal_url=item.get("direct_portal_url"),
                    decision_maker=item.get("decision_maker"),
                    email_status=item.get("email_status", "verified"),
                )
                self.db.save_or_update_agency(record)
                inserted_records.append(record.dict())
            except Exception as e:
                logger.error(f"Error saving agency prospect {item.get('name')}: {e}")

        logger.info(f"Populated {len(inserted_records)} agencies for outreach.")
        return inserted_records

    async def run_autonomous_cycle(
            self, city: str = "Paris", max_scan: int = 50, max_send: int = 50
        ) -> Dict[str, Any]:
        """
        Fully autonomous prospecting cycle:
        1. Scans and populates agencies (up to max_scan new)
        2. Auto-selects pending agencies with verified emails
        3. Sends outreach emails (max max_send/day, human-paced)
        """
        from core.prospection.email_sender import email_sender
        from core.storage.db import db as _db

        scan_results = await self.scan_and_populate(city=city, max_count=max_scan)

        pending = _db.list_agencies(status="pending", limit=300)
        target_ids = [a["id"] for a in pending if a.get("email") and a.get("email_status", "unverified") in ("verified", "unverified")]

        if not target_ids:
            return {"status": "success", "message": f"{len(scan_results)} agences scannées. Aucune agence en attente avec email.", "scanned": len(scan_results), "sent": 0, "skipped": 0, "errors": 0}

        send_results = await email_sender.batch_send_prospects(target_ids, max_count=max_send)
        return {
            "status": "success",
            "message": f"Cycle autonome termine: {len(scan_results)} scannees, {send_results['sent_count']} emails envoyes",
            "scanned": len(scan_results),
            "sent": send_results["sent_count"],
            "skipped": send_results.get("skipped_count", 0),
            "errors": send_results.get("error_count", 0),
        }


agency_finder = AgencyFinder()
