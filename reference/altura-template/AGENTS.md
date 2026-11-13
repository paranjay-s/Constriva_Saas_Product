# AGENTS.md — Altura Coastal Residences

Instructions for AI coding agents (Codex, Claude Code, Cursor and others) working in this folder. The person you are working with always has the final say: when their request and these notes disagree, follow them.

## Project

A landing page for a luxury real estate brand: a layered dusk hero with a giant wordmark behind the house and refractive glass navigation, followed by a full-screen walkthrough of one residence that the visitor moves through room by room, one scroll at a time.

- Stack: static HTML, CSS and JavaScript (index.html, styles.css, tour.css and four small scripts), no build step and no libraries
- `README.md` is the buyer guide. `CREDITS.md` lists every library and image with its license. `LICENSE.md` (when present) is the HorizonX license.

## Run it

   - With Python (already installed on Mac and Linux): `python3 -m http.server 8080`
   - Or with Node.js: `npx serve .`

Then open `http://localhost:8080` (with `npx serve`, use the address it prints).

## Where things are

- `index.html`: the page markup: hero, navigation, mobile menu, collection tags, featured residence card and the walkthrough with its eight captions.
- `styles.css`: hero, navigation and glass styles. Colors and glass settings are the variables in the `:root` block at the top.
- `tour.css`: walkthrough layout, captions and progress bar.
- `hero.js`: fits the giant wordmark behind the house roof, reveals the interface on load and opens the mobile menu.
- `glass.js`: refractive glass for every element marked `data-glass` (Chromium browsers; other browsers keep a frosted fallback from `styles.css`).
- `tour.js`: loads the walkthrough frames and draws them on a canvas as you scroll, with captions that fade in per room.
- `pager.js`: one-screen-per-scroll paging: each wheel turn, swipe or arrow key glides to the next stop (the hero, then each room).
- `assets/house-bg.webp` and `assets/house-fg.webp`: the hero photo and the same photo with only the house and trees, layered over the wordmark.
- `assets/tour/d/`: 421 landscape walkthrough frames (1600 × 900) for desktop and tablet. `assets/tour/m/`: the same 421 frames cropped portrait (640 × 1080) for phones. `assets/tour/poster.webp`: the still shown before the frames load.
- `README.md` (the buyer guide), `CREDITS.md` (fonts and images), and `AGENTS.md` plus `CLAUDE.md` (instructions for AI coding agents).

## How to change things

- **Colors and glass:** edit the `:root` block at the top of `styles.css`. `--page` is the page background, `--clear-glass` the nav and tag glass, `--glass` the frosted card glass, `--radius` the corner roundness.
- **Glass strength:** each glass element carries `data-glass-refraction`, `data-glass-depth`, `data-glass-dispersion` and `data-glass-frost` attributes in `index.html`. Lower values give a calmer effect.
- **Text:** edit the copy directly in `index.html`. The walkthrough captions are the `<li class="beat">` items; `data-at` is the stop each caption belongs to.
- **Hero photo:** replace `assets/house-bg.webp` (full photo) and `assets/house-fg.webp` (the same photo with the sky removed, transparent above the roof). If your photo has a different shape or roof line, update `ASPECT`, `ROOF_Y`, `HOUSE_CX` and `CLIP_Y` at the top of `hero.js`.
- **Walkthrough frames:** export your own camera move as numbered WebP files (`0001.webp`, `0002.webp`, ...) into `assets/tour/d/` (landscape) and `assets/tour/m/` (portrait). Set `data-frames` on `#tour` in `index.html` to the frame count, set `ROOMS` in `tour.js` to the number of stops minus one, and raise `data-version` so browsers stop using the old cached frames.
- **Fonts:** Inter, IBM Plex Mono and Poppins load from Google Fonts in the `<head>` of `index.html`. Swap that `<link>` and the `font-family` values in the CSS to change them.
- **Breakpoints:** the hero adapts at 1180 px, 960 px and 600 px wide; the walkthrough at 960 px and 600 px (search for `@media` in the CSS).

## Motion

- No animation library is used: the motion is plain JavaScript and CSS.
- **Walkthrough scrub** (`tour.js`): scroll position picks a frame; adjacent frames are blended so the camera moves smoothly, and frames near the current one are decoded ahead of time.
- **Paging** (`pager.js`): `HERO_MS` (1000 ms) and `ROOM_MS` (4500 ms) set how long each glide takes. Scrolling again during a glide queues the next room or turns back. Delete the `pager.js` `<script>` tag to get free scrolling.
- If a visitor has **Reduce motion** turned on in their system settings (the `prefers-reduced-motion` setting), the walkthrough jumps between rooms without gliding and the hero shows without its entrance animation.

## Rules for this project

- Keep it a static site with no build step unless the user asks to port it.
- Colors and glass come from the `:root` variables in `styles.css`. Change those instead of hard-coding new values.
- The walkthrough frame count lives in `data-frames` on `#tour`; the number of stops in `ROOMS` in `tour.js` and in the captions' `data-at` values. Keep all three in sync, and raise `data-version` whenever the frames change.
- `pager.js` reads its stops from the captions' `data-at` values. Keep wheel, touch and keyboard paging working together, and keep the `prefers-reduced-motion` behavior.
- Keep the current look and motion unless the user asks to change them. Before a large change, say what you plan to do.
- Every animation you add or change must keep working with `prefers-reduced-motion` and when its script fails to load.
- Fonts are not covered by the HorizonX license. If the user changes the fonts, use ones they own or have a license for, and never download font files they did not provide.
- When you add a library, font or image, add it to `CREDITS.md` with its version and license.
- Do not add analytics, tracking or other third-party scripts unless the user asks for them.

## Check your work

1. Serve the folder and open every section of the page.
2. Make sure the browser console shows no errors and no file returns 404.
3. Check the layout at 390 px and 1440 px wide.
4. Turn on reduced motion in the operating system and check that the content still appears.

## License

The template is licensed to its owner through their HorizonX membership. Building and shipping sites from it is allowed; publishing or reselling the source files as a template is not. Terms: https://horizonx.so/terms
