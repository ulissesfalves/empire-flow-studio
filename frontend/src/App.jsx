import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Clapperboard, Loader2, Search, Globe, Film, Bot, BrainCircuit, Cpu, Terminal, Clock, Mic, Download, Monitor, Smartphone } from 'lucide-react'; // ✅ Adicionado Monitor e Smartphone

export default function MagnateAI() {
  const [topic, setTopic] = useState("The Rise of NVIDIA");
  const [status, setStatus] = useState('idle');
  const [videoUrl, setVideoUrl] = useState(null);
  const [logs, setLogs] = useState([]);
  
  const [availableModels, setAvailableModels] = useState({ gemini: [], openai: [] });
  
  const [writerProvider, setWriterProvider] = useState("gemini");
  const [writerModel, setWriterModel] = useState("");
  
  const [criticProvider, setCriticProvider] = useState("gemini");
  const [criticModel, setCriticModel] = useState("");
  
  const [duration, setDuration] = useState("medium");
  const [voiceProvider, setVoiceProvider] = useState("no_preference");
  const [aspectRatio, setAspectRatio] = useState("horizontal"); // ✅ NOVO: Aspect Ratio
  
  const logsEndRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    axios.get('http://localhost:8000/available-models')
      .then(res => setAvailableModels(res.data))
      .catch(err => console.error(err));
  }, []);

  useEffect(() => {
    const list = availableModels[writerProvider] || [];
    if (list.length > 0) setWriterModel(list[0].id);
  }, [writerProvider, availableModels]);

  useEffect(() => {
    const list = availableModels[criticProvider] || [];
    if (list.length > 0) setCriticModel(list[0].id);
  }, [criticProvider, availableModels]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // ✅ Força reload do vídeo quando URL muda
  useEffect(() => {
    if (videoUrl && videoRef.current) {
      videoRef.current.load();
    }
  }, [videoUrl]);

  const handleCreateStream = () => {
    setStatus('streaming');
    setVideoUrl(null);
    setLogs([]);
    
    const url = `http://localhost:8000/create-stream?topic=${encodeURIComponent(topic)}&writer_provider=${writerProvider}&writer_model=${writerModel}&critic_provider=${criticProvider}&critic_model=${criticModel}&duration=${duration}&voice_provider=${voiceProvider}&aspect_ratio=${aspectRatio}`;
    
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.log) setLogs(prev => [...prev, `> ${data.log}`]);
      if (data.status === 'done') {
        console.log('✅ Vídeo pronto:', data.url); // ✅ Debug
        setVideoUrl(data.url);
        setStatus('done');
        eventSource.close();
      }
      if (data.status === 'error') {
        setStatus('error');
        setLogs(prev => [...prev, `🛑 ERRO: ${data.message}`]);
        eventSource.close();
      }
    };
    
    eventSource.onerror = (err) => {
      console.error('❌ EventSource error:', err);
      eventSource.close();
    };
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans flex flex-col md:flex-row">
      <div className="w-full md:w-1/3 p-6 border-r border-slate-800 flex flex-col gap-6 bg-slate-900 overflow-y-auto">
        <div className="flex items-center gap-3 text-emerald-500">
          <Globe size={28} />
          <h1 className="text-2xl font-bold tracking-tighter text-white">MAGNATE <span className="text-emerald-500">STUDIO</span></h1>
        </div>

        {/* DURAÇÃO */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <label className="text-xs font-bold text-slate-400 uppercase flex items-center gap-2 mb-3">
            <Clock size={14} /> Duração do Vídeo
          </label>
          <select value={duration} onChange={(e) => setDuration(e.target.value)} className="w-full bg-slate-950 text-white p-2 rounded border border-slate-600 text-sm outline-none focus:border-emerald-500">
            <option value="short">⚡ Curto (Shorts/TikTok - 30s)</option>
            <option value="medium">📺 Médio (Padrão YouTube - 3min)</option>
            <option value="long">📽️ Longo (Documentário - 10min+)</option>
            <option value="surprise">🎲 Surpreenda-me (IA Decide)</option>
          </select>
        </div>

        {/* FORMATO DE TELA - NOVO */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <label className="text-xs font-bold text-slate-400 uppercase flex items-center gap-2 mb-3">
            <Monitor size={14} /> Formato de Tela
          </label>
          <div className="flex gap-2">
            <button 
              onClick={() => setAspectRatio('vertical')} 
              className={`flex-1 py-3 rounded-lg text-xs font-bold border transition-all ${
                aspectRatio === 'vertical' 
                  ? 'bg-purple-600 text-white border-purple-500' 
                  : 'bg-slate-900 text-slate-400 border-slate-700 hover:border-slate-600'
              }`}
            >
              <Smartphone size={16} className="mx-auto mb-1" />
              <div>Vertical</div>
              <div className="text-[10px] opacity-60">9:16 Shorts</div>
            </button>
            <button 
              onClick={() => setAspectRatio('horizontal')} 
              className={`flex-1 py-3 rounded-lg text-xs font-bold border transition-all ${
                aspectRatio === 'horizontal' 
                  ? 'bg-blue-600 text-white border-blue-500' 
                  : 'bg-slate-900 text-slate-400 border-slate-700 hover:border-slate-600'
              }`}
            >
              <Monitor size={16} className="mx-auto mb-1" />
              <div>Horizontal</div>
              <div className="text-[10px] opacity-60">16:9 YouTube</div>
            </button>
          </div>
        </div>

        {/* NARRADOR (VOZ) */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <label className="text-xs font-bold text-slate-400 uppercase flex items-center gap-2 mb-3">
            <Mic size={14} /> Narrador (Voz)
          </label>
          <select value={voiceProvider} onChange={(e) => setVoiceProvider(e.target.value)} className="w-full bg-slate-950 text-white p-2 rounded border border-slate-600 text-sm outline-none focus:border-emerald-500">
            <option value="elevenlabs">ElevenLabs (Premium)</option>
            <option value="edge_tts">Edge TTS (Gratuito)</option>
            <option value="no_preference">Sem Preferência (Auto)</option>
          </select>
        </div>

        {/* ROTEIRISTA */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <label className="text-xs font-bold text-emerald-400 uppercase flex items-center gap-2 mb-3">
            <Bot size={14} /> Roteirista (Criativo)
          </label>
          <div className="flex gap-2 mb-3">
            <button onClick={() => setWriterProvider('gemini')} className={`flex-1 py-1 rounded text-xs font-bold border ${writerProvider === 'gemini' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400'}`}>Gemini</button>
            <button onClick={() => setWriterProvider('openai')} className={`flex-1 py-1 rounded text-xs font-bold border ${writerProvider === 'openai' ? 'bg-emerald-600 text-white' : 'bg-slate-900 text-slate-400'}`}>OpenAI</button>
          </div>
          <select value={writerModel} onChange={(e) => setWriterModel(e.target.value)} className="w-full bg-slate-950 text-white p-2 rounded border border-slate-600 text-sm">
            {availableModels[writerProvider]?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>

        {/* CRÍTICO */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <label className="text-xs font-bold text-red-400 uppercase flex items-center gap-2 mb-3">
            <BrainCircuit size={14} /> Crítico (Analítico)
          </label>
          <div className="flex gap-2 mb-3">
            <button onClick={() => setCriticProvider('gemini')} className={`flex-1 py-1 rounded text-xs font-bold border ${criticProvider === 'gemini' ? 'bg-red-600 text-white' : 'bg-slate-900 text-slate-400'}`}>Gemini</button>
            <button onClick={() => setCriticProvider('openai')} className={`flex-1 py-1 rounded text-xs font-bold border ${criticProvider === 'openai' ? 'bg-red-600 text-white' : 'bg-slate-900 text-slate-400'}`}>OpenAI</button>
          </div>
          <select value={criticModel} onChange={(e) => setCriticModel(e.target.value)} className="w-full bg-slate-950 text-white p-2 rounded border border-slate-600 text-sm">
            {availableModels[criticProvider]?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>

        <div className="flex-1 flex flex-col gap-4">
          <label className="text-xs font-bold text-slate-400 uppercase flex items-center gap-2">
            <Search size={14} /> Tópico Viral
          </label>
          <textarea value={topic} onChange={(e) => setTopic(e.target.value)} className="w-full h-32 bg-slate-950 p-4 rounded-lg border border-slate-700 text-white focus:border-emerald-500 outline-none resize-none text-lg font-medium" />
          
          <button onClick={handleCreateStream} disabled={status === 'streaming'} className={`w-full font-bold py-4 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg ${status === 'streaming' ? 'bg-slate-700 cursor-wait text-slate-300' : 'bg-emerald-600 hover:bg-emerald-500 text-white'}`}>
            {status === 'streaming' ? <><Loader2 className="animate-spin" /> BATALHANDO...</> : <><Film size={20} /> INICIAR PRODUÇÃO</>}
          </button>
        </div>

        <div className="bg-black rounded-lg p-4 font-mono text-xs text-green-400 border border-slate-800 h-48 overflow-hidden flex flex-col">
          <div className="flex items-center gap-2 text-slate-500 border-b border-slate-800 pb-2 mb-2"><Terminal size={12} /> LOGS</div>
          <div className="overflow-y-auto flex-1 scrollbar-hide">
            {logs.map((log, i) => <div key={i} className="mb-1 break-words">{log}</div>)}
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>

      <div className="flex-1 p-10 bg-black flex flex-col items-center justify-center relative">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{backgroundImage: 'radial-gradient(circle, #333 1px, transparent 1px)', backgroundSize: '30px 30px'}}></div>
        {!videoUrl ? (
          <div className="text-center opacity-30 flex flex-col items-center">
            <Clapperboard size={64} className="mb-4" />
            <h2 className="text-2xl font-bold">{status === 'streaming' ? 'PRODUZINDO...' : 'AGUARDANDO'}</h2>
          </div>
        ) : (
          <div className="w-full max-w-5xl z-10">
            <video 
              ref={videoRef}
              controls 
              autoPlay 
              className={`w-full rounded-xl shadow-2xl border border-slate-800 ${
                aspectRatio === 'vertical' ? 'max-w-md mx-auto' : 'max-w-5xl'
              }`}
              style={aspectRatio === 'vertical' ? { aspectRatio: '9/16' } : {}}
              onError={(e) => console.error('❌ Erro no player:', e)}
              onLoadedMetadata={() => console.log('✅ Vídeo carregado')}
            >
              <source src={videoUrl} type="video/mp4" />
              Seu navegador não suporta vídeo HTML5.
            </video>
            <a 
              href={videoUrl} 
              download 
              className="mt-6 inline-flex items-center justify-center w-full bg-slate-800 hover:bg-slate-700 text-white py-3 rounded-lg gap-2"
            >
              <Download size={18} /> Baixar Vídeo
            </a>
          </div>
        )}
      </div>
    </div>
  );
}