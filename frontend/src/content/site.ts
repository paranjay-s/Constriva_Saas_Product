export const BRAND = "Constriva";

export type BeatPlacement =
  | "intro"
  | "left"
  | "right"
  | "low-left"
  | "low-right"
  | "end";

export interface Beat {
  at: number; // stop index, 0 … ROOMS
  placement: BeatPlacement;
  eyebrow: string;
  title: string[]; // one string per line (rendered with <br>)
  isXl?: boolean;
  isBold?: boolean;
  sub: string;
  highlight?: string;
  cta?: { label: string; href: string };
}

export interface NavLink {
  label: string;
  href: string;
  isActive?: boolean;
}

export interface CollectionChip {
  num: string;
  label: string;
  count: string;
  href: string;
}

export interface FeaturedResidence {
  eyebrow: string;
  name: string;
  place: string;
  specs: string[];
  price: string;
  linkText: string;
  href: string;
}

export interface SiteContent {
  brand: string;
  meta: {
    title: string;
    description: string;
  };
  nav: {
    links: NavLink[];
    cta: {
      label: string;
      href: string;
    };
  };
  chips: CollectionChip[];
  featured: FeaturedResidence;
  lede: {
    text: string;
    link: {
      label: string;
      href: string;
    };
  };
  beats: Beat[];
}

export const siteContent: SiteContent = {
  brand: BRAND,
  meta: {
    title: "Constriva — From 2D floor plan to live 3D, with the BOQ built in",
    description:
      "Turn a 2D floor plan into a live 3D home you can walk through, with a material-wise BOQ you can download as a PDF.",
  },
  nav: {
    links: [
      { label: "Product", href: "#", isActive: true },
      { label: "Features", href: "#" },
      { label: "How it works", href: "#" },
      { label: "Pricing", href: "#" },
      { label: "Resources", href: "#" },
    ],
    cta: {
      label: "Try Constriva",
      href: "/auth",
    },
  },
  chips: [
    { num: "01", label: "Plan to 3D", count: "Live", href: "#" },
    { num: "02", label: "BOQ sheets", count: "PDF", href: "#" },
    { num: "03", label: "Material AI", count: "Photo", href: "#" },
  ],
  featured: {
    eyebrow: "Live demo",
    name: "Sample villa",
    place: "Rendered from a 2D floor plan",
    specs: ["2D plan", "3D model", "BOQ"],
    price: "2D → 3D",
    linkText: "Take the tour",
    href: "#tour",
  },
  lede: {
    text: "Upload a 2D floor plan and walk through it in live 3D, with every material counted before you break ground.",
    link: {
      label: "See how it works",
      href: "#tour",
    },
  },
  beats: [
    {
      at: 0,
      placement: "intro",
      eyebrow: "Constriva — Live 3D demo",
      title: ["Constriva"],
      isXl: true,
      sub: "A 2D floor plan, rendered as a live 3D home. Scroll to step inside.",
    },
    {
      at: 1,
      placement: "left",
      eyebrow: "01 / Import 2D Plan",
      title: ["Import plan,", "in live 3D"],
      isBold: true,
      sub: "Upload a 2D floor plan. Get a live model.",
      highlight: "Upload 2D Plan → Live 3D Walkthrough",
      cta: {
        label: "Import 2D Plan",
        href: "/projects/import",
      },
    },
    {
      at: 2,
      placement: "right",
      eyebrow: "02 / Walkthrough",
      title: ["Room by", "room"],
      isBold: true,
      sub: "Move through the home before it is built.",
      cta: {
        label: "Open Walkthrough",
        href: "/projects/3d-workspace",
      },
    },
    {
      at: 3,
      placement: "low-left",
      eyebrow: "03 / BOQ Sheets",
      title: ["Every", "material"],
      isBold: true,
      sub: "Types, units and quantities, counted for you.",
      cta: {
        label: "View BOQ Sheet",
        href: "/projects/options",
      },
    },
    {
      at: 4,
      placement: "right",
      eyebrow: "04 / Export PDF",
      title: ["One sheet,", "as PDF"],
      isBold: true,
      sub: "Download the material estimate and share it.",
      cta: {
        label: "Export PDF Sheet",
        href: "/projects/options",
      },
    },
    {
      at: 5,
      placement: "left",
      eyebrow: "05 / Highlight",
      title: ["See where", "it goes"],
      isBold: true,
      sub: "Pick a material. See every place it is used.",
      cta: {
        label: "Inspect Materials",
        href: "/materials/analyse",
      },
    },
    {
      at: 6,
      placement: "low-right",
      eyebrow: "06 / Prompt to plan",
      title: ["No plan?", "Prompt it"],
      isBold: true,
      sub: "Describe a home, get a 2D plan, render it in 3D.",
      cta: {
        label: "Prompt a Plan",
        href: "/projects/ai-generator",
      },
    },
    {
      at: 7,
      placement: "end",
      eyebrow: "07 / Material AI",
      title: ["Snap it,", "know it"],
      isBold: true,
      sub: "Send any interior or facade to the agent. It names the materials.",
      cta: {
        label: "Try Constriva Free",
        href: "/auth",
      },
    },
  ],
};
