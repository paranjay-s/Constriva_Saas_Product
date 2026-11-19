/** Studio icons: Lucide-style 1.5 stroke paths (Lucide, ISC License, lucide.dev). */
import type { SVGProps } from 'react';

const PATHS = {
  pen: 'M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7|M18.4 2.6a1 1 0 0 1 3 3l-9 9a2 2 0 0 1-.9.5l-2.9.8a.5.5 0 0 1-.6-.6l.8-2.9a2 2 0 0 1 .5-.8z',
  history: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8|M3 3v5h5|M12 7v5l4 2',
  plan: 'M3 3h18v18H3z|M3 12h9|M12 3v18|M12 15h9',
  image: 'M3 3h18v18H3z|M8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3|M21 15l-5-5L5 21',
  folder: 'M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z',
  home: 'M3 10.5 12 3l9 7.5|M5 9.5V21h14V9.5|M10 21v-6h4v6',
  pause: 'M14 4h4v16h-4z|M6 4h4v16H6z',
  play: 'M6 3l14 9-14 9z',
  panel: 'M3 3h18v18H3z|M9 3v18',
  plus: 'M5 12h14|M12 5v14',
  mic: 'M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z|M19 10v2a7 7 0 0 1-14 0v-2|M12 19v3',
  arrow: 'M7 7h10v10|M7 17 17 7',
  x: 'M18 6 6 18|M6 6l12 12',
  menu: 'M4 7h16|M4 12h16|M4 17h10',
  trash: 'M3 6h18|M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6|M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2',
  clip: 'm21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48',
  chevron: 'm6 9 6 6 6-6',
  undo: 'M3 7v6h6|M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13',
  download: 'M12 3v12|m7 10 5 5 5-5|M5 21h14',
  cube: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z|M3.3 7 12 12l8.7-5|M12 22V12',
  spark: 'M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.5l-1.9-5.7-5.6-1.9L10.1 9z|M19 3v4|M21 5h-4',
  maximize: 'M8 3H5a2 2 0 0 0-2 2v3|M21 8V5a2 2 0 0 0-2-2h-3|M3 16v3a2 2 0 0 0 2 2h3|M16 21h3a2 2 0 0 0 2-2v-3',
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, small, ...rest }: { name: IconName; small?: boolean } & SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" className={`st-i${small ? ' st-i-sm' : ''}`} aria-hidden="true" focusable="false" {...rest}>
      {PATHS[name].split('|').map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
