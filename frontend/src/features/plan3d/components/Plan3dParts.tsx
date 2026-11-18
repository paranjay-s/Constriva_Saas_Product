/** Small pieces shared by the 2D to 3D pages: notices, links that look like buttons, the page frame. */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircleIcon, ArrowLeftIcon } from '../../../components/ui/Icons';

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#C5A77B]';

/** Something went wrong, said out loud; `children` are the ways out (Retry, a link...). */
export function ErrorNotice({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded border border-[#FFB4AB]/40 bg-[#351010] p-4 text-xs text-[#FFB4AB]">
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
    <div role="status" aria-live="polite" className="text-xs text-[#A6A6A6]">
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
      ? 'bg-[#F5F2EB] font-semibold text-[#101010] hover:bg-[#EAE6DD]'
      : 'border border-[#303030] bg-[#181818] text-white hover:border-[#444444] hover:bg-[#202020]';
  return (
    <Link
      to={to}
      aria-label={label}
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium transition-all duration-150 ${look} ${FOCUS}`}
    >
      {children}
    </Link>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={`inline-flex items-center gap-2 rounded font-mono text-xs uppercase tracking-wider text-[#A6A6A6] hover:text-white ${FOCUS}`}
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
    <div className="flex flex-1 flex-col bg-[#101010] text-white">
      <main className={`mx-auto w-full flex-1 px-4 py-8 sm:px-6 sm:py-12 ${wide ? 'max-w-7xl' : 'max-w-3xl'}`}>
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
      <span className="font-mono text-xs uppercase tracking-widest text-[#C5A77B]">{eyebrow}</span>
      <h1 className="break-words font-display text-3xl font-semibold tracking-tight text-white">{title}</h1>
      {children && <div className="text-sm text-[#A6A6A6]">{children}</div>}
    </div>
  );
}
