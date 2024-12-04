"""Deck Builder Command.

Imports a markdown file and creates a deck of
anki cards. The files are of the following format:

# Deck Name

## Sub Deck

### Question

- Content
- In the
- Answers
"""

import os
import secrets

import bs4
import click
import genanki  # type: ignore
import markdown
from bs4 import BeautifulSoup
from pydantic import BaseModel


def generate_identifier() -> int:
    """Generates a random identifier.

    ex. 1607392319, 2059400110, 1091735104
    """
    return 999_999_999 + secrets.randbelow(1_000_000_000)


class Model(BaseModel):
    """Builder model."""

    id: int


class Card(Model):
    """Create card object."""

    front: str
    back: str
    tags: list[str] = []


class Deck(Model):
    """Create deck object."""

    name: str
    sub_decks: list["SubDeck"] = []

    def add_subdeck(self, subdeck: "SubDeck") -> None:
        """Add a subdeck to the deck."""
        self.sub_decks.append(subdeck)

    @property
    def file_name(self) -> str:
        """Sanitize name of the deck."""
        return self.name.replace(" ", "-").lower()


class SubDeck(Deck):
    """Create subdeck object."""

    cards: list[Card] = []

    def add_card(self, card: Card) -> None:
        """Add a card to the subdeck."""
        self.cards.append(card)


class Builder:
    """Deck Builder class."""

    soup: BeautifulSoup
    raw_contents: str
    _html: str

    def __init__(self, content: str) -> None:
        """Deck Builder."""
        self.raw_contents = content
        self._html = self.__class__.create_tree(content)
        self.soup = BeautifulSoup(self._html, "html.parser")

    @property
    def html(self) -> str:
        """Return the HTML content."""
        return self.soup.prettify(formatter="html5")

    @property
    def model(self) -> genanki.Model:
        """Return the model."""
        return genanki.Model(
            generate_identifier(),
            "Simple Model",
            fields=[{"name": "Question"}, {"name": "Answer"}],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Question}}",
                    "afmt": "{{FrontSide}}<hr id='answer'>{{Answer}}",
                }
            ],
        )

    @property
    def dom(self) -> str:
        """Return the DOM content."""
        return self.soup.prettify(formatter="html5")

    @classmethod
    def create_tree(cls: type["Builder"], content: str) -> str:
        """Create a DOM tree from a markdown file."""
        return markdown.markdown(content)

    @classmethod
    def from_file(cls: type["Builder"], fpath: str) -> "Builder":
        """Create a deck from a markdown file."""
        with open(fpath) as file:
            return cls(content=file.read())

    def format_ul(self, ul: BeautifulSoup) -> str:
        """Format the ul element.

        Example:
            <ul>
                Top Level Note
                <li>Sub Note</li>
                <li>Sub Note</li>
            </ul>

            OR

            <ul>
                <li>Top Level Note</li>
                <li>Top Level Note</li>
            </ul>

        Returns:
            - Top Level Note
                - Sub Note
                - Sub Note

            OR

            - Top Level Note
            - Top Level Note
        """
        if not ul:
            return ""

        formatted = ""

        if top_level := ul.find("li"):
            formatted += f"{top_level.text.removesuffix("\n\n\n")}\n"
            for sub_note in top_level.find_next_siblings("li"):
                formatted += f"\t- {sub_note.text}\n"
        else:
            for top_level in ul.find_all("li"):
                if not top_level:
                    continue

                formatted += f"{top_level.text}\n"

        return formatted

    def create_subdeck(self, h2_el: bs4.PageElement) -> SubDeck:
        """Create a subdeck from the h2 element."""
        subdeck_id = generate_identifier()
        subdeck_name = h2_el.text
        click.echo(f"Subdeck: {subdeck_name}")
        return SubDeck(id=subdeck_id, name=subdeck_name)

    def create_note(self, h3_el: bs4.PageElement) -> Card:
        """Create a note from the h3 element."""
        card_id = generate_identifier()
        card_front = h3_el.text
        card_information = h3_el.find_next_sibling("ul")

        if card_information is None:
            raise ValueError

        card_back = self.format_ul(
            BeautifulSoup(
                str(card_information),
                "html.parser",
            )
        )

        click.echo(f"Card: {card_front}")
        return Card(id=card_id, front=card_front, back=card_back)

    def export(self, deck: Deck) -> None:
        """Export to file."""
        genanki.Deck(deck.id, deck.name)
        anki_model = self.model

        for subdeck in deck.sub_decks:
            subdeck_name = f"{deck.name}::{subdeck.name}"
            anki_subdeck = genanki.Deck(subdeck.id, subdeck_name)

            for card in subdeck.cards:
                anki_card = genanki.Note(
                    model=anki_model,
                    fields=[card.front, card.back],
                    tags=card.tags,
                )
                anki_subdeck.add_note(anki_card)

        genanki.Package(anki_subdeck).write_to_file(f"dist/{deck.file_name}.apkg")

    def parse_notes(self, h2: bs4.PageElement) -> list[Card]:
        """Parse notes from the h2 element."""
        notes = []
        for sibling in h2.find_next_siblings():
            if not isinstance(sibling, bs4.Tag):
                continue

            if sibling.name == "h2":
                break
            if sibling.name != "h3":
                continue

            note = self.create_note(sibling)
            notes.append(note)

        return notes

    def build_deck(self) -> Deck:
        """Start deck creation."""
        h1 = self.soup.find("h1")
        if not isinstance(h1, bs4.Tag):
            raise ValueError

        return Deck(id=generate_identifier(), name=h1.text)

    def build_subdecks(self) -> list[SubDeck]:
        """Build subdecks."""
        subdecks = []

        for h2_element in self.soup.find_next_siblings("h2"):
            subdeck = self.create_subdeck(h2_element)
            subdeck.cards = self.parse_notes(h2_element)
            subdecks.append(subdeck)

        h2s: list[bs4.Tag] = self.soup.find_all("h2")

        for h2 in h2s:
            subdeck = self.create_subdeck(h2)
            subdeck.cards = self.parse_notes(h2)
            subdecks.append(subdeck)

        return subdecks

    def traverse(self) -> Deck:
        """Traverse the DOM tree."""
        deck = self.build_deck()
        click.echo(f"Deck: {deck.name}")

        for subdeck in self.build_subdecks():
            deck.add_subdeck(subdeck)

        if not os.path.exists("dist") or not os.path.isdir("dist"):
            os.mkdir("dist")

        return deck

    def __call__(self) -> None:
        """Run the builder."""
        deck = self.traverse()
        self.export(deck)


@click.command(name="read", help="Read markdown file.")
@click.option(
    "--file-path",
    "--file",
    "-f",
    "-p",
    help="Path to markdown file.",
    type=click.Path(exists=True),
    required=True,
)
def build(file_path: str) -> None:
    """Read markdown file."""
    builder = Builder.from_file(file_path)
    builder()
