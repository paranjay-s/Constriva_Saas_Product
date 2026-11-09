import React, { createContext, useContext, useEffect, useState } from 'react';
import { DEFAULT_ARCHITECTURAL_PLAN, INITIAL_MATERIAL_ITEMS } from '../lib/defaultPlan';
import type { LoanComparison, MaterialQuantityItem, PlanJSON, Project, ProjectType } from '../types';

interface ProjectContextType {
  activeProject: Project | null;
  planData: PlanJSON;
  materials: MaterialQuantityItem[];
  selectedMaterialTag: string | null;
  activeRoomId: string | null;
  loanComparison: LoanComparison;
  createProject: (name: string, type: ProjectType, description?: string) => Project;
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
      if (stored) return JSON.parse(stored);
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
    availableLoan: 1500000, // ₹15,00,000 as in AGENTS.md example
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

  // Persist plan data changes
  const setPlanData = (plan: PlanJSON) => {
    setPlanDataState(plan);
    localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(plan));
  };

  const createProject = (name: string, type: ProjectType, description?: string): Project => {
    const newProject: Project = {
      id: 'proj_' + Math.random().toString(36).substring(2, 9),
      name,
      type,
      description,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      status: 'draft',
    };
    setActiveProject(newProject);
    localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(newProject));
    return newProject;
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
        activeProject,
        planData,
        materials,
        selectedMaterialTag,
        activeRoomId,
        loanComparison,
        createProject,
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
