import React, { createContext, useContext, useEffect, useState } from 'react';
import { DEFAULT_ARCHITECTURAL_PLAN, INITIAL_MATERIAL_ITEMS } from '../lib/defaultPlan';
import type { LoanComparison, MaterialQuantityItem, PlanJSON, Project, ProjectType } from '../types';
import { projectsApi } from '../features/projects/api';

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  isLoadingProjects: boolean;
  planData: PlanJSON;
  materials: MaterialQuantityItem[];
  selectedMaterialTag: string | null;
  activeRoomId: string | null;
  loanComparison: LoanComparison;
  fetchProjects: () => Promise<void>;
  createProject: (name: string, type: ProjectType, description?: string) => Promise<Project>;
  selectProject: (project: Project) => void;
  deleteProject: (projectId: string) => Promise<void>;
  setPlanData: (plan: PlanJSON) => void;
  setMaterials: React.Dispatch<React.SetStateAction<MaterialQuantityItem[]>>;
  setSelectedMaterialTag: (tag: string | null) => void;
  setActiveRoomId: (roomId: string | null) => void;
  updateLoanAmount: (amount: number) => void;
  setProjectStatus: (status: Project['status']) => void;
}

const PROJECT_STORAGE_KEY = 'construtiva_active_project';
const PLAN_STORAGE_KEY = 'construtiva_plan_data';

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState<boolean>(false);

  const [activeProject, setActiveProject] = useState<Project | null>(() => {
    try {
      const stored = localStorage.getItem(PROJECT_STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {
      // fallback
    }
    return {
      id: 'proj_default_pavilion',
      name: 'Pavilion Serena Residences',
      type: 'Residential',
      description: 'Single-story modern residential villa with oak finishes and sunlit courtyards.',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'ready',
    };
  });

  const [planData, setPlanDataState] = useState<PlanJSON>(() => {
    try {
      const stored = localStorage.getItem(PLAN_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && Array.isArray(parsed.levels) && parsed.levels.length > 0) {
          return parsed;
        }
      }
    } catch {
      // fallback
    }
    return DEFAULT_ARCHITECTURAL_PLAN;
  });

  const [materials, setMaterials] = useState<MaterialQuantityItem[]>(INITIAL_MATERIAL_ITEMS);
  const [selectedMaterialTag, setSelectedMaterialTag] = useState<string | null>(null);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);

  // Calculate total material cost from materials list
  const totalCost = materials.reduce((acc, item) => acc + item.estimatedAmount, 0);

  const [loanComparison, setLoanComparison] = useState<LoanComparison>({
    availableLoan: 1500000,
    estimatedMaterialCost: totalCost,
    remainingAmount: Math.max(0, 1500000 - totalCost),
    shortfall: Math.max(0, totalCost - 1500000),
    isSufficient: 1500000 >= totalCost,
  });

  // Keep loan calculation synchronized when total cost changes
  useEffect(() => {
    const cost = materials.reduce((acc, item) => acc + item.estimatedAmount, 0);
    setLoanComparison((prev) => ({
      ...prev,
      estimatedMaterialCost: cost,
      remainingAmount: Math.max(0, prev.availableLoan - cost),
      shortfall: Math.max(0, cost - prev.availableLoan),
      isSufficient: prev.availableLoan >= cost,
    }));
  }, [materials]);

  // Persist project changes
  useEffect(() => {
    if (activeProject) {
      localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(activeProject));
    }
  }, [activeProject]);

  // Fetch projects on initial mount if authenticated
  const fetchProjects = async () => {
    const token = localStorage.getItem('construtiva_auth_token');
    if (!token) {
      return;
    }
    setIsLoadingProjects(true);
    try {
      const list = await projectsApi.list();
      setProjects(list);
    } catch (err) {
      console.warn('Failed to fetch projects list from backend:', err);
    } finally {
      setIsLoadingProjects(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // Persist plan data changes
  const setPlanData = (plan: PlanJSON) => {
    setPlanDataState(plan);
    localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(plan));
  };

  const createProject = async (name: string, type: ProjectType, description?: string): Promise<Project> => {
    try {
      const apiProj = await projectsApi.create(name, type, description);
      setActiveProject(apiProj);
      setProjects((prev) => [apiProj, ...prev.filter((p) => p.id !== apiProj.id)]);
      localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(apiProj));
      return apiProj;
    } catch (err) {
      console.warn('Backend createProject call failed, falling back to local session project:', err);
      const fallbackProject: Project = {
        id: 'proj_' + Math.random().toString(36).substring(2, 9),
        name,
        type,
        description,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        status: 'draft',
      };
      setActiveProject(fallbackProject);
      setProjects((prev) => [fallbackProject, ...prev]);
      localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(fallbackProject));
      return fallbackProject;
    }
  };

  const selectProject = (project: Project) => {
    setActiveProject(project);
    localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(project));
  };

  const deleteProject = async (projectId: string) => {
    try {
      await projectsApi.delete(projectId);
    } catch (err) {
      console.warn('Failed to delete project on backend:', err);
    }
    setProjects((prev) => prev.filter((p) => p.id !== projectId));
    if (activeProject?.id === projectId) {
      setActiveProject(null);
      localStorage.removeItem(PROJECT_STORAGE_KEY);
    }
  };

  const updateLoanAmount = (amount: number) => {
    const cost = loanComparison.estimatedMaterialCost;
    setLoanComparison({
      availableLoan: amount,
      estimatedMaterialCost: cost,
      remainingAmount: Math.max(0, amount - cost),
      shortfall: Math.max(0, cost - amount),
      isSufficient: amount >= cost,
    });
  };

  const setProjectStatus = (status: Project['status']) => {
    if (activeProject) {
      setActiveProject({ ...activeProject, status, updatedAt: new Date().toISOString() });
    }
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        isLoadingProjects,
        planData,
        materials,
        selectedMaterialTag,
        activeRoomId,
        loanComparison,
        fetchProjects,
        createProject,
        selectProject,
        deleteProject,
        setPlanData,
        setMaterials,
        setSelectedMaterialTag,
        setActiveRoomId,
        updateLoanAmount,
        setProjectStatus,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};
