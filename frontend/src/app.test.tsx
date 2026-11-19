import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import { AuthPage } from './features/auth/AuthPage';
import { HomePage } from './features/home/HomePage';
import { CreateProjectPage } from './features/projects/CreateProjectPage';
import { ProjectOptionsPage } from './features/projects/ProjectOptionsPage';
import { ImportPlanPage } from './features/files/ImportPlanPage';
import { WorkspacePage } from './features/plan-viewer/WorkspacePage';
import { AiGeneratorPage } from './features/chat/AiGeneratorPage';
import { LegacyAiGeneratorPage } from './features/chat/LegacyAiGeneratorPage';
import { MaterialFinderPage } from './features/materials';
import { LoanAnalysisPage } from './features/loan/LoanAnalysisPage';

// Mock PlanViewer 3D Canvas in jsdom test environment
vi.mock('./features/plan-viewer/PlanViewer', () => ({
  PlanViewer: () => <div data-testid="mock-3d-plan-viewer">3D Architectural Plan Viewer</div>,
}));

// Helper to render within required providers
function renderWithProviders(ui: React.ReactElement, initialRoute = '/') {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <ProjectProvider>{ui}</ProjectProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('Constriva Frontend - 9 Core Required Pages', () => {
  it('renders Route 1: /auth (Authentication Page)', () => {
    renderWithProviders(<AuthPage />);
    expect(screen.getByText(/architectural intelligence platform/i)).toBeDefined();
    expect(screen.getByText(/sign in to workspace/i)).toBeDefined();
    expect(screen.getByText(/instant architect demo access/i)).toBeDefined();
  });

  it('renders Route 2: /home (Project overview)', () => {
    renderWithProviders(<HomePage />);
    expect(screen.getByRole('heading', { name: 'Project overview' })).toBeDefined();
    expect(screen.getByRole('link', { name: /create new project/i })).toBeDefined();
    expect(screen.getByRole('link', { name: 'Floor plan chat' })).toBeDefined();
    expect(screen.getByRole('link', { name: 'Image analysis' })).toBeDefined();
  });

  it('renders Route 3: /projects/new (Project Setup Information)', () => {
    renderWithProviders(<CreateProjectPage />);
    expect(screen.getByText(/create project/i)).toBeDefined();
    expect(screen.getByText(/project name \*/i)).toBeDefined();
    expect(screen.getByText(/residential/i)).toBeDefined();
  });

  it('renders Route 4: /projects/options (Strictly 2 Workflow Choices)', () => {
    renderWithProviders(<ProjectOptionsPage />);
    expect(screen.getByRole('heading', { name: 'Choose a plan source' })).toBeDefined();
    expect(screen.getByText(/import existing 2d plan/i)).toBeDefined();
    expect(screen.getByText(/create your own 2d plan/i)).toBeDefined();
  });

  it('renders Route 5: /projects/import (2D Blueprint Upload & SSE Pipeline)', () => {
    renderWithProviders(<ImportPlanPage />);
    expect(screen.getByText(/import architectural floor plan/i)).toBeDefined();
    expect(screen.getByText(/drag and drop your architectural pdf here/i)).toBeDefined();
    expect(screen.getByText(/process architectural plan/i)).toBeDefined();
  });

  it('renders Route 6: /projects/3d-workspace (3D Model & BOQ Material Estimate)', () => {
    renderWithProviders(<WorkspacePage />);
    expect(screen.getByText(/bill of materials/i)).toBeDefined();
    expect(screen.getByText(/engineering quantity survey/i)).toBeDefined();
    expect(screen.getByTestId('mock-3d-plan-viewer')).toBeDefined();
  });

  it('renders Route 7: /projects/ai-generator (AI Floor Plan Generator)', () => {
    renderWithProviders(<AiGeneratorPage />);
    // chat studio: sidebar with history, composer in the middle, project picker
    expect(screen.getByRole('complementary', { name: 'Sidebar' })).toBeDefined();
    expect(screen.getByRole('textbox', { name: /describe the house/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /choose project/i })).toBeDefined();
  });

  it('keeps the old generator at /projects/ai-generator/legacy until it is retired', () => {
    renderWithProviders(<LegacyAiGeneratorPage />);
    expect(screen.getByText(/conversational cad/i)).toBeDefined();
  });

  it('renders Route 8: /materials/analyse (Material Finder)', () => {
    renderWithProviders(<MaterialFinderPage />);
    expect(screen.getByText(/material finder · the ai names the finishes/i)).toBeDefined();
    expect(screen.getByRole('textbox', { name: /ask about the photo/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /add photos/i })).toBeDefined();
    expect(screen.queryByText('What should I look at?')).toBeNull();
  });

  it('renders Route 9: /projects/loan-analysis (Bank Sanction vs Material BOQ)', () => {
    renderWithProviders(<LoanAnalysisPage />);
    expect(screen.getByText(/construction loan feasibility analysis/i)).toBeDefined();
    expect(screen.getByText(/sanctioned loan facility/i)).toBeDefined();
    expect(screen.getByText(/estimated material boq cost/i)).toBeDefined();
  });
});
