"""IFC4 from the building model (IfcOpenShell, LGPL-3.0, used as a library).

    IfcProject > IfcSite > IfcBuilding > IfcBuildingStorey (one per storey)
    IfcWall          extruded from the wall's centre line, run on to the far face of the
                     walls it meets; exterior walls flagged IsExternal
    IfcOpeningElement + IfcDoor / IfcWindow   each opening voids its wall and is filled
    IfcSpace         every room, its net outline extruded to the storey's clear height,
                     with its name, type and net area
    IfcSlab          the ground floor slab under the footprint

Units are millimetres in the file (the API takes metres). Revit and ArchiCAD import IFC4
Reference View files like this; tests validate it with ifcopenshell.validate and open it
in FreeCAD.
"""

import math
import tempfile
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from app.modules.ai.floorplan.model.building import Building, Opening, Wall
from app.modules.ai.floorplan.model.planto3d import _wall_rect

SLAB_MM = 200


def _placement(x: float, y: float, z: float, angle: float) -> np.ndarray:
    m = np.eye(4)
    m[0][0], m[0][1] = math.cos(angle), -math.sin(angle)
    m[1][0], m[1][1] = math.sin(angle), math.cos(angle)
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


class _Ifc:
    def __init__(self, b: Building) -> None:
        self.b = b
        self.D = b.site.depth
        f = ifcopenshell.api.project.create_file(version="IFC4")
        self.f = f
        self.project = ifcopenshell.api.root.create_entity(
            f, ifc_class="IfcProject", name=b.meta.project or "Floor plan"
        )
        ifcopenshell.api.unit.assign_unit(
            f,
            length={"is_metric": True, "raw": "MILLIMETERS"},
            area={"is_metric": True, "raw": "SQUARE_METRE"},
        )
        model = ifcopenshell.api.context.add_context(f, context_type="Model")
        self.body = ifcopenshell.api.context.add_context(
            f,
            context_type="Model",
            context_identifier="Body",
            target_view="MODEL_VIEW",
            parent=model,
        )
        self.site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site")
        self.building = ifcopenshell.api.root.create_entity(
            f, ifc_class="IfcBuilding", name=b.meta.project or "Villa"
        )
        ifcopenshell.api.aggregate.assign_object(
            f, products=[self.site], relating_object=self.project
        )
        ifcopenshell.api.aggregate.assign_object(
            f, products=[self.building], relating_object=self.site
        )

    def P(self, x: float, y: float) -> tuple[float, float]:
        """mm, y down -> m, y up."""
        return x / 1000, (self.D - y) / 1000

    def product(self, ifc_class: str, name: str, rep, matrix, storey, **attrs):
        p = ifcopenshell.api.root.create_entity(self.f, ifc_class=ifc_class, name=name)
        for k, v in attrs.items():
            setattr(p, k, v)
        ifcopenshell.api.geometry.edit_object_placement(
            self.f, product=p, matrix=matrix, is_si=True
        )
        if rep is not None:
            ifcopenshell.api.geometry.assign_representation(self.f, product=p, representation=rep)
        if storey is not None:
            ifcopenshell.api.spatial.assign_container(
                self.f, products=[p], relating_structure=storey
            )
        return p

    def wall(self, w: Wall, walls: list[Wall], storey, height_m: float):
        x0, y0, x1, y1 = _wall_rect(w, walls)
        t = w.thickness / 1000
        if w.horizontal:
            start, length, angle = self.P(x0, w.a[1]), (x1 - x0) / 1000, 0.0
        else:  # runs south on the plan = -y in the IFC
            start, length, angle = self.P(w.a[0], y0), (y1 - y0) / 1000, -math.pi / 2
        rep = ifcopenshell.api.geometry.add_wall_representation(
            self.f, context=self.body, length=length, height=height_m, thickness=t, offset=-t / 2
        )
        wall = self.product(
            "IfcWall", w.id, rep, _placement(start[0], start[1], 0.0, angle), storey
        )
        pset = ifcopenshell.api.pset.add_pset(self.f, product=wall, name="Pset_WallCommon")
        ifcopenshell.api.pset.edit_pset(
            self.f,
            pset=pset,
            properties={"IsExternal": w.kind == "exterior", "LoadBearing": w.kind == "exterior"},
        )
        return wall, (x0 if w.horizontal else y0)

    def opening(self, o: Opening, w: Wall, wall_entity, run_start: float, storey) -> None:
        t = w.thickness / 1000 + 0.1
        width, height, sill = o.width / 1000, o.height / 1000, o.sill / 1000
        if w.horizontal:
            sx, sy = self.P(w.a[0] + o.offset - o.width / 2, w.a[1])
            angle = 0.0
        else:
            sx, sy = self.P(w.a[0], w.a[1] + o.offset - o.width / 2)
            angle = -math.pi / 2
        rep = ifcopenshell.api.geometry.add_wall_representation(
            self.f, context=self.body, length=width, height=height, thickness=t, offset=-t / 2
        )
        hole = self.product(
            "IfcOpeningElement", f"{o.id}-opening", rep, _placement(sx, sy, sill, angle), None
        )
        ifcopenshell.api.feature.add_feature(self.f, feature=hole, element=wall_entity)
        if o.kind == "door":
            op = (
                "DOUBLE_DOOR_SINGLE_SWING"
                if o.operation == "double"
                else ("SLIDING_TO_LEFT" if o.operation == "sliding" else "SINGLE_SWING_LEFT")
            )
            # the door and window helpers take project units (mm), unlike the wall helper
            rep = ifcopenshell.api.geometry.add_door_representation(
                self.f,
                context=self.body,
                overall_height=o.height,
                overall_width=o.width,
                operation_type=op,
            )
            ifc_class = "IfcDoor"
        else:
            rep = ifcopenshell.api.geometry.add_window_representation(
                self.f, context=self.body, overall_height=o.height, overall_width=o.width
            )
            ifc_class = "IfcWindow"
        place = _placement(sx, sy, sill, angle)
        # the lining sits across the wall: move it back by half the wall
        place[0][3] += -math.sin(angle) * 0 + math.sin(angle) * (w.thickness / 2000)
        place[1][3] += -math.cos(angle) * (w.thickness / 2000)
        filling = self.product(
            ifc_class,
            o.id,
            rep,
            place,
            storey,
            OverallHeight=o.height,
            OverallWidth=o.width,
        )
        ifcopenshell.api.feature.add_filling(self.f, opening=hole, element=filling)
        _ = run_start

    def space(self, r, storey, height_m: float, walls: list[Wall]) -> None:
        bands = unary_union(
            [
                Polygon(
                    [
                        (_wall_rect(w, walls)[0], _wall_rect(w, walls)[1]),
                        (_wall_rect(w, walls)[2], _wall_rect(w, walls)[1]),
                        (_wall_rect(w, walls)[2], _wall_rect(w, walls)[3]),
                        (_wall_rect(w, walls)[0], _wall_rect(w, walls)[3]),
                    ]
                )
                for w in walls
                if r.id in w.rooms
            ]
        )
        net = Polygon(r.polygon).difference(bands) if not bands.is_empty else Polygon(r.polygon)
        if net.geom_type != "Polygon":
            net = max(getattr(net, "geoms", [Polygon(r.polygon)]), key=lambda g: g.area)
        pts = [self.P(x, y) for x, y in list(net.exterior.coords)[:-1]]
        rep = ifcopenshell.api.geometry.add_slab_representation(
            self.f, context=self.body, depth=height_m, polyline=pts
        )
        sp = self.product("IfcSpace", r.name, rep, _placement(0, 0, 0, 0), None, LongName=r.type)
        ifcopenshell.api.aggregate.assign_object(self.f, products=[sp], relating_object=storey)
        pset = ifcopenshell.api.pset.add_pset(self.f, product=sp, name="Pset_SpaceCommon")
        ifcopenshell.api.pset.edit_pset(self.f, pset=pset, properties={"Reference": r.id})
        qto = ifcopenshell.api.pset.add_qto(self.f, product=sp, name="Qto_SpaceBaseQuantities")
        ifcopenshell.api.pset.edit_qto(
            self.f,
            qto=qto,
            properties={"NetFloorArea": r.net_area_m2, "GrossFloorArea": r.gross_area_m2},
        )

    def build(self) -> bytes:
        for st in self.b.storeys:
            storey = ifcopenshell.api.root.create_entity(
                self.f, ifc_class="IfcBuildingStorey", name=st.name
            )
            storey.Elevation = st.elevation
            ifcopenshell.api.aggregate.assign_object(
                self.f, products=[storey], relating_object=self.building
            )
            height_m = (st.walls[0].height if st.walls else st.height - 300) / 1000
            entities = {}
            for w in st.walls:
                entities[w.id] = self.wall(w, st.walls, storey, height_m)
            for o in st.openings:
                wall_entity, start = entities[o.wall]
                self.opening(o, st.wall(o.wall), wall_entity, start, storey)
            for r in st.rooms:
                self.space(r, storey, min(height_m, 2.7), st.walls)
            foot = unary_union([Polygon(r.polygon) for r in st.rooms]).buffer(
                max((w.thickness for w in st.walls if w.kind == "exterior"), default=200) / 2,
                join_style="mitre",
            )
            if foot.geom_type == "Polygon" and st.index == 0:
                pts = [self.P(x, y) for x, y in list(foot.exterior.coords)[:-1]]
                rep = ifcopenshell.api.geometry.add_slab_representation(
                    self.f, context=self.body, depth=SLAB_MM / 1000, polyline=pts
                )
                self.product(
                    "IfcSlab",
                    "GROUND SLAB",
                    rep,
                    _placement(0, 0, -SLAB_MM / 1000, 0),
                    storey,
                    PredefinedType="FLOOR",
                )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.ifc"
            self.f.write(str(path))
            return path.read_bytes()


def building_ifc(b: Building) -> bytes:
    return _Ifc(b).build()
