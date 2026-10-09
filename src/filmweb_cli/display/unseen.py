from rich.table import Table

from filmweb_cli.schemas.info.content_info import TitleInfo
from filmweb_cli.schemas.info.rating import ContentRating

from .console import console


def print_unseen(films: list[tuple[TitleInfo, ContentRating]]) -> None:
    if not films:
        console.print("[dim]No unseen titles found.[/dim]")
        console.print()
        return

    table = Table(box=None, show_header=True, header_style="bold", padding=(0, 2))
    table.add_column("Rate", justify="right")
    table.add_column("Votes", justify="right", style="dim")
    table.add_column("Year", style="dim")
    table.add_column("Title")
    table.add_column("ID", style="dim")

    for info, rating in films:
        title = info.title
        if info.original_title and info.original_title != info.title:
            title += f" [dim]({info.original_title})[/dim]"

        table.add_row(
            f"[bold magenta]{rating.rate:.2f}[/bold magenta]",
            str(rating.count),
            str(info.year or ""),
            title,
            str(info.id),
        )

    console.print(table)
    console.print()
