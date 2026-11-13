import { useRef } from "react";
import { Hero } from "../../components/hero/Hero";
import { Tour } from "../../components/tour/Tour";

export function LandingPage() {
  const heroRef = useRef<HTMLElement | null>(null);
  const tourRef = useRef<HTMLElement | null>(null);

  return (
    <main className="page">
      <Hero heroRef={heroRef} />
      <Tour tourRef={tourRef} heroRef={heroRef} />
    </main>
  );
}

export default LandingPage;
