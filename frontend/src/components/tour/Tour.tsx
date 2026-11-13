import type { RefObject } from "react";
import { siteContent } from "../../content/site";
import { FRAME_COUNT, VERSION } from "../../content/tour.config";
import { Beat } from "./Beat";
import { ProgressBar } from "./ProgressBar";
import { useTourScrub } from "../../hooks/useTourScrub";
import { usePager } from "../../hooks/usePager";

interface TourProps {
  tourRef: RefObject<HTMLElement | null>;
  heroRef: RefObject<HTMLElement | null>;
}

export function Tour({ tourRef, heroRef }: TourProps) {
  const { beats } = siteContent;

  useTourScrub(tourRef);
  usePager(tourRef, heroRef);

  const getBaseUrl = () => {
    const base = import.meta.env.BASE_URL || "/";
    return base.endsWith("/") ? base : `${base}/`;
  };

  return (
    <section
      ref={tourRef}
      className="tour"
      id="tour"
      data-frames={FRAME_COUNT}
      data-version={VERSION}
      aria-labelledby="tour-title"
    >
      <div className="tour__sticky">
        <canvas className="tour__canvas" aria-hidden="true"></canvas>
        <img
          className="tour__poster"
          src={`${getBaseUrl()}assets/tour/poster.webp?v=${VERSION}`}
          width={1600}
          height={900}
          alt=""
          decoding="async"
          loading="lazy"
        />
        <div className="tour__shade" aria-hidden="true"></div>

        <ol className="tour__beats">
          {beats.map((beat) => (
            <Beat key={beat.at} beat={beat} />
          ))}
        </ol>

        <ProgressBar />
      </div>
    </section>
  );
}
