import { useRef, type RefObject } from "react";
import { siteContent } from "../../content/site";
import { BrandMark, CtaArrow } from "../ui/Icons";
import { useGlass } from "../../hooks/useGlass";

interface NavProps {
  menuBtnRef: RefObject<HTMLButtonElement | null>;
}

export function Nav({ menuBtnRef }: NavProps) {
  const { brand, nav } = siteContent;
  const navLinksRef = useRef<HTMLElement | null>(null);

  useGlass(navLinksRef, {
    refraction: 80,
    depth: 20,
    dispersion: 50,
    frost: 4,
  });

  useGlass(menuBtnRef, {
    refraction: 80,
    depth: 20,
    dispersion: 50,
    frost: 4,
  });

  return (
    <header className="nav" data-reveal>
      <a className="brand" href="#" aria-label={`${brand} home`}>
        <BrandMark className="brand__mark" />
        <span className="brand__name">{brand}</span>
      </a>

      <nav
        ref={navLinksRef}
        className="nav__links"
        aria-label="Primary"
        data-glass
        data-glass-refraction="80"
        data-glass-depth="20"
        data-glass-dispersion="50"
        data-glass-frost="4"
      >
        {nav.links.map((link) => (
          <a
            key={link.label}
            className={`nav__link ${link.isActive ? "is-active" : ""}`}
            href={link.href}
            aria-current={link.isActive ? "page" : undefined}
          >
            {link.label}
          </a>
        ))}
      </nav>

      <a className="cta" href={nav.cta.href}>
        <span>{nav.cta.label}</span>
        <span className="cta__icon" aria-hidden="true">
          <CtaArrow />
        </span>
      </a>

      <button
        ref={menuBtnRef}
        className="menu-btn"
        type="button"
        data-glass
        data-glass-refraction="80"
        data-glass-depth="20"
        data-glass-dispersion="50"
        data-glass-frost="4"
        aria-expanded="false"
        aria-controls="mobile-menu"
        aria-label="Open menu"
      >
        <span></span>
        <span></span>
      </button>
    </header>
  );
}
