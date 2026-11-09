import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '../components/ui/ProtectedRoute';
import { AppLayout } from '../components/layout/AppLayout';

import { AuthPage } from '../features/auth/AuthPage';
import { HomePage } from '../features/home/HomePage';
import { CreateProjectPage } from '../features/projects/CreateProjectPage';
import { ProjectOptionsPage } from '../features/projects/ProjectOptionsPage';
import { ImportPlanPage } from '../features/files/ImportPlanPage';
import { WorkspacePage } from '../features/plan-viewer/WorkspacePage';
import { AiGeneratorPage } from '../features/chat/AiGeneratorPage';
import { AnalyseMaterialsPage } from '../features/materials/AnalyseMaterialsPage';
import { LoanAnalysisPage } from '../features/loan/LoanAnalysisPage';

export const router = createBrowserRouter([
  // Public Route
  {
    path: '/auth',
    element: <AuthPage />,
  },

  // Protected Routes within Common Atelier App Layout
  {
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        path: '/home',
        element: <HomePage />,
      },
      {
        path: '/projects/new',
        element: <CreateProjectPage />,
      },
      {
        path: '/projects/options',
        element: <ProjectOptionsPage />,
      },
      {
        path: '/projects/import',
        element: <ImportPlanPage />,
      },
      {
        path: '/projects/3d-workspace',
        element: <WorkspacePage />,
      },
      {
        path: '/projects/ai-generator',
        element: <AiGeneratorPage />,
      },
      {
        path: '/materials/analyse',
        element: <AnalyseMaterialsPage />,
      },
      {
        path: '/projects/loan-analysis',
        element: <LoanAnalysisPage />,
      },
    ],
  },

  // Fallbacks
  {
    path: '/',
    element: <Navigate to="/home" replace />,
  },
  {
    path: '*',
    element: <Navigate to="/home" replace />,
  },
]);
