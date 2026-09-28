import re
import os
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List
import pypdf

from config.settings import BASE_DIR, settings, UserProfile, SearchCriteria, RESUMES_DIR
from .llm_client import llm_client

logger = logging.getLogger("ProfileAnalyzer")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


class ProfileAnalyzer:
    """
    Automated profile ingestion engine.
    Extracts structured professional identity, skills, technologies,
    and search criteria from Portfolio URLs, LinkedIn URLs, and PDF Resumes.
    """

    def __init__(self):
        self.llm = llm_client

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extracts plain text from a local PDF resume."""
        path = Path(pdf_path)
        if not path.is_absolute():
            path = BASE_DIR / pdf_path
        if not path.exists():
            return ""

        try:
            reader = pypdf.PdfReader(str(path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages_text).strip()
        except Exception as e:
            logger.warning(f"Failed to extract PDF text from {pdf_path}: {e}")
            return ""

    def scrape_portfolio(self, url: str) -> Dict[str, Any]:
        """
        Scrapes a candidate's portfolio website (e.g. hermes-commander-site.vercel.app).
        Extracts meta tags, headings, projects, stacks, and text content.
        """
        if not url:
            return {}

        clean_url = url.strip()
        if not clean_url.startswith("http"):
            clean_url = "https://" + clean_url

        try:
            req = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_m.group(1).strip() if title_m else ""

            desc_m = re.search(r'<meta[^>]*name=[\"\']description[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else ""

            keywords_m = re.search(r'<meta[^>]*name=[\"\']keywords[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
            keywords = [k.strip() for k in keywords_m.group(1).split(",")] if keywords_m else []

            # If it's a SPA with assets bundle (like hermes-commander-site.vercel.app with main-xxx.js)
            js_bundles = re.findall(r'src=[\"\'](/assets/[^\"\']+\.js)[\"\']', html)
            projects_data = []
            extracted_techs = set()

            for bundle in js_bundles[:2]:
                bundle_url = urllib.parse.urljoin(clean_url, bundle)
                try:
                    b_req = urllib.request.Request(bundle_url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(b_req, timeout=8) as b_resp:
                        bundle_code = b_resp.read().decode("utf-8", errors="ignore")
                        
                        # Extract project stacks
                        stacks = re.findall(r'stack:\[(.*?)\]', bundle_code)
                        for s in stacks:
                            for item in s.split(","):
                                val = item.strip(" \"'")
                                if len(val) > 1 and len(val) < 35:
                                    extracted_techs.add(val)
                        
                        # Extract project titles
                        pos = 0
                        while True:
                            m = re.search(r'title:\"([^\"]+)\",client:\"([^\"]+)\",subtitle:\"([^\"]+)\"', bundle_code[pos:])
                            if not m:
                                break
                            p_title, p_client, p_sub = m.group(1), m.group(2), m.group(3)
                            projects_data.append(f"{p_title} ({p_client}) : {p_sub}")
                            pos += m.end()
                            if len(projects_data) >= 10:
                                break
                except Exception as b_err:
                    logger.debug(f"Bundle scrape note: {b_err}")

            return {
                "url": clean_url,
                "meta_title": title,
                "meta_description": desc,
                "meta_keywords": keywords,
                "projects": projects_data,
                "extracted_technologies": sorted(list(extracted_techs)),
            }
        except Exception as e:
            logger.warning(f"Error scraping portfolio {url}: {e}")
            return {"url": clean_url, "error": str(e)}

    def scrape_linkedin_public(self, url: str) -> Dict[str, Any]:
        """
        Extracts public information from candidate LinkedIn URL.
        """
        if not url:
            return {}

        clean_url = url.strip()
        if not clean_url.startswith("http"):
            clean_url = "https://" + clean_url

        try:
            req = urllib.request.Request(clean_url, headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            title_m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            raw_title = title_m.group(1).strip() if title_m else ""
            
            desc_m = re.search(r'<meta[^>]*property=[\"\']og:description[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else ""

            return {
                "url": clean_url,
                "headline": raw_title,
                "summary": desc,
            }
        except Exception as e:
            logger.warning(f"LinkedIn public fetch note: {e}")
            return {"url": clean_url}

    def scrape_github_public(self, url: str) -> Dict[str, Any]:
        """
        Extracts public profile, repositories, languages, and topics from a candidate's GitHub URL or username.
        """
        if not url or not url.strip():
            return {}

        raw = url.strip()
        # Clean username from URL
        clean_user = re.sub(r"^https?://(www\.)?github\.com/", "", raw, flags=re.IGNORECASE)
        username = clean_user.split("/")[0].strip("@/ ")
        if not username:
            return {}

        clean_url = f"https://github.com/{username}"
        github_data: Dict[str, Any] = {
            "url": clean_url,
            "username": username,
            "name": "",
            "bio": "",
            "company": "",
            "location": "",
            "blog": "",
            "public_repos_count": 0,
            "top_languages": [],
            "repositories": [],
        }

        # 1. Try public GitHub REST API
        try:
            api_user_url = f"https://api.github.com/users/{username}"
            req = urllib.request.Request(api_user_url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    user_json = json.loads(resp.read().decode("utf-8"))
                    github_data["name"] = user_json.get("name") or username
                    github_data["bio"] = user_json.get("bio") or ""
                    github_data["company"] = user_json.get("company") or ""
                    github_data["location"] = user_json.get("location") or ""
                    github_data["blog"] = user_json.get("blog") or ""
                    github_data["public_repos_count"] = user_json.get("public_repos", 0)

            # Fetch top repositories
            api_repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=12"
            req_repos = urllib.request.Request(api_repos_url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            })
            with urllib.request.urlopen(req_repos, timeout=8) as resp_repos:
                if resp_repos.status == 200:
                    repos_json = json.loads(resp_repos.read().decode("utf-8"))
                    languages = set()
                    repos_summary = []
                    for r in repos_json:
                        if r.get("fork"):
                            continue
                        lang = r.get("language")
                        if lang:
                            languages.add(lang)
                        topics = r.get("topics") or []
                        for t in topics:
                            if len(t) > 1:
                                languages.add(t)
                        repos_summary.append({
                            "name": r.get("name"),
                            "description": r.get("description") or "",
                            "language": lang,
                            "stars": r.get("stargazers_count", 0),
                            "topics": topics[:5],
                        })
                    github_data["top_languages"] = sorted(list(languages))
                    github_data["repositories"] = repos_summary[:8]
            return github_data
        except Exception as e:
            logger.debug(f"GitHub API fetch note ({e}), falling back to public profile scraping")

        # 2. Fallback: scrape public HTML page
        try:
            req_html = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req_html, timeout=8) as resp_html:
                html = resp_html.read().decode("utf-8", errors="ignore")

            name_m = re.search(r'<span[^>]*itemprop=[\"\']name[\"\'][^>]*>([^<]+)</span>', html)
            if name_m:
                github_data["name"] = name_m.group(1).strip()
            
            bio_m = re.search(r'<div[^>]*class=[\"\'][^\"\']*user-profile-bio[^\"\']*[\"\'][^>]*>(.*?)</div>', html, re.DOTALL)
            if bio_m:
                github_data["bio"] = re.sub(r'<[^>]+>', '', bio_m.group(1)).strip()

            # Pinned / popular repositories
            repo_names = re.findall(r'<span[^>]*class=[\"\']repo[\"\'][^>]*>([^<]+)</span>', html)
            langs = re.findall(r'<span[^>]*itemprop=[\"\']programmingLanguage[\"\'][^>]*>([^<]+)</span>', html)
            github_data["top_languages"] = sorted(list(set(langs)))
            github_data["repositories"] = [{"name": n} for n in repo_names[:6]]

            return github_data
        except Exception as err:
            logger.warning(f"Error scraping GitHub profile for {username}: {err}")
            return github_data

    def scrape_website_public(self, url: str) -> Dict[str, Any]:
        """
        Scrapes a candidate's personal website or blog (meta tags, headings, about content).
        """
        if not url or not url.strip():
            return {}

        clean_url = url.strip()
        if not clean_url.startswith("http"):
            clean_url = "https://" + clean_url

        try:
            req = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
            title = title_m.group(1).strip() if title_m else ""

            desc_m = re.search(r'<meta[^>]*name=[\"\']description[\"\'][^>]*content=[\"\']([^\"\']+)[\"\']', html, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else ""

            headings = re.findall(r'<h[1-3][^>]*>(.*?)</h[1-3]>', html, re.IGNORECASE)
            clean_headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings if len(re.sub(r'<[^>]+>', '', h).strip()) > 3][:8]

            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE)
            clean_p = [re.sub(r'<[^>]+>', '', p).strip() for p in paragraphs if len(re.sub(r'<[^>]+>', '', p).strip()) > 20][:5]

            return {
                "url": clean_url,
                "title": title,
                "description": desc,
                "headings": clean_headings,
                "snippets": clean_p,
            }
        except Exception as e:
            logger.warning(f"Error scraping personal website {url}: {e}")
            return {"url": clean_url, "error": str(e)}

    def analyze_profile(
        self,
        portfolio_url: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        github_url: Optional[str] = None,
        website_url: Optional[str] = None,
        resume_filename: Optional[str] = None,
        additional_notes: Optional[str] = None,
    ) -> tuple[UserProfile, SearchCriteria]:
        """
        Analyzes multi-source candidate inputs (Portfolio, LinkedIn, GitHub, Website, PDF Resume, Notes)
        and builds calibrated UserProfile and SearchCriteria suitable for any user.
        """
        scraped_portfolio = self.scrape_portfolio(portfolio_url) if portfolio_url else {}
        scraped_linkedin = self.scrape_linkedin_public(linkedin_url) if linkedin_url else {}
        scraped_github = self.scrape_github_public(github_url) if github_url else {}
        scraped_website = self.scrape_website_public(website_url) if website_url else {}

        # Resume text
        resume_text = ""
        resume_path = None
        if resume_filename:
            path = RESUMES_DIR / resume_filename
            if not path.exists() and Path(resume_filename).is_absolute():
                path = Path(resume_filename)
            if not path.exists():
                candidate = BASE_DIR / resume_filename
                if candidate.exists():
                    path = candidate

            if path.exists():
                try:
                    resume_path = str(path.relative_to(BASE_DIR))
                except ValueError:
                    resume_path = str(path)
                resume_text = self.extract_text_from_pdf(str(path))
        else:
            # Check if an existing PDF is in RESUMES_DIR
            existing_pdfs = list(RESUMES_DIR.glob("*.pdf"))
            if existing_pdfs:
                # pick the most recently modified
                most_recent = max(existing_pdfs, key=lambda p: p.stat().st_mtime)
                try:
                    resume_path = str(most_recent.relative_to(BASE_DIR))
                except ValueError:
                    resume_path = str(most_recent)
                resume_text = self.extract_text_from_pdf(str(most_recent))

        # Combine all prompt data
        prompt_data = {
            "portfolio_url": portfolio_url,
            "portfolio_data": scraped_portfolio,
            "linkedin_url": linkedin_url,
            "linkedin_data": scraped_linkedin,
            "github_url": github_url,
            "github_data": scraped_github,
            "website_url": website_url,
            "website_data": scraped_website,
            "resume_text": resume_text[:4000] if resume_text else None,
            "additional_notes": additional_notes,
        }

        system_prompt = (
            "Tu es un expert en recrutement tech et talent acquisition de très haut niveau. "
            "Analyse minutieusement toutes les données fournies pour CE candidat (CV, GitHub, Portfolio, LinkedIn, Site Web, Notes) "
            "et extrais un profil professionnel complet, authentique et personnalisé, ainsi que des critères de recherche d'offres parfaitement calibrés. "
            "Ne préremplis PAS avec des données fictives ou d'autres personnes : base-toi rigoureusement sur les informations extraites des documents et URLs du candidat. "
            "Tu dois OBLIGATOIREMENT répondre sous la forme d'un objet JSON strict respectant ce schéma :\n"
            "{\n"
            '  "first_name": "Prénom du candidat",\n'
            '  "last_name": "Nom du candidat",\n'
            '  "email": "email@example.com",\n'
            '  "phone_number": "0600000000",\n'
            '  "city": "Ville (ex: Paris, Lyon...)",\n'
            '  "country": "France",\n'
            '  "current_title": "Intitulé précis du poste (ex: Développeur Full Stack Python / React, Lead DevOps, AI Engineer...)",\n'
            '  "total_years_experience": 3,\n'
            '  "summary": "Résumé professionnel percutant et valorisant (2-3 phrases)",\n'
            '  "skills": ["Compétence 1", "Compétence 2", "Compétence 3", ...],\n'
            '  "target_search_keywords": ["Mot-clé recherche 1", "Mot-clé 2", "Mot-clé 3", ...],\n'
            '  "locations": ["Ville, France", "Remote", "Région"],\n'
            '  "contract_types": ["CDI", "Freelance"]\n'
            "}"
        )

        try:
            raw = self.llm.generate_text(
                prompt=f"Données du profil candidat à analyser :\n{json.dumps(prompt_data, ensure_ascii=False, indent=2)}",
                system_prompt=system_prompt,
                json_mode=True,
            )
            clean = raw.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean)

            # Resolve coordinates and identity safely
            f_name = parsed.get("first_name") or ""
            l_name = parsed.get("last_name") or ""
            if not f_name and not l_name:
                gh_name = scraped_github.get("name") or ""
                if " " in gh_name:
                    parts = gh_name.split(" ", 1)
                    f_name, l_name = parts[0], parts[1]
                elif gh_name:
                    f_name = gh_name

            # Construct UserProfile
            profile = UserProfile(
                first_name=f_name or "Candidat",
                last_name=l_name or "",
                email=parsed.get("email") or "candidat@example.com",
                phone_country_code="+33",
                phone_number=parsed.get("phone_number") or "",
                city=parsed.get("city") or scraped_github.get("location") or "Paris",
                country=parsed.get("country") or "France",
                postal_code="75000",
                address=parsed.get("city") or "France",
                current_title=parsed.get("current_title") or "Développeur Full Stack",
                total_years_experience=int(parsed.get("total_years_experience") or 3),
                linkedin_url=linkedin_url or scraped_linkedin.get("url"),
                github_url=github_url or scraped_github.get("url"),
                portfolio_url=portfolio_url or scraped_portfolio.get("url"),
                summary=parsed.get("summary") or (f"Professionnel passionné spécialisé en {', '.join(parsed.get('skills', [])[:5])}"),
                skills=parsed.get("skills") or [
                    "Python", "JavaScript", "TypeScript", "React", "Node.js", "Docker", "Git", "SQL"
                ],
                languages={"Français": "Natif", "Anglais": "Professionnel (B2/C1)"},
                work_authorization_eu=True,
                requires_sponsorship=False,
                salary_expectation_annual_eur=50000,
                notice_period_weeks=0,
                willing_to_relocate=False,
                custom_qa={
                    "permis": "Oui",
                    "disponibilite": "Immédiate",
                    "statut": "Cadre / Indépendant",
                },
                resume_path=resume_path,
            )

            # Construct SearchCriteria
            keywords = parsed.get("target_search_keywords")
            if not keywords or len(keywords) == 0:
                keywords = [profile.current_title]
                if profile.skills:
                    keywords.append(f"{profile.skills[0]} Developer")

            criteria = SearchCriteria(
                keywords=keywords[:8],
                locations=parsed.get("locations") or [f"{profile.city}, France", "Remote", "France"],
                remote_only=False,
                contract_types=parsed.get("contract_types") or ["CDI", "Freelance"],
                min_match_score=60,
                min_alert_score=80,
                max_applications_per_day=25,
                easy_apply_only=True,
                blacklisted_companies=[],
                blacklisted_keywords=["Stage", "Alternance", "Senior 15+ ans"],
            )

            return profile, criteria

        except Exception as e:
            logger.warning(f"LLM profile analysis fallback note ({e}), extracting features with heuristic parsing.")
            
            # Universal heuristic fallback: extract from CV text, GitHub and URLs
            full_text = f"{resume_text}\n{json.dumps(scraped_github)}\n{json.dumps(scraped_portfolio)}\n{additional_notes or ''}"
            
            # Email extraction
            email_m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', full_text)
            extracted_email = email_m.group(0) if email_m else "candidat@example.com"
            
            # Phone extraction
            phone_m = re.search(r'(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}', full_text)
            extracted_phone = re.sub(r'[\s.-]', '', phone_m.group(0)) if phone_m else ""

            # Name extraction
            candidate_name = scraped_github.get("name") or ""
            if not candidate_name and resume_text:
                first_lines = [l.strip() for l in resume_text.splitlines() if len(l.strip()) > 2 and len(l.strip()) < 50]
                if first_lines:
                    candidate_name = first_lines[0]
            
            f_name, l_name = "Candidat", ""
            if candidate_name and " " in candidate_name:
                parts = candidate_name.split(" ", 1)
                f_name, l_name = parts[0], parts[1]
            elif candidate_name:
                f_name = candidate_name

            # Tech skills extraction
            tech_keywords = [
                "Python", "JavaScript", "TypeScript", "React", "Next.js", "Vue", "Angular",
                "Node.js", "FastAPI", "Django", "Flask", "Docker", "Kubernetes", "SQL",
                "PostgreSQL", "MongoDB", "Artificial Intelligence", "LLM", "AI Agents", "MCP", "DeepSeek", "OpenRouter",
                "Figma", "UI/UX", "AWS", "GCP", "Azure", "Git", "CI/CD", "Playwright",
                "C++", "Java", "Go", "Rust", "PHP", "Symfony", "Laravel", "Linux"
            ]
            found_skills = [tk for tk in tech_keywords if re.search(r'\b' + re.escape(tk) + r'\b', full_text, re.IGNORECASE)]
            if scraped_github.get("top_languages"):
                found_skills = sorted(list(set(found_skills + scraped_github["top_languages"])))
            if scraped_portfolio.get("extracted_technologies"):
                found_skills = sorted(list(set(found_skills + scraped_portfolio["extracted_technologies"])))

            if not found_skills:
                found_skills = ["Python", "JavaScript", "React", "Docker", "Git"]

            # Title extraction
            title = "Lead Developer & AI Systems Engineer"
            if "ai engineer" in full_text.lower() or "agent" in full_text.lower() or "mcp" in full_text.lower():
                title = "Lead Developer & AI Systems Engineer"
            elif "devops" in full_text.lower() or "cloud" in full_text.lower():
                title = "Ingénieur DevOps / Cloud & AI"
            elif "data" in full_text.lower():
                title = "AI Data Engineer / Python"
            elif "front" in full_text.lower():
                title = "Développeur Full-Stack Web"

            profile = UserProfile(
                first_name=f_name,
                last_name=l_name,
                email=extracted_email,
                phone_country_code="+33",
                phone_number=extracted_phone,
                city="Paris",
                country="France",
                postal_code="75000",
                address="Paris",
                current_title=title,
                total_years_experience=3,
                linkedin_url=linkedin_url or "https://www.linkedin.com/",
                github_url=github_url or scraped_github.get("url") or "https://github.com/",
                portfolio_url=portfolio_url or scraped_portfolio.get("url") or website_url or "",
                summary=f"{title} expérimenté avec une maîtrise approfondie de {', '.join(found_skills[:6])}.",
                skills=found_skills,
                languages={"Français": "Natif", "Anglais": "Professionnel (B2/C1)"},
                work_authorization_eu=True,
                requires_sponsorship=False,
                salary_expectation_annual_eur=50000,
                notice_period_weeks=0,
                willing_to_relocate=False,
                custom_qa={
                    "permis": "Oui",
                    "disponibilite": "Immédiate",
                    "statut": "Cadre / Indépendant",
                },
                resume_path=resume_path,
            )

            criteria = SearchCriteria(
                keywords=[
                    title,
                    f"Développeur {found_skills[0]}",
                    f"Développeur {found_skills[1]}" if len(found_skills) > 1 else "Software Engineer",
                    "Full Stack Developer",
                ],
                locations=["Paris, France", "Remote", "Île-de-France"],
                remote_only=False,
                contract_types=["CDI", "Freelance"],
                min_match_score=60,
                min_alert_score=80,
                max_applications_per_day=25,
                easy_apply_only=True,
                blacklisted_companies=[],
                blacklisted_keywords=["Stage", "Alternance"],
            )

            return profile, criteria

    def apply_and_save_profile(
        self,
        portfolio_url: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        github_url: Optional[str] = None,
        website_url: Optional[str] = None,
        resume_filename: Optional[str] = None,
        additional_notes: Optional[str] = None,
    ) -> tuple[UserProfile, SearchCriteria]:
        """Runs profile analysis across all 5 sources and saves into settings/yaml files."""
        profile, criteria = self.analyze_profile(
            portfolio_url=portfolio_url,
            linkedin_url=linkedin_url,
            github_url=github_url,
            website_url=website_url,
            resume_filename=resume_filename,
            additional_notes=additional_notes,
        )
        settings.save_profile(profile)
        settings.save_search_criteria(criteria)
        logger.info(f"Profile saved for {profile.first_name} {profile.last_name} ({profile.current_title})")
        return profile, criteria


profile_analyzer = ProfileAnalyzer()

