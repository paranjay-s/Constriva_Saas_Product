/**
 * Header shared by the dashboard pages: brand, the current module, section links and the
 * account menu (name and email come from the signed-in user).
 */
import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ArchMark } from './icons';

const MODULES: [prefix: string, label: string][] = [
  ['/home', 'Overview'],
  ['/projects/new', 'New project'],
  ['/projects/options', 'New project'],
  ['/3d', '2D to 3D'],
  ['/boq', 'BOQ raw materials'],
  ['/projects/loan-analysis', 'Loan analysis'],
  ['/projects/ai-generator', 'Floor plan chat'],
];

export function moduleFor(pathname: string): string {
  return MODULES.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'Studio';
}

/** "Demo Architect" -> "DA"; falls back to the first letters of the email. */
export function initialsOf(name?: string, email?: string): string {
  const words = (name || '').trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  const one = words[0] || (email || '').split('@')[0];
  return (one.slice(0, 2) || '?').toUpperCase();
}

export function DashHeader() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const account = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !account.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  // step 2 of project creation belongs to the same section as step 1
  const inNew = pathname.startsWith('/projects/new') || pathname.startsWith('/projects/options');

  return (
    <header className="cv-header">
      <div className="cv-brand">
        <Link to="/home" className="cv-chip" aria-label="Constriva home">
          <ArchMark />
        </Link>
        <div className="cv-module">
          <span className="cv-dot cv-pulse" aria-hidden="true" />
          <span>
            <em>Module</em> · {moduleFor(pathname)}
          </span>
        </div>
      </div>

      <nav className="cv-nav" aria-label="Sections">
        <NavLink to="/home">Overview</NavLink>
        <Link to="/projects/new" aria-current={inNew ? 'page' : undefined}>
          New project
        </Link>
        <NavLink to="/3d">2D to 3D</NavLink>
        <NavLink to="/boq">BOQ</NavLink>
        <span className="cv-nav-sep" aria-hidden="true" />
        <NavLink to="/projects/ai-generator">Floor plan chat</NavLink>
        <NavLink to="/materials/analyse">Image analysis</NavLink>
      </nav>

      <div className="cv-account" ref={account}>
        <button
          type="button"
          className="cv-avatar"
          aria-label="Account"
          aria-haspopup="true"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {initialsOf(user?.name, user?.email)}
        </button>
        {open && (
          <div className="cv-menu">
            <p className="cv-menu-name">{user?.name || 'Signed in'}</p>
            {user?.email && <p className="cv-menu-mail">{user.email}</p>}
            <button
              type="button"
              className="cv-btn cv-btn-sm cv-btn-block"
              style={{ marginTop: 12 }}
              onClick={() => {
                signOut();
                navigate('/auth');
              }}
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
