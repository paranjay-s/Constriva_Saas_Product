import * as THREE from 'three';

// Material definitions for realistic and clay rendering modes
export interface MaterialTheme {
  isClay: boolean;
  wallPlaster: THREE.MeshStandardMaterialParameters;
  wallPlasterExt: THREE.MeshStandardMaterialParameters;
  foundationSlab: THREE.MeshStandardMaterialParameters;
  woodSlatAccent: THREE.MeshStandardMaterialParameters;
  bedroomFloor: THREE.MeshStandardMaterialParameters;
  livingFloor: THREE.MeshStandardMaterialParameters;
  kitchenFloor: THREE.MeshStandardMaterialParameters;
  bathFloor: THREE.MeshStandardMaterialParameters;
  diningFloor: THREE.MeshStandardMaterialParameters;
  balconyFloor: THREE.MeshStandardMaterialParameters;
  lawnFloor: THREE.MeshStandardMaterialParameters;
  corridorFloor: THREE.MeshStandardMaterialParameters;
  utilityFloor: THREE.MeshStandardMaterialParameters;
  voidFloor: THREE.MeshStandardMaterialParameters;
  rugSlateBlue: THREE.MeshStandardMaterialParameters;
  rugNeutral: THREE.MeshStandardMaterialParameters;
  doorWood: THREE.MeshStandardMaterialParameters;
  doorFrame: THREE.MeshStandardMaterialParameters;
  windowFrame: THREE.MeshStandardMaterialParameters;
  windowGlass: THREE.MeshStandardMaterialParameters;
  railingMetal: THREE.MeshStandardMaterialParameters;
  railingGlass: THREE.MeshStandardMaterialParameters;
  // Furniture
  sofaFabric: THREE.MeshStandardMaterialParameters;
  cushionBlue: THREE.MeshStandardMaterialParameters;
  cushionFabric: THREE.MeshStandardMaterialParameters;
  chairFabric: THREE.MeshStandardMaterialParameters;
  marbleTable: THREE.MeshStandardMaterialParameters;
  brassGold: THREE.MeshStandardMaterialParameters;
  bedHeadboardTeal: THREE.MeshStandardMaterialParameters;
  bedLinen: THREE.MeshStandardMaterialParameters;
  bedDuvet: THREE.MeshStandardMaterialParameters;
  bedThrow: THREE.MeshStandardMaterialParameters;
  woodFurniture: THREE.MeshStandardMaterialParameters;
  darkWood: THREE.MeshStandardMaterialParameters;
  countertop: THREE.MeshStandardMaterialParameters;
  cabinetry: THREE.MeshStandardMaterialParameters;
  sanitaryCeramic: THREE.MeshStandardMaterialParameters;
  chromeFixture: THREE.MeshStandardMaterialParameters;
  tvScreen: THREE.MeshStandardMaterialParameters;
  indoorPlant: THREE.MeshStandardMaterialParameters;
  plantPotWhite: THREE.MeshStandardMaterialParameters;
  lampGlow: THREE.MeshStandardMaterialParameters;
}

