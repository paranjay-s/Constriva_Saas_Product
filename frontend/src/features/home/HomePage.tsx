import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import {
  ArrowRightIcon,
  BoxIcon,
  ImageIcon,
  RefreshIcon,
  TrashIcon,
} from '../../components/ui/Icons';
import { Navbar } from '../../components/ui/Navbar';
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

  const handleOpenProject = (project: (typeof projects)[0]) => {
    selectProject(project);
    navigate('/projects/options');
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this project?')) {
      await deleteProject(projectId);
    }
  };

  return (
    <div className="min-h-screen bg-[#101010] flex flex-col text-[#FFFFFF]">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-12 lg:py-16 flex flex-col justify-center">
        {/* Header section */}
        <div className="mb-12 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#181818] border border-[#303030] text-[#C5A77B] text-[11px] uppercase tracking-widest font-mono mb-4">
            <span>Spatial Engine & Material Intelligence</span>
          </div>
          <h1 className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-tight text-[#FFFFFF] leading-tight">
            What would you like to build today?
          </h1>
          <p className="text-sm sm:text-base text-[#A6A6A6] mt-4 font-normal leading-relaxed">
            Select one of the two core actions below or resume work on an existing project.
          </p>
        </div>

        {/* Exactly Two Primary Choices */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto w-full">
          {/* Action 1: Create New Project */}
          <Card
            interactive
            onClick={() => navigate('/projects/new')}
            className="group relative bg-[#181818] border-[#303030] hover:border-[#C5A77B] p-8 lg:p-10 flex flex-col justify-between transition-all duration-200"
          >
            <div>
              <div className="w-14 h-14 rounded-lg bg-[#202020] border border-[#303030] group-hover:border-[#C5A77B] flex items-center justify-center text-[#C5A77B] mb-6 transition-colors">
                <BoxIcon size={28} />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#737373] block mb-2">
                Action 01 // Architectural Project
              </span>
              <h2 className="font-display font-semibold text-2xl text-[#FFFFFF] group-hover:text-[#F5F2EB] transition-colors">
                Create New Project
              </h2>
              <p className="text-sm text-[#A6A6A6] mt-3 leading-relaxed">
                Start a new architectural project. Upload an existing 2D floor-plan PDF or generate one from scratch using the conversational AI.
              </p>
            </div>

            <div className="mt-8 pt-6 border-t border-[#252525] flex items-center justify-between text-xs font-semibold text-[#F5F2EB]">
              <span className="group-hover:translate-x-1 transition-transform inline-flex items-center gap-2">
                Start Project Flow
                <ArrowRightIcon size={16} className="text-[#C5A77B]" />
              </span>
              <span className="text-[10px] font-mono text-[#737373] uppercase tracking-wider">
                PDF or AI
              </span>
            </div>
          </Card>

          {/* Action 2: Analyse Interior Materials */}
          <Card
            interactive
            onClick={() => navigate('/materials/analyse')}
            className="group relative bg-[#181818] border-[#303030] hover:border-[#C5A77B] p-8 lg:p-10 flex flex-col justify-between transition-all duration-200"
          >
            <div>
              <div className="w-14 h-14 rounded-lg bg-[#202020] border border-[#303030] group-hover:border-[#C5A77B] flex items-center justify-center text-[#C5A77B] mb-6 transition-colors">
                <ImageIcon size={28} />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#737373] block mb-2">
                Action 02 // Computer Vision
              </span>
              <h2 className="font-display font-semibold text-2xl text-[#FFFFFF] group-hover:text-[#F5F2EB] transition-colors">
                Analyse Interior Materials
              </h2>
              <p className="text-sm text-[#A6A6A6] mt-3 leading-relaxed">
                Take or upload a photo of any room or building facade to identify finishes, estimated surface areas, and indicative procurement costs.
              </p>
            </div>

            <div className="mt-8 pt-6 border-t border-[#252525] flex items-center justify-between text-xs font-semibold text-[#F5F2EB]">
              <span className="group-hover:translate-x-1 transition-transform inline-flex items-center gap-2">
                Inspect Photo
                <ArrowRightIcon size={16} className="text-[#C5A77B]" />
              </span>
              <span className="text-[10px] font-mono text-[#737373] uppercase tracking-wider">
                Photo Recognition
              </span>
            </div>
          </Card>
        </div>

        {/* Existing Projects Section */}
        <section className="mt-16 max-w-4xl mx-auto w-full">
          <div className="flex items-center justify-between mb-6 pb-3 border-b border-[#252525]">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#C5A77B] block mb-1">
                Workspace Repository
              </span>
              <h2 className="font-display font-semibold text-2xl text-[#FFFFFF]">
                Your Architectural Projects
              </h2>
            </div>
            <button
              onClick={() => fetchProjects()}
              disabled={isLoadingProjects}
              className="inline-flex items-center gap-1.5 text-xs text-[#A6A6A6] hover:text-[#FFFFFF] bg-[#181818] border border-[#303030] px-3 py-1.5 rounded transition-colors cursor-pointer"
            >
              <RefreshIcon size={14} className={isLoadingProjects ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {isLoadingProjects && projects.length === 0 ? (
            <div className="p-8 text-center text-sm text-[#737373] bg-[#141414] border border-[#252525] rounded-lg">
              Loading projects from database...
            </div>
          ) : projects.length === 0 ? (
            <div className="p-8 text-center bg-[#141414] border border-[#252525] rounded-lg">
              <p className="text-sm text-[#A6A6A6]">No saved projects found.</p>
              <p className="text-xs text-[#737373] mt-1">
                Start by setting up your first building project using the option above.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((proj) => {
                const isActive = activeProject?.id === proj.id;
                return (
                  <div
                    key={proj.id}
                    onClick={() => handleOpenProject(proj)}
                    className={`group relative p-5 rounded-lg border transition-all cursor-pointer flex flex-col justify-between ${
                      isActive
                        ? 'bg-[#1a1815] border-[#C5A77B] ring-1 ring-[#C5A77B]/50'
                        : 'bg-[#181818] border-[#303030] hover:border-[#444444]'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-[#252525] text-[#C5A77B]">
                          {proj.type || 'Residential'}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => handleDeleteProject(e, proj.id)}
                          className="opacity-0 group-hover:opacity-100 text-[#737373] hover:text-[#EF4444] p-1 transition-opacity cursor-pointer"
                          title="Delete project"
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                      <h3 className="font-semibold text-base text-[#FFFFFF] group-hover:text-[#F5F2EB] line-clamp-1">
                        {proj.name}
                      </h3>
                      {proj.description && (
                        <p className="text-xs text-[#A6A6A6] mt-1.5 line-clamp-2">
                          {proj.description}
                        </p>
                      )}
                    </div>

                    <div className="mt-4 pt-3 border-t border-[#252525] flex items-center justify-between text-[11px] text-[#737373]">
                      <span>{new Date(proj.createdAt).toLocaleDateString()}</span>
                      <span className="text-[#C5A77B] group-hover:translate-x-0.5 transition-transform inline-flex items-center gap-1">
                        Open <ArrowRightIcon size={12} />
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
