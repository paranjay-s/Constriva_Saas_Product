import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
import { ProtectedRoute } from '../components/ui/ProtectedRoute';
import { AppLayout } from '../components/layout/AppLayout';

import { AuthPage } from '../features/auth/AuthPage';
import { LandingPage } from '../features/landing/LandingPage';
import { HomePage } from '../features/home/HomePage';
import { CreateProjectPage } from '../features/projects/CreateProjectPage';
import { ProjectOptionsPage } from '../features/projects/ProjectOptionsPage';
import { Plan3dFurniturePage, Plan3dHomePage, Plan3dJobPage } from '../features/plan3d';
import { AiGeneratorPage } from '../features/chat/AiGeneratorPage';
import { LegacyAiGeneratorPage } from '../features/chat/LegacyAiGeneratorPage';
import { MaterialFinderPage } from '../features/materials';
import { BoqPage } from '../features/sheets';
import { LoanAnalysisPage } from '../features/loan/LoanAnalysisPage';

/** The route table; exported on its own so tests can run it in a memory router. */
export const routes: RouteObject[] = [
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
      // 2D to 3D: upload and list, the furniture models, and one plan's flow
      {
        path: '/3d',
        element: <Plan3dHomePage />,
      },
      {
        path: '/3d/furniture',
        element: <Plan3dFurniturePage />,
      },
      {
        path: '/3d/:jobId',
        element: <Plan3dJobPage />,
      },
      // the addresses of the pages that 2D to 3D replaced, kept alive for old links
      {
        path: '/projects/import',
        element: <Navigate to="/3d" replace />,
      },
      {
        path: '/projects/3d-workspace',
        element: <Navigate to="/3d" replace />,
      },
      {
        path: '/projects/ai-generator/legacy',
        element: <LegacyAiGeneratorPage />,
      },
      {
        path: '/boq',
        element: <BoqPage />,
      },
      {
        path: '/projects/loan-analysis',
        element: <LoanAnalysisPage />,
      },
    ],
  },

  // Chat studios (floor plans, image analysis): full screen with their own sidebar
  {
    path: '/projects/ai-generator',
    element: (
      <ProtectedRoute>
        <AiGeneratorPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/materials/analyse',
    element: (
      <ProtectedRoute>
        <MaterialFinderPage />
      </ProtectedRoute>
    ),
  },

  // Landing Page Route
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/landing',
    element: <LandingPage />,
  },
  {
    path: '*',
    element: <Navigate to="/home" replace />,
  },
];

export const router = createBrowserRouter(routes);
