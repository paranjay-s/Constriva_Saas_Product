// frontend/src/features/plan-viewer/materials/materials.ts
// Enscape-Tier Procedural PBR Engine & Architectural Shaders
import * as THREE from 'three';

// Procedural texture cache to ensure zero memory waste and fast reuse
interface ProceduralPbrTextures {
  carraraMarble: THREE.CanvasTexture;
  herringboneOak: THREE.CanvasTexture;
  ceramicTile: THREE.CanvasTexture;
  sandStucco: THREE.CanvasTexture;
  lawnGrass: THREE.CanvasTexture;
  teakDeck: THREE.CanvasTexture;
}

let pbrTextures: ProceduralPbrTextures | null = null;

function createCarraraMarbleCanvas(): HTMLCanvasElement {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  // Luminous porcelain base
  ctx.fillStyle = '#F8F7F4';
  ctx.fillRect(0, 0, size, size);

  // Subtle tonal clouding
  const grad = ctx.createLinearGradient(0, 0, size, size);
  grad.addColorStop(0, 'rgba(235, 230, 222, 0.4)');
  grad.addColorStop(0.5, 'rgba(248, 247, 244, 0.2)');
  grad.addColorStop(1, 'rgba(230, 225, 218, 0.4)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Organic soft Carrara grey/warm gold veins
  const drawVein = (
    pts: [number, number][],
    color: string,
    width: number,
    blur: number
  ) => {
    ctx.save();
    ctx.filter = `blur(${blur}px)`;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1];
      const curr = pts[i];
      const cpx = (prev[0] + curr[0]) / 2 + (Math.random() - 0.5) * 40;
      const cpy = (prev[1] + curr[1]) / 2 + (Math.random() - 0.5) * 40;
      ctx.quadraticCurveTo(cpx, cpy, curr[0], curr[1]);
    }
    ctx.stroke();
    ctx.restore();
  };

  // Primary feather veins
  drawVein(
    [[60, 0], [220, 260], [480, 520], [780, 740], [1024, 980]],
    'rgba(145, 135, 125, 0.16)',
    9,
    4
  );
  drawVein(
    [[0, 340], [260, 480], [520, 780], [700, 1024]],
    'rgba(160, 150, 140, 0.14)',
    6,
    3
  );

  // Fine micro-fractures with subtle gold undertone
  drawVein(
    [[350, 100], [420, 320], [560, 460], [840, 620]],
    'rgba(180, 155, 120, 0.18)',
    3,
    1.5
  );
  drawVein(
    [[700, 50], [620, 240], [720, 420], [920, 540]],
    'rgba(150, 140, 130, 0.15)',
    2.5,
    1
  );

  return canvas;
}

function createHerringboneOakCanvas(): HTMLCanvasElement {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  // Base warm natural honey oak
  ctx.fillStyle = '#C89C65';
  ctx.fillRect(0, 0, size, size);

  const plankW = 48;
  const plankL = 144;

  const oakColors = [
    '#C4955B',
    '#CB9F68',
    '#BC8D54',
    '#D2A772',
    '#C79860',
    '#BF9056',
  ];

  ctx.save();
  // Draw chevron rows
  for (let y = -plankL; y < size + plankL; y += plankW * 2) {
    for (let x = -plankL; x < size + plankL; x += plankL) {
      const colIdx = Math.floor(Math.abs(Math.sin(x * 12 + y * 17)) * oakColors.length);
      ctx.fillStyle = oakColors[colIdx % oakColors.length];

      // Left branch of chevron (45 deg)
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(Math.PI / 4);
      ctx.fillRect(0, 0, plankL, plankW);

      // Micro grain lines
      ctx.fillStyle = 'rgba(60, 35, 15, 0.05)';
      for (let g = 6; g < plankW; g += 9) {
        ctx.fillRect(0, g, plankL, 1.5);
      }

      // Dark joint border
      ctx.strokeStyle = 'rgba(40, 25, 10, 0.35)';
      ctx.lineWidth = 1.8;
      ctx.strokeRect(0, 0, plankL, plankW);
      ctx.restore();

      // Right branch of chevron (-45 deg)
      ctx.save();
      ctx.translate(x + plankL * 0.707, y);
      ctx.rotate(-Math.PI / 4);
      ctx.fillRect(0, 0, plankL, plankW);

      ctx.fillStyle = 'rgba(60, 35, 15, 0.05)';
      for (let g = 6; g < plankW; g += 9) {
        ctx.fillRect(0, g, plankL, 1.5);
      }

      ctx.strokeStyle = 'rgba(40, 25, 10, 0.35)';
      ctx.lineWidth = 1.8;
      ctx.strokeRect(0, 0, plankL, plankW);
      ctx.restore();
    }
  }
  ctx.restore();

  return canvas;
}

