import { apiRequest } from '../../lib/api';
import type { PlanJSON } from '../../types';

export interface RoomSpecification {
  id: string;
  name: string;
  dimensions: string;
  category: string;
  tag: string;
  x_ft: number;
  y_ft: number;
  w_ft: number;
  h_ft: number;
  area_sqft?: number;
}

export interface GeneratePlanPayload {
  project_id?: string;
  plot_width: number;
  plot_length: number;
  area_sqft?: number;
  goal: 'residence' | 'rental' | string;
  config_type: '1_bhk' | '2_bhk' | '3_bhk' | '4_bhk' | 'dual_rental_2bhk' | string;
  facing: 'East' | 'North' | 'West' | 'South' | string;
  client_name?: string;
  user_prompt?: string;
}

export interface GeneratedPlanResponse {
  plan_id: string;
  project_id: string;
  name: string;
  plot_width_ft: number;
  plot_length_ft: number;
  area_sqft: number;
  goal: string;
  config_type: string;
  facing: string;
  rooms: RoomSpecification[];
  ai_commentary: string;
  png_base64: string;
  png_download_url: string;
  plan_json: PlanJSON;
}

export interface ChatPlanPayload {
  message: string;
  project_id?: string;
  plan_id?: string;
  plot_width?: number;
  plot_length?: number;
  goal?: string;
  config_type?: string;
  facing?: string;
}

export interface ChatPlanResponse {
  reply: string;
  plan_id: string;
  project_id: string;
  plan: GeneratedPlanResponse;
}

export const aiPlanApi = {
  /**
   * Generates a calibrated 2D architectural working blueprint PNG & 3D PlanJSON
   * taking plot parameters, goal, configuration, and custom instructions from user.
   */
  generatePlan: async (payload: GeneratePlanPayload): Promise<GeneratedPlanResponse> => {
    return apiRequest<GeneratedPlanResponse>('/api/v1/ai/generate-plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Conversational CAD assistant to modify and refine the 2D floor plan interactively.
   */
  chatWithAssistant: async (payload: ChatPlanPayload): Promise<ChatPlanResponse> => {
    return apiRequest<ChatPlanResponse>('/api/v1/ai/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
