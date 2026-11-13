(() => {
  const root = document.documentElement;
  const hero = document.getElementById("hero");
  const wordmark = hero.querySelector(".wordmark");
  const chars = wordmark.querySelectorAll(".wordmark__char");
  const nav = hero.querySelector(".nav");
  const menuBtn = hero.querySelector(".menu-btn");
  const menu = document.getElementById("mobile-menu");
  const images = [...hero.querySelectorAll(".stage__img")];

  root.classList.add("js");

  // Photo geometry, in fractions of the 1200x1000 source.
  const ASPECT = 1200 / 1000;
  const ROOF_Y = 0.455; // top edge of the roof slab
  const HOUSE_CX = 0.49; // horizontal centre of the house
  const CLIP_Y = 0.476; // just below the lowest roof edge; hides letter slivers in the side gaps

  const clamp = (v, min, max) => Math.min(Math.max(v, min), max);

  // Font metrics measured once the display face is loaded.
  let metrics = null;
  const measure = () => {
    const style = getComputedStyle(wordmark);
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = `${style.fontWeight} 100px ${style.fontFamily}`;
    const ascent = ctx.measureText("l").actualBoundingBoxAscent / 100;
    const xHeight = ctx.measureText("x").actualBoundingBoxAscent / 100;
    return { ascent, xHeight };
  };

  const layout = () => {
    const W = hero.clientWidth;
    const H = hero.clientHeight;
    const mobile = W < 700;

    // Cover the hero with the photo, keeping the roof line near mid-height.
    const sw = Math.max(W, H * ASPECT);
    const sh = sw / ASPECT;
    const roofTarget = H * (mobile ? 0.53 : 0.44);
    const sy = clamp(roofTarget - ROOF_Y * sh, H - sh, 0);
    const sx = clamp(W / 2 - HOUSE_CX * sw, W - sw, 0);
    const roof = sy + ROOF_Y * sh;

    hero.style.setProperty("--sw", `${sw}px`);
    hero.style.setProperty("--sh", `${sh}px`);
    hero.style.setProperty("--sx", `${sx}px`);
    hero.style.setProperty("--sy", `${sy}px`);

    if (!metrics) metrics = measure();

    // Size the wordmark to the width first, then cap it so the tallest
    // letters stay clear of the navigation.
    const sideMargin = W * (mobile ? 0.035 : 0.06);
    const targetWidth = W - sideMargin * 2;
    wordmark.style.setProperty("--wm-size", "100px");
    const widthAt100 = wordmark.querySelector(".wordmark__line").getBoundingClientRect().width;
    let size = (targetWidth / widthAt100) * 100;

    const hidden = mobile ? 0.14 : 0.2; // share of the x-height tucked behind the roof; small, so the word stays readable
    const navBottom = nav.getBoundingClientRect().bottom - hero.getBoundingClientRect().top;
    const minTop = navBottom + H * (mobile ? 0.12 : 0.07);
    const maxSize = (roof - minTop) / (metrics.ascent - hidden * metrics.xHeight);
    size = Math.min(size, maxSize);

    // The short letters must also start below the collections index (top right).
    // offsetTop ignores the entrance transform, so this is stable during the reveal.
    const index = hero.querySelector(".index");
    if (index && index.offsetParent) {
      const indexBottom = index.offsetTop + index.offsetHeight + H * 0.025;
      size = Math.min(size, (roof - indexBottom) / ((1 - hidden) * metrics.xHeight));
    }

    const baseline = roof + hidden * metrics.xHeight * size;
    wordmark.style.setProperty("--wm-size", `${size}px`);
    const box = wordmark.getBoundingClientRect();
    const lineRect = wordmark.querySelector(".wordmark__line").getBoundingClientRect();
    const probe = document.createElement("span");
    probe.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline";
    wordmark.querySelector(".wordmark__line").appendChild(probe);
    const baselineInBox = probe.getBoundingClientRect().top - box.top;
    probe.remove();

    const wmWidth = lineRect.width;
    const wmX = (W - wmWidth) / 2;
    const wmY = baseline - baselineInBox;
    wordmark.style.setProperty("--wm-x", `${wmX}px`);
    wordmark.style.setProperty("--wm-y", `${wmY}px`);
    const clipInBox = sy + CLIP_Y * sh - wmY;
    wordmark.style.clipPath = `polygon(-10% -30%, 110% -30%, 110% ${clipInBox}px, -10% ${clipInBox}px)`;
  };

  const ready = () => root.classList.add("is-ready");

  const decode = (img) =>
    img.complete && img.naturalWidth ? Promise.resolve() : img.decode().catch(() => {});

  const fonts = document.fonts ? document.fonts.load('500 100px "Poppins"').catch(() => {}) : Promise.resolve();
  const fontTimeout = new Promise((r) => setTimeout(r, 1500));

  Promise.race([fonts, fontTimeout])
    .then(() => {
      metrics = null;
      layout();
      return Promise.all(images.map(decode));
    })
    .then(() => requestAnimationFrame(() => requestAnimationFrame(ready)));

  // A late font swap changes the metrics; re-measure once it lands.
  if (document.fonts) {
    document.fonts.ready.then(() => {
      metrics = null;
      layout();
    });
  }

  let raf = 0;
  const onResize = () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(layout);
  };
  window.addEventListener("resize", onResize);
  if ("ResizeObserver" in window) new ResizeObserver(onResize).observe(hero);

  // Mobile menu.
  const setMenu = (open) => {
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    // The menu is see-through glass; hide the chips behind it so they don't show through.
    hero.classList.toggle("is-menu-open", open);
    if (open) {
      menu.hidden = false;
      requestAnimationFrame(() => menu.classList.add("is-open"));
    } else {
      menu.classList.remove("is-open");
      setTimeout(() => {
        if (menuBtn.getAttribute("aria-expanded") === "false") menu.hidden = true;
      }, 260);
    }
  };
  menuBtn.addEventListener("click", () => setMenu(menuBtn.getAttribute("aria-expanded") !== "true"));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && menuBtn.getAttribute("aria-expanded") === "true") {
      setMenu(false);
      menuBtn.focus();
    }
  });
  window.matchMedia("(min-width: 901px)").addEventListener("change", (e) => {
    if (e.matches) setMenu(false);
  });
})();
