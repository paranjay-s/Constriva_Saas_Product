// materials/palette.ts
// Single source of truth for all architectural design tokens (sRGB Hex)

export const PALETTE = {
  // Studio sky backdrop — soft atmospheric daylight gradient (replaces washed-out white)
  bgTop: '#D8E7F5',
  bgBottom: '#C2D7E9',

  // Ground and plinth base
  ground: '#E5E0D5',
  plinth: '#DDD7CD',

  // Architectural walls & caps
  wallFace: '#FAF8F4', // Interior silk eggshell plaster
  wallFaceExterior: '#ECE4D4', // Exterior warm sand stucco
  wallCapExterior: '#2B2C30', // Signature dark charcoal exterior cap
  wallCapInterior: '#E6E3DC', // Subtle light interior cap
  wallSkirting: '#382D22', // 10cm dark walnut baseboard skirting

  // Glazing & fenestration
  glass: '#C5E6F2',
  frame: '#232427',

  // Flooring
  woodLiving: '#C89A65',
  woodLivingLow: '#BC8D58',
  woodLivingHigh: '#D6A872',
  woodBedroom: '#C4955B', // Warm honey oak herringbone
  woodDeck: '#BA8048', // Rich teak terrace decking
  woodDeckLow: '#AC723B',
  woodDeckHigh: '#C98F56',
  tileBath: '#DCE2E7', // Modern anti-skid porcelain tile
  tileGrout: '#C6CDD3',
  marblePuja: '#F7F5F0', // Polished Italian Carrara marble
  concrete: '#CACAC6',

  // Soft rounded furniture
  fabricLight: '#ECE8E1',
  cushion: '#DDD7CD',
  linen: '#F6F4EE',
  woodFurniture: '#B88755',
  accentTeal: '#2A5C63', // Signature architectural accent
  accentGold: '#C8A048',
  stoolDark: '#262628',
  stone: '#F4F2EC',
  rug: '#D6D3CB',

  // Greenery & landscaping
  foliageA: '#588A47',
  foliageB: '#447537',
  foliageC: '#76A052',
  pot: '#E5E0D6',

  // Vehicles
  car: '#D2D6DC',
  carGlass: '#282F36',
  carTyre: '#18181A',

  // Ambient Occlusion
  aoBase: '#000000',

  // Material Highlighting (BOQ verification)
  highlightBrick: '#E05638',
  highlightSteel: '#06B6D4',
  highlightCement: '#A855F7',
  highlightSand: '#F59E0B',
  highlightBallast: '#6366F1',
  highlightPlaster: '#FB7185',
  highlightTiles: '#10B981',
} as const;

export type ColorToken = keyof typeof PALETTE;
