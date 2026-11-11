// materials/textures.ts
import * as THREE from 'three';
import { mulberry32 } from '../utils/rng';
import { PALETTE } from './palette';

export interface TextureCache {
  woodLiving: THREE.CanvasTexture;
  woodBedroom: THREE.CanvasTexture;
  woodDeck: THREE.CanvasTexture;
  tileBath: THREE.CanvasTexture;
  concrete: THREE.CanvasTexture;
  marblePuja: THREE.CanvasTexture;
  contactBlob: THREE.CanvasTexture;
}

let cachedTextures: TextureCache | null = null;

export function disposeTextures() {
  if (cachedTextures) {
    Object.values(cachedTextures).forEach((t) => {
      if (t && typeof (t as any).dispose === 'function') {
        (t as any).dispose();
      }
    });
    cachedTextures = null;
  }
}

export function getOrCreateTextures(maxAnisotropy: number = 8): TextureCache {
  if (cachedTextures) return cachedTextures;

  const woodLiving = makeWoodTexture({
    baseHex: PALETTE.woodLiving,
    lowHex: PALETTE.woodLivingLow,
    highHex: PALETTE.woodLivingHigh,
    plankW: 0.16,
    tile: 2.4,
    seed: 42,
    maxAnisotropy,
  });

  const woodBedroom = makeWoodTexture({
    baseHex: PALETTE.woodBedroom,
    lowHex: PALETTE.woodLiving,
    highHex: PALETTE.woodLivingHigh,
    plankW: 0.16,
    tile: 2.4,
    seed: 101,
    maxAnisotropy,
  });

  const woodDeck = makeWoodTexture({
    baseHex: PALETTE.woodDeck,
    lowHex: PALETTE.woodDeckLow,
    highHex: PALETTE.woodDeckHigh,
    plankW: 0.14,
    tile: 2.4,
    seed: 202,
    maxAnisotropy,
  });

  const tileBath = makeTileTexture({
    baseHex: PALETTE.tileBath,
    groutHex: PALETTE.tileGrout,
    tile: 0.6,
    maxAnisotropy,
  });

  const concrete = makeConcreteTexture({
    baseHex: PALETTE.concrete,
    maxAnisotropy,
  });

  const marblePuja = makeMarbleTexture({
    baseHex: PALETTE.marblePuja,
    maxAnisotropy,
  });

  const contactBlob = makeBlobTexture();

  cachedTextures = {
    woodLiving,
    woodBedroom,
    woodDeck,
    tileBath,
    concrete,
    marblePuja,
    contactBlob,
  };

  return cachedTextures;
}

/**
 * Creates 2048x2048 continuous wood plank texture with subtle grain and staggered butt joints
 */
export function makeWoodTexture({
  baseHex,
  lowHex,
  highHex,
  plankW = 0.16,
  tile = 2.4,
  seed = 42,
  maxAnisotropy = 8,
}: {
  baseHex: string;
  lowHex?: string;
  highHex?: string;
  plankW?: number;
  tile?: number;
  seed?: number;
  maxAnisotropy?: number;
}): THREE.CanvasTexture {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) {
    const dummy = new THREE.CanvasTexture(canvas);
    return dummy;
  }

  const rng = mulberry32(seed);

  // Background fill
  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, size, size);

  // Calculate number of plank rows
  const numRows = Math.round(tile / plankW);
  const rowHeight = size / numRows;

  const lowCol = new THREE.Color(lowHex || baseHex);
  const highCol = new THREE.Color(highHex || baseHex);

  for (let r = 0; r < numRows; r++) {
    const y0 = r * rowHeight;

    // Slight row tint variation
    const rowT = rng();
    const rowColor = new THREE.Color().copy(lowCol).lerp(highCol, rowT);
    ctx.fillStyle = rowColor.getStyle();
    ctx.fillRect(0, y0, size, rowHeight);

    // Staggered butt joints per row (2 to 4 planks per row)
    const numPlanks = 3 + Math.floor(rng() * 2);
    let currX = 0;
    const offsets: number[] = [0];
    for (let p = 0; p < numPlanks - 1; p++) {
      currX += (size / numPlanks) * (0.8 + rng() * 0.4);
      if (currX < size - 40) offsets.push(currX);
    }
    offsets.push(size);

    for (let p = 0; p < offsets.length - 1; p++) {
      const x0 = offsets[p];
      const x1 = offsets[p + 1];

      // Subtle plank grain streaks
      ctx.fillStyle = 'rgba(0, 0, 0, 0.035)';
      for (let g = 0; g < 18; g++) {
        const gy = y0 + rng() * rowHeight;
        const gh = 1 + rng() * 1.5;
        ctx.fillRect(x0, gy, x1 - x0, gh);
      }

      ctx.fillStyle = 'rgba(255, 255, 255, 0.03)';
      for (let g = 0; g < 10; g++) {
        const gy = y0 + rng() * rowHeight;
        const gh = 1 + rng();
        ctx.fillRect(x0, gy, x1 - x0, gh);
      }

      // Vertical butt joint line
      if (x0 > 0) {
        ctx.fillStyle = 'rgba(40, 25, 15, 0.35)';
        ctx.fillRect(x0 - 0.75, y0, 1.5, rowHeight);
      }
    }

    // Horizontal seam between planks
    ctx.fillStyle = 'rgba(40, 25, 15, 0.28)';
    ctx.fillRect(0, y0, size, 1.2);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1 / tile, 1 / tile);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(maxAnisotropy, 8);
  texture.generateMipmaps = true;
  return texture;
}

