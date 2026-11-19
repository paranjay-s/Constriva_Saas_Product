/** Route /projects/options: step 02, choose where the floor plan comes from. */
import React from 'react';
import { Link } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { ArrowRight } from '../dashboard';
import { ProjectFlow } from './ProjectFlow';

export const ProjectOptionsPage: React.FC = () => {
  const { activeProject } = useProject();

  return (
    <ProjectFlow
      step={2}
      title="Choose a plan source"
      locked={!activeProject}
      left={
        <div className="cv-card cv-card-glow cv-form cv-push cv-rise" style={{ ['--d' as string]: '.2s' }}>
          {activeProject ? (
            <>
              <dl className="cv-summary" style={{ margin: 0 }}>
                <dt>Project</dt>
                <dd data-testid="options-project">{activeProject.name}</dd>
                <dt>Project type</dt>
                <dd>{activeProject.type}</dd>
                {activeProject.description && (
                  <>
                    <dt>Description</dt>
                    <dd style={{ fontSize: 14, color: 'var(--cv-text-2)' }}>{activeProject.description}</dd>
                  </>
                )}
              </dl>
              <p style={{ fontSize: 14, color: 'var(--cv-text-2)' }}>
                Already have a plan saved in this project? Open it in 3D.
              </p>
              <div className="cv-actions">
                <Link to="/projects/new" className="cv-link">
                  New project
                </Link>
                <Link to="/projects/3d-workspace" className="cv-btn">
                  Open 3D workspace
                  <ArrowRight />
                </Link>
              </div>
            </>
          ) : (
            <>
              <p style={{ fontSize: 15 }}>No project is selected.</p>
              <div className="cv-actions">
                <Link to="/home" className="cv-link">
                  Back to home
                </Link>
                <Link to="/projects/new" className="cv-btn cv-btn-primary">
                  Create a project
                  <ArrowRight />
                </Link>
              </div>
            </>
          )}
        </div>
      }
    />
  );
};
