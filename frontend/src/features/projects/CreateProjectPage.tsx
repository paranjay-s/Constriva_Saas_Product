/** Route /projects/new: step 01, the project details. Saved with POST /api/v1/projects. */
import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import type { ProjectType } from '../../types';
import { ArrowRight } from '../dashboard';
import { ProjectFlow } from './ProjectFlow';

const PROJECT_TYPES: { type: ProjectType; label: string; desc: string }[] = [
  { type: 'Residential', label: 'Residential', desc: 'Villas, apartments and homes' },
  { type: 'Commercial', label: 'Commercial', desc: 'Offices, retail, workspaces' },
  { type: 'Interior', label: 'Interior design', desc: 'Renovations and refits' },
  { type: 'Other', label: 'Other', desc: 'Institutional or mixed-use' },
];

export const CreateProjectPage: React.FC = () => {
  const [name, setName] = useState('');
  const [type, setType] = useState<ProjectType>('Residential');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const { createProject } = useProject();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // where to continue after creating (e.g. back to the floor plan generator); internal paths only
  const next = params.get('next');
  const after = next && next.startsWith('/') && !next.startsWith('//') ? next : '/projects/options';

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
      navigate(after);
    } catch (err) {
      const e2 = err as { detail?: string; message?: string };
      setError(e2?.detail || e2?.message || 'Failed to create project. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ProjectFlow
      step={1}
      title="Create project"
      locked
      left={
        <form className="cv-card cv-card-glow cv-form cv-push cv-rise" style={{ ['--d' as string]: '.2s' }} onSubmit={handleSubmit} noValidate>
          <label className="cv-label">
            Project name *
            <input
              className="cv-input"
              type="text"
              required
              autoFocus
              maxLength={120}
              placeholder="e.g. Pavilion Serena Residences"
              value={name}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? 'project-error' : undefined}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
            />
            {error && (
              <span id="project-error" role="alert" className="cv-field-error">
                {error}
              </span>
            )}
          </label>

          <fieldset style={{ margin: 0, padding: 0, border: 0 }}>
            <legend className="cv-label" style={{ padding: 0, marginBottom: 7 }}>
              Project type
            </legend>
            <div className="cv-types">
              {PROJECT_TYPES.map((pt) => (
                <button key={pt.type} type="button" className="cv-type" aria-pressed={type === pt.type} onClick={() => setType(pt.type)}>
                  <b>{pt.label}</b>
                  <span>{pt.desc}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <label className="cv-label">
            Project description (optional)
            <textarea
              className="cv-input"
              rows={2}
              placeholder="e.g. 3-bedroom single-family layout with open courtyard."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>

          <div className="cv-actions">
            <Link to="/home" className="cv-link">
              Back to home
            </Link>
            <button type="submit" className="cv-btn cv-btn-primary" disabled={isLoading}>
              {isLoading ? 'Creating project…' : 'Continue to options'}
              <ArrowRight />
            </button>
          </div>
        </form>
      }
    />
  );
};
