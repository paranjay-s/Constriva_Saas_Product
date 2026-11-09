import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { ArrowLeftIcon, ArrowRightIcon, FilePdfIcon, SparklesIcon } from '../../components/ui/Icons';
import { Navbar } from '../../components/ui/Navbar';
import { useProject } from '../../context/ProjectContext';

export const ProjectOptionsPage: React.FC = () => {
  const { activeProject } = useProject();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#101010] flex flex-col text-[#FFFFFF]">
      <Navbar />

      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-12 flex flex-col justify-center">
        <button
          onClick={() => navigate('/projects/new')}
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#A6A6A6] hover:text-[#FFFFFF] mb-8 cursor-pointer transition-colors"
        >
          <ArrowLeftIcon size={16} />
          Back to Project Details
        </button>

        <div className="mb-10 text-center max-w-2xl mx-auto">
          <span className="text-xs font-mono uppercase tracking-widest text-[#C5A77B]">
            Step 02 // Floor Plan Source
          </span>
          <h1 className="font-display font-semibold text-3xl sm:text-4xl tracking-tight text-[#FFFFFF] mt-2">
            How would you like to build your plan?
          </h1>
          <p className="text-sm text-[#A6A6A6] mt-3">
            For project <span className="text-[#FFFFFF] font-semibold">{activeProject?.name || 'New Project'}</span>, choose how you want to produce the architectural floor plan.
          </p>
        </div>

        {/* The Two Clear Options */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Option 1: Import Existing 2D Plan */}
          <Card
            interactive
            onClick={() => navigate('/projects/import')}
            className="group bg-[#181818] border-[#303030] hover:border-[#C5A77B] p-8 flex flex-col justify-between transition-all"
          >
            <div>
              <div className="w-14 h-14 rounded-lg bg-[#202020] border border-[#303030] group-hover:border-[#C5A77B] flex items-center justify-center text-[#C5A77B] mb-6 transition-colors">
                <FilePdfIcon size={28} />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#737373] block mb-2">
                Option 01 // File Upload
              </span>
              <h2 className="font-display font-semibold text-2xl text-[#FFFFFF] group-hover:text-[#F5F2EB] transition-colors">
                Import Existing 2D Plan
              </h2>
              <p className="text-sm text-[#A6A6A6] mt-3 leading-relaxed">
                Upload an architectural PDF drawing. The system will extract wall geometry, detect openings, and generate your interactive 3D model automatically.
              </p>
            </div>

            <div className="mt-8 pt-6 border-t border-[#252525]">
              <Button
                variant="primary"
                size="md"
                className="w-full"
                rightIcon={<ArrowRightIcon size={16} />}
              >
                Import PDF Drawing
              </Button>
            </div>
          </Card>

          {/* Option 2: Create Your Own 2D Plan */}
          <Card
            interactive
            onClick={() => navigate('/projects/ai-generator')}
            className="group bg-[#181818] border-[#303030] hover:border-[#C5A77B] p-8 flex flex-col justify-between transition-all"
          >
            <div>
              <div className="w-14 h-14 rounded-lg bg-[#202020] border border-[#303030] group-hover:border-[#C5A77B] flex items-center justify-center text-[#C5A77B] mb-6 transition-colors">
                <SparklesIcon size={28} />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-[#737373] block mb-2">
                Option 02 // AI Synthesis
              </span>
              <h2 className="font-display font-semibold text-2xl text-[#FFFFFF] group-hover:text-[#F5F2EB] transition-colors">
                Create Your Own 2D Plan
              </h2>
              <p className="text-sm text-[#A6A6A6] mt-3 leading-relaxed">
                Describe the rooms and layout in ordinary language. The AI conversational assistant will draft the 2D architectural blueprint and let you refine it interactively.
              </p>
            </div>

            <div className="mt-8 pt-6 border-t border-[#252525]">
              <Button
                variant="accent"
                size="md"
                className="w-full"
                rightIcon={<ArrowRightIcon size={16} />}
              >
                Launch AI Plan Generator
              </Button>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
};

