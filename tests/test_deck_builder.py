from commands.deck_builder import generate_identifier


def test_generate_identifier() -> None:
    """Test for generate_identifier."""
    for _ in range(10):
        assert len(str(generate_identifier())) == 10
