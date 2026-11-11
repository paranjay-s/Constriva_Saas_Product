import { apiRequest } from '../../lib/api';
import type { Project, ProjectType } from '../../types';

export interface BackendProject {
  id: string;
  user_id?: string;
  name: string;
  description?: string | null;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
  active_plan?: any;
}

export function mapBackendProject(p: BackendProject): Project {
  let projectType: ProjectType = 'Residential';
  let cleanDesc = p.description || '';

  if (cleanDesc.startsWith('[Commercial]')) {
    projectType = 'Commercial';
    cleanDesc = cleanDesc.replace('[Commercial]', '').trim();
  } else if (cleanDesc.startsWith('[Interior]')) {
    projectType = 'Interior';
    cleanDesc = cleanDesc.replace('[Interior]', '').trim();
  } else if (cleanDesc.startsWith('[Other]')) {
    projectType = 'Other';
    cleanDesc = cleanDesc.replace('[Other]', '').trim();
  } else if (cleanDesc.startsWith('[Residential]')) {
    projectType = 'Residential';
    cleanDesc = cleanDesc.replace('[Residential]', '').trim();
  }

  return {
    id: p.id,
    name: p.name,
    type: projectType,
    description: cleanDesc || undefined,
    createdAt: p.created_at || new Date().toISOString(),
    updatedAt: p.updated_at || new Date().toISOString(),
    status: (p.status === 'active' ? 'ready' : p.status || 'draft') as any,
  };
}

export const projectsApi = {
  create: async (name: string, type: ProjectType = 'Residential', description?: string): Promise<Project> => {
    const encodedDescription = `[${type}] ${description || ''}`.trim();
    const payload = {
      name,
      description: encodedDescription,
      status: 'active',
    };
    const res = await apiRequest<BackendProject>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return mapBackendProject(res);
  },

  list: async (): Promise<Project[]> => {
    const res = await apiRequest<BackendProject[]>('/api/v1/projects', {
      method: 'GET',
    });
    return (res || []).map(mapBackendProject);
  },

  get: async (projectId: string): Promise<Project> => {
    const res = await apiRequest<BackendProject>(`/api/v1/projects/${projectId}`, {
      method: 'GET',
    });
    return mapBackendProject(res);
  },

  delete: async (projectId: string): Promise<{ deleted: boolean; project_id: string }> => {
    return apiRequest<{ deleted: boolean; project_id: string }>(`/api/v1/projects/${projectId}`, {
      method: 'DELETE',
    });
  },
};
