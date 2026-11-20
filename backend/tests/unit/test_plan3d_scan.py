"""The scan reader (plan3d/scan_reader.py): labels, sanity checks and a drawn scan read end to end.
No AI is involved; OCR runs locally (RapidOCR)."""

import cv2
import numpy as np
import pymupdf
import pytest

from app.modules.plan3d import scan_reader as sr


@pytest.mark.parametrize(
    ("text", "dims"),
    [
        ("15'9\"x12'4\"", (15.75, 12 + 4 / 12)),
        ("15' X 12'", (15.0, 12.0)),
        ("BEDROOM 12'-6\" x 10'", (12.5, 10.0)),
        ("4.50 x 3.60", (4.5 / 0.3048, 3.6 / 0.3048)),
        ("KITCHEN", None),
        ("3 x 4", None),  # bare integers are not a metric size
    ],
)
def test_label_sizes(text, dims):
    got = sr.label_dims_ft(text)
    if dims is None:
        assert got is None
    else:
        assert got == pytest.approx(dims, rel=1e-3)


def test_metric_labels_without_their_decimal_point_count_only_on_metric_sheets():
    assert sr._dims_words(["474X322"], metric_page=True) == pytest.approx(
        (4.74 / 0.3048, 3.22 / 0.3048), rel=1e-3
    )
    assert sr._dims_words(["474X322"], metric_page=False) is None


def test_a_texture_read_as_walls_is_not_a_plausible_floor():
    walls = [[0, 1, 0, 40, 0], [0, 30, 0, 1, 0], [29, 30, 0, 40, 0], [0, 30, 39, 40, 0]]
    assert sr._plausible({"walls": walls, "size": [30, 40]})
    stripes = [[x, x + 0.3, 0, 40, 0] for x in range(0, 30)] * 3
    assert not sr._plausible({"walls": stripes, "size": [30, 40]})
    assert not sr._plausible({"walls": [], "size": [30, 40]})


def drawn_scan(two_floors: bool = False) -> bytes:
    """An image-only PDF: a 30 x 20 ft two-room plan drawn at 1:100, 200 dpi, labels in print."""
    dpi = 200
    px_ft = 304.8 / 100 / 25.4 * dpi  # pixels per real foot at 1:100
    img = np.full((1400, 2400 if two_floors else 1300), 255, np.uint8)

    def plan(ox: int, oy: int, title: str) -> None:
        def p(x, y):
            return int(ox + x * px_ft), int(oy + y * px_ft)

        t = max(4, int(0.6 * px_ft))
        for a, b in [
            ((0, 0), (30, 0)),
            ((0, 20), (30, 20)),
            ((0, 0), (0, 20)),
            ((30, 0), (30, 20)),
        ]:
            cv2.line(img, p(*a), p(*b), 0, t)
        cv2.line(img, p(16, 0), p(16, 8), 0, t)  # partition with a door gap from 8 to 11 ft
        cv2.line(img, p(16, 11), p(16, 20), 0, t)
        r = int(3 * px_ft)  # the door: a leaf and its swing, hinged at (16, 8)
        cv2.line(img, p(16, 8), p(19, 8), 0, 2)
        cv2.ellipse(img, p(16, 8), (r, r), 0, 0, 90, 0, 1)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, "BEDROOM", p(4, 9), font, 1.0, 0, 2)
        cv2.putText(img, "15'5\"x19'5\"", p(4, 11.5), font, 0.9, 0, 2)  # clear sizes
        cv2.putText(img, "LIVING", p(19, 9), font, 1.0, 0, 2)
        cv2.putText(img, "13'5\"x19'5\"", p(18.5, 11.5), font, 0.9, 0, 2)
        cv2.putText(img, title, p(6, 24), font, 1.0, 0, 2)

    plan(150, 200, "GROUND FLOOR PLAN")
    if two_floors:
        plan(1300, 200, "FIRST FLOOR PLAN")
    ok, png = cv2.imencode(".png", img)
    assert ok
    doc = pymupdf.open()
    w_pt, h_pt = img.shape[1] / dpi * 72, img.shape[0] / dpi * 72
    page = doc.new_page(width=w_pt, height=h_pt)
    page.insert_image(page.rect, stream=png.tobytes())
    return doc.tobytes()


def test_a_drawn_scan_is_read_with_its_rooms_named_and_its_scale_fitted_to_the_labels():
    res = sr.read_scan_pdf(drawn_scan())
    assert res.plan is not None and res.scale_source == "labels"
    (floor,) = res.plan["floors"]
    rooms = {r["label"].upper(): r for r in floor["rooms"] if r["label"]}
    assert {"BEDROOM", "LIVING"} <= set(rooms)
    w, h = floor["size"]
    # outside size: 30 x 20 ft between wall centres plus a 0.6 ft wall
    assert w == pytest.approx(30.6, rel=0.03) and h == pytest.approx(20.6, rel=0.03)
    assert len(floor["walls"]) >= 4


def test_two_drawings_on_one_sheet_are_two_storeys_in_title_order():
    res = sr.read_scan_pdf(drawn_scan(two_floors=True))
    assert res.plan is not None
    assert [f["name"] for f in res.plan["floors"]] == ["Ground Floor Plan", "First Floor Plan"]