export const REALISTIC_THEME: MaterialTheme = {
  isClay: false,
  wallPlaster: {
    color: '#E8E3D8', // Warm architectural linen ivory for interior room dividing walls
    roughness: 0.82,
    metalness: 0.01,
  },
  wallPlasterExt: {
    color: '#FFFFFF', // Crisp architectural pure white for exterior boundary walls
    roughness: 0.85,
    metalness: 0.01,
  },
  foundationSlab: {
    color: '#FFFFFF', // Crisp white plinth slab
    roughness: 0.8,
    metalness: 0.02,
  },
  woodSlatAccent: {
    color: '#C69358', // Warm vertical timber slats
    roughness: 0.45,
    metalness: 0.03,
  },
  bedroomFloor: {
    color: '#C4955B', // Warm natural honey oak parquet
    roughness: 0.38,
    metalness: 0.04,
  },
  livingFloor: {
    color: '#D4A367', // Warm luminous amber oak
    roughness: 0.36,
    metalness: 0.04,
  },
  kitchenFloor: {
    color: '#DCD6CB', // Modern polished pearl travertine tile
    roughness: 0.32,
    metalness: 0.05,
  },
  bathFloor: {
    color: '#E5EDF4', // Elegant cool Carrara marble porcelain
    roughness: 0.22,
    metalness: 0.08,
  },
  diningFloor: {
    color: '#CE9E63', // Continuous warm oak dining
    roughness: 0.38,
    metalness: 0.04,
  },
  balconyFloor: {
    color: '#BA834E', // Rich warm natural teak terrace decking
    roughness: 0.65,
    metalness: 0.02,
  },
  lawnFloor: {
    color: '#3E8E34', // Rich vibrant emerald grass (Homescapes realistic tone)
    roughness: 0.88,
    metalness: 0.01,
  },
  corridorFloor: {
    color: '#E8E3DA', // Light polished limestone circulation floor
    roughness: 0.45,
    metalness: 0.03,
  },
  utilityFloor: {
    color: '#CBD5E1', // Cool non-slip brushed slate utility tile
    roughness: 0.4,
    metalness: 0.02,
  },
  voidFloor: {
    color: '#4B5563', // Deep charcoal architectural ventilation shaft
    roughness: 0.95,
    metalness: 0.0,
  },
  rugSlateBlue: {
    color: '#4A6B82', // Rich slate denim blue area rug
    roughness: 0.95,
    metalness: 0.0,
  },
  rugNeutral: {
    color: '#D8D3C8', // Neutral woven rug
    roughness: 0.92,
    metalness: 0.0,
  },
  doorWood: {
    color: '#A87342', // Warm natural timber door
    roughness: 0.42,
    metalness: 0.04,
  },
  doorFrame: {
    color: '#222326', // Sleek architectural black bronze
    roughness: 0.4,
    metalness: 0.35,
  },
  windowFrame: {
    color: '#1E1E20', // Architectural black aluminum
    roughness: 0.3,
    metalness: 0.5,
  },
  windowGlass: {
    color: '#B6D6E8',
    transparent: true,
    opacity: 0.28,
    roughness: 0.1,
    metalness: 0.1,
  },
  railingMetal: {
    color: '#222326',
    roughness: 0.35,
    metalness: 0.7,
  },
  railingGlass: {
    color: '#C8E2EF',
    transparent: true,
    opacity: 0.35,
    roughness: 0.1,
    metalness: 0.05,
  },
  sofaFabric: {
    color: '#E4E2DC', // Contemporary light warm grey / ivory linen
    roughness: 0.88,
    metalness: 0.02,
  },
  cushionBlue: {
    color: '#3E5E72', // Slate denim blue accent cushion
    roughness: 0.82,
    metalness: 0.02,
  },
  cushionFabric: {
    color: '#D4CEBF', // Neutral textured cushion
    roughness: 0.82,
    metalness: 0.02,
  },
  chairFabric: {
    color: '#F4F2EE', // Cream upholstered seat
    roughness: 0.85,
    metalness: 0.01,
  },
  marbleTable: {
    color: '#FAFAFA', // Polished white Carrara marble
    roughness: 0.18,
    metalness: 0.12,
  },
  brassGold: {
    color: '#CCA352', // Brushed warm satin brass
    roughness: 0.28,
    metalness: 0.85,
  },
  bedHeadboardTeal: {
    color: '#234B5C', // Rich deep teal/petrol velvet headboard
    roughness: 0.75,
    metalness: 0.05,
  },
  bedLinen: {
    color: '#FFFFFF', // Crisp white hotel bedding
    roughness: 0.9,
    metalness: 0.01,
  },
  bedDuvet: {
    color: '#F4F4F2', // Soft white duvet
    roughness: 0.85,
    metalness: 0.01,
  },
  bedThrow: {
    color: '#5A626A', // Folded slate/charcoal bed throw
    roughness: 0.88,
    metalness: 0.02,
  },
  woodFurniture: {
    color: '#B8854E', // Warm honey oak timber
    roughness: 0.42,
    metalness: 0.04,
  },
  darkWood: {
    color: '#38281B', // Deep espresso walnut
    roughness: 0.45,
    metalness: 0.04,
  },
  countertop: {
    color: '#FCFCFC', // Pure white polished quartz countertop
    roughness: 0.15,
    metalness: 0.1,
  },
  cabinetry: {
    color: '#52686F', // Contemporary slate-grey / sage cabinetry
    roughness: 0.52,
    metalness: 0.06,
  },
  sanitaryCeramic: {
    color: '#FFFFFF', // Gloss white ceramic
    roughness: 0.15,
    metalness: 0.08,
  },
  chromeFixture: {
    color: '#DCDCDC',
    roughness: 0.12,
    metalness: 0.92,
  },
  tvScreen: {
    color: '#141416',
    roughness: 0.1,
    metalness: 0.85,
  },
  indoorPlant: {
    color: '#2E562A', // Lush tropical green foliage
    roughness: 0.55,
    metalness: 0.02,
  },
  plantPotWhite: {
    color: '#FFFFFF', // Clean white ceramic pot
    roughness: 0.3,
    metalness: 0.05,
  },
  lampGlow: {
    color: '#FFF2D6',
    emissive: '#FFDF9E',
    emissiveIntensity: 0.9,
    roughness: 0.25,
  },
};

