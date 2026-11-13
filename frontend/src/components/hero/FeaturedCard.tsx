import { useRef } from "react";
import { siteContent } from "../../content/site";
import { LinkArrow } from "../ui/Icons";
import { useGlass } from "../../hooks/useGlass";

export function FeaturedCard() {
  const cardRef = useRef<HTMLAnchorElement | null>(null);
  const { featured } = siteContent;

  useGlass(cardRef, {
    refraction: 80,
    depth: 20,
    dispersion: 50,
    frost: 32,
  });

  return (
    <a
      ref={cardRef}
      className="feature"
      href={featured.href}
      data-reveal
      data-glass
      data-glass-refraction="80"
      data-glass-depth="20"
      data-glass-dispersion="50"
      data-glass-frost="32"
    >
      <span className="feature__eyebrow">
        <span className="feature__live" aria-hidden="true"></span>
        {featured.eyebrow}
      </span>
      <span className="feature__name">{featured.name}</span>
      <span className="feature__place">{featured.place}</span>
      <span className="feature__specs">
        {featured.specs.map((spec) => (
          <span key={spec}>{spec}</span>
        ))}
      </span>
      <span className="feature__foot">
        <span className="feature__price">{featured.price}</span>
        <span className="feature__go">
          {featured.linkText}
          <LinkArrow />
        </span>
      </span>
    </a>
  );
}
