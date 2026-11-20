"""Building <-> PlanJSON 2.0 (the BOQ's format, metres). Lossless both ways.

`to_planjson` writes every wall, opening and room as PlanJSON 2.0 defines them (opening
`offset` to the opening's centre, `position` its centre point), and keeps what PlanJSON
has no field for in extra keys the schema allows: wall `subkind` (partition), opening
`operation` / `hinge` / `rooms` / `main_entrance`, room `type` / `net_area_m2` /
`gross_area_m2` / `finish`, level `fixtures` / `stairs`, and plan `site` / `areas` /
`meta`. Open areas (pool, garden, lawn, parking, paving...) are rooms with kind
`outdoor`, so the BOQ prices their paving and landscape.

`from_planjson` rebuilds the identical Building from that document; the round trip is
tested (tests/floorplan/test_fp_building.py).
"""

from typing import Any

from app.modules.ai.floorplan.model.building import (
    Areas,
    Building,
    Fixture,
    Meta,
    Opening,
    Room,
    Site,
    SiteElement,
    Stair,
    Storey,
    Wall,
)
from app.modules.plans.room_types import boq_kind_from, resolve_boq_type
from app.modules.plans.schemas import PlanJSON

OUTDOOR_BOQ = {"parking": "outdoor", "driveway": "outdoor", "paving": "outdoor"}


def _m(v: int) -> float:
    return round(v / 1000, 3)


def _mm(v: float) -> int:
    return int(round(v * 1000))


def _pt(p) -> list[float]:
    return [_m(p[0]), _m(p[1])]


def _ipt(p) -> tuple[int, int]:
    return (_mm(p[0]), _mm(p[1]))


def to_planjson(b: Building) -> dict[str, Any]:
    levels = []
    for st in b.storeys:
        walls = {w.id: w for w in st.walls}
        jwalls = [
            {
                "id": w.id,
                "start": _pt(w.a),
                "end": _pt(w.b),
                "thickness": _m(w.thickness),
                "kind": "exterior" if w.kind == "exterior" else "interior",
                "subkind": w.kind,
                "height": _m(w.height),
                "rooms": list(w.rooms),
            }
            for w in st.walls
        ]
        jopen = []
        for o in st.openings:
            w = walls[o.wall]
            cx = w.a[0] + (o.offset if w.horizontal else 0)
            cy = w.a[1] + (0 if w.horizontal else o.offset)
            jopen.append(
                {
                    "id": o.id,
                    "wall_id": o.wall,
                    "type": o.kind,
                    "offset": _m(o.offset),
                    "position": [_m(cx), _m(cy)],
                    "width": _m(o.width),
                    "height": _m(o.height),
                    "sill": _m(o.sill),
                    "operation": o.operation,
                    "hinge": o.hinge,
                    "rooms": list(o.rooms),
                    "main_entrance": o.main_entrance,
                }
            )
        jrooms = []
        for r in st.rooms:
            kind = "indoor" if r.enclosed else "void"
            jrooms.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "kind": kind,
                    "boq_kind": boq_kind_from(r.name, kind) or kind,
                    "boq_type": resolve_boq_type(r.name, None, r.net_area_m2)
                    if kind == "indoor"
                    else None,
                    "polygon": [_pt(p) for p in r.polygon],
                    "type": r.type,
                    "zone": r.zone,
                    "enclosed": r.enclosed,
                    "finish": r.finish,
                    "net_area_m2": r.net_area_m2,
                    "gross_area_m2": r.gross_area_m2,
                    "part_of": r.part_of,
                }
            )
        if st.index == 0:
            for e in b.site.elements:
                if e.kind in ("boundary_wall", "gate", "plot"):
                    continue
                jrooms.append(
                    {
                        "id": e.id,
                        "name": e.name or e.kind.upper(),
                        "kind": "outdoor",
                        "boq_kind": OUTDOOR_BOQ.get(e.kind, "outdoor"),
                        "boq_type": None,
                        "polygon": [_pt(p) for p in e.polygon],
                        "type": e.kind,
                        "site_element": True,
                    }
                )
        levels.append(
            {
                "index": st.index,
                "name": st.name,
                "storey_id": st.id,
                "elevation": _m(st.elevation),
                "height_mm": st.height,
                "wall_height": _m(st.walls[0].height) if st.walls else 3.0,
                "wall_height_source": "stated",
                "walls": jwalls,
                "openings": jopen,
                "rooms": jrooms,
                "columns": [],
                "fixtures": [f.model_dump(mode="json") for f in st.fixtures],
                "stairs": [s.model_dump(mode="json") for s in st.stairs],
            }
        )
    doc = {
        "schema_version": "2.0",
        "version": b.meta.version,
        "units": "m",
        "building_type": "villa",
        "scale_source": "stated_scale",
        "project_title": b.meta.project,
        "client": b.meta.client,
        "subject": b.meta.title,
        "levels": levels,
        "confidence": {"overall": 1.0},
        "warnings": [],
        "plot": {"width": _m(b.site.width), "depth": _m(b.site.depth)},
        "built_area_m2": b.areas.built_up_m2,
        "site": b.site.model_dump(mode="json"),
        "areas": b.areas.model_dump(mode="json"),
        "meta": b.meta.model_dump(mode="json"),
        "generator": {"schema": b.schema_, "plan_id": b.meta.plan_id},
    }
    PlanJSON.model_validate(doc)  # what the BOQ reads must stay valid PlanJSON 2.0
    return doc


def from_planjson(doc: dict[str, Any]) -> Building:
    storeys = []
    for lv in doc["levels"]:
        walls = [
            Wall(
                id=w["id"],
                a=_ipt(w["start"]),
                b=_ipt(w["end"]),
                thickness=_mm(w["thickness"]),
                kind=w["subkind"],
                height=_mm(w["height"]),
                rooms=w["rooms"],
            )
            for w in lv["walls"]
        ]
        openings = [
            Opening(
                id=o["id"],
                wall=o["wall_id"],
                kind=o["type"],
                operation=o["operation"],
                offset=_mm(o["offset"]),
                width=_mm(o["width"]),
                height=_mm(o["height"]),
                sill=_mm(o["sill"]),
                rooms=tuple(o["rooms"]),
                hinge=o["hinge"],
                main_entrance=o["main_entrance"],
            )
            for o in lv["openings"]
        ]
        rooms = [
            Room(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                zone=r["zone"],
                polygon=[_ipt(p) for p in r["polygon"]],
                enclosed=r["enclosed"],
                finish=r["finish"],
                net_area_m2=r["net_area_m2"],
                gross_area_m2=r["gross_area_m2"],
                part_of=r["part_of"],
            )
            for r in lv["rooms"]
            if not r.get("site_element")
        ]
        storeys.append(
            Storey(
                id=lv["storey_id"],
                name=lv["name"],
                index=lv["index"],
                elevation=_mm(lv["elevation"]),
                height=lv["height_mm"],
                walls=walls,
                openings=openings,
                rooms=rooms,
                fixtures=[Fixture.model_validate(f) for f in lv["fixtures"]],
                stairs=[Stair.model_validate(s) for s in lv["stairs"]],
            )
        )
    site = Site.model_validate(doc["site"])
    site = site.model_copy(
        update={"elements": [SiteElement.model_validate(e) for e in doc["site"]["elements"]]}
    )
    return Building(
        meta=Meta.model_validate(doc["meta"]),
        site=site,
        storeys=storeys,
        areas=Areas.model_validate(doc["areas"]),
    )
