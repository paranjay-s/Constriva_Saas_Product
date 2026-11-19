/**
 * The studio drawn as a small skyline: one building per project, one storey per 2D floor
 * plan in it, and one floating picture frame per image analysis. A project with no plan
 * yet is an empty dashed plot. Every number comes from the lists the backend returns.
 */

import { plural } from './format';

export interface SkylineProject {
  id: string;
  name: string;
  plans: number;
}

export const MAX_BUILDINGS = 4;
export const MAX_FLOORS = 4;
export const MAX_FRAMES = 4;

const W = 340;
const GROUND = 118;


export function planLabel(n: number): string {
  return n === 0 ? 'no plan yet' : plural(n, 'plan');
}

function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
}

export function skylineSummary(projects: SkylineProject[], analyses: number): string {
  if (projects.length === 0) return `No projects yet; ${plural(analyses, 'image analysis', 'image analyses')}`;
  const parts = projects.slice(0, MAX_BUILDINGS).map((p) => `${p.name} has ${planLabel(p.plans)}`);
  const more = projects.length - MAX_BUILDINGS;
  if (more > 0) parts.push(`and ${plural(more, 'more project')}`);
  return `Your studio as a skyline: ${parts.join(', ')}; ${plural(analyses, 'image analysis', 'image analyses')}`;
}

export function Skyline({ projects, analyses }: { projects: SkylineProject[]; analyses: number }) {
  const shown = projects.slice(0, MAX_BUILDINGS);
  const hidden = projects.length - shown.length;
  const slots = Math.max(shown.length, 1);
  const slotW = (W - 20) / slots;
  const bw = Math.min(80, slotW - 18);
  const frames = Math.min(analyses, MAX_FRAMES);
  const windows = bw >= 60 ? 3 : 2;
  const labelMax = Math.max(8, Math.floor((slotW - 6) / 5.6));
  // taller storeys while the buildings are low, so a young studio does not look empty
  const tallest = Math.max(1, ...shown.map((p) => Math.min(p.plans, MAX_FLOORS)));
  const FLOOR_H = Math.max(20, Math.min(30, Math.floor(84 / tallest)));
  // crop the empty sky when nothing floats in it
  const top = frames > 0 ? 0 : Math.max(0, GROUND - tallest * FLOOR_H - 26);

  return (
    <svg role="img" aria-label={skylineSummary(projects, analyses)} viewBox={`0 ${top} ${W} ${150 - top}`}>
      <path d={`M10 ${GROUND} H${W - 10}`} stroke="rgba(255,255,255,.35)" strokeWidth="1" fill="none" />

      {shown.length === 0 && (
        <g>
          <rect className="cv-march" x={W / 2 - 40} y={GROUND - 30} width="80" height="30" fill="none" stroke="rgba(255,255,255,.55)" strokeDasharray="4 5" />
          <path d={`M${W / 2} ${GROUND - 22} V${GROUND - 8} M${W / 2 - 7} ${GROUND - 15} H${W / 2 + 7}`} stroke="#bff6fb" strokeWidth="1.6" strokeLinecap="round" />
          <text x={W / 2} y="131" textAnchor="middle" fill="#eef3f8">your first project</text>
        </g>
      )}

      {shown.map((p, i) => {
        const cx = 10 + slotW * i + slotW / 2;
        const x = cx - bw / 2;
        const floors = Math.min(p.plans, MAX_FLOORS);
        const top = GROUND - floors * FLOOR_H;
        const gap = (bw - windows * 12) / (windows + 1);
        return (
          <g key={p.id} data-testid="skyline-building" data-floors={floors}>
            {floors === 0 ? (
              <>
                <rect className="cv-march" x={x} y={GROUND - 30} width={bw} height="30" fill="none" stroke="rgba(255,255,255,.55)" strokeDasharray="4 5" />
                <path d={`M${cx} ${GROUND - 22} V${GROUND - 8} M${cx - 7} ${GROUND - 15} H${cx + 7}`} stroke="#bff6fb" strokeWidth="1.6" strokeLinecap="round" />
              </>
            ) : (
              <>
                {Array.from({ length: floors }, (_, f) => {
                  const y = GROUND - (f + 1) * FLOOR_H;
                  return (
                    <g key={f}>
                      <rect className="cv-floor" x={x} y={y} width={bw} height={FLOOR_H} fill="rgba(124,232,242,.14)" stroke="#bff6fb" strokeWidth="1.1" style={{ ['--d' as string]: `${0.4 + i * 0.15 + f * 0.2}s` }} />
                      {Array.from({ length: windows }, (_, w) => (
                        <rect key={w} className="cv-window" x={x + gap + w * (12 + gap)} y={y + (FLOOR_H - 10) / 2} width="12" height="10" fill="#bff6fb" style={{ ['--d' as string]: `${-((i * 3 + f * 2 + w) % 7) * 0.4}s` }} />
                      ))}
                    </g>
                  );
                })}
                <path d={`M${x - 6} ${top} H${x + bw + 6}`} stroke="#fff" strokeWidth="2" strokeLinecap="round" />
                {p.plans > MAX_FLOORS && (
                  <text x={cx} y={top - 6} textAnchor="middle" fill="#bff6fb">+{p.plans - MAX_FLOORS}</text>
                )}
              </>
            )}
            <text x={cx} y="131" textAnchor="middle" fill="#eef3f8">{clip(p.name, labelMax)}</text>
            <text x={cx} y="143" textAnchor="middle" fill="#a3afbf">{planLabel(p.plans)}</text>
          </g>
        );
      })}

      {Array.from({ length: frames }, (_, i) => {
        const x = W - 44 - i * 34;
        const y = 8 + (i % 2) * 12;
        const rot = `rotate(${i % 2 ? 7 : -8} ${x + 13} ${y + 9.5})`;
        return (
          <g key={i} className="cv-frame" data-testid="skyline-frame" fill="rgba(124,160,255,.22)" stroke="#a9c0ff" strokeWidth="1.1" style={{ ['--d' as string]: `${-i * 1.3}s` }}>
            <rect x={x} y={y} width="26" height="19" rx="3" transform={rot} />
            <path d={`M${x + 4} ${y + 15} l7 -8 l5 5 l3 -3 l4 5`} fill="none" transform={rot} />
          </g>
        );
      })}
      {analyses > MAX_FRAMES && (
        <text x={W - 44 - frames * 34 + 20} y="24" textAnchor="end" fill="#a9c0ff">+{analyses - MAX_FRAMES}</text>
      )}
      {hidden > 0 && (
        <text x="10" y={top + 10} fill="#a3afbf">+{hidden} more</text>
      )}
    </svg>
  );
}