export const CLAY_THEME: MaterialTheme = {
  isClay: true,
  wallPlaster: {
    color: '#EDE9E1',
    roughness: 0.9,
    metalness: 0.0,
  },
  wallPlasterExt: {
    color: '#E4DFD5',
    roughness: 0.92,
    metalness: 0.0,
  },
  foundationSlab: {
    color: '#DCD6CA',
    roughness: 0.85,
    metalness: 0.0,
  },
  woodSlatAccent: {
    color: '#D2CBBF',
    roughness: 0.85,
    metalness: 0.0,
  },
  bedroomFloor: {
    color: '#DFD8CC',
    roughness: 0.85,
    metalness: 0.0,
  },
  livingFloor: {
    color: '#E8E3DA',
    roughness: 0.85,
    metalness: 0.0,
  },
  kitchenFloor: {
    color: '#DDD8CE',
    roughness: 0.85,
    metalness: 0.0,
  },
  bathFloor: {
    color: '#DCD7CE',
    roughness: 0.85,
    metalness: 0.0,
  },
  diningFloor: {
    color: '#E2DDD3',
    roughness: 0.85,
    metalness: 0.0,
  },
  balconyFloor: {
    color: '#D5CFC3',
    roughness: 0.9,
    metalness: 0.0,
  },
  lawnFloor: {
    color: '#D2D8CF',
    roughness: 0.9,
    metalness: 0.0,
  },
  corridorFloor: {
    color: '#E0DAD0',
    roughness: 0.85,
    metalness: 0.0,
  },
  utilityFloor: {
    color: '#D4CEC4',
    roughness: 0.85,
    metalness: 0.0,
  },
  voidFloor: {
    color: '#B8B2A8',
    roughness: 0.95,
    metalness: 0.0,
  },
  rugSlateBlue: {
    color: '#CDC7BD',
    roughness: 0.9,
    metalness: 0.0,
  },
  rugNeutral: {
    color: '#DAD4CA',
    roughness: 0.9,
    metalness: 0.0,
  },
  doorWood: {
    color: '#C2BBB0',
    roughness: 0.8,
    metalness: 0.0,
  },
  doorFrame: {
    color: '#8A847A',
    roughness: 0.8,
    metalness: 0.0,
  },
  windowFrame: {
    color: '#7A756D',
    roughness: 0.8,
    metalness: 0.0,
  },
  windowGlass: {
    color: '#CBD3D8',
    transparent: true,
    opacity: 0.5,
    roughness: 0.2,
  },
  railingMetal: {
    color: '#858076',
    roughness: 0.8,
    metalness: 0.0,
  },
  railingGlass: {
    color: '#CBD3D8',
    transparent: true,
    opacity: 0.45,
    roughness: 0.2,
  },
  sofaFabric: {
    color: '#DDD7CD',
    roughness: 0.9,
    metalness: 0.0,
  },
  cushionBlue: {
    color: '#C8C2B7',
    roughness: 0.9,
    metalness: 0.0,
  },
  cushionFabric: {
    color: '#D4CFC5',
    roughness: 0.9,
    metalness: 0.0,
  },
  chairFabric: {
    color: '#E5E0D6',
    roughness: 0.9,
    metalness: 0.0,
  },
  marbleTable: {
    color: '#EAE6DE',
    roughness: 0.8,
    metalness: 0.0,
  },
  brassGold: {
    color: '#BCB6AA',
    roughness: 0.8,
    metalness: 0.0,
  },
  bedHeadboardTeal: {
    color: '#BCB6AC',
    roughness: 0.9,
    metalness: 0.0,
  },
  bedLinen: {
    color: '#EBE7DF',
    roughness: 0.9,
    metalness: 0.0,
  },
  bedDuvet: {
    color: '#DFD9CE',
    roughness: 0.9,
    metalness: 0.0,
  },
  bedThrow: {
    color: '#CEC8BF',
    roughness: 0.9,
    metalness: 0.0,
  },
  woodFurniture: {
    color: '#CCC6BC',
    roughness: 0.85,
    metalness: 0.0,
  },
  darkWood: {
    color: '#B5AFA4',
    roughness: 0.85,
    metalness: 0.0,
  },
  countertop: {
    color: '#E7E3DB',
    roughness: 0.85,
    metalness: 0.0,
  },
  cabinetry: {
    color: '#C0B9AE',
    roughness: 0.85,
    metalness: 0.0,
  },
  sanitaryCeramic: {
    color: '#E8E4DC',
    roughness: 0.85,
    metalness: 0.0,
  },
  chromeFixture: {
    color: '#A59F95',
    roughness: 0.7,
    metalness: 0.1,
  },
  tvScreen: {
    color: '#8A847A',
    roughness: 0.8,
    metalness: 0.0,
  },
  indoorPlant: {
    color: '#BDB7AC',
    roughness: 0.85,
    metalness: 0.0,
  },
  plantPotWhite: {
    color: '#E6E2DA',
    roughness: 0.85,
    metalness: 0.0,
  },
  lampGlow: {
    color: '#EFEBE3',
    roughness: 0.8,
  },
};

