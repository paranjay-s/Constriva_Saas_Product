import { describe, it, expect, vi, beforeEach } from 'vitest';
import { aiPlanApi, type GeneratePlanPayload } from './api';

describe('AI 2D Floor Plan API Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('generatePlan sends parameters and returns synthesized CAD blueprint and PlanJSON', async () => {
    const mockResponse = {
      plan_id: 'plan_123',
      project_id: 'proj_456',
      name: "36'6\" X 55' 3-BHK Residence",
      plot_width_ft: 36.5,
      plot_length_ft: 55.0,
      area_sqft: 2007.5,
      goal: 'residence',
      config_type: '3_bhk',
      facing: 'East',
      rooms: [
        {
          id: 'room_1',
          name: 'MASTER BEDROOM',
          dimensions: "14' X 12'",
          category: 'Bedroom',
          tag: 'bedroom',
          x_ft: 0,
          y_ft: 0,
          w_ft: 14,
          h_ft: 12,
        },
      ],
      ai_commentary: 'Calibrated 3-BHK residence layout with master suite in Southwest.',
      png_base64: 'iVBORw0KGgoAAAANSUhEUgAA...',
      png_download_url: '/api/v1/plans/plan_123/download-png',
      plan_json: { version: 1, units: 'm', levels: [] },
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const payload: GeneratePlanPayload = {
      plot_width: 36.5,
      plot_length: 55.0,
      goal: 'residence',
      config_type: '3_bhk',
      facing: 'East',
      client_name: 'SMT. GEETA GAUD',
      user_prompt: 'Front parking for 2 cars, puja room in northeast',
    };

    const result = await aiPlanApi.generatePlan(payload);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain('/api/v1/ai/generate-plan');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(payload);

    expect(result.plan_id).toBe('plan_123');
    expect(result.rooms.length).toBe(1);
    expect(result.png_base64).toBe('iVBORw0KGgoAAAANSUhEUgAA...');
  });

  it('chatWithAssistant sends modification message and returns updated plan and assistant commentary', async () => {
    const mockChatResponse = {
      reply: 'Enlarged master bedroom to 16ft and added second attached toilet.',
      plan_id: 'plan_123',
      project_id: 'proj_456',
      plan: {
        plan_id: 'plan_123',
        project_id: 'proj_456',
        name: "36'6\" X 55' Revised 3-BHK Residence",
        plot_width_ft: 36.5,
        plot_length_ft: 55.0,
        area_sqft: 2007.5,
        goal: 'residence',
        config_type: '3_bhk',
        facing: 'East',
        rooms: [],
        ai_commentary: 'Revised drawing with enlarged master bedroom.',
        png_base64: 'iVBORw0KGgoAAAANSUhEUgAA...',
        png_download_url: '/api/v1/plans/plan_123/download-png',
        plan_json: { version: 1, units: 'm', levels: [] },
      },
    };

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockChatResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await aiPlanApi.chatWithAssistant({
      message: 'Enlarge master bedroom to 16ft',
      plan_id: 'plan_123',
      plot_width: 36.5,
      plot_length: 55.0,
      goal: 'residence',
      config_type: '3_bhk',
      facing: 'East',
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toContain('/api/v1/ai/chat');
    expect(init?.method).toBe('POST');

    expect(result.reply).toContain('Enlarged master bedroom');
    expect(result.plan.name).toContain('Revised');
  });
});