/**
 * Creates 1024x1024 bathroom ceramic porcelain tile texture with grout
 */
export function makeTileTexture({
  baseHex,
  groutHex,
  tile = 0.6,
  maxAnisotropy = 8,
}: {
  baseHex: string;
  groutHex: string;
  tile?: number;
  maxAnisotropy?: number;
}): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return new THREE.CanvasTexture(canvas);

  // Base tile fill
  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, size, size);

  const tilesCount = 4; // 4x4 tiles
  const tileSize = size / tilesCount;
  const groutW = 2.5;

  ctx.fillStyle = groutHex;
  for (let i = 0; i <= tilesCount; i++) {
    const pos = i * tileSize;
    // Horizontal grout
    ctx.fillRect(0, pos - groutW / 2, size, groutW);
    // Vertical grout
    ctx.fillRect(pos - groutW / 2, 0, groutW, size);
  }

  // Very subtle surface specular texture
  ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1 / tile, 1 / tile);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(maxAnisotropy, 8);
  texture.generateMipmaps = true;
  return texture;
}

/**
 * Creates subtle parking concrete surface texture
 */
export function makeConcreteTexture({
  baseHex,
  maxAnisotropy = 8,
}: {
  baseHex: string;
  maxAnisotropy?: number;
}): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return new THREE.CanvasTexture(canvas);

  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, size, size);

  // Subtle stipple noise
  const rng = mulberry32(777);
  ctx.fillStyle = 'rgba(0, 0, 0, 0.03)';
  for (let i = 0; i < 600; i++) {
    const x = rng() * size;
    const y = rng() * size;
    const s = 1 + rng() * 2;
    ctx.fillRect(x, y, s, s);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(0.5, 0.5);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(maxAnisotropy, 4);
  texture.generateMipmaps = true;
  return texture;
}

/**
 * Creates subtle light marble texture for Puja room
 */
export function makeMarbleTexture({
  baseHex,
  maxAnisotropy = 8,
}: {
  baseHex: string;
  maxAnisotropy?: number;
}): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return new THREE.CanvasTexture(canvas);

  ctx.fillStyle = baseHex;
  ctx.fillRect(0, 0, size, size);

  // Subtle warm veins
  ctx.strokeStyle = 'rgba(180, 160, 140, 0.08)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(30, 0);
  ctx.bezierCurveTo(120, 200, 300, 180, 480, 512);
  ctx.stroke();

  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(300, 0);
  ctx.bezierCurveTo(220, 150, 150, 380, 100, 512);
  ctx.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(0.5, 0.5);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(maxAnisotropy, 4);
  texture.generateMipmaps = true;
  return texture;
}

/**
 * Creates 128x128 radial contact shadow blob for soft furniture grounding
 */
export function makeBlobTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  if (!ctx) return new THREE.CanvasTexture(canvas);

  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2;

  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
  grad.addColorStop(0, 'rgba(0, 0, 0, 0.42)');
  grad.addColorStop(0.4, 'rgba(0, 0, 0, 0.22)');
  grad.addColorStop(0.8, 'rgba(0, 0, 0, 0.06)');
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
