"""R11: share-link signatures."""

from app.cards.share import sign, verify


def test_signed_link_round_trips():
    token = sign("123", 2000000000)
    assert verify(token) == ("123", 2000000000)


def test_tampered_links_fail():
    token = sign("123", 2000000000)
    assert verify(token.replace("123", "124", 1)) is None
    assert verify(token.replace(".2000000000.", ".2000000001.")) is None
    assert verify("garbage") is None
