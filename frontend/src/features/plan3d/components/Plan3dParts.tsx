/** Small pieces shared by the 2D to 3D pages: notices, links that look like buttons, the page frame.
 * They follow the dashboard's look (features/dashboard/dashboard.css): ink, cyan, pills, light display type. */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircleIcon, ArrowLeftIcon } from '../../../components/ui/Icons';

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#bff6fb] focus-visible:ring-offset-2 focus-visible:ring-offset-[#04060a]';

/** Something went wrong, said out loud; `children` are the ways out (Retry, a link...). */
export function ErrorNotice({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-xl border border-[#ffb4ab]/40 bg-[#ffb4ab]/[0.08] p-4 text-[13px] text-[#ffb4ab]">
      <div className="flex items-start gap-3">
        <AlertCircleIcon size={18} className="shrink-0" aria-hidden="true" />
        <span className="min-w-0 break-words leading-relaxed">{message}</span>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

/** A quiet line about something that is happening. */
export function StatusNote({ children }: { children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" className="font-mono text-xs text-[#a3afbf]">
      {children}
    </div>
  );
}

interface LinkButtonProps {
  to: string;
  variant?: 'primary' | 'secondary';
  /** The name read out, when the words on the button are not enough on their own (e.g. "Open"). */
  label?: string;
  children: ReactNode;
}

/** A link to another page of the app, drawn like a small button. */
export function LinkButton({ to, variant = 'secondary', label, children }: LinkButtonProps) {
  const look =
    variant === 'primary'
      ? 'bg-[linear-gradient(135deg,#bff6fb,#7ca0ff)] font-semibold text-[#04060a] hover:brightness-110'
      : 'border border-white/20 bg-white/[0.06] text-white hover:bg-white/[0.12]';
  return (
    <Link
      to={to}
      aria-label={label}
      className={`inline-flex h-9 items-center justify-center gap-1.5 rounded-full px-4 text-[13px] font-medium transition-all duration-150 ${look} ${FOCUS}`}
    >
      {children}
    </Link>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={`inline-flex h-11 items-center gap-2 rounded-full border border-white/10 bg-[rgba(10,14,21,0.78)] px-4 text-sm text-[#c9d3df] hover:text-white ${FOCUS}`}
    >
      <ArrowLeftIcon size={16} aria-hidden="true" />
      {children}
    </Link>
  );
}

interface PageFrameProps {
  /** Pages with an iframe use the full width; the others stay narrow. */
  wide?: boolean;
  children: ReactNode;
}

export function PageFrame({ wide = false, children }: PageFrameProps) {
  return (
    <div className="relative z-[2] flex flex-1 flex-col text-[#eef3f8]">
      <main className={`mx-auto w-full flex-1 px-4 py-6 sm:px-7 sm:py-8 ${wide ? 'max-w-7xl' : 'max-w-3xl'}`}>
        <div className="flex flex-col gap-8">{children}</div>
      </main>
    </div>
  );
}

interface PageTitleProps {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}

export function PageTitle({ eyebrow, title, children }: PageTitleProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="font-mono text-xs uppercase tracking-[0.08em] text-[#bff6fb]">{eyebrow}</span>
      <h1 className="break-words text-[clamp(32px,3.6vw,48px)] font-light leading-[1.04] tracking-[-0.03em] text-white">{title}</h1>
      {children && <div className="mt-2 text-[15px] leading-relaxed text-[#c9d3df]">{children}</div>}
    </div>
  );
}
