/** Line icons for the dashboard pages (24 px grid, inherit the text colour). */
import type { ReactNode, SVGProps } from 'react';

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 18, children, ...rest }: P & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const ArchMark = (p: P) => (
  <Svg size={22} strokeWidth={1.7} {...p}>
    <path d="M5 21V11a7 7 0 0 1 14 0v10" />
    <path d="M9 21v-9a3 3 0 0 1 6 0v9" />
    <path d="M3 21h18" />
  </Svg>
);
export const PlanIcon = (p: P) => (
  <Svg {...p}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M3 12h9v9M12 3v5" />
  </Svg>
);
export const PhotoIcon = (p: P) => (
  <Svg {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <circle cx="9" cy="10" r="1.6" />
    <path d="M21 16l-5-5-8 8" />
  </Svg>
);
export const ArrowRight = (p: P) => (
  <Svg strokeWidth={2} {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Svg>
);
export const ArrowLeft = (p: P) => (
  <Svg size={16} strokeWidth={2} {...p}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Svg>
);
export const Plus = (p: P) => (
  <Svg size={20} strokeWidth={2} {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const Trash = (p: P) => (
  <Svg size={16} {...p}>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
  </Svg>
);
export const Refresh = (p: P) => (
  <Svg {...p}>
    <path d="M20 12a8 8 0 1 1-2.3-5.7" />
    <path d="M20 4v4h-4" />
  </Svg>
);
export const FileUp = (p: P) => (
  <Svg size={20} strokeWidth={1.7} {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M12 18v-6M9 14.5l3-3 3 3" />
  </Svg>
);
export const Spark = (p: P) => (
  <Svg size={20} strokeWidth={1.7} {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18" />
  </Svg>
);
export const DashedRing = (p: P) => (
  <Svg size={20} strokeWidth={1.7} strokeDasharray="2 3" {...p}>
    <circle cx="12" cy="12" r="9" />
  </Svg>
);
