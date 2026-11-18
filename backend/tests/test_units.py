from datetime import date, timedelta

from app.services import scripts
from app.services.insights import build_matcher, parse_sales_csv, rank
from app.util import decrypt, encrypt, normalize_name, parse_price_cents

ROW = {"name": "Chicken Biryani", "price": "$14.99",
       "description": "Fragrant basmati rice layered with slow-cooked chicken, saffron and crispy fried onions"}


def good_script(**over):
    s = {
        "hook": "People keep coming back",
        "beats": [{"caption": "Chicken Biryani", "seconds": 4}, {"caption": "Slow-cooked chicken", "seconds": 4.5},
                  {"caption": "Only $14.99", "seconds": 5}],
        "voiceover": "The Chicken Biryani at Kumar's. Saffron basmati and slow-cooked chicken. Just $14.99.",
        "veo_prompt": "steam rising", "title": "Chicken Biryani at Kumar's", "description": "Try it.",
        "hashtags": ["#biryani"], "facts_used": [{"field": "name", "value": "Chicken Biryani"}],
    }
    s.update(over)
    return s


# ---------------------------------------------------------------- util

def test_normalize_name():
    assert normalize_name("Chicken Biryani") == "chicken biryani"
    assert normalize_name("CHICKEN  BIRYANI!!") == "chicken biryani"
    assert normalize_name("Garlic Naan (LG)") == "garlic naan"
    assert normalize_name("Large Mango Lassi") == "mango lassi"
    assert normalize_name("Veg Samosa") == "vegetable samosa"
    assert normalize_name("Chkn Tikka") == "chicken tikka"
    assert normalize_name("Mac & Cheese") == "mac and cheese"
    assert normalize_name("Chef's Thali") == "chef s thali"
    assert normalize_name("Chicken Biriyani") == "chicken biryani"
    assert normalize_name("") == ""


def test_parse_price():
    assert parse_price_cents("$14.99") == 1499
    assert parse_price_cents("14") == 1400
    assert parse_price_cents("") is None
    assert parse_price_cents("free") is None
    assert parse_price_cents("1,200.50") == 120050


def test_fernet_roundtrip():
    assert decrypt(encrypt("refresh-token-xyz")) == "refresh-token-xyz"


# ---------------------------------------------------------------- script validation

def test_validator_accepts_grounded():
    assert scripts.validate_script(scripts.normalize_script(good_script(), 15), ROW, 15) == []


def test_validator_rejects_wrong_price():
    s = scripts.normalize_script(good_script(voiceover="Chicken Biryani for just $12.99 today."), 15)
    assert any("does not match" in p for p in scripts.validate_script(s, ROW, 15))


def test_validator_rejects_invented_claims():
    s = scripts.normalize_script(good_script(voiceover="Chicken Biryani, gluten-free and 20% off this week!"), 15)
    probs = scripts.validate_script(s, ROW, 15)
    assert any("invented claims" in p for p in probs)


def test_validator_requires_dish_name():
    s = scripts.normalize_script(good_script(beats=[{"caption": "So good", "seconds": 13.5}],
                                             voiceover="You'll love this. Just $14.99.", hook="Look at this"), 15)
    assert any("must appear" in p for p in scripts.validate_script(s, ROW, 15))


def test_validator_null_price_forbids_dollars():
    row = dict(ROW, price=None)
    s = scripts.normalize_script(good_script(), 15)
    assert any("menu has none" in p for p in scripts.validate_script(s, row, 15))


def test_template_script_is_valid():
    for angle in ("top_seller", "rising", "slow_mover", None):
        t = scripts.template_script(ROW, angle, "Kumar's", 15)
        assert scripts.validate_script(t, ROW, 15) == [], angle
    t = scripts.template_script(dict(ROW, price=None), None, "Kumar's", 15)
    assert scripts.validate_script(t, dict(ROW, price=None), 15) == []
    assert "$" not in t["voiceover"]


def test_wrap_caption_limits():
    w = scripts.wrap_caption("Fragrant basmati rice layered with slow-cooked chicken and saffron")
    lines = w.split("\n")
    assert len(lines) <= 2
    assert all(len(line) <= 23 for line in lines)


def test_normalize_script_rescales_beats():
    s = scripts.normalize_script(good_script(beats=[{"caption": "a", "seconds": 1}, {"caption": "b", "seconds": 1}]), 15)
    from app.services.gemini import END_CARD_S

    assert abs(sum(b["seconds"] for b in s["beats"]) - (15 - END_CARD_S)) < 0.1


# ---------------------------------------------------------------- insights

def test_csv_aliases_and_drops():
    text = "Business Date,Item Name,Qty,Net Sales\n2026-11-01,Chicken Biryani,3,44.97\n" \
           "11/02/2026,Garlic Naan (LG),2,6.98\n2026-11-03,Butter Chicken,-1,-15.99\n,,,\nbad,row,x,1\n"
    res = parse_sales_csv(text)
    assert len(res.rows) == 2
    assert res.dropped == 2  # refund + bad row (blank skipped silently)
    assert res.rows[1].date == date(2026, 11, 2)


def test_csv_missing_columns():
    import pytest

    from app.services.insights import CsvFormatError

    with pytest.raises(CsvFormatError):
        parse_sales_csv("foo,bar\n1,2\n")


def test_matcher():
    m = build_matcher([(1, "Chicken Biryani"), (2, "Garlic Naan"), (3, "Vegetable Samosa")])
    assert m("chicken biryani") == 1
    assert m("Garlic Naan (LG)") == 2
    assert m("Chicken Biriyani") == 1
    assert m("Veg Samosa") == 3
    assert m("Gift Card") is None


def _series(item, weekly, end=date(2026, 11, 15)):
    out = []
    start = end - timedelta(days=len(weekly) * 7 - 1)
    for w, total in enumerate(weekly):
        out.append((start + timedelta(days=w * 7 + 3), item, total))
    return out


def test_rank_picks():
    sales = _series(1, [50, 50, 63, 83]) + _series(2, [110, 108, 107, 112]) + _series(3, [8, 7, 5, 5]) + _series(4, [30, 30, 30, 31])
    picks = {p.angle: p for p in rank(sales, items_with_photo={1, 2, 3})}
    assert picks["top_seller"].menu_item_id == 2
    assert picks["rising"].menu_item_id == 1
    assert picks["rising"].metric["wow_pct"] == 32
    assert picks["slow_mover"].menu_item_id == 3


def test_rank_short_history_only_top_seller():
    sales = [(date(2026, 11, 10), 1, 5), (date(2026, 11, 12), 2, 9)]
    picks = rank(sales, {1, 2})
    assert [p.angle for p in picks] == ["top_seller"]


def test_rank_rising_needs_volume():
    # item 5 doubles but from 2 → 4 (below the qty thresholds), so it can't be "rising"
    sales = _series(1, [50, 50, 50, 55]) + _series(5, [2, 2, 2, 4]) + _series(2, [100, 100, 100, 100])
    picks = {p.angle: p for p in rank(sales, {1, 2, 5})}
    assert picks["rising"].menu_item_id == 1