function createCeramicTileCanvas(): HTMLCanvasElement {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  // Modern anti-skid porcelain tile tone
  ctx.fillStyle = '#E2E5E8';
  ctx.fillRect(0, 0, size, size);

  const numTiles = 4; // 60cm x 60cm tiles in 2.4m repeat
  const tileSize = size / numTiles;
  const groutW = 4;

  for (let r = 0; r < numTiles; r++) {
    for (let c = 0; c < numTiles; c++) {
      const x = c * tileSize;
      const y = r * tileSize;

      // Slight tile-to-tile tonal jitter
      const tone = 230 + Math.floor(Math.sin(r * 5 + c * 7) * 8);
      ctx.fillStyle = `rgb(${tone}, ${tone + 2}, ${tone + 4})`;
      ctx.fillRect(x + groutW, y + groutW, tileSize - groutW * 2, tileSize - groutW * 2);

      // Micro-stipple non-slip surface noise
      ctx.fillStyle = 'rgba(0, 0, 0, 0.025)';
      for (let i = 0; i < 280; i++) {
        const sx = x + groutW + Math.random() * (tileSize - groutW * 2);
        const sy = y + groutW + Math.random() * (tileSize - groutW * 2);
        ctx.fillRect(sx, sy, 1.5, 1.5);
      }
    }
  }

  // Grout grid lines
  ctx.strokeStyle = '#CBD1D6';
  ctx.lineWidth = groutW;
  for (let i = 0; i <= numTiles; i++) {
    const pos = i * tileSize;
    ctx.beginPath();
    ctx.moveTo(pos, 0);
    ctx.lineTo(pos, size);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, pos);
    ctx.lineTo(size, pos);
    ctx.stroke();
  }

  return canvas;
}

function createSandStuccoCanvas(): HTMLCanvasElement {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  ctx.fillStyle = '#EDE8DE';
  ctx.fillRect(0, 0, size, size);

  // Micro stucco stipple grain
  ctx.fillStyle = 'rgba(60, 50, 40, 0.035)';
  for (let i = 0; i < 4000; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    ctx.fillRect(x, y, 1.5, 1.5);
  }

  ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
  for (let i = 0; i < 3000; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    ctx.fillRect(x, y, 1.5, 1.5);
  }

  return canvas;
}

function createLawnGrassCanvas(): HTMLCanvasElement {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  ctx.fillStyle = '#3E8E34';
  ctx.fillRect(0, 0, size, size);

  // Organic grass blade noise
  ctx.fillStyle = 'rgba(30, 80, 20, 0.12)';
  for (let i = 0; i < 5000; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const len = 2 + Math.random() * 4;
    ctx.fillRect(x, y, 1.5, len);
  }

  ctx.fillStyle = 'rgba(80, 170, 50, 0.12)';
  for (let i = 0; i < 4000; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const len = 2 + Math.random() * 3;
    ctx.fillRect(x, y, 1.5, len);
  }

  return canvas;
}

function createTeakDeckCanvas(): HTMLCanvasElement {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) return canvas;

  ctx.fillStyle = '#BA834E';
  ctx.fillRect(0, 0, size, size);

  const numPlanks = 8;
  const plankH = size / numPlanks;
  for (let i = 0; i < numPlanks; i++) {
    const y = i * plankH;
    const tone = Math.sin(i * 3) * 8;
    ctx.fillStyle = `rgb(${186 + tone}, ${131 + tone}, ${78 + tone})`;
    ctx.fillRect(0, y, size, plankH - 3);

    // Expansion joint
    ctx.fillStyle = 'rgba(30, 18, 8, 0.4)';
    ctx.fillRect(0, y + plankH - 3, size, 3);
  }

  return canvas;
}

