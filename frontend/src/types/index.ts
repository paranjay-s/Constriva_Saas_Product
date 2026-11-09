export * from './plan';

export interface User {
  id: string;
  email: string;
  name?: string;
}

export type ProjectType = 'Residential' | 'Commercial' | 'Interior' | 'Other';

export interface Project {
  id: string;
  name: string;
  type: ProjectType;
  description?: string;
  createdAt: string;
  updatedAt: string;
  status: 'draft' | 'imported' | 'generated' | 'ready';
}

export interface MaterialQuantityItem {
  id: string;
  materialName: string;
  totalArea: string;
  quantity: string;
  category: string;
  rate: number;
  unit: string;
  estimatedAmount: number;
  surfaceTag: 'marble' | 'paint' | 'wood' | 'tiles' | 'concrete';
}

export interface CostSummary {
  subtotal: number;
  wasteContingency: number;
  totalEstimatedCost: number;
  currency: string;
}

export interface LoanComparison {
  availableLoan: number;
  estimatedMaterialCost: number;
  remainingAmount: number;
  shortfall: number;
  isSufficient: boolean;
  notes?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  updatedPlanSummary?: string;
}

export interface PhotoMaterialResult {
  id: string;
  material: string;
  category: string;
  estimatedArea: string;
  indicativeRate: string;
  description: string;
  confidence: 'High' | 'Moderate' | 'Indicative';
}

