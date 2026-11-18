"""Room labels -> room types (rooms.classify, web/rooms.json), table driven. python3 tests/test_rooms.py
Every label the owner reported, English, abbreviations, misspellings, UAE and Arabic labels, and labels that must stay
unknown (they become 'multipurpose' and are flagged, never guessed)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import furnish, rooms  # noqa: E402

CASES = [
    # the owner's list
    ("SERVICE LIFT", "lift"), ("LIFT", "lift"), ("BAR AREA", "bar"), ("ENTRANCE FOYER", "foyer"), ("BREAKFAST AREA", "breakfast"),
    ("SHOW KITCHEN", "kitchen"), ("COLD STORE", "store"), ("HOT STORE", "store"), ("GUEST BEDROOM", "bedroom"),
    ("DOCK FOR YACHT", "dock"), ("SWIMMING POOL", "pool"), ("FUTURE SWIMMING POOL", "pool"), ("DIRTY KITCHEN", "kitchen"),
    ("WET KITCHEN", "kitchen"), ("FAMILY LIVING AREA", "living"), ("STAIRCASE HALL", "stair"), ("MAID'S ROOM", "bedroom"),
    ("WINE STORE", "store"), ("AQUARIUM", "water"), ("LANDSCAPE COURT", "garden"), ("FOUNTAIN", "water"),
    # bedrooms
    ("BEDROOM", "bedroom"), ("BED ROOM", "bedroom"), ("BEDROOM 1", "bedroom"), ("BEDROOM-2", "bedroom"), ("MASTER BEDROOM", "bedroom"),
    ("M.BED", "bedroom"), ("M.B.R", "bedroom"), ("BR 3", "bedroom"), ("KIDS ROOM", "bedroom"), ("GUEST ROOM", "bedroom"),
    ("DRIVER'S ROOM", "bedroom"), ("DRIVER ROOM", "bedroom"), ("MAID ROOM 300X250", "bedroom"), ("NANNY ROOM", "bedroom"),
    ("MASTER SUITE", "bedroom"), ("BEDRM", "bedroom"), ("Bedroom", "bedroom"), ("bed room 2", "bedroom"), ("BEDROM", "bedroom"),
    ("غرفة نوم", "bedroom"), ("غرفة نوم رئيسية", "bedroom"), ("غرفة خادمة", "bedroom"), ("غرفة السائق", "bedroom"),
    # wet rooms
    ("TOILET", "toilet"), ("TOI.", "toilet"), ("BATH", "toilet"), ("BATHROOM", "toilet"), ("W.C.", "toilet"), ("WC", "toilet"),
    ("POWDER ROOM", "toilet"), ("POWDER", "toilet"), ("ENSUITE", "toilet"), ("SHOWER", "toilet"), ("DRESS/TOI.", "toilet"),
    ("TOILETT", "toilet"), ("حمام", "toilet"), ("دورة مياه", "toilet"),
    # kitchen, dining, living
    ("KITCHEN", "kitchen"), ("KIT.", "kitchen"), ("KIT 9'X7'8", "kitchen"), ("KITCHN", "kitchen"), ("OPEN KITCHEN", "kitchen"),
    ("KITCHENETTE", "kitchen"), ("مطبخ", "kitchen"), ("DINING", "dining"), ("DINING AREA", "dining"), ("DIN.", "dining"),
    ("DINNING", "dining"), ("DRG./DIN.", "dining"), ("صالة طعام", "dining"), ("LIVING", "living"), ("LIVING ROOM", "living"),
    ("FAMILY ROOM", "living"), ("FAMILY HALL", "living"), ("LOUNGE", "living"), ("DRAWING ROOM", "living"), ("DRG.", "living"),
    ("SITTING", "living"), ("HALL", "living"), ("MAJLIS", "living"), ("MEN MAJLIS", "living"), ("LADIES MAJLIS", "living"),
    ("RECEPTION", "living"), ("مجلس", "living"), ("مجلس رجال", "living"), ("صالة", "living"), ("LIVNG", "living"),
    ("BREAKFAST", "breakfast"), ("BREAKFAST NOOK", "breakfast"), ("BAR", "bar"), ("WET BAR", "bar"), ("COFFEE BAR", "bar"),
    # entrance, circulation
    ("FOYER", "foyer"), ("ENTRANCE", "foyer"), ("ENTRANCE HALL", "foyer"), ("ENTRY", "foyer"), ("VESTIBULE", "foyer"),
    ("مدخل", "foyer"), ("LOBBY", "passage"), ("ENT.LOBBY", "passage"), ("PASSAGE", "passage"), ("CORRIDOR", "passage"),
    ("GALLERY", "passage"), ("LANDING", "passage"), ("STAIR", "stair"), ("STAIRCASE", "stair"), ("UP", "stair"),
    ("STAIR HALL", "stair"), ("درج", "stair"), ("ELEVATOR", "lift"), ("PASSENGER LIFT", "lift"), ("مصعد", "lift"),
    # other rooms
    ("PRAYER ROOM", "puja"), ("PUJA", "puja"), ("MUSALLA", "puja"), ("مصلى", "puja"), ("GYM", "gym"), ("FITNESS ROOM", "gym"),
    ("GYMNASIUM", "gym"), ("HOME CINEMA", "cinema"), ("HOME THEATRE", "cinema"), ("MEDIA ROOM", "cinema"), ("CINEMA", "cinema"),
    ("STUDY", "study"), ("OFFICE", "study"), ("HOME OFFICE", "study"), ("LIBRARY", "study"), ("مكتب", "study"),
    ("LAUNDRY", "wash"), ("LAUNDRY ROOM", "wash"), ("UTILITY", "wash"), ("UTILITY ROOM", "wash"), ("WASH", "wash"),
    ("WASH AREA", "wash"), ("غرفة غسيل", "wash"), ("STORE", "store"), ("STORE ROOM", "store"), ("STR.", "store"),
    ("STORAGE", "store"), ("PANTRY", "store"), ("DRY STORE", "store"), ("مخزن", "store"), ("DRESS", "dress"),
    ("DRESSING ROOM", "dress"), ("WALK IN CLOSET", "dress"), ("W.I.C", "dress"), ("WARDROBE", "dress"), ("غرفة ملابس", "dress"),
    # outside
    ("TERRACE", "balcony"), ("ROOF TERRACE", "balcony"), ("BALCONY", "balcony"), ("SIT-OUT", "balcony"), ("VERANDAH", "balcony"),
    ("PATIO", "balcony"), ("DECK", "balcony"), ("شرفة", "balcony"), ("تراس", "balcony"), ("GARAGE", "parking"),
    ("CAR PORCH", "parking"), ("CAR PARKING", "parking"), ("PARKING", "parking"), ("PORTICO", "parking"), ("موقف سيارات", "parking"),
    ("مرآب", "parking"), ("GARDEN", "garden"), ("LAWN", "garden"), ("COURTYARD", "garden"), ("حديقة", "garden"),
    ("OPEN TO SKY", "open"), ("CUTOUT", "open"), ("DUCT", "duct"), ("SHAFT", "duct"),
    # water
    ("POOL", "pool"), ("PLUNGE POOL", "pool"), ("INFINITY POOL", "pool"), ("JACUZZI", "pool"), ("KIDS POOL", "pool"),
    ("مسبح", "pool"), ("جاكوزي", "pool"), ("WATER BODY", "water"), ("WATER FEATURE", "water"), ("POND", "water"),
    ("REFLECTING POOL", "water"), ("نافورة", "water"), ("DOCK", "dock"), ("JETTY", "dock"), ("PIER", "dock"), ("BOAT SHED", "dock"),
    ("BOATHOUSE", "dock"), ("MARINA", "dock"), ("مرسى", "dock"),
    # never guessed: numbers, sizes, codes, words no rule knows
    ("8 25,00", None), ("14'X12'8", None), ("1", None), ("ROOM A", None), ("AREA 1", None), ("SPACE", None), ("X-1", None),
    ("", None), ("ZONE B", None), ("MECHANICAL", None),
]

fails = [(label, want, rooms.classify(label)) for label, want in CASES if rooms.classify(label)[0] != want]
for label, want, got in fails:
    print(f"FAIL {label!r}: want {want}, got {got}")
assert len(CASES) >= 150, len(CASES)
# every type has a floor, a colour and (when it is furnished) a rule; every phrase belongs to a type
for t, v in rooms.TYPES.items():
    assert {"label", "kind", "floor", "colour", "furnish"} <= set(v), t
    assert v["furnish"] is None or v["furnish"] in furnish.RULES, t
assert set(rooms.VOCAB["phrases"]) <= set(rooms.TYPES)
print(f"{'FAIL' if fails else 'ok  '} room labels: {len(CASES) - len(fails)}/{len(CASES)} typed as expected")
sys.exit(1 if fails else 0)
