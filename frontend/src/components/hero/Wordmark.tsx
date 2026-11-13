import type { CSSProperties } from "react";
import { BRAND } from "../../content/site";

export function Wordmark() {
  const letters = BRAND.toLowerCase().split("");

  return (
    <h1 className="wordmark" id="hero-title" aria-label={BRAND}>
      <span className="wordmark__line" aria-hidden="true">
        {letters.map((char, i) => (
          <span
            key={i}
            className="wordmark__char"
            style={{ "--i": i } as CSSProperties}
          >
            {char}
          </span>
        ))}
      </span>
    </h1>
  );
}
