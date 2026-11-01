from invoice_agent.validate import check, valid_spanish_tax_id

GOOD = {"supplier": "Demo SL", "supplier_tax_id": "B12345674", "invoice_number": "F1", "date": "2026-01-15",
        "base": 100.0, "vat_rate": 21, "vat": 21.0, "total": 121.0, "currency": "EUR"}


def test_tax_ids():
    assert valid_spanish_tax_id("B12345674")
    assert not valid_spanish_tax_id("B12345670")
    assert valid_spanish_tax_id("12345678Z")
    assert not valid_spanish_tax_id("12345678A")
    assert valid_spanish_tax_id("X1234567L")
    assert not valid_spanish_tax_id(None)


def test_good_invoice_passes():
    assert check(GOOD, set()) == []


def test_bad_total():
    assert any("total" in p for p in check(dict(GOOD, total=131.0), set()))


def test_duplicate():
    assert any("duplicate" in p for p in check(GOOD, {("B12345674", "F1")}))


def test_irpf_withholding():
    inv = dict(GOOD, withholding_rate=15, withholding=15.0, total=106.0)
    assert check(inv, set()) == []
    assert any("withholding" in p for p in check(dict(inv, total=121.0), set()))


def test_mixed_vat_rates_skip_rate_check():
    assert check(dict(GOOD, vat_rate=None, vat=16.0, total=116.0), set()) == []


def test_missing_and_future():
    problems = check(dict(GOOD, invoice_number=None, date="2999-01-01"), set())
    assert "missing invoice_number" in problems and "date in the future" in problems
