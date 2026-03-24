from decimal import Decimal

from report.text_formatting import format_cargo_for_cell, format_ton, kg_to_t


def test_format_cargo_for_cell_breaks_on_capitalized_words():
    text = "уголь Каменный МаркаД"
    got = format_cargo_for_cell(text)
    assert got == "уголь <br/>Каменный <br/>МаркаД"


def test_format_cargo_for_cell_escapes_html():
    got = format_cargo_for_cell("Песок <мытый>")
    assert "&lt;мытый&gt;" in got


def test_format_ton_trims_trailing_zeroes():
    assert format_ton(Decimal("1.200")) == "1,2"
    assert format_ton(Decimal("2.000")) == "2"
    assert format_ton(Decimal("0.125")) == "0,125"


def test_kg_to_t_conversion():
    assert kg_to_t(0) == ""
    assert kg_to_t(1000) == "1"
    assert kg_to_t(1250) == "1,25"
