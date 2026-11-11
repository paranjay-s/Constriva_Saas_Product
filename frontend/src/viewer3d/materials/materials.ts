// materials/materials.ts
import * as THREE from 'three';
import { PALETTE } from './palette';
import { getOrCreateTextures, disposeTextures } from './textures';

export interface MaterialLibrary {
  wallFace: THREE.MeshStandardMaterial;
  wallFaceExterior: THREE.MeshStandardMaterial;
  wallCapExterior: THREE.MeshStandardMaterial;
  wallCapInterior: THREE.MeshStandardMaterial;
  wallSkirting: THREE.MeshStandardMaterial;
  glass: THREE.MeshPhysicalMaterial;
  frame: THREE.MeshStandardMaterial;
  doorWood: THREE.MeshStandardMaterial;
  ground: THREE.MeshStandardMaterial;
  plinth: THREE.MeshStandardMaterial;
  floorLiving: THREE.MeshStandardMaterial;
  floorBedroom: THREE.MeshStandardMaterial;
  floorDeck: THREE.MeshStandardMaterial;
  floorBath: THREE.MeshStandardMaterial;
  floorPuja: THREE.MeshStandardMaterial;
  floorConcrete: THREE.MeshStandardMaterial;
  fabricLight: THREE.MeshStandardMaterial;
  cushion: THREE.MeshStandardMaterial;
  linen: THREE.MeshStandardMaterial;
  woodFurniture: THREE.MeshStandardMaterial;
  accentTeal: THREE.MeshStandardMaterial;
  accentGold: THREE.MeshStandardMaterial;
  stoolDark: THREE.MeshStandardMaterial;
  stone: THREE.MeshStandardMaterial;
  rug: THREE.MeshStandardMaterial;
  foliageA: THREE.MeshStandardMaterial;
  foliageB: THREE.MeshStandardMaterial;
  foliageC: THREE.MeshStandardMaterial;
  pot: THREE.MeshStandardMaterial;
  car: THREE.MeshStandardMaterial;
  carGlass: THREE.MeshStandardMaterial;
  carTyre: THREE.MeshStandardMaterial;
  contactBlob: THREE.MeshBasicMaterial;
  wallBaseAO: THREE.MeshBasicMaterial;

  // Highlights
  highlightBrick: THREE.MeshStandardMaterial;
  highlightSteel: THREE.MeshStandardMaterial;
  highlightCement: THREE.MeshStandardMaterial;
  highlightSand: THREE.MeshStandardMaterial;
  highlightBallast: THREE.MeshStandardMaterial;
  highlightPlaster: THREE.MeshStandardMaterial;
  highlightTiles: THREE.MeshStandardMaterial;
  dispose: () => void;
}

let cachedMaterials: MaterialLibrary | null = null;

