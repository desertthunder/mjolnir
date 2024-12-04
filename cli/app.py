"""Click application."""

import click

from commands.deck_builder import build


@click.group()
def main() -> None:
    """Run the application."""
    click.echo("Mjolnir...⚡️")


main.add_command(build)


def run_app() -> None:
    """Run the application."""
    main()
