import { Fragment } from "react";
import type { Beat as BeatType } from "../../content/site";
import { LinkArrow, PlayCue } from "../ui/Icons";

interface BeatProps {
  beat: BeatType;
}

export function Beat({ beat }: BeatProps) {
  const { at, placement, eyebrow, title, isXl, isBold, sub, highlight, cta } = beat;
  const isIntro = placement === "intro";
  const id = isIntro ? "tour-intro" : at === 1 ? "tour-living" : undefined;
  const titleId = isIntro ? "tour-title" : undefined;

  return (
    <li className={`beat beat--${placement}`} data-at={at} id={id}>
      <p className="beat__eyebrow">{eyebrow}</p>

      {highlight && (
        <div className="beat__highlight" aria-label="Feature highlight">
          <span className="beat__highlight-dot" aria-hidden="true"></span>
          <span className="beat__highlight-text">{highlight}</span>
        </div>
      )}

      <h2
        className={`beat__title ${isXl ? "beat__title--xl" : ""} ${isBold ? "beat__title--bold" : ""}`}
        id={titleId}
      >
        {title.map((line, i) => (
          <Fragment key={i}>
            {line}
            {i < title.length - 1 && <br />}
          </Fragment>
        ))}
      </h2>

      <p className="beat__sub">{sub}</p>

      {isIntro && (
        <span className="beat__cue" aria-hidden="true">
          <PlayCue />
        </span>
      )}

      {cta && (
        <a className="beat__cta" href={cta.href}>
          <span>{cta.label}</span>
          <LinkArrow />
        </a>
      )}
    </li>
  );
}
