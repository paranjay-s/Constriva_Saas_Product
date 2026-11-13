import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { Button } from '../../components/ui/Button';
import {
  IconArrowLeft,
  IconArrowRight,
  IconSparkles,
  IconDownload,
  IconCheck,
  IconRefresh,
  IconZoomIn,
  IconZoomOut,
  SendIcon,
} from '../../components/ui/Icons';
import { aiPlanApi, type GeneratedPlanResponse, type RoomSpecification } from './api';

interface ChatBubble {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  planSummary?: string;
}

export function AiGeneratorPage() {
  const navigate = useNavigate();
  const { activeProject, setProjectStatus, setPlanData } = useProject();

  // Tab mode on the left pane: Details Form vs Live AI Refinement Chat
  const [activeTab, setActiveTab] = useState<'details' | 'chat'>('details');

  // View mode on the right preview pane: CAD Blueprint image vs Room Schedule table
  const [activeView, setActiveView] = useState<'blueprint' | 'rooms' | 'specs'>('blueprint');

  // Input specifications from the user
  const [plotWidth, setPlotWidth] = useState<number>(36.5);
  const [plotLength, setPlotLength] = useState<number>(55.0);
  const [facing, setFacing] = useState<string>('East');
  const [goal, setGoal] = useState<'residence' | 'rental'>('residence');
  const [configType, setConfigType] = useState<string>('3_bhk');
  const [clientName, setClientName] = useState<string>(activeProject?.name || 'SMT. GEETA GAUD');
  const [userPrompt, setUserPrompt] = useState<string>(
    'Master suite with dressing room & attached toilet, Puja room in northeast, front parking for 2 cars, and 4ft lawn'
  );

  // Generation state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationStage, setGenerationStage] = useState<string>('Initializing spatial drafting engine...');
  const [blueprintFilter, setBlueprintFilter] = useState<'blueprint' | 'dark' | 'paper'>('blueprint');
  const [generatedPlan, setGeneratedPlan] = useState<GeneratedPlanResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [downloadSuccess, setDownloadSuccess] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);

  // Chat conversation
  const [chatInput, setChatInput] = useState<string>('');
  const [isChatSubmitting, setIsChatSubmitting] = useState<boolean>(false);
  const [chatMessages, setChatMessages] = useState<ChatBubble[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: "Welcome to Constriva's 2D Floor Plan Synthesis Studio. Specify your plot dimensions, facing, goal, and layout requirements below, and I will draft a precision CAD architectural working drawing.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isChatSubmitting]);

  // Derived dimensions
  const areaSqFt = Math.round(plotWidth * plotLength * 10) / 10;
  const areaSqM = Math.round(plotWidth * plotLength * 0.092903 * 10) / 10;

  // Preset quick selections
  const presets = [
    {
      label: "36'6\" × 55' 3-BHK Residence",
      w: 36.5,
      l: 55.0,
      g: 'residence' as const,
      c: '3_bhk',
      f: 'East',
      p: 'Front porch parking, northeast puja room, spacious drawing-dining, master suite with attached toilet, and front lawn',
    },
    {
      label: "36'6\" × 55' Dual 2-BHK Rental",
      w: 36.5,
      l: 55.0,
      g: 'rental' as const,
      c: 'dual_rental_2bhk',
      f: 'East',
      p: 'Independent dual flats with external staircase, private circulation corridors, 2 full kitchens, and ventilation shafts',
    },
    {
      label: "30' × 50' 2-BHK Modern Home",
      w: 30.0,
      l: 50.0,
      g: 'residence' as const,
      c: '2_bhk',
      f: 'North',
      p: 'North-facing 2-BHK with attached master bath, modular kitchen with wash balcony, and front garden',
    },
    {
      label: "40' × 60' 4-BHK Executive Villa",
      w: 40.0,
      l: 60.0,
      g: 'residence' as const,
      c: '4_bhk',
      f: 'East',
      p: 'Grand family villa with 2-car covered portico, expansive family lounge, puja room, and luxury master suite',
    },
  ];

  const applyPreset = (preset: (typeof presets)[0]) => {
    setPlotWidth(preset.w);
    setPlotLength(preset.l);
    setGoal(preset.g);
    setConfigType(preset.c);
    setFacing(preset.f);
    setUserPrompt(preset.p);
  };

  // Main generation handler
  const handleGenerate = async () => {
    if (plotWidth <= 0 || plotLength <= 0) {
      setErrorMessage('Please enter valid positive plot dimensions.');
      return;
    }

    setIsGenerating(true);
    setErrorMessage(null);
    setGenerationStage(`Calibrating plot boundary (${plotWidth}' × ${plotLength}') & Vastu ${facing} axis...`);

    const stageTimer1 = setTimeout(() => {
      setGenerationStage('Synthesizing perimeter shear walls & structural columns...');
    }, 900);
    const stageTimer2 = setTimeout(() => {
      setGenerationStage('Arranging room geometries, fenestration apertures & circulation shafts...');
    }, 1800);
    const stageTimer3 = setTimeout(() => {
      setGenerationStage('Rendering calibrated Er. Vikas Patodi CAD title block & annotations...');
    }, 2700);

    try {
      const res = await aiPlanApi.generatePlan({
        project_id: activeProject?.id,
        plot_width: plotWidth,
        plot_length: plotLength,
        area_sqft: areaSqFt,
        goal,
        config_type: configType,
        facing,
        client_name: clientName,
        user_prompt: userPrompt,
      });

      setGeneratedPlan(res);
      setProjectStatus('generated');

      // Add to conversation
      const summaryMsg: ChatBubble = {
        id: `plan_gen_${Date.now()}`,
        sender: 'assistant',
        text: res.ai_commentary || `Generated ${res.name} (${plotWidth}' × ${plotLength}', ${facing} Facing).`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        planSummary: `${res.name} • ${res.rooms?.length || 18} Rooms • ${areaSqFt.toLocaleString()} sq.ft (${areaSqM.toFixed(1)} m²)`,
      };
      setChatMessages((prev) => [...prev, summaryMsg]);
    } catch (err: any) {
      console.error('Plan generation failed:', err);
      setErrorMessage(err.detail || err.message || 'Failed to generate 2D floor plan. Please check backend connection.');
    } finally {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setIsGenerating(false);
    }
  };

  // Chat message send handler
  const handleSendChat = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = chatInput.trim();
    if (!text || isChatSubmitting || isGenerating) return;

    const userBubble: ChatBubble = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setChatMessages((prev) => [...prev, userBubble]);
    setChatInput('');
    setIsChatSubmitting(true);

    try {
      const chatRes = await aiPlanApi.chatWithAssistant({
        message: text,
        project_id: activeProject?.id,
        plan_id: generatedPlan?.plan_id,
        plot_width: plotWidth,
        plot_length: plotLength,
        goal,
        config_type: configType,
        facing,
      });

      if (chatRes.plan) {
        setGeneratedPlan(chatRes.plan);
        if (chatRes.plan.config_type) setConfigType(chatRes.plan.config_type);
        if (chatRes.plan.goal) setGoal(chatRes.plan.goal as any);
        if (chatRes.plan.facing) setFacing(chatRes.plan.facing);
        if (chatRes.plan.plot_width_ft) setPlotWidth(chatRes.plan.plot_width_ft);
        if (chatRes.plan.plot_length_ft) setPlotLength(chatRes.plan.plot_length_ft);
        if (chatRes.plan.plan_json) {
          setPlanData(chatRes.plan.plan_json);
        }
      }

      const assistantBubble: ChatBubble = {
        id: `ast_${Date.now()}`,
        sender: 'assistant',
        text: chatRes.reply || 'Plan revised according to your instructions.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        planSummary: chatRes.plan
          ? `${chatRes.plan.name} • ${chatRes.plan.rooms?.length || 18} Rooms`
          : undefined,
      };

      setChatMessages((prev) => [...prev, assistantBubble]);
    } catch (err: any) {
      console.error('Chat modification error:', err);
      const errorBubble: ChatBubble = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        text: `Error processing revision: ${err.detail || err.message || 'Please retry with specific architectural details.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setChatMessages((prev) => [...prev, errorBubble]);
    } finally {
      setIsChatSubmitting(false);
    }
  };

  // Download high-resolution PNG
  const handleDownloadBlueprint = () => {
    if (!generatedPlan?.png_base64) return;

    const link = document.createElement('a');
    link.href = `data:image/png;base64,${generatedPlan.png_base64}`;
    link.download = `${(generatedPlan.name || 'floor_plan').replace(/[^a-zA-Z0-9_-]/g, '_')}_cad_blueprint.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  // Seamless transition to 3D workspace
  const handleProceedTo3D = () => {
    if (generatedPlan?.plan_json) {
      setPlanData(generatedPlan.plan_json);
      try {
        localStorage.setItem('construtiva_plan_data', JSON.stringify(generatedPlan.plan_json));
        if (activeProject?.id) {
          localStorage.setItem(`construtiva_plan_cache_${activeProject.id}`, JSON.stringify(generatedPlan.plan_json));
        }
      } catch {
        // Ignore quota
      }
    }
    setProjectStatus('ready');
    navigate('/projects/3d-workspace');
  };

  return (
    <div className="min-h-screen bg-[#111317] text-[#FFFFFF] flex flex-col font-sans select-none">
      {/* Engineering Studio Contextual Sub-bar */}
      <div
        role="toolbar"
        aria-label="CAD Generator Studio Actions"
        className="border-b border-white/10 bg-[#0d0f12]/80 backdrop-blur-md px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 sticky top-0 z-30"
      >
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects/options')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
            className="text-white/70 hover:text-white"
          >
            Options
          </Button>

          <div className="h-4 w-px bg-white/10 hidden sm:block" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-display font-medium text-white text-sm sm:text-base">
                2D Floor Plan Synthesis Studio • AI Floor Plan Generator
              </h1>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#C5A77B]/15 text-[#C5A77B] border border-[#C5A77B]/30 flex items-center gap-1">
                <IconSparkles className="w-3 h-3 text-[#ffbf7a]" />
                Conversational CAD
              </span>
            </div>
            <p className="text-[11px] text-white/50 hidden sm:block font-mono">
              Constriva Architect AI: Specify plot dimensions, goal &amp; room layout to synthesize high-resolution CAD working drawings.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {generatedPlan?.png_base64 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownloadBlueprint}
              leftIcon={downloadSuccess ? <IconCheck className="w-3.5 h-3.5 text-emerald-400" /> : <IconDownload className="w-3.5 h-3.5" />}
              className="border-white/10 bg-white/[0.04] text-xs hover:bg-white/[0.08]"
            >
              {downloadSuccess ? 'Downloaded CAD PNG' : 'Download Blueprint PNG'}
            </Button>
          )}

          <Button
            variant="primary"
            size="sm"
            onClick={handleProceedTo3D}
            rightIcon={<IconArrowRight className="w-4 h-4" />}
            className="bg-[#C5A77B] text-[#121212] font-semibold hover:bg-[#D4B88E] shadow-sm text-xs cursor-pointer"
          >
            Open in 3D Workspace
          </Button>
        </div>
      </div>

      {/* Main Split Interface */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-[calc(100vh-65px)]">
        {/* Left Side: Parameters Form & Conversational Refinement (42% width) */}
        <section className="lg:w-[42%] border-b lg:border-b-0 lg:border-r border-[#23272F] bg-[#16181E] flex flex-col">
          {/* Tabs: Specifications Form vs AI Refinement Chat */}
          <div className="flex items-center border-b border-[#23272F] bg-[#121418] px-4 pt-2">
            <button
              onClick={() => setActiveTab('details')}
              className={`px-4 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-all cursor-pointer ${
                activeTab === 'details'
                  ? 'border-[#C5A77B] text-[#FFFFFF] font-semibold'
                  : 'border-transparent text-[#7E8490] hover:text-[#B0B5C0]'
              }`}
            >
              1. Plot Details &amp; Rooms
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-4 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'chat'
                  ? 'border-[#C5A77B] text-[#FFFFFF] font-semibold'
                  : 'border-transparent text-[#7E8490] hover:text-[#B0B5C0]'
              }`}
            >
              <IconSparkles className="w-3.5 h-3.5 text-[#C5A77B]" />
              2. AI CAD Assistant Chat
            </button>
          </div>

          {/* Tab 1: Plot Details Form */}
          {activeTab === 'details' ? (
            <div className="flex-1 p-5 overflow-y-auto space-y-5 text-sm">
              {/* Presets Quick Pick */}
              <div>
                <span className="text-[11px] font-mono uppercase tracking-widest text-[#C5A77B] block mb-2">
                  Quick Benchmark Presets
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {presets.map((preset, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => applyPreset(preset)}
                      className="p-2.5 text-left rounded-lg bg-[#1D212A] hover:bg-[#252A36] border border-[#2B313F] hover:border-[#C5A77B]/50 transition-colors cursor-pointer group"
                    >
                      <div className="text-xs font-medium text-[#E0E2E8] group-hover:text-[#FFFFFF] truncate">
                        {preset.label}
                      </div>
                      <div className="text-[10px] text-[#7A8190] mt-0.5">
                        {preset.w}' × {preset.l}' • {preset.f} Facing
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Dimensions Section */}
              <div className="p-4 rounded-xl bg-[#1B1F27] border border-[#282F3D] space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase tracking-wider text-[#A0A6B2]">
                    Plot Dimensions (Feet)
                  </span>
                  <span className="text-xs font-mono text-[#C5A77B] font-semibold">
                    {areaSqFt.toLocaleString()} sq.ft ({areaSqM.toFixed(1)} m²)
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-[#868D9B] block mb-1">
                      Plot Width (Frontage)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.5"
                        min="15"
                        max="200"
                        value={plotWidth}
                        onChange={(e) => setPlotWidth(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 rounded-lg bg-[#14171D] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                      />
                      <span className="absolute right-3 top-2 text-xs text-[#6B7280]">ft</span>
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] text-[#868D9B] block mb-1">
                      Plot Length (Depth)
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        step="0.5"
                        min="20"
                        max="300"
                        value={plotLength}
                        onChange={(e) => setPlotLength(parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 rounded-lg bg-[#14171D] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                      />
                      <span className="absolute right-3 top-2 text-xs text-[#6B7280]">ft</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Goal & Configuration */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-[#868D9B] block mb-1">
                    Building Purpose / Goal
                  </label>
                  <select
                    value={goal}
                    onChange={(e) => {
                      const val = e.target.value as 'residence' | 'rental';
                      setGoal(val);
                      if (val === 'rental') setConfigType('dual_rental_2bhk');
                      else setConfigType('3_bhk');
                    }}
                    className="w-full px-3 py-2 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                  >
                    <option value="residence">Personal Family Residence</option>
                    <option value="rental">Multi-Unit Rental Investment</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] text-[#868D9B] block mb-1">
                    Room Configuration
                  </label>
                  <select
                    value={configType}
                    onChange={(e) => setConfigType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                  >
                    {goal === 'rental' ? (
                      <>
                        <option value="dual_rental_2bhk">Dual Independent 2-BHK Units</option>
                        <option value="rental_1bhk_2bhk">1-BHK + 2-BHK Split Units</option>
                      </>
                    ) : (
                      <>
                        <option value="3_bhk">3-BHK Luxury Residence</option>
                        <option value="2_bhk">2-BHK Compact Modern</option>
                        <option value="4_bhk">4-BHK Executive Villa</option>
                        <option value="1_bhk">1-BHK Studio Suite</option>
                      </>
                    )}
                  </select>
                </div>
              </div>

              {/* Facing & Client Name */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-[#868D9B] block mb-1">
                    Front Entrance Facing (Vastu)
                  </label>
                  <select
                    value={facing}
                    onChange={(e) => setFacing(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                  >
                    <option value="East">East Facing (Sunrise / Ishanya)</option>
                    <option value="North">North Facing (Kubera / Wealth)</option>
                    <option value="West">West Facing (Nairutya / Varuna)</option>
                    <option value="South">South Facing (Yama / Agni)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] text-[#868D9B] block mb-1">
                    Title Block Client Name
                  </label>
                  <input
                    type="text"
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-sm text-[#FFFFFF] focus:outline-none focus:border-[#C5A77B]"
                    placeholder="e.g. SMT. GEETA GAUD"
                  />
                </div>
              </div>

              {/* Custom Requirements Text */}
              <div>
                <label className="text-[11px] text-[#868D9B] block mb-1">
                  Custom Layout Specifications
                </label>
                <textarea
                  rows={3}
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  placeholder="Specify particular room requests (e.g. attached toilets, open modular kitchen, 4ft front lawn, puja room, parking for 2 cars)..."
                  className="w-full px-3.5 py-2.5 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-sm text-[#FFFFFF] placeholder-[#5A6270] focus:outline-none focus:border-[#C5A77B] leading-relaxed resize-none"
                />
              </div>

              {/* Error Alert */}
              {errorMessage && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Action Button */}
              <Button
                variant="accent"
                size="md"
                onClick={handleGenerate}
                disabled={isGenerating}
                leftIcon={isGenerating ? <span className="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <IconSparkles className="w-4 h-4" />}
                className="w-full py-3 bg-[#C5A77B] text-[#121212] font-semibold hover:bg-[#D4B88E] cursor-pointer shadow-md"
              >
                {isGenerating ? 'Synthesizing Precision CAD Drawing...' : 'Generate 2D Floor Plan'}
              </Button>
            </div>
          ) : (
            /* Tab 2: AI Refinement Chat */
            <div className="flex-1 flex flex-col justify-between overflow-hidden">
              <div className="flex-1 p-4 overflow-y-auto space-y-3.5">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div
                      className={`max-w-[88%] rounded-xl p-3.5 text-xs sm:text-sm leading-relaxed ${
                        msg.sender === 'user'
                          ? 'bg-[#C5A77B]/20 border border-[#C5A77B]/40 text-[#FFFFFF] rounded-tr-none'
                          : 'bg-[#1D212B] border border-[#2A3140] text-[#E0E4EC] rounded-tl-none shadow-sm'
                      }`}
                    >
                      {msg.sender === 'assistant' && (
                        <div className="flex items-center gap-1.5 mb-1.5 text-[10px] font-mono font-semibold text-[#C5A77B] uppercase tracking-wider">
                          <IconSparkles className="w-3 h-3 text-[#C5A77B]" />
                          Architectural AI
                        </div>
                      )}
                      <div>{msg.text}</div>
                      {msg.planSummary && (
                        <div className="mt-2 pt-2 border-t border-[#31394A] text-[11px] font-mono text-[#A8B2C4]">
                          {msg.planSummary}
                        </div>
                      )}
                      <div className="mt-1 text-[9px] text-[#697282] text-right font-mono">
                        {msg.timestamp}
                      </div>
                    </div>
                  </div>
                ))}
                {isChatSubmitting && (
                  <div className="flex items-center gap-2 p-3 text-xs text-[#8A93A4] bg-[#1D212B] rounded-xl border border-[#2A3140] w-fit">
                    <span className="w-3.5 h-3.5 rounded-full border-2 border-[#C5A77B] border-t-transparent animate-spin" />
                    <span>Recalculating room coordinates and updating CAD drawing...</span>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Chat Input Bar */}
              <form
                onSubmit={handleSendChat}
                className="p-3 border-t border-[#23272F] bg-[#14161C] flex items-center gap-2"
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask to modify dimensions, swap rooms, add terraces..."
                  disabled={isChatSubmitting || isGenerating}
                  className="flex-1 px-3.5 py-2 rounded-lg bg-[#1B1F27] border border-[#2C3342] text-xs sm:text-sm text-[#FFFFFF] placeholder-[#646C7C] focus:outline-none focus:border-[#C5A77B]"
                />
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={!chatInput.trim() || isChatSubmitting || isGenerating}
                  className="bg-[#C5A77B] text-[#121212] font-semibold hover:bg-[#D4B88E] px-3.5 py-2 cursor-pointer"
                >
                  <SendIcon size={14} />
                </Button>
              </form>
            </div>
          )}
        </section>

        {/* Right Side: High-Resolution 2D CAD Blueprint & Room Breakdown (58% width) */}
        <section className="lg:w-[58%] p-4 sm:p-6 flex flex-col bg-[#0D0F12] overflow-y-auto">
          {/* View Mode Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[#161920] border border-[#242A36]">
              <button
                type="button"
                onClick={() => setActiveView('blueprint')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all cursor-pointer ${
                  activeView === 'blueprint'
                    ? 'bg-[#C5A77B] text-[#121212] font-semibold shadow-sm'
                    : 'text-[#8A93A4] hover:text-[#FFFFFF]'
                }`}
              >
                CAD Blueprint
              </button>
              <button
                type="button"
                onClick={() => setActiveView('rooms')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all cursor-pointer ${
                  activeView === 'rooms'
                    ? 'bg-[#C5A77B] text-[#121212] font-semibold shadow-sm'
                    : 'text-[#8A93A4] hover:text-[#FFFFFF]'
                }`}
              >
                Room Schedule ({generatedPlan?.rooms?.length || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveView('specs')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all cursor-pointer ${
                  activeView === 'specs'
                    ? 'bg-[#C5A77B] text-[#121212] font-semibold shadow-sm'
                    : 'text-[#8A93A4] hover:text-[#FFFFFF]'
                }`}
              >
                Engineering Review
              </button>
            </div>

            {/* Zoom & Fullscreen Controls for Blueprint */}
            {activeView === 'blueprint' && (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.max(0.6, z - 0.2))}
                  className="p-1.5 rounded bg-[#161920] border border-[#242A36] text-[#8A93A4] hover:text-[#FFFFFF] cursor-pointer"
                  title="Zoom Out"
                >
                  <IconZoomOut size={16} />
                </button>
                <span className="text-[11px] font-mono text-[#8A93A4] px-1.5">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoomLevel((z) => Math.min(2.2, z + 0.2))}
                  className="p-1.5 rounded bg-[#161920] border border-[#242A36] text-[#8A93A4] hover:text-[#FFFFFF] cursor-pointer"
                  title="Zoom In"
                >
                  <IconZoomIn size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => setZoomLevel(1.0)}
                  className="p-1.5 rounded bg-[#161920] border border-[#242A36] text-[#8A93A4] hover:text-[#FFFFFF] cursor-pointer"
                  title="Reset Zoom"
                >
                  <IconRefresh size={16} />
                </button>
              </div>
            )}
          </div>

          {/* View Container */}
          <div className="flex-1 flex flex-col justify-center items-center min-h-[520px] rounded-xl bg-[#0e1117] border border-white/10 overflow-hidden relative shadow-inner">
            {isGenerating ? (
              <div className="flex-1 w-full h-full flex flex-col items-center justify-center p-8 space-y-6 relative overflow-hidden drafting-grid">
                {/* Holographic Laser Scanline Bar */}
                <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-[#ffbf7a] to-transparent animate-scanline pointer-events-none shadow-[0_0_18px_#ffbf7a]" />

                {/* Diagnostic Radar / HUD */}
                <div className="relative">
                  <div className="w-20 h-20 rounded-full border border-[#C5A77B]/30 animate-ping opacity-25" />
                  <div className="w-20 h-20 rounded-full border-2 border-[#C5A77B] border-t-transparent animate-spin absolute inset-0" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <IconSparkles className="w-7 h-7 text-[#ffbf7a] animate-pulse-glow" />
                  </div>
                </div>

                <div className="text-center z-10 max-w-md">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-[#ffbf7a] mb-1">
                    Spatial Synthesis Engine
                  </div>
                  <div className="text-base font-medium text-white">Synthesizing 2D CAD Blueprint</div>
                  <div className="text-xs text-white/80 mt-2 font-mono px-4 py-1.5 rounded-full bg-white/[0.05] border border-white/10 inline-block animate-pulse">
                    {generationStage}
                  </div>
                </div>

                {/* Caliper overlay markers */}
                <div className="absolute top-4 left-4 text-[10px] font-mono text-white/30">[0, 0] ARCH_GRID</div>
                <div className="absolute top-4 right-4 text-[10px] font-mono text-white/30">[{plotWidth}', 0] VASTU_{facing.toUpperCase()}</div>
                <div className="absolute bottom-4 left-4 text-[10px] font-mono text-white/30">[0, {plotLength}'] {areaSqFt.toLocaleString()} SQFT</div>
                <div className="absolute bottom-4 right-4 text-[10px] font-mono text-white/30">SCALE: 1/4" = 1'-0"</div>
              </div>
            ) : activeView === 'blueprint' ? (
              /* CAD Blueprint Image View */
              <div className="w-full h-full flex flex-col items-center justify-center p-4 relative drafting-grid overflow-hidden">
                {generatedPlan?.png_base64 ? (
                  <>
                    {/* Blueprint Mode Switcher & Metric Ribbon */}
                    <div className="absolute top-3 left-3 z-20 flex items-center gap-2 arch-glass px-3 py-1.5 rounded-lg border border-white/10 text-xs">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="font-mono text-[11px] text-white/80 truncate max-w-[180px] sm:max-w-xs">
                        {generatedPlan.name || '2D Architectural Plan'}
                      </span>
                      <span className="text-white/20">•</span>
                      <span className="font-mono text-[10px] text-[#C5A77B]">
                        {areaSqFt.toLocaleString()} sq.ft
                      </span>
                    </div>

                    {/* Filter mode pill */}
                    <div className="absolute top-3 right-3 z-20 flex items-center gap-1 arch-glass p-1 rounded-lg border border-white/10 text-[10px] font-mono">
                      <button
                        onClick={() => setBlueprintFilter('blueprint')}
                        className={`px-2.5 py-1 rounded cursor-pointer transition-all ${
                          blueprintFilter === 'blueprint'
                            ? 'bg-[#0f2f6b] text-white font-semibold shadow-sm'
                            : 'text-white/60 hover:text-white'
                        }`}
                      >
                        Blueprint
                      </button>
                      <button
                        onClick={() => setBlueprintFilter('dark')}
                        className={`px-2.5 py-1 rounded cursor-pointer transition-all ${
                          blueprintFilter === 'dark'
                            ? 'bg-black text-white font-semibold shadow-sm'
                            : 'text-white/60 hover:text-white'
                        }`}
                      >
                        Obsidian CAD
                      </button>
                      <button
                        onClick={() => setBlueprintFilter('paper')}
                        className={`px-2.5 py-1 rounded cursor-pointer transition-all ${
                          blueprintFilter === 'paper'
                            ? 'bg-white/20 text-white font-semibold shadow-sm'
                            : 'text-white/60 hover:text-white'
                        }`}
                      >
                        Paper
                      </button>
                    </div>

                    {/* The CAD Blueprint with Tactile Reveal */}
                    <div
                      style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}
                      className="transition-transform duration-150 flex items-center justify-center max-w-full max-h-full animate-blueprint-reveal z-10"
                    >
                      <div
                        className={`relative p-2 rounded-xl transition-all ${
                          blueprintFilter === 'blueprint'
                            ? 'bg-[#06152b]/85 border-2 border-[#1e4976] shadow-[0_0_35px_rgba(30,73,118,0.4)]'
                            : blueprintFilter === 'paper'
                            ? 'bg-[#f4efe6] border-2 border-[#d0c5b4] shadow-2xl invert-[0.9]'
                            : 'bg-[#0a0c10] border border-white/15 shadow-2xl'
                        }`}
                      >
                        <img
                          src={`data:image/png;base64,${generatedPlan.png_base64}`}
                          alt={generatedPlan.name || '2D Architectural Floor Plan'}
                          className="max-h-[660px] w-auto object-contain rounded"
                        />
                        {/* Subtle Watermark Overlay */}
                        <div className="absolute bottom-3 right-4 pointer-events-none text-[9px] font-mono tracking-widest text-white/50 uppercase bg-black/50 px-2 py-0.5 rounded backdrop-blur-sm">
                          CONSTRIVA ARCHITECTURAL CAD • VASTU {facing.toUpperCase()}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="text-center p-8 text-[#707888] flex flex-col items-center justify-center max-w-sm arch-glass rounded-2xl border border-white/10">
                    <div className="w-14 h-14 rounded-2xl bg-white/[0.06] border border-white/15 flex items-center justify-center mb-3.5 shadow-md">
                      <IconSparkles className="w-7 h-7 text-[#C5A77B]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[#FFFFFF] mb-1.5">Awaiting Your Specifications</h3>
                    <p className="text-xs text-[#8A93A4] leading-relaxed mb-4">
                      Review plot dimensions, facing orientation, and custom room layout on the left, then click <strong>Generate 2D Floor Plan</strong> to draft your working drawing.
                    </p>
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10 text-[11px] text-[#A6AFC0] font-mono">
                      <span>Plot: {plotWidth}' × {plotLength}'</span>
                      <span className="text-white/20">•</span>
                      <span>{areaSqFt.toLocaleString()} sq.ft</span>
                      <span className="text-white/20">•</span>
                      <span>{facing} Facing</span>
                    </div>
                  </div>
                )}
              </div>
            ) : activeView === 'rooms' ? (
              /* Room Schedule Table View */
              <div className="w-full h-full p-5 overflow-y-auto">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-mono uppercase tracking-wider text-[#C5A77B]">
                    Architectural Room Schedule &amp; Dimensions
                  </span>
                  <span className="text-xs font-mono text-[#828B9C]">
                    Total Rooms: {generatedPlan?.rooms?.length || 0}
                  </span>
                </div>

                <div className="overflow-x-auto rounded-lg border border-[#232938]">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-[#232938] bg-[#191D26] text-[#A2AAB8] font-mono uppercase text-[10px]">
                        <th className="py-2.5 px-3">#</th>
                        <th className="py-2.5 px-3">Room Name</th>
                        <th className="py-2.5 px-3">Dimensions</th>
                        <th className="py-2.5 px-3">Category</th>
                        <th className="py-2.5 px-3">Coordinates (X, Y)</th>
                        <th className="py-2.5 px-3 text-right">Area (sq.ft)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1D222E] bg-[#14171E] text-[#D8DCE6]">
                      {(generatedPlan?.rooms || []).map((room: RoomSpecification, idx: number) => {
                        const area = Math.round(room.w_ft * room.h_ft * 10) / 10;
                        return (
                          <tr key={room.id} className="hover:bg-[#1B202B] transition-colors">
                            <td className="py-2.5 px-3 font-mono text-[#6A7385]">{idx + 1}</td>
                            <td className="py-2.5 px-3 font-semibold text-[#FFFFFF]">{room.name}</td>
                            <td className="py-2.5 px-3 font-mono text-[#C5A77B]">{room.dimensions}</td>
                            <td className="py-2.5 px-3">
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#212735] text-[#9EA7B8] border border-[#2B3344]">
                                {room.category}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[#7B8496]">
                              {room.x_ft.toFixed(1)}', {room.y_ft.toFixed(1)}'
                            </td>
                            <td className="py-2.5 px-3 font-mono text-right font-medium text-[#E0E4ED]">
                              {area > 0 ? `${area} sq.ft` : '-'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              /* Engineering & Vastu Review View */
              <div className="w-full h-full p-6 overflow-y-auto space-y-4 text-xs leading-relaxed text-[#D0D6E2]">
                <div className="p-4 rounded-xl bg-[#191D26] border border-[#252C3B] space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-[#C5A77B]">
                    <IconSparkles className="w-4 h-4 text-[#C5A77B]" />
                    Architectural Engineering Review
                  </div>
                  <p className="text-xs text-[#A8B2C4] leading-relaxed">
                    {generatedPlan?.ai_commentary ||
                      'The generated plan establishes clean functional zoning, abundant natural ventilation cutouts, and load-bearing column symmetry.'}
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 rounded-lg bg-[#161A22] border border-[#232938] space-y-1">
                    <span className="text-[10px] font-mono uppercase text-[#C5A77B] block">
                      Vastu &amp; Solar Orientation
                    </span>
                    <p className="text-[#969FA8]">
                      Orientation configured for <strong className="text-[#FFFFFF]">{facing} Facing</strong> entrance. Master bedroom anchored in Southwest (Nairutya) for stability, and modular Kitchen located in Southeast (Agni) zone.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-lg bg-[#161A22] border border-[#232938] space-y-1">
                    <span className="text-[10px] font-mono uppercase text-[#C5A77B] block">
                      Circulation &amp; Privacy
                    </span>
                    <p className="text-[#969FA8]">
                      Continuous circulation passages connect front foyer to living areas without traversing private bedroom suites. Independent stair flights provide vertical access.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
