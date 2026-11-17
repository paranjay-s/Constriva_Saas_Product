"""The analysis tools: alternatives, swaps, suitability, comparisons, care, supporting items,
coverage, piece sizes and totals. Offline (keyword reader, no LLM)."""

import pytest

from app.modules.ai.material_agent import tools
from app.modules.ai.material_agent.chat import catalog_mentions, keyword_intent
from app.modules.ai.material_agent.normalise import normalise
from tests.material_agent.conftest import TV_WALL
from tests.material_agent.test_mat_api import BASE, _analyse, _chat, _line, api  # noqa: F401

WALL = {"kind": "wall", "length": 12, "height": 10, "label": "TV wall"}


# ------------------------------------------------------------------ unit level


def test_profiles_suitability_and_alternatives():
    assert "non-porous" in tools.profile("quartz")["durability"]
    assert tools.suitability("engineered_wood", "bathroom")[0] is False
    assert tools.suitability("vitrified_tile", "bathroom")[0] is True
    assert tools.suitability("spc_vinyl", "kitchen floor")[0] is True
    assert tools.suitability("wood_veneer_panel", "outdoor")[0] is False
    marble = normalise(TV_WALL.materials)[1]
    names = [o["name"] for o in tools.alternatives(marble, "living")]
    assert names and "Italian marble" not in names
    bath = [o["name"] for o in tools.alternatives("engineered_wood", "bathroom")]
    assert "Engineered wood flooring" not in bath and "Laminate flooring" not in bath
    assert any("SPC" in n or "Wood-look" in n for n in bath)
    cmp_ = tools.compare("quartz", "granite")
    assert cmp_["a"]["name"].startswith("Quartz") and cmp_["b"]["name"] == "Granite"


def test_piece_sizes_and_mentions():
    p = tools.parse_piece_size("I'll use 2 x 4 ft tiles")
    assert (p.width_ft, p.length_ft) == (2, 4)
    mm = tools.parse_piece_size("600x1200 slabs")
    assert mm.label == "600 × 1200 mm" and mm.width_ft == pytest.approx(1.9685, abs=1e-3)
    assert tools.parse_piece_size("no size here") is None
    assert catalog_mentions("replace the marble with quartz") == ["marble", "quartz"]


def test_keyword_routing():
    mats = normalise(TV_WALL.materials)
    cases = {
        "instead of this product what can we use to make it better": ("advise", "alternatives"),
        "use quartz instead": ("substitute", None),
        "replace the marble with granite": ("substitute", None),
        "can I use the veneer in the bathroom?": ("advise", "suitability"),
        "quartz vs granite for the counter": ("advise", "compare"),
        "how do I maintain the veneer": ("advise", "maintenance"),
        "is it scratch resistant?": ("advise", "durability"),
        "how is the veneer installed?": ("advise", "installation"),
        "pros and cons of the marble": ("advise", "pros_cons"),
        "will this design suit a small room?": ("advise", "general"),
        "what else do I need, adhesive?": ("supporting_materials", None),
        "marble is only 40% of the wall": ("set_coverage", None),
        "I'll use 2 x 4 ft tiles for the marble": ("set_piece_size", None),
        "total of everything": ("totals", None),
        "why 3 sheets?": ("explain_quantity", None),
        "which is cheaper, quartz or granite?": ("money_question", None),
    }
    for text, (action, topic) in cases.items():
        got = keyword_intent(text, mats)
        assert (got.action, got.topic) == (action, topic), text


# ------------------------------------------------------------------- over HTTP


