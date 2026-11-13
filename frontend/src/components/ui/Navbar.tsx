import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { BrandMark } from './Icons';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, signOut } = useAuth();
  const { activeProject } = useProject();
  const navigate = useNavigate();
  const location = useLocation();

  const navLinks = [
    { label: 'Studio Home', path: '/home' },
    { label: 'New Project', path: '/projects/new' },
    { label: '3D Workspace', path: '/projects/3d-workspace' },
    { label: 'AI Generator', path: '/projects/ai-generator' },
    { label: 'Material AI', path: '/materials/analyse' },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/10 bg-[#0d0f12]/85 backdrop-blur-xl px-4 lg:px-8 py-3 flex items-center justify-between transition-colors">
      {/* Brand & Active Project */}
      <div className="flex items-center gap-6">
        <Link to="/home" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-white/[0.06] border border-white/15 flex items-center justify-center text-[#C5A77B] group-hover:scale-105 group-hover:border-[#C5A77B] transition-all">
            <BrandMark className="w-5 h-5 text-[#C5A77B]" />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-medium text-base tracking-wider uppercase text-white">
              Constriva
            </span>
            <span className="text-[9px] uppercase tracking-widest text-white/50 -mt-1 font-mono">
              Atelier Suite
            </span>
          </div>
        </Link>

        {activeProject && (
          <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-white/10">
            <span className="w-2 h-2 rounded-full bg-[#ffbf7a] animate-pulse-glow" />
            <span className="text-[10px] uppercase tracking-wider text-white/50 font-mono">
              Active:
            </span>
            <span className="text-xs font-medium text-[#fff1e2] bg-white/[0.05] border border-white/10 px-2.5 py-0.5 rounded-full">
              {activeProject.name}
            </span>
          </div>
        )}
      </div>

      {/* Center Navigation Pills (Desktop) */}
      <nav className="hidden md:flex items-center gap-1 p-1 rounded-full arch-glass-pill border border-white/10 text-xs font-medium">
        {navLinks.map((link) => {
          const isActive = location.pathname === link.path;
          return (
            <Link
              key={link.path}
              to={link.path}
              className={`px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive
                  ? 'bg-black text-white shadow-sm font-semibold'
                  : 'text-white/70 hover:text-white hover:bg-white/[0.08]'
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      {/* Right User & Actions */}
      <div className="flex items-center gap-3">
        {isAuthenticated ? (
          <>
            <div className="hidden sm:flex items-center gap-2 text-xs text-white/70 bg-white/[0.04] border border-white/10 px-3 py-1.5 rounded-full">
              <span className="w-2 h-2 rounded-full bg-[#C5A77B]" />
              <span className="font-mono text-[11px]">{user?.email || 'Architect'}</span>
            </div>
            <button
              onClick={() => {
                signOut();
                navigate('/auth');
              }}
              className="text-xs font-mono text-white/60 hover:text-white bg-white/[0.03] hover:bg-white/[0.08] px-3.5 py-1.5 rounded-full transition-all border border-white/10 cursor-pointer"
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link
            to="/auth"
            className="text-xs font-semibold bg-white text-[#101418] hover:bg-white/90 px-4 py-1.5 rounded-full transition-all shadow-md hover:-translate-y-0.5"
          >
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};
