#!/usr/bin/env python3
"""
Sentencing Council Guideline Scraper

Crawls the UK Sentencing Council website to extract structured sentencing
guideline data for all offences (magistrates' court and Crown Court).

Usage:
    python main.py                      # Scrape all guidelines
    python main.py --court magistrates  # Scrape only magistrates' court
    python main.py --court crown        # Scrape only Crown Court
    python main.py --url URL            # Scrape a single guideline page
    python main.py --list-only          # Just list discovered offences
    python main.py --output data/out    # Custom output directory
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from scraper.crawler import SentencingCrawler
from scraper.parser import GuidelineParser
from scraper.models import Guideline
from scraper.export import (
    export_json,
    export_individual_json,
    export_csv_summary,
    export_offence_index,
)
from scraper.config import OUTPUT_DIR

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def scrape_single_url(url: str, court_type: str = "") -> Guideline:
    """Scrape a single guideline page."""
    crawler = SentencingCrawler()
    soup = crawler.get_soup(url)
    parser = GuidelineParser(soup, url, court_type)
    return parser.parse()


def scrape_all(
    court_filter: str = "",
    output_dir: str = OUTPUT_DIR,
    list_only: bool = False,
    delay: float = 1.0,
    limit: int = 0,
) -> list[Guideline]:
    """Scrape all guidelines from the Sentencing Council website."""
    crawler = SentencingCrawler(delay=delay)

    # Step 1: Discover all offence links
    console.print("\n[bold blue]Step 1:[/] Discovering offence guidelines...\n")

    offences = crawler.discover_all_offences()

    # Filter by court type if requested (keep unknowns for post-scrape filtering)
    filter_after_scrape = False
    if court_filter:
        filtered = [
            o for o in offences
            if court_filter.lower() in o.court_type.lower()
            or o.court_type in ("all", "both")
        ]
        unknown = [
            o for o in offences
            if not o.court_type or o.court_type.lower() == "unknown"
        ]
        if unknown:
            filter_after_scrape = True
        offences = filtered + unknown

    if not offences:
        console.print("[red]No offences found. The website structure may have changed.[/]")
        console.print("Try running with --url to scrape a specific guideline page.")
        return []

    # Display discovered offences
    table = Table(title=f"Discovered {len(offences)} Offences")
    table.add_column("Offence", style="cyan")
    table.add_column("Court", style="green")
    table.add_column("Category", style="yellow")
    for o in offences:
        table.add_row(o.name, o.court_type, o.category)
    console.print(table)

    if list_only:
        return []

    if limit and limit > 0:
        offences = offences[:limit]
        console.print(f"[yellow]Limiting to first {len(offences)} offences.[/]")

    # Step 2: Scrape each guideline page
    console.print(f"\n[bold blue]Step 2:[/] Scraping {len(offences)} guideline pages...\n")

    guidelines = []
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping guidelines", total=len(offences))

        for offence in offences:
            try:
                progress.update(task, description=f"Scraping: {offence.name[:50]}")
                soup = crawler.get_soup(offence.url)
                parser = GuidelineParser(soup, offence.url, offence.court_type)
                guideline = parser.parse()
                guidelines.append(guideline)
            except Exception as e:
                errors.append({"offence": offence.name, "url": offence.url, "error": str(e)})
                logging.getLogger(__name__).warning(f"Failed to scrape {offence.name}: {e}")
            finally:
                progress.advance(task)

    # Step 3: Export results
    if court_filter and filter_after_scrape:
        before = len(guidelines)
        guidelines = [
            g for g in guidelines
            if court_filter.lower() in g.court_type.lower()
            or g.court_type in ("all", "both")
        ]
        console.print(
            f"\n[bold blue]Step 2b:[/] Filtered after scrape: {before} → {len(guidelines)}\n"
        )
    console.print(f"\n[bold blue]Step 3:[/] Exporting {len(guidelines)} guidelines...\n")

    export_json(guidelines, f"{output_dir}/guidelines.json")
    export_individual_json(guidelines, f"{output_dir}/guidelines")
    export_csv_summary(guidelines, f"{output_dir}/sentencing_ranges.csv")
    export_offence_index(guidelines, f"{output_dir}/offence_index.json")

    # Summary
    console.print(f"\n[bold green]Done![/]")
    console.print(f"  Successfully scraped: {len(guidelines)} guidelines")
    console.print(f"  Failed: {len(errors)} guidelines")
    console.print(f"  Output directory: {output_dir}/")

    if errors:
        console.print(f"\n[yellow]Failed offences:[/]")
        for err in errors:
            console.print(f"  - {err['offence']}: {err['error']}")

        # Save errors for debugging
        errors_path = f"{output_dir}/errors.json"
        with open(errors_path, "w") as f:
            json.dump(errors, f, indent=2)

    return guidelines


def main():
    parser = argparse.ArgumentParser(
        description="Scrape sentencing guidelines from the UK Sentencing Council website",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--court",
        choices=["magistrates", "crown", "all"],
        default="all",
        help="Which court's guidelines to scrape (default: all)",
    )
    parser.add_argument(
        "--url",
        help="Scrape a single guideline page URL",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list discovered offences, don't scrape details",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of offences to process (0 = no limit)",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    console.print("[bold]Sentencing Council Guideline Scraper[/]")
    console.print("=" * 45)

    if args.url:
        # Single page mode
        console.print(f"\nScraping: {args.url}")
        guideline = scrape_single_url(args.url, args.court)

        output_path = f"{args.output}/single_guideline.json"
        Path(args.output).mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(guideline.to_json())

        console.print(f"\n[green]Saved to {output_path}[/]")
        console.print(f"  Offence: {guideline.offence_name}")
        console.print(f"  Sentencing ranges: {len(guideline.sentencing_ranges)}")
        console.print(f"  Aggravating factors: {len(guideline.aggravating_factors)}")
        console.print(f"  Mitigating factors: {len(guideline.mitigating_factors)}")
    else:
        # Full scrape mode
        court_filter = "" if args.court == "all" else args.court
        scrape_all(
            court_filter=court_filter,
            output_dir=args.output,
            list_only=args.list_only,
            delay=args.delay,
            limit=args.limit,
        )


if __name__ == "__main__":
    main()
