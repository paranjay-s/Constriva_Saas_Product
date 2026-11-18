/**
 * Test data only: a BoqResult exactly as the server sends it.
 *
 * It covers what the page must cope with: six categories (codes A to F), lettered serials
 * ("17a", "17b"), rows out of order, an excluded row, allowance rows, a row without
 * `quantity_decimals`, the same sub-category name in two categories, extra keys on rows
 * and on the loose objects, the assumptions the bill was calculated with (two levels with
 * their own heights, a building type from the plan that is none of the three a person can
 * pick), and the older top-level keys the page must ignore.
 */

interface RawComponent {
  label: string;
  quantity: number;
  unit: string;
  quantity_decimals?: number;
}

function row(
  serial_no: number | string,
  item_code: string,
  category_code: string,
  category: string,
  sub_category: string,
  name: string,
  unit: string,
  quantity: number,
  extra: Record<string, unknown> = {},
) {
  return {
    serial_no,
    item_code,
    category_code,
    category,
    sub_category,
    name,
    unit,
    quantity,
    components: [] as RawComponent[],
    calc_type: 'geometry',
    quote_status: 'INCLUDED',
    note: '',
    ...extra,
  };
}

const A = 'Structure and Masonry';
const B = 'Civil, Finishing and Waterproofing';
const C = 'Architectural Components';
const D = 'Electrical and HVAC';
const E = 'Plumbing and Sanitary';
const F = 'Site Setup';

export const RAW_BOQ_RESULT = {
  items: [
    row(18, 'false_ceiling', 'B', B, 'Ceilings', 'Gypsum false ceiling', 'm2', 1234.5, { quantity_decimals: 2 }),
    row('17b', 'wall_putty', 'B', B, 'Painting', 'Wall putty', 'kg', 310, { quantity_decimals: 2 }),
    row(1, 'bricks', 'A', A, 'Masonry', 'Bricks', 'nos', 12480, {
      quantity_decimals: 0,
      components: [
        { label: 'Brickwork volume', quantity: 28.6, unit: 'm3', quantity_decimals: 2 },
        { label: 'Mortar joints', quantity: 6250, unit: 'kg', quantity_decimals: 2 },
        { label: 'Wall panels', quantity: 42, unit: 'nos', quantity_decimals: 0 },
      ],
      note: 'Includes 5% waste for cutting and breakage.',
      // keys the calculator keeps on its core rows; they must survive a round trip to export
      id: 'mat-bricks',
      surface_tag: 'masonry_walls',
      waste_multiplier: 1.05,
      details: { wall_volume_m3: 28.6 },
    }),
    row(58, 'site_barricading', 'F', F, 'Preliminaries', 'Site barricading', 'rm', 96.5, {
      quantity_decimals: 2,
      calc_type: 'allowance',
      quote_status: 'EXCLUDED_FROM_QUOTE',
      note: 'Provided by the client.',
    }),
    // no quantity_decimals: the unit decides (litres are measured)
    row(17, 'interior_paint', 'B', B, 'Painting', 'Interior emulsion paint', 'l', 86.4),
    row(33, 'switches_sockets', 'D', D, 'Wiring devices', 'Switches and sockets', 'nos', 64, {
      quantity_decimals: 0,
      calc_type: 'allowance',
      note: 'Allowance of 8 points per room.',
    }),
    row('17a', 'interior_primer', 'B', B, 'Painting', 'Interior primer', 'l', 43.2, { quantity_decimals: 2 }),
    row(2, 'steel', 'A', A, 'Reinforcement', 'Steel reinforcement', 'kg', 2884.5, { quantity_decimals: 2 }),
    row(3, 'cement', 'A', A, 'Concrete and binders', 'Cement', 'bags (50 kg)', 412, { quantity_decimals: 0 }),
    row(27, 'internal_doors', 'C', C, 'Doors and glazing', 'Internal doors', 'nos', 9, {
      quantity_decimals: 0,
      calc_type: 'count',
    }),
    row(48, 'wash_basins', 'E', E, 'Sanitary fixtures', 'Wash basins', 'nos', 3, {
      quantity_decimals: 0,
      calc_type: 'count',
    }),
    row(30, 'driveway_paving', 'C', C, 'External works', 'Driveway paving', 'm2', 54, {
      quantity_decimals: 2,
      quote_status: 'EXCLUDED_FROM_QUOTE',
      note: 'Outside the building quote.',
    }),
    row(22, 'compound_wall', 'B', B, 'External works', 'Compound wall plaster', 'm2', 148.25, { quantity_decimals: 2 }),
  ],
  warnings: [
    'Scale was assumed: no scale text or dimension label was found.',
    'Two rooms have no name and were counted as general rooms.',
    'Staircase area was estimated from the stair symbol.',
    'External works are measured from the plot boundary.',
  ],
  geometry_summary: {
    a_built_total_m2: 1234.5,
    a_built_total_sqft: 13288.05,
    levels_count: 2,
    rooms_count: 14,
    bathrooms_count: 3,
    wall_length_m: 212.4,
  },
  project_metadata: {
    project_title: 'Green Villa',
    client: 'Sharma Family',
    subject: null,
    building_type: 'Residential',
    source_file_name: 'green-villa.pdf',
    drawing_no: 'A-101',
  },
  assumptions: {
    // the plan's own words, lower-cased by the server
    building_type: 'residential',
    building_type_source: 'plan',
    ceiling_heights_m: [2.8, 3.1],
    ceiling_height_source: 'plan',
    tile_size_mm: '600x600',
    tile_pattern: 'standard',
    false_ceiling_share: 1,
    plot_perimeter_m: null,
    // a key the page does not know: it must survive a round trip to export
    skirting_height_mm: 100,
  },
  // older keys: ignored by the page and never sent to export
  materials: [{ id: 'mat-bricks', name: 'Bricks' }],
  materials_by_key: { bricks: { id: 'mat-bricks', name: 'Bricks', quantity: 12480 } },
  level_summaries: [{ level: 0, area_m2: 620 }],
  room_breakdown: [{ room: 'Living', area_m2: 32.5 }],
};
