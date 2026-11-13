import { siteContent } from "./site";

export const FRAME_COUNT = 421;
export const VERSION = "1";
export const ROOMS = siteContent.beats.length - 1;
export const PER_ROOM = (FRAME_COUNT - 1) / ROOMS;

// Dev-time assertion ensuring configuration invariants
if (import.meta.env?.DEV) {
  if (ROOMS !== 7) {
    console.warn(`[tour.config] Expected 7 rooms for 8 beats, got ${ROOMS}`);
  }
  const maxAt = Math.max(...siteContent.beats.map((b) => b.at));
  if (maxAt !== ROOMS) {
    console.warn(
      `[tour.config] Max beat 'at' index (${maxAt}) does not match ROOMS (${ROOMS})`
    );
  }
}
