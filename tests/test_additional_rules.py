from decimal import Decimal

from parser.models import WeighingData
from report.additional_rules import apply_additional_formula
from report.weighing_print_data import WeighingPrintData


def _wd(
    *,
    tara: int,
    brutto: int,
    netto: int,
    adjusted: int = 0,
    price: str = "16000",
    amount: str = "0",
) -> WeighingData:
    return WeighingData(
        weighing_number="100",
        plate_number="851EM02",
        tara_kg=tara,
        brutto_kg=brutto,
        netto_kg=netto,
        cargo="Уголь",
        counterparty="Тест",
        invoice_number="100",
        price_per_ton=Decimal(price),
        amount=Decimal(amount),
        weighing_datetime=None,
        user="u",
        message_sent_at=None,
        adjusted_netto_kg=adjusted,
    )


def test_apply_additional_formula_uses_previous_effective_brutto() -> None:
    prev = _wd(tara=18000, brutto=45000, netto=27000, adjusted=28000)
    curr = _wd(tara=19000, brutto=47000, netto=26000, adjusted=0, price="20000")

    out = apply_additional_formula(curr, prev)

    # previous effective brutto = prev.tara + prev.adjusted = 46000
    assert out.tara_kg == 46000
    assert out.netto_kg == 26000
    assert out.brutto_kg == 72000
    assert out.amount == Decimal("520000.00")


def test_apply_additional_formula_prefers_current_adjusted_netto() -> None:
    prev = _wd(tara=15000, brutto=40000, netto=25000, adjusted=0)
    curr = _wd(tara=20000, brutto=50000, netto=30000, adjusted=31000, price="15000")

    out = apply_additional_formula(curr, prev)

    assert out.tara_kg == 40000
    assert out.netto_kg == 31000
    assert out.brutto_kg == 71000
    assert out.amount == Decimal("465000.00")


def test_from_weighing_mode_additional_requires_previous() -> None:
    curr = _wd(tara=20000, brutto=50000, netto=30000, adjusted=0, amount="480000")
    try:
        WeighingPrintData.from_weighing_mode(curr, mode="additional")
    except ValueError as exc:
        assert "previous_weighing is required" in str(exc)
    else:
        raise AssertionError("ValueError expected for missing previous_weighing")

