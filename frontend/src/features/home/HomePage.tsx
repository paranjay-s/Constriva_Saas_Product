import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRightIcon,
  BoxIcon,
  ImageIcon,
  RefreshIcon,
  TrashIcon,
  IconSparkles,
  IconFilePdf,
} from '../../components/ui/Icons';
import { useProject } from '../../context/ProjectContext';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    projects,
    isLoadingProjects,
    fetchProjects,
    selectProject,
    deleteProject,
    activeProject,
  } = useProject();

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleOpenProject = async (project: (typeof projects)[0]) => {
    await selectProject(project);
    navigate('/projects/3d-workspace');
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this project?')) {
      await deleteProject(projectId);
    }
  };

  return (
    <div className="flex-1 bg-[#0d0f12] text-white flex flex-col font-ui relative overflow-hidden">
      {/* Background Architectural Ambient Lighting */}
      <div
        className="absolute top-0 left-1/4 w-96 h-96 bg-[#0f2f6b]/20 rounded-full blur-3xl pointer-events-none"
        aria-hidden="true"
      />
      <div
        className="absolute bottom-10 right-10 w-96 h-96 bg-[#c5a77b]/10 rounded-full blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-10 lg:py-14 flex flex-col justify-start z-10">
        {/* Studio Hero Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full arch-glass text-[11px] font-mono uppercase tracking-widest text-[#ffbf7a] mb-4">
              <span className="w-1.5 h-1.5 rounded-full bg-[#ffbf7a] animate-pulse-glow" />
              <span>Constriva Architectural OS</span>
            </div>
            <h1 className="font-display font-medium text-3xl sm:text-4xl lg:text-5xl text-white tracking-tight leading-tight">
              Architectural Studio Workspace
            </h1>
            <p className="text-sm sm:text-base text-white/70 mt-2 max-w-2xl font-normal leading-relaxed">
              Transform architectural drawings into photorealistic 3D environments with automated Bill of Quantities (BOQ) material schedules.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/projects/new')}
              className="group inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-white text-[#101418] font-semibold text-xs hover:bg-[#f0f4f8] transition-all shadow-md hover:-translate-y-0.5 cursor-pointer"
            >
              <span>+ Create New Project</span>
              <span className="w-5 h-5 rounded-full bg-[#101418] text-white flex items-center justify-center group-hover:rotate-45 transition-transform duration-300">
                <ArrowRightIcon size={12} />
              </span>
            </button>
          </div>
        </div>

        {/* 4 Core Pillars Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-14">
          {/* Action 1: 2D Plan to 3D */}
          <div
            onClick={() => navigate('/projects/new')}
            className="arch-glass arch-glass-hover p-6 rounded-2xl flex flex-col justify-between cursor-pointer group"
          >
            <div>
              <div className="w-12 h-12 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-[#ffbf7a] mb-4 group-hover:scale-105 transition-transform">
                <BoxIcon size={22} />
              </div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 block mb-1">
                Pillar 01 // Spatial BIM
              </span>
              <h2 className="font-display font-medium text-lg text-white group-hover:text-[#fff1e2] transition-colors">
                2D Plan to 3D
              </h2>
              <p className="text-xs text-white/70 mt-2 leading-relaxed">
                Upload CAD floor plans or architectural PDFs to synthesize an interactive 3D walkthrough.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-[#C5A77B]">
              <span>Upload PDF</span>
              <ArrowRightIcon size={14} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Action 2: Prompt to Plan */}
          <div
            onClick={() => navigate('/projects/ai-generator')}
            className="arch-glass arch-glass-hover p-6 rounded-2xl flex flex-col justify-between cursor-pointer group"
          >
            <div>
              <div className="w-12 h-12 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-[#C5A77B] mb-4 group-hover:scale-105 transition-transform">
                <IconSparkles size={22} />
              </div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 block mb-1">
                Pillar 02 // Synthesis
              </span>
              <h2 className="font-display font-medium text-lg text-white group-hover:text-[#fff1e2] transition-colors">
                Prompt to Plan
              </h2>
              <p className="text-xs text-white/70 mt-2 leading-relaxed">
                Describe desired plot dimensions and layout requirements in words to generate 2D CAD blueprints.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-[#C5A77B]">
              <span>Prompt Studio</span>
              <ArrowRightIcon size={14} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Action 3: BOQ Sheets */}
          <div
            onClick={() => navigate('/projects/options')}
            className="arch-glass arch-glass-hover p-6 rounded-2xl flex flex-col justify-between cursor-pointer group"
          >
            <div>
              <div className="w-12 h-12 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-[#A7F3D0] mb-4 group-hover:scale-105 transition-transform">
                <IconFilePdf size={22} />
              </div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 block mb-1">
                Pillar 03 // Quantities
              </span>
              <h2 className="font-display font-medium text-lg text-white group-hover:text-[#fff1e2] transition-colors">
                BOQ Sheets (PDF)
              </h2>
              <p className="text-xs text-white/70 mt-2 leading-relaxed">
                Automated itemized material schedules with spatial 3D highlighting and downloadable PDFs.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-[#C5A77B]">
              <span>Cost Sheets</span>
              <ArrowRightIcon size={14} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Action 4: Material AI */}
          <div
            onClick={() => navigate('/materials/analyse')}
            className="arch-glass arch-glass-hover p-6 rounded-2xl flex flex-col justify-between cursor-pointer group"
          >
            <div>
              <div className="w-12 h-12 rounded-xl bg-white/[0.06] border border-white/10 flex items-center justify-center text-[#ffbf7a] mb-4 group-hover:scale-105 transition-transform">
                <ImageIcon size={22} />
              </div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/50 block mb-1">
                Pillar 04 // Vision AI
              </span>
              <h2 className="font-display font-medium text-lg text-white group-hover:text-[#fff1e2] transition-colors">
                Photo to Materials
              </h2>
              <p className="text-xs text-white/70 mt-2 leading-relaxed">
                Take or upload a photo of any facade or room to inspect finishes, textures, and quantity estimates.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-[#C5A77B]">
              <span>Analyse Interior Materials</span>
              <ArrowRightIcon size={14} className="group-hover:translate-x-1 transition-transform" />
            </div>
          </div>
        </div>

        {/* Existing Projects Section */}
        <section className="w-full">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#C5A77B] block mb-1">
                Studio Archive // {projects.length} Repositories
              </span>
              <h2 className="font-display font-medium text-2xl text-white">
                Active Architectural Projects
              </h2>
            </div>
            <button
              onClick={() => fetchProjects()}
              disabled={isLoadingProjects}
              className="inline-flex items-center gap-2 text-xs font-mono text-white/70 hover:text-white arch-glass px-4 py-2 rounded-full transition-all cursor-pointer hover:border-white/20"
            >
              <RefreshIcon size={14} className={isLoadingProjects ? 'animate-spin' : ''} />
              <span>Refresh Studio</span>
            </button>
          </div>

          {isLoadingProjects && projects.length === 0 ? (
            <div className="p-12 text-center text-sm font-mono text-white/50 arch-glass rounded-2xl">
              Loading architectural models from repository...
            </div>
          ) : projects.length === 0 ? (
            <div className="p-12 text-center arch-glass rounded-3xl drafting-grid">
              <div className="w-12 h-12 rounded-full bg-white/[0.06] border border-white/15 flex items-center justify-center text-[#C5A77B] mx-auto mb-3">
                <BoxIcon size={24} />
              </div>
              <h3 className="font-display font-medium text-lg text-white">No architectural projects found</h3>
              <p className="text-xs text-white/60 mt-1 max-w-md mx-auto">
                Begin your first spatial model by uploading a 2D floor plan PDF or using the AI CAD generator.
              </p>
              <button
                onClick={() => navigate('/projects/new')}
                className="mt-5 px-5 py-2.5 rounded-full bg-white text-[#101418] font-semibold text-xs hover:bg-white/90 transition-all shadow-md cursor-pointer"
              >
                + Create First Project
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {projects.map((proj) => {
                const isActive = activeProject?.id === proj.id;
                return (
                  <div
                    key={proj.id}
                    onClick={() => handleOpenProject(proj)}
                    className={`group relative p-6 rounded-2xl arch-glass arch-glass-hover transition-all cursor-pointer flex flex-col justify-between ${
                      isActive ? 'border-[#C5A77B] shadow-[0_0_24px_rgba(197,167,123,0.15)]' : ''
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-white/[0.08] text-[#ffbf7a] border border-white/10">
                          {proj.type || 'Residential'}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteProject(e, proj.id)}
                          className="opacity-0 group-hover:opacity-100 text-white/40 hover:text-red-400 p-1 transition-all cursor-pointer"
                          title="Delete project"
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>

                      <h3 className="font-display font-medium text-lg text-white group-hover:text-[#fff1e2] line-clamp-1 transition-colors">
                        {proj.name}
                      </h3>
                      {proj.description && (
                        <p className="text-xs text-white/70 mt-2 line-clamp-2 leading-relaxed">
                          {proj.description}
                        </p>
                      )}
                    </div>

                    <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between text-[11px] font-mono text-white/60">
                      <span>{new Date(proj.createdAt).toLocaleDateString()}</span>
                      <span className="text-[#C5A77B] group-hover:translate-x-1 transition-transform inline-flex items-center gap-1.5 font-semibold">
                        Enter Workspace <ArrowRightIcon size={12} />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};
