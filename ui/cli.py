import asyncio
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from config.settings import settings
from core.storage.db import db
from core.browser.session_setup import setup_platform_session
from core.watcher.watcher_service import watcher_service
from platforms.linkedin import LinkedInPlatform
from platforms.indeed import IndeedPlatform
from platforms.francetravail import FranceTravailPlatform

app = typer.Typer(
    help="🤖 Agent Intelligent de Veille & Candidature Automatisée (LinkedIn, Indeed, France Travail)",
    rich_markup_mode="rich",
)
console = Console()


@app.command("session")
def session_cmd(platform: str = typer.Argument("linkedin", help="Plateforme (linkedin, indeed ou francetravail)")):
    """Ouvre un navigateur pour enregistrer vos identifiants et cookies de session de manière persistante."""
    plat = platform.lower()
    if plat not in ["linkedin", "indeed", "francetravail"]:
        console.print("[red]Erreur : La plateforme doit être 'linkedin', 'indeed' ou 'francetravail'[/red]")
        raise typer.Exit(code=1)
    asyncio.run(setup_platform_session(plat))


@app.command("search")
def search_cmd(
    platform: str = typer.Option("linkedin", "--platform", "-p", help="Plateforme (linkedin, indeed ou francetravail)"),
    query: str = typer.Option("Développeur Python", "--query", "-q", help="Mots-clés de recherche"),
    location: str = typer.Option("Paris", "--location", "-l", help="Localisation"),
    limit: int = typer.Option(10, "--limit", "-n", help="Nombre d'offres à extraire"),
):
    """Recherche des offres sur la plateforme spécifiée et affiche les résultats."""
    async def _do_search():
        console.print(f"[bold cyan]🔍 Recherche sur {platform.upper()} : '{query}' à '{location}'...[/bold cyan]")
        if platform.lower() == "linkedin":
            plat = LinkedInPlatform()
        elif platform.lower() == "indeed":
            plat = IndeedPlatform()
        else:
            plat = FranceTravailPlatform()

        jobs = await plat.search_jobs(query=query, location=location, limit=limit)
        await plat.close()

        table = Table(title=f"Offres trouvées sur {platform.upper()} ({len(jobs)})", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Titre du poste", style="bold green")
        table.add_column("Entreprise", style="yellow")
        table.add_column("Lieu", style="cyan")
        table.add_column("Lien", style="blue")

        for idx, job in enumerate(jobs, 1):
            table.add_row(
                str(idx),
                job.title,
                job.company,
                job.location,
                job.url[:60] + "..." if len(job.url) > 60 else job.url,
            )
        console.print(table)

    asyncio.run(_do_search())


@app.command("watch")
def watch_cmd(
    interval: int = typer.Option(30, "--interval", "-i", help="Intervalle de scan en minutes"),
    once: bool = typer.Option(False, "--once", help="Effectuer un seul cycle de scan et quitter"),
):
    """Lance la veille automatique sur LinkedIn, Indeed et France Travail avec alertes IA."""
    async def _do_watch():
        console.print(Panel.fit(
            f"[bold green]📡 Démarrage du Service de Veille Automatique[/bold green]\n"
            f"[dim]Plateformes: LinkedIn, Indeed, France Travail | Intervalle: {interval} min | Scan unique: {once}[/dim]",
            title="AutoApply Watcher",
            border_style="cyan",
        ))

        if once:
            detected = await watcher_service.run_once()
            console.print(f"[bold green]✓ Cycle terminé : {len(detected)} nouvelle(s) offre(s) qualifiée(s).[/bold green]")
        else:
            await watcher_service.start(interval_minutes=interval)
            console.print("[yellow]Veille en cours... Appuyez sur Ctrl+C pour arrêter.[/yellow]")
            try:
                while watcher_service.is_running:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                await watcher_service.stop()
                console.print("\n[bold red]Veille arrêtée.[/bold red]")

    asyncio.run(_do_watch())


@app.command("run")
def run_cmd(
    platform: str = typer.Option("all", "--platform", "-p", help="Plateforme (linkedin, indeed, francetravail ou all)"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Nombre maximum de candidatures pour ce run"),
    headless: bool = typer.Option(False, "--headless", help="Exécuter le navigateur en arrière-plan (sans fenêtre)"),
):
    """Lance le cycle de candidature automatique assisté par IA."""
    settings.headless_browser = headless

    async def _do_run():
        console.print(Panel.fit(
            f"[bold green]🚀 Démarrage de l'Agent de Candidature[/bold green]\n"
            f"[dim]Plateforme: {platform.upper()} | Headless: {headless} | Mode validation: {settings.human_in_the_loop}[/dim]",
            title="Job Application Agent",
            border_style="green",
        ))

        platforms_to_run = []
        if platform.lower() in ["linkedin", "all"]:
            platforms_to_run.append(LinkedInPlatform())
        if platform.lower() in ["indeed", "all"]:
            platforms_to_run.append(IndeedPlatform())
        if platform.lower() in ["francetravail", "all"]:
            platforms_to_run.append(FranceTravailPlatform())

        for p in platforms_to_run:
            console.print(f"\n[bold yellow]─── Traitement de la plateforme : {p.platform_name.upper()} ───[/bold yellow]")
            results = await p.run(max_applications=limit)
            console.print(f"[bold green]Terminé pour {p.platform_name.upper()} : {len(results)} offres traitées.[/bold green]")
            await p.close()

    asyncio.run(_do_run())


@app.command("stats")
def stats_cmd():
    """Affiche les statistiques des candidatures et de la veille."""
    stats = db.get_stats()
    records = db.list_applications(limit=15)

    console.print(Panel(
        f"[bold white]Total opportunités & candidatures :[/bold white] [cyan]{stats['total_records']}[/cyan]\n"
        f"[bold white]Aujourd'hui envoyées :[/bold white] [green]{stats['today_applied']}[/green]\n"
        f"[bold white]Par statut :[/bold white] {stats['status_breakdown']}\n"
        f"[bold white]Par plateforme :[/bold white] {stats['platform_breakdown']}",
        title="📊 Statistiques Globales & Veille",
        border_style="cyan",
    ))

    table = Table(title="Dernières Opportunités / Candidatures", show_header=True, header_style="bold blue")
    table.add_column("ID", width=4)
    table.add_column("Plateforme", width=12)
    table.add_column("Poste", style="bold")
    table.add_column("Entreprise", style="yellow")
    table.add_column("Score IA", justify="center")
    table.add_column("Statut", justify="center")
    table.add_column("Date", style="dim")

    status_colors = {
        "applied": "[bold green]Postulé[/bold green]",
        "detected": "[bold purple]Détecté (Veille)[/bold purple]",
        "requires_review": "[bold yellow]À valider[/bold yellow]",
        "skipped": "[dim]Ignoré[/dim]",
        "failed": "[bold red]Échec[/bold red]",
        "found": "[cyan]Trouvé[/cyan]",
    }

    for r in records:
        table.add_row(
            str(r["id"]),
            r["platform"],
            r["job_title"],
            r["company"],
            f"{r['match_score']}%" if r["match_score"] is not None else "-",
            status_colors.get(r["status"], r["status"]),
            r["created_at"][:16].replace("T", " "),
        )
    console.print(table)


@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Hôte d'écoute"),
    port: int = typer.Option(8000, "--port", "-p", help="Port d'écoute"),
):
    """Lance le tableau de bord Web moderne pour gérer votre veille et postuler en direct."""
    import uvicorn
    console.print(f"[bold green]🌐 Lancement du Dashboard Web sur http://{host}:{port}[/bold green]")
    uvicorn.run("ui.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
