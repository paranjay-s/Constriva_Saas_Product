"""Building: the one model every drawing and export of a generated plan is made from.

Units are millimetres and every stored coordinate is a multiple of GRID_MM (50 mm).
Origin: the plot's north-west corner; x grows east, y grows south (north is up on the
sheet when `site.north_deg` is 0). Wall positions are centre lines; room polygons are
measured on wall centre lines too, so neighbouring rooms share edges exactly.

The solver works on room rectangles (`schemas.plan.FloorPlan`, cm). `model.build`
turns a solved FloorPlan into a Building, deterministically: walls with types and
thicknesses, hosted doors and windows, fixtures, stair flights and site elements.
Everything downstream (SVG/PDF/PNG sheet, DXF, IFC, DWG, PlanJSON 2.0 for the BOQ, the
PlanTo3D plan for 3D) reads only this model.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA = "constriva.building/1"
GRID_MM = 50

Pt = tuple[int, int]
WallKind = Literal["exterior", "interior", "partition", "boundary"]
OpeningKind = Literal["door", "window"]
Operation = Literal["hinged", "double", "sliding", "opening", "fixed", "casement"]
FixtureKind = Literal[
    "wc",
    "basin",
    "shower",
    "bath",
    "counter",
    "sink",
    "hob",
    "fridge",
    "wardrobe",
    "bed_double",
    "bed_single",
    "side_table",
    "sofa",
    "armchair",
    "coffee_table",
    "dining_table",
    "desk",
    "tree",
    "plant",
    "washer",
]
FURNITURE_KINDS = frozenset(
    {
        "bed_double",
        "bed_single",
        "side_table",
        "sofa",
        "armchair",
        "coffee_table",
        "dining_table",
        "desk",
        "tree",
        "plant",
    }
)
SiteKind = Literal[
    "plot",
    "pool",
    "garden",
    "lawn",
    "courtyard",
    "parking",
    "driveway",
    "dock",
    "deck",
    "balcony",
    "paving",
    "boundary_wall",
    "gate",
]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Revision(_M):
    rev: str
    date: str
    description: str
    model: str = ""  # the AI model that made this version, when one did


class Meta(_M):
    plan_id: str
    version: int = 1
    project: str = ""
    client: str = ""
    title: str = "GROUND FLOOR PLAN"
    drawing_number: str = "A-101"
    scale: int = 100  # 1:scale on the sheet
    sheet: Literal["A3", "A1"] = "A3"
    date: str = ""
    unit_display: Literal["ft", "m", "cm", "mm"] = "ft"
    revisions: list[Revision] = Field(default_factory=list)
    model: str = ""  # the AI model that made the current version
    disclaimer: str = "FOR DESIGN PURPOSES ONLY, NOT FOR CONSTRUCTION"


class Wall(_M):
    id: str
    a: Pt
    b: Pt
    thickness: int
    kind: WallKind
    height: int
    rooms: list[str] = Field(default_factory=list, description="Rooms on either side")

    @property
    def horizontal(self) -> bool:
        return self.a[1] == self.b[1]

    @property
    def length(self) -> int:
        return abs(self.b[0] - self.a[0]) + abs(self.b[1] - self.a[1])


class Opening(_M):
    id: str
    wall: str
    kind: OpeningKind
    operation: Operation
    offset: int = Field(description="Wall start to the opening's centre, along the wall")
    width: int
    height: int
    sill: int = 0
    rooms: tuple[str | None, str | None] = Field(
        description="Rooms on the two sides (None = outside); for a door the first is the "
        "room it opens into"
    )
    hinge: Literal["start", "end"] | None = Field(
        default=None, description="End of the opening (towards the wall's a or b) with the hinge"
    )
    main_entrance: bool = False


class ArcWall(_M):
    """A curved wall (C3.1): its centre line is an arc of `radius` round `center`, from angle
    `start_deg` to `end_deg` (degrees in the model's axes: from +x towards +y, i.e. clockwise on
    the drawing, y growing south; end > start, a full circle is 0..360). No openings."""

    id: str
    center: Pt
    radius: int
    thickness: int
    start_deg: float = 0.0
    end_deg: float = 360.0
    kind: WallKind = "interior"
    height: int = 3000
    rooms: list[str] = Field(default_factory=list)


class Room(_M):
    id: str
    name: str
    type: str
    zone: str
    polygon: list[Pt]
    enclosed: bool = True
    finish: str = ""
    net_area_m2: float = 0.0
    gross_area_m2: float = 0.0
    part_of: str | None = None
    # a round room: centre and inside radius (mm); its polygon is the circle as a polygon
    circle: tuple[int, int, int] | None = Field(default=None, exclude_if=lambda v: v is None)


class Fixture(_M):
    id: str
    room: str
    kind: FixtureKind
    x: int  # centre
    y: int
    w: int  # along the back wall
    d: int  # depth away from the back wall
    rotation: Literal[0, 90, 180, 270] = 0  # 0 = back against the north side

    @property
    def furniture(self) -> bool:
        return self.kind in FURNITURE_KINDS


class Flight(_M):
    x: int
    y: int
    w: int
    h: int
    axis: Literal["x", "y"]  # direction of travel
    up: Literal[1, -1]  # +1: going up towards +axis
    risers: int


class Stair(_M):
    id: str
    room: str
    width: int
    riser: int
    tread: int
    risers: int
    headroom: int
    landing: tuple[int, int, int, int] | None = None  # x, y, w, h
    flights: list[Flight]
    # a spiral stair (C3.1) climbs round a column in its room's square; its flights are then
    # the room's square, travelled round
    shape: Literal["straight", "spiral"] = Field(
        default="straight", exclude_if=lambda v: v == "straight"
    )


class SiteElement(_M):
    id: str
    kind: SiteKind
    name: str = ""
    polygon: list[Pt]
    water: list[Pt] | None = None  # pool: the water inside the walkway
    room: str | None = None  # the solver room it came from


class Setbacks(_M):
    front: int
    rear: int
    left: int
    right: int


class Site(_M):
    width: int
    depth: int
    road_side: Literal["north", "south", "east", "west"] = "south"
    north_deg: float = 0.0
    setbacks: Setbacks
    elements: list[SiteElement] = Field(default_factory=list)

    @property
    def area_m2(self) -> float:
        return self.width * self.depth / 1e6


class Storey(_M):
    id: str
    name: str
    index: int = 0
    elevation: int = 0
    height: int
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    fixtures: list[Fixture] = Field(default_factory=list)
    stairs: list[Stair] = Field(default_factory=list)
    arcs: list[ArcWall] = Field(default_factory=list, exclude_if=lambda v: not v)

    def wall(self, wall_id: str) -> Wall:
        return next(w for w in self.walls if w.id == wall_id)

    def room(self, room_id: str) -> Room:
        return next(r for r in self.rooms if r.id == room_id)


class Areas(_M):
    plot_m2: float
    built_up_m2: float  # gross: footprint to the outer face of external walls (DBC K.5.2.7)
    built_up_net_m2: float  # sum of room net areas (inside the wall faces)
    exterior_m2: float  # plot minus built-up
    coverage: float  # built_up / plot
    rooms_gross_m2: float  # sum of room gross areas; equals built_up by construction


class Building(_M):
    schema_: str = Field(default=SCHEMA, alias="schema")
    meta: Meta
    site: Site
    storeys: list[Storey]
    areas: Areas

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_json_dict(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)