export function getOrCreateMaterials(maxAnisotropy: number = 8): MaterialLibrary {
  if (cachedMaterials) return cachedMaterials;

  const textures = getOrCreateTextures(maxAnisotropy);

  // Signature dollhouse walls
  const wallFace = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.wallFace),
    roughness: 0.88,
    metalness: 0.0,
  });

  const wallFaceExterior = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.wallFaceExterior),
    roughness: 0.92,
    metalness: 0.0,
  });

  const wallSkirting = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.wallSkirting),
    roughness: 0.42,
    metalness: 0.04,
  });

  const wallCapExterior = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.wallCapExterior),
    roughness: 0.72,
    metalness: 0.05,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  });

  const wallCapInterior = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.wallCapInterior),
    roughness: 0.88,
    metalness: 0.0,
  });

  // Glazing
  const glass = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(PALETTE.glass),
    transparent: true,
    opacity: 0.28,
    roughness: 0.05,
    metalness: 0.1,
    transmission: 0.8,
    ior: 1.5,
    depthWrite: false,
  });

  const frame = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.frame),
    roughness: 0.45,
    metalness: 0.35,
  });

  const doorWood = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.woodFurniture),
    roughness: 0.45,
    metalness: 0.04,
  });

  // Ground and plinth
  const ground = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.ground),
    roughness: 0.95,
    metalness: 0.0,
  });

  const plinth = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.plinth),
    roughness: 0.85,
    metalness: 0.02,
  });

  // Floors
  const floorLiving = new THREE.MeshStandardMaterial({
    map: textures.woodLiving,
    roughness: 0.42,
    metalness: 0.03,
  });

  const floorBedroom = new THREE.MeshStandardMaterial({
    map: textures.woodBedroom,
    roughness: 0.44,
    metalness: 0.03,
  });

  const floorDeck = new THREE.MeshStandardMaterial({
    map: textures.woodDeck,
    roughness: 0.65,
    metalness: 0.01,
  });

  const floorBath = new THREE.MeshStandardMaterial({
    map: textures.tileBath,
    roughness: 0.26,
    metalness: 0.05,
  });

  const floorPuja = new THREE.MeshStandardMaterial({
    map: textures.marblePuja,
    roughness: 0.22,
    metalness: 0.08,
  });

  const floorConcrete = new THREE.MeshStandardMaterial({
    map: textures.concrete,
    roughness: 0.9,
    metalness: 0.0,
  });

  // Furniture
  const fabricLight = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.fabricLight),
    roughness: 0.95,
    metalness: 0.0,
  });

  const cushion = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.cushion),
    roughness: 0.92,
    metalness: 0.0,
  });

  const linen = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.linen),
    roughness: 0.9,
    metalness: 0.0,
  });

  const woodFurniture = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.woodFurniture),
    roughness: 0.48,
    metalness: 0.03,
  });

  const accentTeal = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.accentTeal),
    roughness: 0.72,
    metalness: 0.02,
  });

  const accentGold = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.accentGold),
    roughness: 0.35,
    metalness: 0.3,
  });

  const stoolDark = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.stoolDark),
    roughness: 0.55,
    metalness: 0.15,
  });

  const stone = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.stone),
    roughness: 0.35,
    metalness: 0.04,
  });

  const rug = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.rug),
    roughness: 0.95,
    metalness: 0.0,
  });

  const foliageA = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.foliageA),
    roughness: 0.85,
    metalness: 0.0,
    flatShading: false,
  });

  const foliageB = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.foliageB),
    roughness: 0.85,
    metalness: 0.0,
    flatShading: false,
  });

  const foliageC = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.foliageC),
    roughness: 0.85,
    metalness: 0.0,
    flatShading: false,
  });

  const pot = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.pot),
    roughness: 0.78,
    metalness: 0.02,
  });

  const car = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.car),
    roughness: 0.3,
    metalness: 0.5,
  });

  const carGlass = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.carGlass),
    roughness: 0.1,
    metalness: 0.8,
  });

  const carTyre = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.carTyre),
    roughness: 0.95,
    metalness: 0.0,
  });

  const contactBlob = new THREE.MeshBasicMaterial({
    map: textures.contactBlob,
    transparent: true,
    opacity: 0.48,
    depthWrite: false,
  });

  const wallBaseAO = new THREE.MeshBasicMaterial({
    color: new THREE.Color(0x000000),
    transparent: true,
    opacity: 0.18,
    depthWrite: false,
  });

  // Quantity Surveying highlights
  const highlightBrick = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightBrick),
    emissive: new THREE.Color(PALETTE.highlightBrick),
    emissiveIntensity: 0.65,
    roughness: 0.6,
  });

  const highlightSteel = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightSteel),
    emissive: new THREE.Color(PALETTE.highlightSteel),
    emissiveIntensity: 0.7,
    roughness: 0.4,
  });

  const highlightCement = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightCement),
    emissive: new THREE.Color(PALETTE.highlightCement),
    emissiveIntensity: 0.65,
    roughness: 0.6,
  });

  const highlightSand = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightSand),
    emissive: new THREE.Color(PALETTE.highlightSand),
    emissiveIntensity: 0.65,
    roughness: 0.6,
  });

  const highlightBallast = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightBallast),
    emissive: new THREE.Color(PALETTE.highlightBallast),
    emissiveIntensity: 0.65,
    roughness: 0.6,
  });

  const highlightPlaster = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightPlaster),
    emissive: new THREE.Color(PALETTE.highlightPlaster),
    emissiveIntensity: 0.65,
    roughness: 0.6,
  });

  const highlightTiles = new THREE.MeshStandardMaterial({
    color: new THREE.Color(PALETTE.highlightTiles),
    emissive: new THREE.Color(PALETTE.highlightTiles),
    emissiveIntensity: 0.65,
    roughness: 0.35,
  });

  cachedMaterials = {
    wallFace,
    wallFaceExterior,
    wallCapExterior,
    wallCapInterior,
    wallSkirting,
    glass,
    frame,
    doorWood,
    ground,
    plinth,
    floorLiving,
    floorBedroom,
    floorDeck,
    floorBath,
    floorPuja,
    floorConcrete,
    fabricLight,
    cushion,
    linen,
    woodFurniture,
    accentTeal,
    accentGold,
    stoolDark,
    stone,
    rug,
    foliageA,
    foliageB,
    foliageC,
    pot,
    car,
    carGlass,
    carTyre,
    contactBlob,
    wallBaseAO,
    highlightBrick,
    highlightSteel,
    highlightCement,
    highlightSand,
    highlightBallast,
    highlightPlaster,
    highlightTiles,
    dispose: () => {
      disposeTextures();
      cachedMaterials = null;
    },
  };

  return cachedMaterials;
}
