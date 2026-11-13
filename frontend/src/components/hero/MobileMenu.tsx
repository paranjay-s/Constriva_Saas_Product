import type { RefObject } from "react";
import { siteContent } from "../../content/site";
import { useGlass } from "../../hooks/useGlass";

interface MobileMenuProps {
  menuRef: RefObject<HTMLDivElement | null>;
}

export function MobileMenu({ menuRef }: MobileMenuProps) {
  const { nav } = siteContent;

  useGlass(menuRef, {
    refraction: 80,
    depth: 20,
    dispersion: 50,
    frost: 4,
  });

  return (
    <div
      ref={menuRef}
      className="mobile-menu"
      id="mobile-menu"
      hidden
      data-glass
      data-glass-refraction="80"
      data-glass-depth="20"
      data-glass-dispersion="50"
      data-glass-frost="4"
    >
      {nav.links.map((link) => (
        <a
          key={link.label}
          className={link.isActive ? "is-active" : undefined}
          href={link.href}
          aria-current={link.isActive ? "page" : undefined}
        >
          {link.label}
        </a>
      ))}
      <a className="mobile-menu__cta" href={nav.cta.href}>
        {nav.cta.label}
      </a>
    </div>
  );
}