export type RoomCategory =
  | 'living'
  | 'bedroom'
  | 'kitchen'
  | 'bathroom'
  | 'dining'
  | 'balcony'
  | 'corridor'
  | 'lawn'
  | 'parking'
  | 'utility'
  | 'void'
  | 'general';

export function categorizeRoom(roomName?: string | null, roomId?: string | null): RoomCategory {
  const text = `${roomName || ''} ${roomId || ''}`.toLowerCase();

  if (text.includes('park') || text.includes('car') || text.includes('garage') || text.includes('driveway')) {
    return 'parking';
  }
  if (text.includes('open') || text.includes('shaft') || text.includes('duct') || text.includes('void')) {
    return 'void';
  }
  if (text.includes('lawn') || text.includes('garden')) {
    return 'lawn';
  }
  if (text.includes('bed') || text.includes('master') || text.includes('guest') || text.includes('child')) {
    return 'bedroom';
  }
  if (text.includes('bath') || text.includes('toilet') || text.includes('toi') || text.includes('wc') || text.includes('powder')) {
    return 'bathroom';
  }
  if (text.includes('kitchen') || text.includes('kit') || text.includes('pantry') || text.includes('cook')) {
    return 'kitchen';
  }
  if (text.includes('dining') || (text.includes('din') && !text.includes('building'))) {
    return 'dining';
  }
  if (text.includes('balcony') || text.includes('terrace') || text.includes('verandah') || text.includes('sitout') || text.includes('deck') || text.includes('porch')) {
    return 'balcony';
  }
  if (text.includes('living') || text.includes('drg') || text.includes('drawing') || text.includes('lounge') || text.includes('hall') || text.includes('family')) {
    return 'living';
  }
  if (text.includes('corridor') || text.includes('passage') || text.includes('foyer') || text.includes('entry') || text.includes('hallway') || text.includes('stair')) {
    return 'corridor';
  }
  if (text.includes('wash') || text.includes('laundry') || text.includes('util')) {
    return 'utility';
  }
  return 'general';
}

export function getRoomFloorMaterialParams(
  category: RoomCategory,
  theme: MaterialTheme
): THREE.MeshStandardMaterialParameters {
  switch (category) {
    case 'bedroom':
      return theme.bedroomFloor;
    case 'living':
      return theme.livingFloor;
    case 'dining':
      return theme.diningFloor;
    case 'kitchen':
      return theme.kitchenFloor;
    case 'bathroom':
      return theme.bathFloor;
    case 'balcony':
      return theme.balconyFloor;
    case 'lawn':
      return theme.lawnFloor;
    case 'corridor':
      return theme.corridorFloor;
    case 'utility':
      return theme.utilityFloor;
    case 'void':
      return theme.voidFloor;
    case 'parking':
      return {
        color: '#A2A9B2',
        roughness: 0.82,
        metalness: 0.04,
      };
    case 'general':
    default:
      return theme.corridorFloor;
  }
}
