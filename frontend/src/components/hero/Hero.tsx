import { useRef, type RefObject } from "react";
import { Wordmark } from "./Wordmark";
import { Nav } from "./Nav";
import { MobileMenu } from "./MobileMenu";
import { CollectionIndex } from "./CollectionIndex";
import { FeaturedCard } from "./FeaturedCard";
import { Lede } from "./Lede";
import { useHeroLayout } from "../../hooks/useHeroLayout";
import { useMobileMenu } from "../../hooks/useMobileMenu";

interface HeroProps {
  heroRef: RefObject<HTMLElement | null>;
}

export function Hero({ heroRef }: HeroProps) {
  const menuBtnRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useHeroLayout(heroRef);
  useMobileMenu(heroRef, menuBtnRef, menuRef);

  const getBaseUrl = () => {
    const base = import.meta.env.BASE_URL || "/";
    return base.endsWith("/") ? base : `${base}/`;
  };

  return (
    <section ref={heroRef} className="hero" id="hero" aria-labelledby="hero-title">
      {/* Layer 1: full photo (sky + house) */}
      <div className="stage stage--bg" aria-hidden="true">
        <img
          className="stage__img"
          src={`${getBaseUrl()}assets/house-bg.webp?v=evening1`}
          width={1200}
          height={1000}
          alt=""
          decoding="async"
          fetchPriority="high"
        />
        <div className="stage__sky"></div>
      </div>

      {/* Layer 2: giant wordmark, sits behind the house */}
      <Wordmark />

      {/* Layer 3: house + trees cut out of the same photo */}
      <div className="stage stage--fg" aria-hidden="true">
        <img
          className="stage__img"
          src={`${getBaseUrl()}assets/house-fg.webp?v=evening1`}
          width={1200}
          height={1000}
          alt=""
          decoding="async"
          fetchPriority="high"
        />
      </div>

      <div className="hero__shade" aria-hidden="true"></div>

      {/* Layer 4: interface */}
      <Nav menuBtnRef={menuBtnRef} />
      <MobileMenu menuRef={menuRef} />
      <CollectionIndex />

      <div className="foot">
        <FeaturedCard />
        <Lede />
      </div>
    </section>
  );
}