def test_alternatives_for_this_product_then_swap(api):  # noqa: F811
    client, _ = api
    view = _analyse(client, WALL)
    rid = view["id"]
    q = _chat(client, rid, "instead of this product what can we use to make it better")
    assert q["status"] == "needs_input" and "Statuario marble" in q["options"]  # which one?
    alt = _chat(client, rid, "Statuario marble")
    assert alt["status"] == "ok" and "Instead of **Statuario marble**" in alt["message"]
    assert "use " in alt["message"] and "instead" in alt["message"]  # how to switch
    # "this" now means the marble: no second question
    swap = _chat(client, rid, "ok use quartz instead")
    assert swap["status"] == "ok" and "Swapped **Statuario marble** for **Quartz" in swap["message"]
    names = [m["display_name"] for m in swap["session"]["materials"]]
    assert "Quartz (engineered stone)" in names and "Statuario marble" not in names
    line = _line(swap["session"], "quartz")
    assert line["total_qty"] == 39.6 and line["application"] == "TV wall"  # same place and share
    back = _chat(client, rid, "replace quartz with statuario marble")
    assert back["status"] == "ok" and "Swapped **Quartz" in back["message"]


def test_suitability_compare_and_care(api):  # noqa: F811
    client, _ = api
    rid = _analyse(client, WALL)["id"]
    no = _chat(client, rid, "can I use the veneer in the bathroom?")
    assert no["message"].startswith("**Not recommended**") and "water resistance" in no["message"]
    cmp_ = _chat(client, rid, "quartz vs granite for the counter")
    assert "**Quartz (engineered stone)** vs **Granite**" in cmp_["message"]
    care = _chat(client, rid, "how do I maintain the veneer")
    assert "Fluted walnut veneer panel" in care["message"] and "dry cloth" in care["message"]


def test_supporting_coverage_pieces_and_totals(api):  # noqa: F811
    client, _ = api
    rid = _analyse(client, WALL)["id"]
    sup = _chat(client, rid, "what else do I need?")
    msg = sup["message"]
    assert "3 sheets** backing plywood" in msg  # 84 sq ft / 32 -> 2.6 -> 3
    assert "2 bags (20 kg)** stone adhesive" in msg  # 36 / 30 -> 1.2 -> 2
    assert "Also needed" in msg
    support = sup["session"]["report"]["supporting"]
    assert {s["item"] for s in support} >= {
        "Backing plywood (8 x 4 ft)",
        "Grout",
        "Stone / surface sealer",
    }

    cov = _chat(client, rid, "marble is only 40% of the wall")
    assert _line(cov["session"], "marble")["total_qty"] == 52.8  # 120 x 0.4 = 48 -> +10 %
    pcs = _chat(client, rid, "I'll use 2 x 4 ft tiles for the marble")
    line = _line(pcs["session"], "marble")
    assert (line["buy_qty"], line["buy_unit"]) == (7, "pieces (2 × 4 ft)")  # 52.8 / 8 = 6.6 -> 7
    tot = _chat(client, rid, "total of everything")
    assert "**Statuario marble**: **52.8 sq ft**" in tot["message"]


def test_advice_never_talks_money(api):  # noqa: F811
    client, _ = api
    rid = _analyse(client, WALL)["id"]
    r = _chat(client, rid, "which is cheaper, quartz or granite?")
    assert "quantities only" in r["message"]


def test_countertop_support_singular_units_and_inline_bullets():
    from app.modules.ai.material_agent.explain import bullets_on_lines
    from app.modules.ai.material_agent.schemas import QuantityLine

    granite = normalise(TV_WALL.materials)[1].model_copy(update={"catalog_id": "granite"})
    line = QuantityLine(
        material_id=granite.id,
        material="Granite",
        application="Kitchen platform (L-shape)",
        surface_sqft=32,
        coverage_ratio=1,
        net_qty=16,
        wastage_pct=10,
        total_qty=17.6,
    )
    items = {(s.item, s.qty, s.unit) for s in tools.supporting([line], [granite])}
    # a counter top is fixed and sealed, not laid with adhesive and grout like a floor
    assert items == {
        ("Silicone / epoxy for fixing", 1, "tube"),
        ("Stone / surface sealer", 1, "litre"),
    }
    assert tools.unit_for(1, "bags (20 kg)") == "bag (20 kg)" and tools.unit_for(1, "kg") == "kg"
    assert bullets_on_lines("Yes. - one. - two.") == "Yes.\n- one.\n- two."
