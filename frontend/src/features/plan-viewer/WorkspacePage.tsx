import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { PlanViewer } from './PlanViewer';
import { Button } from '../../components/ui/Button';
import { filesApi } from '../files';
import { IconArrowLeft, IconArrowRight } from '../../components/ui/Icons';

export function WorkspacePage() {
  const navigate = useNavigate();
  const { activeProject, setPlanData } = useProject();

  // Fetch the plan from the FastAPI backend on project mount/change
  useEffect(() => {
    if (!activeProject?.id) return;
    let isCurrent = true;

    // Load active architectural plan from backend for this project
    filesApi
      .getProjectPlan(activeProject.id)
      .then((res) => {
        if (!isCurrent) return;
        if (res && res.plan_json) {
          setPlanData(res.plan_json);
        }
      })
      .catch((planErr) => {
        console.warn('Backend plan sync note:', planErr);
      });

    return () => {
      isCurrent = false;
    };
  }, [activeProject?.id]);

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col h-screen overflow-hidden">
      {/* 3D Workspace Contextual Toolbar */}
      <div
        role="toolbar"
        aria-label="3D Workspace Controls"
        className="border-b border-white/10 bg-[#0d0f12]/85 backdrop-blur-md px-3 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-3 flex-shrink-0 z-20"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects/options')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            Options
          </Button>

          <div className="h-4 w-px bg-border hidden sm:block" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-sm sm:text-base tracking-tight truncate max-w-[200px] sm:max-w-md">
                {activeProject?.name || 'Pavilion Serena Residences'}
              </h1>
              <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/30">
                {activeProject?.type || 'Residential'}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="hidden sm:inline">3D Active</span>
              </span>
            </div>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/projects/loan-analysis')}
            rightIcon={<IconArrowRight className="w-4 h-4" />}
          >
            <span className="hidden sm:inline">Compare</span> Loan
          </Button>
        </div>
      </div>

      {/* 3D viewport: takes the full width on every breakpoint */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <section className="flex-1 w-full p-2 sm:p-4 flex flex-col min-h-0">
          <div className="flex-1 w-full h-full rounded-xl overflow-hidden border border-border bg-panel shadow-sm">
            <PlanViewer />
          </div>
        </section>
      </main>
    </div>
  );
}

export default WorkspacePage;
