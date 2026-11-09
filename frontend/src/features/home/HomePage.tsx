import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { ArrowRightIcon, BoxIcon, ImageIcon } from '../../components/ui/Icons';
import { Navbar } from '../../components/ui/Navbar';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#101010] flex flex-col text-[#FFFFFF]">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-16 lg:py-24 flex flex-col justify-center">
        {/* Header section */}
        <div className="mb-12 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#181818] border border-[#303030] text-[#C5A77B] text-[11px] uppercase tracking-widest font-mono mb-4">
            <span>Spatial Engine & Material Intelligence</span>
          </div>
          <h1 className="font-display font-semibold text-3xl sm:text-4xl lg:text-5xl tracking-tight text-[#FFFFFF] leading-tight">
            What would you like to build today?
          </h1>
          <p className="text-sm sm:text-base text-[#A6A6A6] mt-4 font-normal leading-relaxed">
            Select one of the two core actions below to begin your architectural workflow.
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
      </main>
    </div>
  );
};

