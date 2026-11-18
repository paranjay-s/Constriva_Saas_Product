"""Furniture that can be replaced by your own model: name -> (label, width, depth in feet, extra arguments).
A file assets/custom/<name>.glb takes the place of the built-in item in every later build: it is scaled to the item's
footprint and stood on the floor. Model it with +Y up and its front facing +Z (the glTF standard)."""
CATALOG = {
    "bed": ("Bed", 5.0, 6.6, {}), "nightstand": ("Nightstand", 1.6, 1.5, {}), "wardrobe": ("Wardrobe", 6.0, 2.0, {}),
    "desk": ("Desk", 4.0, 2.0, {}), "sofa": ("Sofa", 7.0, 3.0, {}), "coffee_table": ("Coffee table", 3.6, 2.0, {}),
    "tv_unit": ("TV unit", 5.0, 1.4, {}), "dining_set": ("Dining set", 6.0, 6.4, {}), "fridge2": ("Fridge", 3.0, 2.4, {}),
    "washer2": ("Washing machine", 2.0, 2.0, {}), "wc2": ("WC", 1.5, 2.3, {}), "vanity": ("Basin", 2.6, 1.7, {}),
    "puja_mandir": ("Mandir", 3.6, 1.5, {}), "plant": ("Plant", 1.5, 1.5, {}),
}
CELL = 20.0        # the preview scene: one item in the middle of each 20 ft cell of a long room


def preview_plan():
    """a plan with every item standing in a row, used to render the pictures on the furniture page"""
    n, t = len(CATALOG), 0.75
    L = n * CELL
    items = [dict(fn=fn, args=[k * CELL + CELL / 2, CELL / 2, 0], kw=kw, solid=False, room="",
                  box=[k * CELL + CELL / 2 - w / 2, k * CELL + CELL / 2 + w / 2, CELL / 2 - d / 2, CELL / 2 + d / 2])
             for k, (fn, (_, w, d, kw)) in enumerate(CATALOG.items())]
    walls = [[0, L, 0, t, 0], [0, L, CELL - t, CELL, 0], [0, t, 0, CELL, 0], [L - t, L, 0, CELL, 0]]
    return dict(version=1, units="ft", floor_height=10.0, slab=0.5, floors=[dict(
        name="Preview", level=0, size=[L, CELL], walls=walls, openings=[], stairs=[], labels=[], items=items,
        rooms=[dict(type="living", label="", rects=[[t, L - t, t, CELL - t]], area=L * CELL)])])
