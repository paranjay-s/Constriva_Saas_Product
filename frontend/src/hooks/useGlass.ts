import { useEffect, type RefObject } from "react";

let filterIdCounter = 0;
const SVG_NS = "http://www.w3.org/2000/svg";

let sharedDefs: SVGSVGElement | null = null;
let sharedDefsUsers = 0;

function getSharedDefs(): SVGSVGElement {
  if (!sharedDefs || !document.body.contains(sharedDefs)) {
    sharedDefs = document.createElementNS(SVG_NS, "svg");
    sharedDefs.setAttribute("aria-hidden", "true");
    sharedDefs.setAttribute("width", "0");
    sharedDefs.setAttribute("height", "0");
    sharedDefs.style.cssText = "position:absolute;width:0;height:0;overflow:hidden;pointer-events:none;";
    document.body.appendChild(sharedDefs);
  }
  return sharedDefs;
}

const buildMap = (w: number, h: number, radius: number, depth: number): string => {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const img = ctx.createImageData(w, h);
  const r = Math.min(radius, w / 2, h / 2);

  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const px = x + 0.5 - w / 2;
      const py = y + 0.5 - h / 2;
      const qx = Math.abs(px) - (w / 2 - r);
      const qy = Math.abs(py) - (h / 2 - r);
      const ox = Math.max(qx, 0);
      const oy = Math.max(qy, 0);
      const outside = Math.hypot(ox, oy);
      const dist = r - (outside + Math.min(Math.max(qx, qy), 0));
      let nx = 0;
      let ny = 0;
      if (dist < depth) {
        if (outside > 0) {
          nx = (ox / outside) * Math.sign(px);
          ny = (oy / outside) * Math.sign(py);
        } else if (qx > qy) {
          nx = Math.sign(px);
        } else {
          ny = Math.sign(py);
        }
        const t = 1 - dist / depth;
        const strength = t * t;
        nx *= -strength;
        ny *= -strength;
      }
      const i = (y * w + x) * 4;
      img.data[i] = Math.round(128 + nx * 127);
      img.data[i + 1] = Math.round(128 + ny * 127);
      img.data[i + 2] = 128;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL();
};

const createEl = (
  name: string,
  attrs: Record<string, string>,
  parent?: SVGElement
): SVGElement => {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
};

const buildFilter = (
  id: string,
  w: number,
  h: number,
  map: string,
  refraction: number,
  dispersion: number,
  frost: number
): SVGElement => {
  const filter = createEl("filter", {
    id,
    x: "0",
    y: "0",
    width: String(w),
    height: String(h),
    filterUnits: "userSpaceOnUse",
    primitiveUnits: "userSpaceOnUse",
    "color-interpolation-filters": "sRGB",
  });

  createEl(
    "feGaussianBlur",
    {
      in: "SourceGraphic",
      stdDeviation: String(frost / 2),
      edgeMode: "duplicate",
      result: "frost",
    },
    filter
  );

  createEl(
    "feImage",
    {
      href: map,
      x: "0",
      y: "0",
      width: String(w),
      height: String(h),
      result: "map",
      preserveAspectRatio: "none",
    },
    filter
  );

  const spread = (dispersion / 100) * 0.16;
  const channels: [string, number, string][] = [
    ["r", 1 + spread, "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"],
    ["g", 1, "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"],
    ["b", 1 - spread, "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"],
  ];

  const scale = Math.min(refraction, 0.8 * Math.min(w, h));
  for (const [c, k, matrix] of channels) {
    createEl(
      "feDisplacementMap",
      {
        in: "frost",
        in2: "map",
        scale: String(scale * k),
        xChannelSelector: "R",
        yChannelSelector: "G",
        result: `d${c}`,
      },
      filter
    );
    createEl(
      "feColorMatrix",
      {
        in: `d${c}`,
        type: "matrix",
        values: matrix,
        result: c,
      },
      filter
    );
  }

  createEl("feBlend", { in: "r", in2: "g", mode: "screen", result: "rg" }, filter);
  createEl("feBlend", { in: "rg", in2: "b", mode: "screen" }, filter);

  return filter;
};

export interface GlassOptions {
  refraction?: number;
  depth?: number;
  dispersion?: number;
  frost?: number;
}

export function useGlass(
  nodeRef: RefObject<HTMLElement | null>,
  options: GlassOptions = {}
) {
  useEffect(() => {
    const node = nodeRef.current;
    if (!node) return;

    // Check for Chromium browser
    const navAny = navigator as unknown as {
      userAgentData?: { brands?: { brand: string }[] };
    };
    const isChromium =
      navAny.userAgentData?.brands?.some((b) => b.brand === "Chromium") ||
      (navigator.userAgent.includes("Chrome") &&
        !navigator.userAgent.includes("Edg") &&
        !navigator.userAgent.includes("OPR"));

    if (!isChromium) return;

    sharedDefsUsers++;
    const defs = getSharedDefs();
    const id = `cg-${++filterIdCounter}`;
    let lastSize = "";

    const refraction = options.refraction ?? Number(node.dataset.glassRefraction ?? 80);
    const depth = options.depth ?? Number(node.dataset.glassDepth ?? 20);
    const dispersion = options.dispersion ?? Number(node.dataset.glassDispersion ?? 50);
    const frost = options.frost ?? Number(node.dataset.glassFrost ?? 32);

    const apply = () => {
      const w = Math.round(node.offsetWidth);
      const h = Math.round(node.offsetHeight);
      if (!w || !h || `${w}x${h}` === lastSize) return;
      lastSize = `${w}x${h}`;

      const radius = parseFloat(getComputedStyle(node).borderTopLeftRadius) || 0;
      defs.querySelector(`#${id}`)?.remove();
      const map = buildMap(w, h, radius, depth);
      if (!map) return;

      defs.appendChild(buildFilter(id, w, h, map, refraction, dispersion, frost));
      const val = `url(#${id})`;
      node.style.backdropFilter = val;
      node.style.setProperty("-webkit-backdrop-filter", val);
      node.setAttribute("data-refractive", "true");
      node.classList.add("is-refractive");
    };

    apply();

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(apply);
      observer.observe(node);
    }

    return () => {
      defs.querySelector(`#${id}`)?.remove();
      observer?.disconnect();
      sharedDefsUsers--;
      if (sharedDefsUsers <= 0 && sharedDefs && document.body.contains(sharedDefs)) {
        sharedDefs.remove();
        sharedDefs = null;
      }
    };
  }, [nodeRef, options.refraction, options.depth, options.dispersion, options.frost]);
}
