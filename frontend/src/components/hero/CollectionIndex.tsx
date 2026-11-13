import { useRef } from "react";
import { siteContent, type CollectionChip } from "../../content/site";
import { useGlass } from "../../hooks/useGlass";

function ChipRow({ chip }: { chip: CollectionChip }) {
  const rowRef = useRef<HTMLAnchorElement | null>(null);

  useGlass(rowRef, {
    refraction: 80,
    depth: 20,
    dispersion: 50,
    frost: 4,
  });

  return (
    <a
      ref={rowRef}
      className="index__row"
      href={chip.href}
      data-glass
      data-glass-refraction="80"
      data-glass-depth="20"
      data-glass-dispersion="50"
      data-glass-frost="4"
    >
      <span className="index__num">{chip.num}</span>
      <span className="index__label">{chip.label}</span>
      <span className="index__count">{chip.count}</span>
    </a>
  );
}

export function CollectionIndex() {
  const { chips } = siteContent;

  return (
    <nav className="index" data-reveal aria-label="Collections">
      {chips.map((chip) => (
        <ChipRow key={chip.num} chip={chip} />
      ))}
    </nav>
  );
}
