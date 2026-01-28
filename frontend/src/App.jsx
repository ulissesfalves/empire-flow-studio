import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { 
  Play, StopCircle, Activity, Layers, Cpu, Film, 
  Mic, Brain, Type as TypeIcon, Smartphone, Monitor, 
  Terminal as TerminalIcon, Image as ImageIcon, 
  Download, RefreshCw, FileText, CheckCircle2, Sparkles,
  Edit3, Wand2
} from 'lucide-react';

// --- SUB-COMPONENT: TERMINAL (LOGS DO SISTEMA) ---
const Terminal = ({ logs }) => {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="h-full bg-slate-950 rounded-xl border border-slate-800 flex flex-col overflow-hidden font-mono text-xs shadow-inner">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-2 text-slate-400">
          <TerminalIcon size={14} />
          <span className="font-semibold tracking-wider">SYSTEM LOGS // STREAM</span>
        </div>
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50"></div>
        </div>
      </div>
      <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-1.5">
        {logs.length === 0 && (
          <span className="text-slate-600 italic">Waiting for process initiation...</span>
        )}
        {logs.map((log, i) => {
          const logText = typeof log === 'string' ? log : log.text;
          const logTime = typeof log === 'string' ? new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'}) : log.time;
          
          return (
            <div key={i} className={`break-words ${
              logText.includes('ERRO') || logText.includes('❌') ? 'text-red-400' : 
              logText.includes('✅') || logText.includes('🎉') ? 'text-emerald-400' : 
              logText.includes('🎬') || logText.includes('🎥') ? 'text-purple-400' :
              logText.includes('🧠') ? 'text-blue-400' :
              'text-slate-300'
            }`}>
              <span className="opacity-30 mr-2">[{logTime}]</span>
              {logText}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
};

// --- SUB-COMPONENT: LIVE CONTEXT (PREVIEW + SEO) ---
const ScriptView = ({ status, logs, youtubeMetadata }) => {
  const isGenerating = status === 'streaming';
  
  const meaningfulLogs = logs.filter(l => {
    const text = typeof l === 'string' ? l : l.text;
    return text.includes("Ato") || 
           text.includes("Cena") || 
           text.includes("Nota:") ||
           text.includes("Salvando como");
  });

  return (
    <div className="h-full bg-slate-900/40 rounded-xl border border-slate-800 flex flex-col overflow-hidden relative backdrop-blur-sm">
      <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
        <h2 className="text-sm font-bold flex items-center gap-2 text-slate-200">
          <FileText size={16} className="text-purple-500" /> Live Pipeline Context
        </h2>
        {isGenerating && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 animate-pulse font-mono">
            PROCESSING
          </span>
        )}
      </div>
      
      <div className="flex-1 p-4 overflow-y-auto custom-scrollbar space-y-4">
        {status === 'idle' && !youtubeMetadata ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600 opacity-40 gap-3">
            <Brain size={48} />
            <p className="text-sm">AI Brain is waiting for input...</p>
          </div>
        ) : (
          <>
             <div className="space-y-2">
                {meaningfulLogs.length === 0 && !youtubeMetadata && (
                  <div className="flex flex-col items-center justify-center h-20 text-slate-500 gap-2">
                    <RefreshCw className="animate-spin" size={20} />
                    <span className="text-xs">Initializing Neural Networks...</span>
                  </div>
                )}
                {meaningfulLogs.map((l, idx) => {
                  const logText = typeof l === 'string' ? l : l.text;
                  return (
                    <div key={idx} className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/50 animate-in fade-in slide-in-from-bottom-2 duration-500">
                      <div className="flex gap-3">
                        <div className="mt-1">
                          {logText.includes("Ato") ? <Film size={14} className="text-purple-400"/> : 
                           logText.includes("Cena") ? <ImageIcon size={14} className="text-blue-400"/> :
                           logText.includes("Nota") ? <Activity size={14} className="text-yellow-400"/> :
                           <CheckCircle2 size={14} className="text-emerald-400"/>}
                        </div>
                        <p className="text-sm text-slate-300 font-medium leading-relaxed">{logText.replace(/^> /, '')}</p>
                      </div>
                    </div>
                  );
                })}
             </div>

             {youtubeMetadata && (
               <div className="mt-6 border-t border-slate-700 pt-4 animate-in zoom-in-95 duration-500">
                 <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-emerald-500/30 rounded-xl p-4 shadow-lg">
                   <div className="flex items-center gap-2 mb-4 text-emerald-400">
                     <Sparkles size={16} />
                     <h3 className="text-xs font-bold uppercase tracking-wider">YouTube Optimization Ready</h3>
                   </div>
                   
                   <div className="space-y-4">
                     <div>
                       <label className="text-[10px] uppercase text-slate-500 font-bold block mb-1">Title Options</label>
                       <div className="space-y-2">
                         {(() => {
                           // Extrai os títulos do metadata
                           const titles = youtubeMetadata.titles || youtubeMetadata.title;
                           
                           if (Array.isArray(titles)) {
                             // Se for array, mostra todos
                             return titles.map((t, idx) => (
                               <div key={idx} className="bg-black/30 p-2 rounded border border-slate-800 text-sm text-white font-medium select-all hover:border-emerald-500/30 transition-colors">
                                 {idx + 1}. {t}
                               </div>
                             ));
                           } else if (typeof titles === 'string') {
                             // Se for string, mostra direto
                             return (
                               <div className="bg-black/30 p-2 rounded border border-slate-800 text-sm text-white font-medium select-all">
                                 {titles}
                               </div>
                             );
                           } else {
                             return (
                               <div className="bg-black/30 p-2 rounded border border-slate-800 text-sm text-slate-500 italic">
                                 No title generated
                               </div>
                             );
                           }
                         })()}
                       </div>
                     </div>
                     
                     <div>
                       <label className="text-[10px] uppercase text-slate-500 font-bold block mb-1">Description</label>
                       <div className="bg-black/30 p-2 rounded border border-slate-800 text-xs text-slate-300 whitespace-pre-wrap select-all">
                         {youtubeMetadata.description || 'No description generated'}
                       </div>
                     </div>

                     <div>
                        <label className="text-[10px] uppercase text-slate-500 font-bold block mb-1">Tags (Copy & Paste)</label>
                        <div className="bg-black/30 p-2 rounded border border-slate-800 text-xs text-slate-400 font-mono select-all hover:border-emerald-500/50 transition-colors cursor-text">
                          {(() => {
                            const tags = youtubeMetadata.tags;
                            
                            // Se for objeto com categorias (broad, medium, long_tail)
                            if (tags && typeof tags === 'object' && !Array.isArray(tags)) {
                              const allTags = [
                                ...(tags.broad || []),
                                ...(tags.medium || []),
                                ...(tags.long_tail || [])
                              ];
                              return allTags.filter(t => t).join(', ');
                            }
                            
                            // Se for array direto
                            if (Array.isArray(tags)) {
                              return tags.join(', ');
                            }
                            
                            // Se for string
                            if (typeof tags === 'string') {
                              return tags.replace(/[\[\]"]/g, '').split(',').map(t => t.trim()).filter(t => t).join(', ');
                            }
                            
                            return 'No tags generated';
                          })()}
                        </div>
                     </div>
                   </div>
                 </div>
               </div>
             )}
          </>
        )}
      </div>
    </div>
  );
};

// --- APP PRINCIPAL ---
export default function MagnateAI() {
  const [status, setStatus] = useState('idle');
  const [logs, setLogs] = useState([]);
  const [videoUrl, setVideoUrl] = useState(null);
  const eventSourceRef = useRef(null);
  const [youtubeMetadata, setYoutubeMetadata] = useState(null);

  // NOVA: Toggle entre AI e Manual
  const [scriptMode, setScriptMode] = useState('ai'); // 'ai' ou 'manual'
  const [manualScript, setManualScript] = useState('');

  const [topic, setTopic] = useState("The hidden history of Bitcoin and its impact on modern finance");
  const [duration, setDuration] = useState("medium");
  const [availableModels, setAvailableModels] = useState({ gemini: [], openai: [] });
  const [writerProvider, setWriterProvider] = useState("gemini");
  const [writerModel, setWriterModel] = useState("");
  const [criticProvider, setCriticProvider] = useState("gemini");
  const [criticModel, setCriticModel] = useState("");
  const [availableVoices, setAvailableVoices] = useState({ voices: [], styles: [] });
  const [voiceConfig, setVoiceConfig] = useState("");
  const [voiceStyle, setVoiceStyle] = useState("documentary");
  const [availableImageProviders, setAvailableImageProviders] = useState({ providers: [], visual_styles: [] });
  const [imageProvider, setImageProvider] = useState("pollinations");
  const [visualStyle, setVisualStyle] = useState("documentary");
  const [aspectRatio, setAspectRatio] = useState("horizontal");
  const [useConsistentSeed, setUseConsistentSeed] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [modelsRes, voicesRes, imagesRes] = await Promise.all([
          axios.get('http://localhost:8000/available-models'),
          axios.get('http://localhost:8000/available-voices'),
          axios.get('http://localhost:8000/available-image-providers')
        ]);
        setAvailableModels(modelsRes.data);
        if (modelsRes.data.gemini?.length) {
          setWriterModel(modelsRes.data.gemini[0].id);
          setCriticModel(modelsRes.data.gemini[0].id);
        }
        setAvailableVoices(voicesRes.data);
        if (voicesRes.data.voices?.length) setVoiceConfig(voicesRes.data.voices[0].id);
        setAvailableImageProviders(imagesRes.data);
      } catch (err) {
        console.error("Erro ao conectar com backend:", err);
        setLogs(prev => [...prev, { 
          text: "❌ Error connecting to backend. Is main.py running?",
          time: new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})
        }]);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    const list = availableModels[writerProvider] || [];
    if (list.length > 0) setWriterModel(list[0].id);
  }, [writerProvider, availableModels]);

  useEffect(() => {
    const list = availableModels[criticProvider] || [];
    if (list.length > 0) setCriticModel(list[0].id);
  }, [criticProvider, availableModels]);

  const handleIgnite = () => {
    if (scriptMode === 'ai' && !topic.trim()) return;
    if (scriptMode === 'manual' && !manualScript.trim()) return;
    
    setStatus('streaming');
    setVideoUrl(null);
    setLogs([]);
    setYoutubeMetadata(null);
    if (eventSourceRef.current) eventSourceRef.current.close();

    const params = new URLSearchParams({
      topic: scriptMode === 'ai' ? topic : 'Custom Script',
      writer_provider: writerProvider,
      writer_model: writerModel,
      critic_provider: criticProvider,
      critic_model: criticModel,
      duration,
      voice_config: voiceConfig,
      voice_style: voiceStyle,
      aspect_ratio: aspectRatio,
      image_provider: imageProvider,
      use_consistent_seed: useConsistentSeed,
      visual_style: visualStyle,
      script_mode: scriptMode,
      manual_script: scriptMode === 'manual' ? manualScript : ''
    });

    const url = `http://localhost:8000/create-stream?${params.toString()}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      if (event.data.startsWith(":")) return;
      const data = JSON.parse(event.data);
      if (data.youtube_metadata) setYoutubeMetadata(data.youtube_metadata);
      if (data.log) {
        setLogs(prev => [...prev, { 
          text: data.log, 
          time: new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'}) 
        }]);
      }
      if (data.status === 'done') {
        setVideoUrl(data.url);
        setStatus('done');
        es.close();
      }
      if (data.status === 'error') {
        setStatus('error');
        setLogs(prev => [...prev, { 
          text: `🛑 FATAL ERROR: ${data.message}`,
          time: new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})
        }]);
        es.close();
      }
    };

    es.onerror = (err) => {
      es.close();
      if (status !== 'done') setStatus('error');
    };
  };

  const handleAbort = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setLogs(prev => [...prev, { 
        text: "🛑 Sequence Aborted by User.",
        time: new Date().toLocaleTimeString([], {hour12:false, hour:'2-digit', minute:'2-digit', second:'2-digit'})
      }]);
      setStatus('idle');
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-100 font-sans selection:bg-purple-500/30 overflow-hidden">
      <div className="w-80 border-r border-slate-800 bg-slate-900/50 flex flex-col p-5 z-20 shadow-2xl overflow-y-auto custom-scrollbar backdrop-blur-md">
        <div className="flex items-center gap-3 mb-8 flex-shrink-0">
          <div className="p-2 bg-gradient-to-br from-purple-600 to-blue-600 rounded-lg shadow-[0_0_15px_rgba(147,51,234,0.5)]">
            <Cpu size={24} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">ViralFlow AI</h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Automated Engine</p>
          </div>
        </div>

        <div className="space-y-6 flex-1">
          {/* NOVA SEÇÃO: Mode Toggle */}
          <div className="group">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block group-hover:text-purple-400 transition-colors">
              Script Source
            </label>
            <div className="grid grid-cols-2 gap-2 mb-3">
              <button
                onClick={() => setScriptMode('ai')}
                disabled={status === 'streaming'}
                className={`flex items-center justify-center gap-1.5 p-2.5 rounded text-[10px] font-bold border transition-all ${
                  scriptMode === 'ai' 
                    ? 'bg-purple-500/10 border-purple-500 text-purple-400' 
                    : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-600'
                }`}
              >
                <Wand2 size={12} /> AI Generated
              </button>
              <button
                onClick={() => setScriptMode('manual')}
                disabled={status === 'streaming'}
                className={`flex items-center justify-center gap-1.5 p-2.5 rounded text-[10px] font-bold border transition-all ${
                  scriptMode === 'manual' 
                    ? 'bg-blue-500/10 border-blue-500 text-blue-400' 
                    : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-600'
                }`}
              >
                <Edit3 size={12} /> Manual Script
              </button>
            </div>

            {scriptMode === 'ai' ? (
              <>
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-purple-500 focus:border-purple-500 outline-none transition-all resize-none h-24 mb-2 placeholder:text-slate-600 shadow-inner"
                  placeholder="Enter your viral topic..."
                  disabled={status === 'streaming'}
                />
                <select
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  disabled={status === 'streaming'}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs focus:ring-1 focus:ring-purple-500 outline-none shadow-sm"
                >
                  <option value="short">⚡ Short (30s - High Pace)</option>
                  <option value="medium">📺 Medium (3m - Standard)</option>
                  <option value="long">📽️ Long (10m+ - Deep Dive)</option>
                  <option value="surprise">🎲 Auto-Optimize</option>
                </select>
              </>
            ) : (
              <div className="space-y-2">
                <textarea
                  value={manualScript}
                  onChange={(e) => setManualScript(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all resize-none h-48 placeholder:text-slate-600 shadow-inner font-mono"
                  placeholder="Paste your script here...

Each paragraph = one scene.

Example:
The world is changing faster than ever before.

But most people don't see what's really happening.

Behind the scenes, a silent revolution is taking place."
                  disabled={status === 'streaming'}
                />
                <p className="text-[10px] text-slate-500 italic">
                  💡 Tip: Each paragraph will become a separate scene with visuals and narration.
                </p>
              </div>
            )}
          </div>

          {/* AI Models - Só mostra no modo AI */}
          {scriptMode === 'ai' && (
            <div className="group">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block flex items-center gap-1 group-hover:text-purple-400 transition-colors">
                <Brain size={12} /> Intelligence Models
              </label>
              <div className="mb-3">
                <span className="text-[10px] text-slate-400 font-semibold mb-1 block flex justify-between">
                  <span>Script Writer</span>
                  <span className="text-[9px] opacity-50 bg-slate-800 px-1 rounded">CREATIVE</span>
                </span>
                <div className="flex gap-1 mb-1">
                  {['gemini', 'openai'].map(p => (
                    <button 
                      key={p} 
                      onClick={() => setWriterProvider(p)}
                      disabled={status === 'streaming'}
                      className={`flex-1 text-[9px] uppercase font-bold py-1.5 rounded border transition-all ${writerProvider === p ? 'bg-purple-600 border-purple-500 text-white shadow-md' : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-600'}`}
                    >{p}</button>
                  ))}
                </div>
                <select 
                  value={writerModel} onChange={(e) => setWriterModel(e.target.value)}
                  disabled={status === 'streaming'}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
                >
                  {availableModels[writerProvider]?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>

              <div>
                <span className="text-[10px] text-slate-400 font-semibold mb-1 block flex justify-between">
                  <span>Viral Critic</span>
                  <span className="text-[9px] opacity-50 bg-slate-800 px-1 rounded">ANALYTICAL</span>
                </span>
                <div className="flex gap-1 mb-1">
                  {['gemini', 'openai'].map(p => (
                    <button 
                      key={p} 
                      onClick={() => setCriticProvider(p)}
                      disabled={status === 'streaming'}
                      className={`flex-1 text-[9px] uppercase font-bold py-1.5 rounded border transition-all ${criticProvider === p ? 'bg-red-600 border-red-500 text-white shadow-md' : 'bg-slate-950 border-slate-800 text-slate-500 hover:border-slate-600'}`}
                    >{p}</button>
                  ))}
                </div>
                <select 
                  value={criticModel} onChange={(e) => setCriticModel(e.target.value)}
                  disabled={status === 'streaming'}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
                >
                  {availableModels[criticProvider]?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </div>
            </div>
          )}

          <div className="group">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block flex items-center gap-1 group-hover:text-purple-400 transition-colors">
              <ImageIcon size={12} /> Visual Engine
            </label>
            <div className="space-y-2">
              <select 
                value={imageProvider} onChange={(e) => setImageProvider(e.target.value)}
                disabled={status === 'streaming'}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
              >
                {availableImageProviders.providers.map(p => (
                  <option key={p.id} value={p.id} disabled={!p.available}>
                    {p.name} {p.cost !== "Grátis" ? '($)' : ''}
                  </option>
                ))}
              </select>
              
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setAspectRatio('vertical')}
                  disabled={status === 'streaming'}
                  className={`flex items-center justify-center gap-1.5 p-2 rounded text-[10px] font-bold border transition-all ${aspectRatio === 'vertical' ? 'bg-purple-500/10 border-purple-500 text-purple-400' : 'bg-slate-950 border-slate-800 text-slate-500'}`}
                >
                  <Smartphone size={12} /> 9:16
                </button>
                <button
                  onClick={() => setAspectRatio('horizontal')}
                  disabled={status === 'streaming'}
                  className={`flex items-center justify-center gap-1.5 p-2 rounded text-[10px] font-bold border transition-all ${aspectRatio === 'horizontal' ? 'bg-blue-500/10 border-blue-500 text-blue-400' : 'bg-slate-950 border-slate-800 text-slate-500'}`}
                >
                  <Monitor size={12} /> 16:9
                </button>
              </div>

              <select 
                value={visualStyle} onChange={(e) => setVisualStyle(e.target.value)}
                disabled={status === 'streaming'}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
              >
                {availableImageProviders.visual_styles.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>

              <label className="flex items-center gap-2 cursor-pointer p-1 hover:bg-slate-900 rounded">
                <input 
                  type="checkbox" 
                  checked={useConsistentSeed} 
                  onChange={(e) => setUseConsistentSeed(e.target.checked)}
                  disabled={status === 'streaming'}
                  className="w-3 h-3 rounded border-slate-600 bg-slate-950 text-purple-600 focus:ring-purple-500"
                />
                <div className="flex items-center gap-1 text-[10px] text-slate-300">
                  <Sparkles size={10} className="text-yellow-500" />
                  <span>Consistent Characters (Fixed Seed)</span>
                </div>
              </label>
            </div>
          </div>

          <div className="group">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 block flex items-center gap-1 group-hover:text-purple-400 transition-colors">
              <Mic size={12} /> Audio & Voice
            </label>
            <div className="space-y-2">
              <select 
                value={voiceConfig} onChange={(e) => setVoiceConfig(e.target.value)}
                disabled={status === 'streaming'}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
              >
                {availableVoices.voices.map(v => (
                  <option key={v.id} value={v.id} disabled={!v.available}>{v.name}</option>
                ))}
              </select>
              <select 
                value={voiceStyle} onChange={(e) => setVoiceStyle(e.target.value)}
                disabled={status === 'streaming'}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs outline-none"
              >
                {availableVoices.styles.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-800 flex-shrink-0">
          {status === 'idle' || status === 'done' || status === 'error' ? (
            <button
              onClick={handleIgnite}
              className="w-full group relative flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white py-3.5 rounded-lg font-bold hover:shadow-[0_0_20px_rgba(147,51,234,0.4)] transition-all duration-300 active:scale-95"
            >
              <Play size={18} className="fill-white group-hover:scale-110 transition-transform" />
              <span>IGNITE ENGINE</span>
            </button>
          ) : (
            <button
              onClick={handleAbort}
              className="w-full flex items-center justify-center gap-2 bg-red-500/10 text-red-400 border border-red-500/30 py-3.5 rounded-lg font-bold hover:bg-red-500/20 transition-all active:scale-95"
            >
              <StopCircle size={18} />
              <span>ABORT SEQUENCE</span>
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0 bg-black relative">
        <div className="absolute inset-0 opacity-20 pointer-events-none" 
             style={{backgroundImage: 'radial-gradient(circle, #1e293b 1px, transparent 1px)', backgroundSize: '20px 20px'}}></div>

        <header className="h-14 border-b border-slate-800 bg-slate-900/40 flex items-center justify-between px-6 backdrop-blur-sm z-10">
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border ${status === 'streaming' ? 'bg-purple-900/20 border-purple-500/30' : 'bg-slate-900 border-slate-800'}`}>
              <div className={`w-2 h-2 rounded-full ${status === 'streaming' ? 'bg-purple-500 animate-pulse' : status === 'done' ? 'bg-green-500' : 'bg-slate-500'}`} />
              <span className="text-[10px] font-mono uppercase text-slate-400 tracking-wider">
                Status: <span className={status === 'streaming' ? 'text-purple-300' : status === 'done' ? 'text-green-300' : 'text-slate-200'}>{status.toUpperCase()}</span>
              </span>
            </div>
            {status === 'streaming' && <span className="text-xs text-purple-400 animate-fade-in font-mono">&gt; Processing Neural Pipeline...</span>}
          </div>
          
          <div className="flex items-center gap-6 text-[10px] font-mono text-slate-500">
            <div className="flex items-center gap-2">
              <Activity size={12} />
              <span>CPU: {status === 'streaming' ? '82%' : '14%'}</span>
            </div>
            <div className="flex items-center gap-2">
              <Layers size={12} />
              <span>MEM: {status === 'streaming' ? '4.1GB' : '1.2GB'}</span>
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-0 overflow-hidden z-10">
          <div className="flex flex-col gap-6 min-h-0">
            <ScriptView status={status} logs={logs} youtubeMetadata={youtubeMetadata} />
          </div>

          <div className="flex flex-col gap-6 min-h-0">
            <div className="flex-1 min-h-0">
              <Terminal logs={logs} />
            </div>

            <div className="flex-1 min-h-0 bg-slate-900/30 rounded-xl border border-slate-800 flex items-center justify-center p-4 shadow-lg backdrop-blur-sm relative group">
              <div 
                className={`relative overflow-hidden bg-black shadow-2xl transition-all duration-700 border border-slate-800 ${
                  aspectRatio === 'vertical' 
                    ? 'h-full aspect-[9/16] rounded-lg' 
                    : 'w-full aspect-[16/9] max-h-full rounded-lg'
                }`}
              >
                {videoUrl ? (
                  <div className="w-full h-full relative">
                    <video 
                      src={videoUrl} 
                      controls 
                      className="w-full h-full object-contain bg-black" 
                      autoPlay 
                    />
                    <a 
                      href={videoUrl} 
                      download
                      className="absolute bottom-4 right-4 bg-white/10 hover:bg-white/20 backdrop-blur-md text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Download Video"
                    >
                      <Download size={20} />
                    </a>
                  </div>
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-slate-700">
                    {status === 'streaming' ? (
                      <div className="flex flex-col items-center gap-3 animate-pulse">
                        <RefreshCw size={32} className="animate-spin text-purple-600" />
                        <div className="text-center">
                          <p className="text-purple-400 font-mono text-xs tracking-widest">RENDERING ASSETS</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        <Film size={48} className="mb-2 opacity-20" />
                        <p className="text-xs font-mono opacity-40">AWAITING OUTPUT</p>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}