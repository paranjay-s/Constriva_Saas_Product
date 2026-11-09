import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { LogoIcon } from './Icons';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, signOut } = useAuth();
  const { activeProject } = useProject();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#303030] bg-[#101010]/95 backdrop-blur px-4 lg:px-8 py-3.5 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <Link to="/home" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded bg-[#181818] border border-[#303030] flex items-center justify-center text-[#C5A77B] group-hover:border-[#C5A77B] transition-colors">
            <LogoIcon size={18} />
          </div>
          <div className="flex flex-col">
            <span className="font-display font-semibold text-base tracking-wider uppercase text-[#FFFFFF]">
              Construtiva
            </span>
            <span className="text-[10px] uppercase tracking-widest text-[#A6A6A6] -mt-1 font-mono">
              Architecture Suite
            </span>
          </div>
        </Link>

        {activeProject && (
          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-[#303030]">
            <span className="text-[11px] uppercase tracking-wider text-[#737373] font-mono">
              Active Project:
            </span>
            <span className="text-xs font-medium text-[#C5A77B] bg-[#181818] border border-[#303030] px-2.5 py-1 rounded">
              {activeProject.name}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {isAuthenticated ? (
          <>
            <div className="hidden sm:flex items-center gap-2 text-xs text-[#A6A6A6] bg-[#181818] border border-[#303030] px-3 py-1.5 rounded">
              <span className="w-2 h-2 rounded-full bg-[#C5A77B]" />
              <span>{user?.email || 'User'}</span>
            </div>
            <button
              onClick={() => {
                signOut();
                navigate('/auth');
              }}
              className="text-xs text-[#A6A6A6] hover:text-[#FFFFFF] hover:bg-[#181818] px-3 py-1.5 rounded transition-colors cursor-pointer border border-transparent hover:border-[#303030]"
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link
            to="/auth"
            className="text-xs font-semibold bg-[#F5F2EB] text-[#101010] hover:bg-[#EAE6DD] px-3.5 py-1.5 rounded transition-colors"
          >
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};