export function getProceduralPbrTextures(): ProceduralPbrTextures {
  if (pbrTextures) return pbrTextures;

  const mkTex = (canvas: HTMLCanvasElement, repeatM = 2.4): THREE.CanvasTexture => {
    const tex = new THREE.CanvasTexture(canvas);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(1 / repeatM, 1 / repeatM);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.generateMipmaps = true;
    return tex;
  };

  pbrTextures = {
    carraraMarble: mkTex(createCarraraMarbleCanvas(), 2.8),
    herringboneOak: mkTex(createHerringboneOakCanvas(), 1.8),
    ceramicTile: mkTex(createCeramicTileCanvas(), 2.4),
    sandStucco: mkTex(createSandStuccoCanvas(), 1.5),
    lawnGrass: mkTex(createLawnGrassCanvas(), 2.0),
    teakDeck: mkTex(createTeakDeckCanvas(), 1.6),
  };

  return pbrTextures;
}

// Full Photorealistic PBR Material Library
export interface PbrMaterialCatalog {
  carraraMarble: THREE.MeshStandardMaterial;
  herringboneOak: THREE.MeshStandardMaterial;
  ceramicTile: THREE.MeshStandardMaterial;
  sandStucco: THREE.MeshStandardMaterial;
  lawnGrass: THREE.MeshStandardMaterial;
  teakDeck: THREE.MeshStandardMaterial;
  interiorPlaster: THREE.MeshStandardMaterial;
  exteriorWallCap: THREE.MeshStandardMaterial;
  skirtingBaseboard: THREE.MeshStandardMaterial;
  crownMoulding: THREE.MeshStandardMaterial;
  doorTimber: THREE.MeshStandardMaterial;
  doorBronzeFrame: THREE.MeshStandardMaterial;
  brushedBrass: THREE.MeshStandardMaterial;
  architecturalGlass: THREE.MeshPhysicalMaterial;
  balconyGlass: THREE.MeshPhysicalMaterial;
  ceilingPlaster: THREE.MeshStandardMaterial;
  coveLedLight: THREE.MeshBasicMaterial;
  spotlightGlow: THREE.MeshBasicMaterial;
  fabricLinen: THREE.MeshStandardMaterial;
  fabricTealAccent: THREE.MeshStandardMaterial;
  leatherDark: THREE.MeshStandardMaterial;
}

let cachedPbrCatalog: PbrMaterialCatalog | null = null;

export function getPbrMaterialCatalog(): PbrMaterialCatalog {
  if (cachedPbrCatalog) return cachedPbrCatalog;

  const tex = getProceduralPbrTextures();

  cachedPbrCatalog = {
    carraraMarble: new THREE.MeshStandardMaterial({
      map: tex.carraraMarble,
      roughness: 0.18,
      metalness: 0.05,
    }),
    herringboneOak: new THREE.MeshStandardMaterial({
      map: tex.herringboneOak,
      roughness: 0.35,
      metalness: 0.02,
    }),
    ceramicTile: new THREE.MeshStandardMaterial({
      map: tex.ceramicTile,
      roughness: 0.52,
      metalness: 0.01,
    }),
    sandStucco: new THREE.MeshStandardMaterial({
      map: tex.sandStucco,
      roughness: 0.92,
      metalness: 0.0,
    }),
    lawnGrass: new THREE.MeshStandardMaterial({
      map: tex.lawnGrass,
      roughness: 0.88,
      metalness: 0.0,
    }),
    teakDeck: new THREE.MeshStandardMaterial({
      map: tex.teakDeck,
      roughness: 0.62,
      metalness: 0.02,
    }),
    interiorPlaster: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#FAF9F6'),
      roughness: 0.84,
      metalness: 0.0,
    }),
    exteriorWallCap: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#2C2D31'),
      roughness: 0.65,
      metalness: 0.1,
    }),
    skirtingBaseboard: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#382D24'), // Dark Walnut skirting
      roughness: 0.42,
      metalness: 0.04,
    }),
    crownMoulding: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#FFFFFF'),
      roughness: 0.6,
      metalness: 0.0,
    }),
    doorTimber: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#9B693A'),
      roughness: 0.38,
      metalness: 0.03,
    }),
    doorBronzeFrame: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#222326'),
      roughness: 0.42,
      metalness: 0.45,
    }),
    brushedBrass: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#D4AF37'),
      roughness: 0.25,
      metalness: 0.82,
    }),
    architecturalGlass: new THREE.MeshPhysicalMaterial({
      color: new THREE.Color('#D8EFF8'),
      transmission: 0.92,
      transparent: true,
      opacity: 0.28,
      ior: 1.52,
      roughness: 0.04,
      thickness: 0.02,
      depthWrite: false,
    }),
    balconyGlass: new THREE.MeshPhysicalMaterial({
      color: new THREE.Color('#CBE8F5'),
      transmission: 0.88,
      transparent: true,
      opacity: 0.35,
      ior: 1.5,
      roughness: 0.06,
      thickness: 0.015,
      depthWrite: false,
    }),
    ceilingPlaster: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#FAF9F5'),
      roughness: 0.88,
      metalness: 0.0,
    }),
    coveLedLight: new THREE.MeshBasicMaterial({
      color: new THREE.Color('#FFE299'), // Warm 3000K Cove LED
    }),
    spotlightGlow: new THREE.MeshBasicMaterial({
      color: new THREE.Color('#FFF5DC'),
    }),
    fabricLinen: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#EFECE6'),
      roughness: 0.88,
      metalness: 0.0,
    }),
    fabricTealAccent: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#2B5F66'),
      roughness: 0.78,
      metalness: 0.0,
    }),
    leatherDark: new THREE.MeshStandardMaterial({
      color: new THREE.Color('#282726'),
      roughness: 0.45,
      metalness: 0.05,
    }),
  };

  return cachedPbrCatalog;
}

