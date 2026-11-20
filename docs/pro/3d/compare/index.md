# Reference vs Low vs High, per room type (PART 2, F)

Left: your reference picture (docs/reference/rooms). Middle: our Low walkthrough (three.js, baked light).
Right: our High still (Cycles, the style handover's look). Sheets are on disk only (they contain your
reference pictures). For design purposes only, not for construction.

| Room type | Sheet | Notes |
|---|---|---|
| Living room | `living_room.jpg` | Furnished in Low and High; the reference's warm wood panelling and feature ceiling are not modelled. |
| Bedroom | `bedroom.jpg` | Bed, wardrobe, desk and art in both; the reference has a padded headboard wall and cove lighting (High has the cove). |
| Bathroom | `bathroom.jpg` | Tiled walls, WC, basin, shower; the reference's stone vanity is richer. |
| Kitchen | `kitchen.jpg` | Oven and microwave tower, fridge, dishwasher (PART 2 D); the island does not fit this plan. |
| Wardrobes / dress | `wardrobes___dress.jpg` | Wardrobe walls; the High camera stands close in this small room. |
| Bar | `bar.jpg` | Empty: this older job reads BAR as a generic room; PART 1's direct export keeps the type and the bar kit. |
| Puja | `puja.jpg` | Empty for the same reason as the bar; the mandir kit is placed when the type is puja. |
| Front elevation | `front_elevation.jpg` | Modern UAE front: fins and an entrance canopy; the reference villas are larger, with stone cladding and screens. |

## What the sheets show

- Low (walkthrough) and High (still) show the same furnished house; High adds the cove light, softer light from the
  path tracer and the finishing pass. Low is wider (the walkthrough's lens).
- Against your references the gap is in the design, not the light: feature ceilings, chandeliers, stone and wood
  feature walls, padded headboards and decor are not in our kits. That is the next step for the kits.
- Bar and puja are empty in this house because this older job's plan reads them as generic rooms (the plan made by
  PART 1's direct export keeps their types, and their kits are placed).
- House: nandu (job 88c31f1e3f0d plan, rebuilt 2026-11-20). Low: three.js walkthrough, Chrome for Testing 158 with
  Metal. High: Cycles on Metal, the style handover's look, evening.
