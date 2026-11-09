import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import {
  IconArrowLeft,
  IconArrowRight,
  IconSparkles,
  IconDownload,
  IconCheck,
} from '../../components/ui/Icons';
import type { ChatMessage } from '../../types';

export function AiGeneratorPage() {
  const navigate = useNavigate();
  const { activeProject, setProjectStatus } = useProject();

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg_1',
      sender: 'assistant',
      text: "Welcome! I am Construtiva's Architectural AI. I have prepared an initial 2-BHK residential floor plan (10.5m × 8.5m) with an open living-dining zone, master bedroom suite, ensuite bath, and terrace. How would you like to refine it? You can ask to enlarge rooms, relocate the entrance, or add features.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      updatedPlanSummary: 'Initial 2-BHK Modern Layout • 89.25 m² Built-Up Area',
    },
  ]);

  const [inputPrompt, setInputPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [planVariant, setPlanVariant] = useState<'standard' | 'expanded_living' | 'terrace_suite'>('standard');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const promptSuggestions = [
    'Add an attached balcony to master bedroom',
    'Enlarge the open-concept living area',
    'Add a utility storage room near kitchen',
    'Optimize for natural north sunlight',
  ];

  const handleSendMessage = (textToSend?: string) => {
    const text = textToSend || inputPrompt;
    if (!text.trim() || isGenerating) return;

    const userMsg: ChatMessage = {
      id: 'msg_' + Date.now(),
      sender: 'user',
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputPrompt('');
    setIsGenerating(true);

    // Simulate AI synthesis & blueprint adjustment
    setTimeout(() => {
      let aiResponseText = '';
      let summaryText = '';

      const lower = text.toLowerCase();
      if (lower.includes('balcony') || lower.includes('terrace')) {
        setPlanVariant('terrace_suite');
        aiResponseText =
          'I have expanded the east balcony into a 14.5 m² private sun terrace adjoining the master suite, with double-glazed sliding glass doors and concrete stone pavers.';
        summaryText = 'Terrace Suite Variant • 96.5 m² Total Area';
      } else if (lower.includes('enlarge') || lower.includes('living') || lower.includes('open')) {
        setPlanVariant('expanded_living');
        aiResponseText =
          'Living and dining area has been widened by 1.2 meters. The partition between kitchen and dining is now an open architectural breakfast counter with pendant lighting clearance.';
        summaryText = 'Expanded Open-Concept Variant • 94.0 m² Total Area';
      } else {
        aiResponseText = `I have adjusted the floor plan according to your instruction: "${text}". Partition walls were recalculated to maintain structural load-bearing symmetry and optimal circulation paths.`;
        summaryText = 'Custom AI Revision • 89.25 m² Total Area';
      }

      const aiMsg: ChatMessage = {
        id: 'msg_' + (Date.now() + 1),
        sender: 'assistant',
        text: aiResponseText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        updatedPlanSummary: summaryText,
      };

      setMessages((prev) => [...prev, aiMsg]);
      setIsGenerating(false);
      setProjectStatus('generated');
    }, 1400);
  };

  const handleDownloadBlueprint = () => {
    const svgElement = document.getElementById('blueprint-canvas');
    if (!svgElement) return;

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svgElement);
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${activeProject?.name || 'blueprint'}_architectural_plan.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  const handleProceedTo3D = () => {
    setProjectStatus('ready');
    navigate('/projects/3d-workspace');
  };

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col">
      {/* Top Header */}
      <header className="border-b border-border bg-surface/80 backdrop-blur-md px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects/options')}
            leftIcon={<IconArrowLeft className="w-4 h-4" />}
          >
            Options
          </Button>

          <div className="h-4 w-px bg-border" />

          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-serif font-medium text-primary text-base sm:text-lg">
                AI Floor Plan Generator
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-accent/15 text-accent border border-accent/30 flex items-center gap-1">
                <IconSparkles className="w-3 h-3" />
                Conversational CAD
              </span>
            </div>
            <p className="text-xs text-secondary hidden sm:block">
              Describe your vision in plain English. The AI draws and updates the 2D architectural blueprint in real-time.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDownloadBlueprint}
            leftIcon={downloadSuccess ? <IconCheck className="w-3.5 h-3.5 text-emerald-400" /> : <IconDownload className="w-3.5 h-3.5" />}
          >
            {downloadSuccess ? 'Downloaded Blueprint' : 'Download Blueprint'}
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleProceedTo3D}
            rightIcon={<IconArrowRight className="w-4 h-4" />}
          >
            Open in 3D Workspace
          </Button>
        </div>
      </header>

      {/* Main Split Layout: Left Chat, Right Blueprint View */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden min-h-[calc(100vh-125px)]">
        {/* Left Side: Chat Conversation Pane (42% width) */}
        <section className="lg:w-[42%] border-b lg:border-b-0 lg:border-r border-border bg-surface flex flex-col">
          {/* Conversation history */}
          <div className="flex-1 p-4 sm:p-5 overflow-y-auto space-y-4 max-h-[calc(100vh-230px)]">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.sender === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-xl p-3.5 sm:p-4 text-sm leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-accent/20 border border-accent/40 text-primary rounded-tr-none'
                      : 'bg-panel border border-border text-primary rounded-tl-none shadow-sm'
                  }`}
                >
                  {msg.sender === 'assistant' && (
                    <div className="flex items-center gap-2 mb-2 text-xs font-semibold text-accent uppercase tracking-wider">
                      <IconSparkles className="w-3.5 h-3.5 text-accent" />
                      <span>Construtiva Architect AI</span>
                    </div>
                  )}

                  <p className="whitespace-pre-line">{msg.text}</p>

                  {msg.updatedPlanSummary && (
                    <div className="mt-2.5 pt-2 border-t border-border/60 text-xs text-secondary flex items-center gap-1.5 font-mono">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      {msg.updatedPlanSummary}
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-secondary mt-1 px-1">
                  {msg.timestamp}
                </span>
              </div>
            ))}

            {isGenerating && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-panel border border-border w-fit text-xs text-secondary animate-pulse">
                <IconSparkles className="w-4 h-4 text-accent animate-spin" />
                <span>Architect AI is recalculating load vectors and CAD coordinates...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Prompt Chips Suggestions */}
          <div className="px-4 py-2 border-t border-border/50 bg-panel/40 flex items-center gap-2 overflow-x-auto scrollbar-none">
            <span className="text-[11px] text-secondary whitespace-nowrap">Try:</span>
            {promptSuggestions.map((sug, i) => (
              <button
                key={i}
                onClick={() => handleSendMessage(sug)}
                className="px-2.5 py-1 rounded-full text-[11px] bg-panel hover:bg-surface border border-border text-secondary hover:text-primary transition-colors whitespace-nowrap"
              >
                {sug}
              </button>
            ))}
          </div>

          {/* Chat Input Field */}
          <div className="p-3 sm:p-4 border-t border-border bg-surface">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="Ask to modify dimensions, swap rooms, add terraces..."
                disabled={isGenerating}
                className="flex-1 px-4 py-2.5 rounded-lg bg-panel border border-border text-sm text-primary placeholder-secondary/60 focus:outline-none focus:border-accent transition-colors disabled:opacity-50"
              />
              <Button
                type="submit"
                variant="primary"
                disabled={!inputPrompt.trim() || isGenerating}
                rightIcon={<IconArrowRight className="w-4 h-4" />}
              >
                Send
              </Button>
            </form>
          </div>
        </section>

        {/* Right Side: Interactive 2D Blueprint Canvas (58% width) */}
        <section className="lg:w-[58%] p-4 sm:p-6 flex flex-col bg-[#141414] overflow-y-auto">
          {/* Blueprint Meta Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded bg-panel border border-border text-xs text-secondary font-mono">
                CAD Coordinate Mode: Metric (Meters)
              </span>
              <span className="text-xs text-secondary">Scale: 1:50 Blueprint</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-secondary">
                Variant: <strong className="text-primary capitalize">{planVariant.replace('_', ' ')}</strong>
              </span>
            </div>
          </div>

          {/* 2D Architectural SVG Blueprint */}
          <div className="flex-1 flex items-center justify-center min-h-[460px] bg-[#11161B] rounded-xl border border-[#232F3E] p-6 shadow-inner relative overflow-hidden">
            {/* Architectural Grid Background */}
            <div
              className="absolute inset-0 opacity-20 pointer-events-none"
              style={{
                backgroundImage:
                  'linear-gradient(to right, #385070 1px, transparent 1px), linear-gradient(to bottom, #385070 1px, transparent 1px)',
                backgroundSize: '30px 30px',
              }}
            />

            <svg
              id="blueprint-canvas"
              viewBox="0 0 750 550"
              className="w-full max-w-[680px] h-auto drop-shadow-2xl relative z-10 font-sans select-none"
            >
              {/* Outer Dimension Lines */}
              <g stroke="#53729A" strokeWidth="1" strokeDasharray="3,3">
                <line x1="50" y1="30" x2="650" y2="30" />
                <line x1="50" y1="20" x2="50" y2="40" />
                <line x1="650" y1="20" x2="650" y2="40" />
                <text x="350" y="24" fill="#8BB5E8" fontSize="12" textAnchor="middle" fontFamily="monospace">
                  10.50 m (External Dimension)
                </text>

                <line x1="30" y1="50" x2="30" y2="480" />
                <line x1="20" y1="50" x2="40" y2="50" />
                <line x1="20" y1="480" x2="40" y2="480" />
                <text x="24" y="270" fill="#8BB5E8" fontSize="12" textAnchor="middle" transform="rotate(-90 24 270)" fontFamily="monospace">
                  8.50 m
                </text>
              </g>

              {/* Floor Polygon Fills */}
              {/* Living & Dining */}
              <rect x="50" y="50" width={planVariant === 'expanded_living' ? 420 : 360} height="240" fill="#1C2633" stroke="#3D5A80" strokeWidth="1.5" />
              {/* Kitchen */}
              <rect x="50" y="290" width="210" height="190" fill="#1E2A38" stroke="#3D5A80" strokeWidth="1.5" />
              {/* Bathroom */}
              <rect x="260" y="290" width={planVariant === 'expanded_living' ? 150 : 150} height="190" fill="#202D3C" stroke="#3D5A80" strokeWidth="1.5" />
              {/* Master Bedroom */}
              <rect x={planVariant === 'expanded_living' ? 470 : 410} y="50" width={planVariant === 'expanded_living' ? 240 : 240} height="240" fill="#1C2633" stroke="#3D5A80" strokeWidth="1.5" />
              {/* Terrace / Balcony */}
              <rect
                x={planVariant === 'expanded_living' ? 470 : 410}
                y="290"
                width={planVariant === 'expanded_living' ? 240 : 240}
                height="190"
                fill={planVariant === 'terrace_suite' ? '#2A3C4F' : '#17202B'}
                stroke="#3D5A80"
                strokeWidth="1.5"
              />

              {/* Room Text Labels */}
              <g textAnchor="middle" fill="#FFFFFF">
                {/* Living */}
                <text x={planVariant === 'expanded_living' ? 260 : 230} y="160" fontSize="15" fontWeight="600" fill="#F5F2EB">
                  LIVING & DINING
                </text>
                <text x={planVariant === 'expanded_living' ? 260 : 230} y="180" fontSize="12" fill="#8BB5E8" fontFamily="monospace">
                  {planVariant === 'expanded_living' ? '36.8 m²' : '30.0 m²'} • Oak Hardwood
                </text>

                {/* Master Bed */}
                <text x={planVariant === 'expanded_living' ? 590 : 530} y="160" fontSize="14" fontWeight="600" fill="#F5F2EB">
                  MASTER SUITE
                </text>
                <text x={planVariant === 'expanded_living' ? 590 : 530} y="180" fontSize="12" fill="#8BB5E8" fontFamily="monospace">
                  22.5 m² • Ensuite Access
                </text>

                {/* Kitchen */}
                <text x="155" y="380" fontSize="14" fontWeight="600" fill="#F5F2EB">
                  KITCHEN
                </text>
                <text x="155" y="400" fontSize="12" fill="#8BB5E8" fontFamily="monospace">
                  12.2 m² • Slate Tile
                </text>

                {/* Bathroom */}
                <text x={planVariant === 'expanded_living' ? 335 : 335} y="380" fontSize="13" fontWeight="600" fill="#F5F2EB">
                  BATHROOM
                </text>
                <text x={planVariant === 'expanded_living' ? 335 : 335} y="400" fontSize="11" fill="#8BB5E8" fontFamily="monospace">
                  9.5 m² • Marble
                </text>

                {/* Balcony / Terrace */}
                <text x={planVariant === 'expanded_living' ? 590 : 530} y="380" fontSize="14" fontWeight="600" fill={planVariant === 'terrace_suite' ? '#C5A77B' : '#F5F2EB'}>
                  {planVariant === 'terrace_suite' ? 'SUN TERRACE' : 'BALCONY'}
                </text>
                <text x={planVariant === 'expanded_living' ? 590 : 530} y="400" fontSize="12" fill="#8BB5E8" fontFamily="monospace">
                  {planVariant === 'terrace_suite' ? '14.5 m² • Pavers' : '15.0 m² • Concrete'}
                </text>
              </g>

              {/* Doors with Swing Arcs */}
              {/* Main Entrance Door */}
              <g stroke="#C5A77B" strokeWidth="2" fill="none">
                <line x1="160" y1="50" x2="205" y2="50" strokeWidth="4" stroke="#11161B" />
                <line x1="160" y1="50" x2="160" y2="90" stroke="#C5A77B" strokeWidth="2.5" />
                <path d="M 160 90 A 40 40 0 0 0 200 50" stroke="#C5A77B" strokeWidth="1.5" strokeDasharray="3,3" />
              </g>

              {/* Bedroom Door */}
              <g stroke="#C5A77B" strokeWidth="2" fill="none">
                <line x1={planVariant === 'expanded_living' ? 470 : 410} y1="180" x2={planVariant === 'expanded_living' ? 470 : 410} y2="220" strokeWidth="4" stroke="#11161B" />
                <line x1={planVariant === 'expanded_living' ? 470 : 410} y1="180" x2={planVariant === 'expanded_living' ? 435 : 375} y2="180" stroke="#C5A77B" strokeWidth="2" />
                <path d={`M ${planVariant === 'expanded_living' ? 435 : 375} 180 A 35 35 0 0 0 ${planVariant === 'expanded_living' ? 470 : 410} 215`} stroke="#C5A77B" strokeWidth="1.5" strokeDasharray="3,3" />
              </g>

              {/* Windows (Double Lines) */}
              <g stroke="#64B5F6" strokeWidth="3">
                <line x1="520" y1="48" x2="600" y2="48" />
                <line x1="520" y1="52" x2="600" y2="52" />

                <line x1="648" y1="120" x2="648" y2="200" />
                <line x1="652" y1="120" x2="652" y2="200" />

                <line x1="48" y1="330" x2="48" y2="400" />
                <line x1="52" y1="330" x2="52" y2="400" />
              </g>

              {/* Exterior Heavy Walls */}
              <rect x="50" y="50" width="600" height="430" fill="none" stroke="#E6ECEF" strokeWidth="6" />

              {/* Internal Walls */}
              <line x1="50" y1="290" x2="650" y2="290" stroke="#E6ECEF" strokeWidth="4" />
              <line x1={planVariant === 'expanded_living' ? 470 : 410} y1="50" x2={planVariant === 'expanded_living' ? 470 : 410} y2="480" stroke="#E6ECEF" strokeWidth="4" />
              <line x1="260" y1="290" x2="260" y2="480" stroke="#E6ECEF" strokeWidth="4" />

              {/* North Arrow Compass */}
              <g transform="translate(610, 80)">
                <circle cx="0" cy="0" r="16" fill="#1C2633" stroke="#8BB5E8" strokeWidth="1.5" />
                <polygon points="0,-12 4,6 0,2 -4,6" fill="#C5A77B" />
                <text x="0" y="-14" fill="#C5A77B" fontSize="9" fontWeight="bold" textAnchor="middle">
                  N
                </text>
              </g>
            </svg>
          </div>

          {/* Plan Specifications Bar */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Card className="p-3 bg-panel/60">
              <span className="text-[11px] text-secondary block">Total Built-Up Area</span>
              <span className="text-sm font-semibold text-primary font-mono">
                {planVariant === 'terrace_suite' ? '96.5 m²' : planVariant === 'expanded_living' ? '94.0 m²' : '89.25 m²'}
              </span>
            </Card>

            <Card className="p-3 bg-panel/60">
              <span className="text-[11px] text-secondary block">Zoned Rooms</span>
              <span className="text-sm font-semibold text-primary">5 Functional Zones</span>
            </Card>

            <Card className="p-3 bg-panel/60">
              <span className="text-[11px] text-secondary block">Wall Construction</span>
              <span className="text-sm font-semibold text-primary">0.25m / 0.15m Brick</span>
            </Card>

            <Card className="p-3 bg-panel/60">
              <span className="text-[11px] text-secondary block">Est. Material BOQ</span>
              <span className="text-sm font-semibold text-accent font-mono">₹9.46 Lakhs</span>
            </Card>
          </div>
        </section>
      </main>
    </div>
  );
}
export default AiGeneratorPage;