// Legacy Theme Compatibility
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
  wallPlaster: { color: '#E8E3D8', roughness: 0.82, metalness: 0.01 },
  wallPlasterExt: { color: '#FFFFFF', roughness: 0.85, metalness: 0.01 },
  foundationSlab: { color: '#FFFFFF', roughness: 0.8, metalness: 0.02 },
  woodSlatAccent: { color: '#C69358', roughness: 0.45, metalness: 0.03 },
  bedroomFloor: { color: '#C4955B', roughness: 0.38, metalness: 0.04 },
  livingFloor: { color: '#D4A367', roughness: 0.36, metalness: 0.04 },
  kitchenFloor: { color: '#DCD6CB', roughness: 0.32, metalness: 0.05 },
  bathFloor: { color: '#E5EDF4', roughness: 0.22, metalness: 0.08 },
  diningFloor: { color: '#CE9E63', roughness: 0.38, metalness: 0.04 },
  balconyFloor: { color: '#BA834E', roughness: 0.65, metalness: 0.02 },
  lawnFloor: { color: '#3E8E34', roughness: 0.88, metalness: 0.01 },
  corridorFloor: { color: '#E8E3DA', roughness: 0.45, metalness: 0.03 },
  utilityFloor: { color: '#CBD5E1', roughness: 0.4, metalness: 0.02 },
  voidFloor: { color: '#4B5563', roughness: 0.95, metalness: 0.0 },
  rugSlateBlue: { color: '#4A6B82', roughness: 0.95, metalness: 0.0 },
  rugNeutral: { color: '#D8D3C8', roughness: 0.92, metalness: 0.0 },
  doorWood: { color: '#A87342', roughness: 0.42, metalness: 0.04 },
  doorFrame: { color: '#222326', roughness: 0.4, metalness: 0.35 },
  windowFrame: { color: '#1E1E20', roughness: 0.3, metalness: 0.5 },
  windowGlass: { color: '#B6D6E8', transparent: true, opacity: 0.28, roughness: 0.1, metalness: 0.1 },
  railingMetal: { color: '#222326', roughness: 0.35, metalness: 0.7 },
  railingGlass: { color: '#C8E2EF', transparent: true, opacity: 0.35, roughness: 0.1, metalness: 0.05 },
  sofaFabric: { color: '#E4E2DC', roughness: 0.88, metalness: 0.02 },
  cushionBlue: { color: '#3E5E72', roughness: 0.82, metalness: 0.02 },
  cushionFabric: { color: '#D4CEBF', roughness: 0.82, metalness: 0.02 },
  chairFabric: { color: '#DFDBD1', roughness: 0.85, metalness: 0.02 },
  marbleTable: { color: '#F4F1EA', roughness: 0.22, metalness: 0.08 },
  brassGold: { color: '#C9A35E', roughness: 0.28, metalness: 0.75 },
  bedHeadboardTeal: { color: '#3D6874', roughness: 0.75, metalness: 0.04 },
  bedLinen: { color: '#F3F0E8', roughness: 0.92, metalness: 0.0 },
  bedDuvet: { color: '#E5E0D4', roughness: 0.88, metalness: 0.0 },
  bedThrow: { color: '#3D6874', roughness: 0.85, metalness: 0.02 },
  woodFurniture: { color: '#C69358', roughness: 0.45, metalness: 0.03 },
  darkWood: { color: '#4A3319', roughness: 0.48, metalness: 0.02 },
  countertop: { color: '#ECE8DF', roughness: 0.25, metalness: 0.06 },
  cabinetry: { color: '#DCD6CB', roughness: 0.45, metalness: 0.02 },
  sanitaryCeramic: { color: '#FFFFFF', roughness: 0.18, metalness: 0.04 },
  chromeFixture: { color: '#E2E8F0', roughness: 0.12, metalness: 0.95 },
  tvScreen: { color: '#151719', roughness: 0.2, metalness: 0.75 },
  indoorPlant: { color: '#3F6E3B', roughness: 0.65, metalness: 0.01 },
  plantPotWhite: { color: '#F0ECE3', roughness: 0.65, metalness: 0.02 },
  lampGlow: { color: '#FFE4A0', roughness: 0.9, metalness: 0.0 },
};

