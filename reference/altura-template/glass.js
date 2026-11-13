// Refractive glass for elements marked [data-glass].
// Settings follow Figma's Glass effect: refraction, depth, dispersion, frost.
// Chromium can run an SVG filter as a backdrop-filter; other engines keep the
// frosted CSS fallback from styles.css.
(() => {
  const chromium = navigator.userAgentData?.brands?.some((b) => b.brand === "Chromium");
  if (!chromium) return;

  const SVG_NS = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(SVG_NS, "svg");
  defs.setAttribute("aria-hidden", "true");
  defs.setAttribute("width", "0");
  defs.setAttribute("height", "0");
  defs.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
  document.body.appendChild(defs);

  // Displacement map for a rounded rectangle. Inside the rim band ("depth")
  // each pixel points inward, strongest at the edge, like the bevel of a lens.
  // Red carries x, green carries y; 128 means no shift.
  const buildMap = (w, h, radius, depth) => {
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(w, h);
    const r = Math.min(radius, w / 2, h / 2);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x + 0.5 - w / 2;
        const py = y + 0.5 - h / 2;
        // Signed distance to the rounded rectangle (negative inside).
        const qx = Math.abs(px) - (w / 2 - r);
        const qy = Math.abs(py) - (h / 2 - r);
        const ox = Math.max(qx, 0);
        const oy = Math.max(qy, 0);
        const outside = Math.hypot(ox, oy);
        const dist = r - (outside + Math.min(Math.max(qx, qy), 0));
        let nx = 0;
        let ny = 0;
        if (dist < depth) {
          // Outward normal of the nearest edge.
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
          // Sample from further inside, so the rim never reads past the card.
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

  const el = (name, attrs, parent) => {
    const node = document.createElementNS(SVG_NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };

  // One displaced copy per colour channel; the slightly different strengths
  // split the edge into a thin colour fringe (dispersion).
  const buildFilter = (id, w, h, map, refraction, dispersion, frost) => {
    const filter = el("filter", {
      id,
      x: "0",
      y: "0",
      width: String(w),
      height: String(h),
      filterUnits: "userSpaceOnUse",
      primitiveUnits: "userSpaceOnUse",
      "color-interpolation-filters": "sRGB",
    });
    // Frost lives inside the filter: chaining a CSS blur() before url() makes
    // Chromium offset the SVG filter region from the card.
    el("feGaussianBlur", { in: "SourceGraphic", stdDeviation: String(frost / 2), edgeMode: "duplicate", result: "frost" }, filter);
    el("feImage", { href: map, x: "0", y: "0", width: String(w), height: String(h), result: "map", preserveAspectRatio: "none" }, filter);
    const spread = (dispersion / 100) * 0.16;
    const channels = [
      ["r", 1 + spread, "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"],
      ["g", 1, "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"],
      ["b", 1 - spread, "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"],
    ];
    // The map shifts pixels by up to half the scale. On small pills a full
    // refraction 80 would reach past the far edge, where the backdrop is empty,
    // so the bend is capped to stay inside the element.
    const scale = Math.min(refraction, 0.8 * Math.min(w, h));
    for (const [c, k, matrix] of channels) {
      el("feDisplacementMap", { in: "frost", in2: "map", scale: String(scale * k), xChannelSelector: "R", yChannelSelector: "G", result: `d${c}` }, filter);
      el("feColorMatrix", { in: `d${c}`, type: "matrix", values: matrix, result: c }, filter);
    }
    el("feBlend", { in: "r", in2: "g", mode: "screen", result: "rg" }, filter);
    el("feBlend", { in: "rg", in2: "b", mode: "screen" }, filter);
    return filter;
  };

  document.querySelectorAll("[data-glass]").forEach((node, n) => {
    const read = (name, fallback) => Number(node.dataset[name] ?? fallback);
    const refraction = read("glassRefraction", 80);
    const depth = read("glassDepth", 20);
    const dispersion = read("glassDispersion", 50);
    const frost = read("glassFrost", 32);
    const id = `glass-${n}`;
    let size = "";

    const apply = () => {
      const w = Math.round(node.offsetWidth);
      const h = Math.round(node.offsetHeight);
      if (!w || !h || `${w}x${h}` === size) return;
      size = `${w}x${h}`;
      const radius = parseFloat(getComputedStyle(node).borderTopLeftRadius) || 0;
      defs.querySelector(`#${id}`)?.remove();
      defs.appendChild(buildFilter(id, w, h, buildMap(w, h, radius, depth), refraction, dispersion, frost));
      const value = `url(#${id})`;
      node.style.backdropFilter = value;
      node.style.webkitBackdropFilter = value;
      node.classList.add("is-refractive");
    };

    apply();
    if ("ResizeObserver" in window) new ResizeObserver(apply).observe(node);
  });
})();
