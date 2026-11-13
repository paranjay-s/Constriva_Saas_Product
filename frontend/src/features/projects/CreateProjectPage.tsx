import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { ArrowLeftIcon, ArrowRightIcon } from '../../components/ui/Icons';
import { Input, Textarea } from '../../components/ui/Input';
import { useProject } from '../../context/ProjectContext';
import type { ProjectType } from '../../types';

const PROJECT_TYPES: { type: ProjectType; label: string; desc: string }[] = [
  { type: 'Residential', label: 'Residential', desc: 'Villas, apartments, and independent homes' },
  { type: 'Commercial', label: 'Commercial', desc: 'Offices, retail stores, and commercial workspaces' },
  { type: 'Interior', label: 'Interior Design', desc: 'Room renovations, material refits, and styling' },
  { type: 'Other', label: 'Other', desc: 'Institutional, hospitality, or mixed-use structures' },
];

export const CreateProjectPage: React.FC = () => {
  const [name, setName] = useState('');
  const [type, setType] = useState<ProjectType>('Residential');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { createProject } = useProject();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Project name is required');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await createProject(name.trim(), type, description.trim() || undefined);
      navigate('/projects/options');
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to create project. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 bg-[#101010] flex flex-col text-[#FFFFFF]">

      <main className="flex-1 max-w-3xl w-full mx-auto px-6 py-12">
        <button
          onClick={() => navigate('/home')}
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#A6A6A6] hover:text-[#FFFFFF] mb-8 cursor-pointer transition-colors"
        >
          <ArrowLeftIcon size={16} />
          Back to Home
        </button>

        <div className="mb-8">
          <span className="text-xs font-mono uppercase tracking-widest text-[#C5A77B]">
            Step 01 // Project Details
          </span>
          <h1 className="font-display font-semibold text-3xl tracking-tight text-[#FFFFFF] mt-1">
            Create Project
          </h1>
          <p className="text-sm text-[#A6A6A6] mt-2">
            Enter the essential details for your building design to begin.
          </p>
        </div>

        <Card className="bg-[#181818] border-[#303030] p-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            {/* Project Name */}
            <Input
              label="Project Name *"
              placeholder="e.g. Pavilion Serena Residences"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
              error={error || undefined}
              helperText="Give your project a recognizable title."
              autoFocus
            />

            {/* Project Type */}
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-wider font-semibold text-[#A6A6A6]">
                Project Type *
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {PROJECT_TYPES.map((pt) => {
                  const isSelected = type === pt.type;
                  return (
                    <button
                      key={pt.type}
                      type="button"
                      onClick={() => setType(pt.type)}
                      className={`text-left p-4 rounded border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-[#202020] border-[#C5A77B] ring-1 ring-[#C5A77B]'
                          : 'bg-[#141414] border-[#303030] hover:border-[#444444]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold text-[#FFFFFF]">{pt.label}</span>
                        <div
                          className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                            isSelected ? 'border-[#C5A77B] bg-[#C5A77B]' : 'border-[#444444]'
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-[#101010]" />}
                        </div>
                      </div>
                      <p className="text-xs text-[#A6A6A6]">{pt.desc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Description (Optional) */}
            <Textarea
              label="Project Description (Optional)"
              placeholder="e.g. 3-bedroom single-family residential layout with open courtyard."
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              helperText="Optional notes or client requirements."
            />

            {/* Action Buttons */}
            <div className="pt-4 border-t border-[#303030] flex items-center justify-between">
              <Button
                type="button"
                variant="ghost"
                onClick={() => navigate('/home')}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="lg"
                isLoading={isLoading}
                rightIcon={<ArrowRightIcon size={16} />}
              >
                Continue to Options
              </Button>
            </div>
          </form>
        </Card>
      </main>
    </div>
  );
};