export const CLAY_THEME: MaterialTheme = {
  isClay: true,
  wallPlaster: { color: '#EDE9E1', roughness: 0.92 },
  wallPlasterExt: { color: '#EDE9E1', roughness: 0.92 },
  foundationSlab: { color: '#E0DBD2', roughness: 0.9 },
  woodSlatAccent: { color: '#D8D2C6', roughness: 0.85 },
  bedroomFloor: { color: '#DFD8CC', roughness: 0.85 },
  livingFloor: { color: '#DFD8CC', roughness: 0.85 },
  kitchenFloor: { color: '#E5E0D6', roughness: 0.8 },
  bathFloor: { color: '#EAE6DD', roughness: 0.75 },
  diningFloor: { color: '#DFD8CC', roughness: 0.85 },
  balconyFloor: { color: '#D5CFC3', roughness: 0.88 },
  lawnFloor: { color: '#D8D4C9', roughness: 0.92 },
  corridorFloor: { color: '#DFD8CC', roughness: 0.85 },
  utilityFloor: { color: '#E2DDD3', roughness: 0.82 },
  voidFloor: { color: '#A09C94', roughness: 0.95 },
  rugSlateBlue: { color: '#D2CCC0', roughness: 0.9 },
  rugNeutral: { color: '#D5CFC3', roughness: 0.9 },
  doorWood: { color: '#D5CFC3', roughness: 0.85 },
  doorFrame: { color: '#C0B9AD', roughness: 0.8 },
  windowFrame: { color: '#BAB3A7', roughness: 0.75 },
  windowGlass: { color: '#D5CFC3', transparent: true, opacity: 0.4, roughness: 0.3 },
  railingMetal: { color: '#BAB3A7', roughness: 0.75 },
  railingGlass: { color: '#D5CFC3', transparent: true, opacity: 0.4, roughness: 0.3 },
  sofaFabric: { color: '#E5E0D6', roughness: 0.9 },
  cushionBlue: { color: '#DDD7CD', roughness: 0.9 },
  cushionFabric: { color: '#DDD7CD', roughness: 0.9 },
  chairFabric: { color: '#E2DDD3', roughness: 0.9 },
  marbleTable: { color: '#EDE9E1', roughness: 0.75 },
  brassGold: { color: '#DDD7CD', roughness: 0.6 },
  bedHeadboardTeal: { color: '#D5CFC3', roughness: 0.88 },
  bedLinen: { color: '#F2EFE8', roughness: 0.92 },
  bedDuvet: { color: '#E8E4DB', roughness: 0.9 },
  bedThrow: { color: '#DDD7CD', roughness: 0.9 },
  woodFurniture: { color: '#D8D2C6', roughness: 0.85 },
  darkWood: { color: '#C5BEB2', roughness: 0.85 },
  countertop: { color: '#EDE9E1', roughness: 0.75 },
  cabinetry: { color: '#E2DDD3', roughness: 0.82 },
  sanitaryCeramic: { color: '#F2EFE8', roughness: 0.7 },
  chromeFixture: { color: '#D5CFC3', roughness: 0.5 },
  tvScreen: { color: '#9E9990', roughness: 0.6 },
  indoorPlant: { color: '#D0CAC0', roughness: 0.88 },
  plantPotWhite: { color: '#EAE6DD', roughness: 0.85 },
  lampGlow: { color: '#EFEBE3', roughness: 0.8 },
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
