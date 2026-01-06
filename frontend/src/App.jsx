import { useState, useEffect } from 'react';
import axios from 'axios';
import { Clapperboard, Play, Loader2, Video, RefreshCw, AlertCircle, Download, CheckCircle, History, Type, Music2 } from 'lucide-react';

export default function ViralShortsStudio() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState('idle');
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [videoUrl, setVideoUrl] = useState(null);
  const [regeneratingId, setRegeneratingId] = useState(null);
  
  // Lista de projetos e ID atual
  const [projects, setProjects] = useState([]);
  const [currentProjectId, setCurrentProjectId] = useState(null);

  // Novo estado para o estilo da legenda
  const [subtitleStyle, setSubtitleStyle] = useState('karaoke'); // 'static' ou 'karaoke'

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/projects');
      setProjects(res.data);
    } catch (e) { console.error("Erro ao buscar projetos", e); }
  };

  const loadProject = async (id) => {
    setStatus('loading');
    try {
      const res = await axios.get(`http://localhost:8000/api/projects/${id}`);
      setData(res.data);
      setPrompt(res.data.prompt);
      setCurrentProjectId(res.data.id);
      setVideoUrl(res.data.video_url || null);
      setStatus(res.data.video_url ? 'success' : 'done');
    } catch (e) {
      alert("Erro ao abrir projeto. Verifique o terminal Python.");
    }
  };

  const handleGenerate = async () => {
    setStatus('loading');
    setData(null);
    setVideoUrl(null);
    setErrorMsg('');
    
    try {
      const res = await axios.post('http://localhost:8000/direct-video', { raw_prompt: prompt });
      if (res.data.error) {
        setStatus('error');
        setErrorMsg(res.data.error);
      } else {
        setData(res.data);
        setCurrentProjectId(res.data.id);
        setStatus('done');
        fetchProjects();
      }
    } catch (error) {
      setStatus('error');
      setErrorMsg("Erro de conexão.");
    }
  };

  const handleRender = async () => {
    if (!data || !data.assets) return;
    setStatus('rendering');
    try {
      const res = await axios.post('http://localhost:8000/render-video', { 
        project_id: currentProjectId,
        assets: data.assets,
        subtitle_style: subtitleStyle // Envia a escolha do usuário
      });
      if (res.data.video_url) {
        setVideoUrl(res.data.video_url);
        setStatus('success');
        fetchProjects();
      } else {
        setStatus('error');
        setErrorMsg("Erro ao renderizar vídeo.");
      }
    } catch (error) {
      setStatus('error');
      setErrorMsg("Falha na renderização.");
    }
  };

  const handleRegenerateScene = async (sceneId, searchTerm, aiPrompt) => {
    setRegeneratingId(sceneId);
    try {
      const res = await axios.post('http://localhost:8000/regenerate-scene', {
        project_id: currentProjectId,
        scene_id: sceneId,
        visual_search_term: searchTerm,
        visual_ai_prompt: aiPrompt
      });

      const newAssets = data.assets.map(asset => {
        if (asset.id === sceneId) {
          return { ...asset, media_url: res.data.media_url, type: res.data.type };
        }
        return asset;
      });

      setData({ ...data, assets: newAssets });
    } catch (error) {
      alert("Erro ao trocar cena.");
    } finally {
      setRegeneratingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white font-sans flex flex-col md:flex-row">
      
      {/* 1. Sidebar Histórico */}
      <div className="w-full md:w-64 bg-gray-950 border-r border-gray-800 p-4 flex flex-col h-screen overflow-y-auto">
        <div className="flex items-center gap-2 text-gray-400 mb-6 font-bold uppercase text-xs tracking-wider">
          <History size={16} /> Histórico de Projetos
        </div>
        <div className="space-y-2">
          {projects.map(p => (
            <button
              key={p.id}
              onClick={() => loadProject(p.id)}
              className={`w-full text-left p-3 rounded-lg text-sm transition-all border ${
                currentProjectId === p.id 
                  ? 'bg-yellow-900/30 border-yellow-600 text-yellow-500' 
                  : 'bg-gray-900 border-gray-800 text-gray-400 hover:bg-gray-800'
              }`}
            >
              <div className="font-bold">{p.id}</div>
              <div className="truncate text-xs opacity-70 mt-1">{p.prompt}</div>
              {p.has_video && <div className="mt-2 flex items-center gap-1 text-[10px] text-green-500"><CheckCircle size={10}/> Vídeo Pronto</div>}
            </button>
          ))}
          {projects.length === 0 && <div className="text-gray-600 text-xs text-center py-4">Nenhum projeto ainda</div>}
        </div>
      </div>

      {/* 2. Área de Controle */}
      <div className="w-full md:w-1/3 p-6 border-r border-gray-800 flex flex-col gap-6 bg-black">
        <div className="flex items-center gap-2 text-yellow-500">
          <Clapperboard size={32} />
          <h1 className="text-2xl font-bold tracking-tighter">VIRAL STUDIO</h1>
        </div>

        <div className="bg-gray-900 p-4 rounded-xl border border-gray-800 shadow-lg">
          <label className="text-xs font-bold text-gray-400 uppercase tracking-widest flex justify-between">
            Prompt do Diretor
            {currentProjectId && <span className="text-yellow-600">ID: {currentProjectId}</span>}
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="w-full h-48 bg-black mt-2 p-4 rounded-lg border border-gray-700 text-gray-300 focus:border-yellow-500 outline-none resize-none"
            placeholder="Descreva seu vídeo aqui..."
          />
          <button
            onClick={handleGenerate}
            disabled={status === 'loading' || status === 'rendering'}
            className="w-full mt-4 bg-yellow-600 hover:bg-yellow-500 text-black font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-all"
          >
            {status === 'loading' ? <Loader2 className="animate-spin" /> : <Play size={20} fill="black" />}
            {status === 'loading' ? 'CRIANDO NOVO PROJETO...' : 'NOVO PROJETO'}
          </button>
        </div>

        {/* Botão Renderizar */}
        {data && (
          <div className="bg-gray-900 p-4 rounded-xl border border-gray-700 animate-fade-in">
            <h3 className="font-bold mb-4 text-gray-300 flex items-center gap-2">
              <Type size={18} /> Estilo da Legenda
            </h3>
            
            {/* Seletor de Estilo */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <button
                onClick={() => setSubtitleStyle('static')}
                className={`p-3 rounded border text-sm font-bold flex flex-col items-center gap-1 transition-all ${
                  subtitleStyle === 'static' 
                    ? 'bg-white text-black border-white' 
                    : 'bg-gray-800 text-gray-400 border-gray-600 hover:bg-gray-700'
                }`}
              >
                <span className="text-xs uppercase">Título Fixo</span>
                <span>"Texto da Tela"</span>
              </button>
              
              <button
                onClick={() => setSubtitleStyle('karaoke')}
                className={`p-3 rounded border text-sm font-bold flex flex-col items-center gap-1 transition-all ${
                  subtitleStyle === 'karaoke' 
                    ? 'bg-yellow-500 text-black border-yellow-500' 
                    : 'bg-gray-800 text-gray-400 border-gray-600 hover:bg-gray-700'
                }`}
              >
                <span className="text-xs uppercase">Karaokê Viral</span>
                <span>"Texto Dinâmico"</span>
              </button>
            </div>

            <button
              onClick={handleRender}
              disabled={status === 'rendering'}
              className={`w-full font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-all ${
                status === 'success' ? 'bg-green-600 hover:bg-green-500 text-white' : 'bg-pink-600 hover:bg-pink-500 text-white'
              }`}
            >
              {status === 'rendering' ? (
                <> <Loader2 className="animate-spin" /> RENDERIZANDO... </>
              ) : status === 'success' ? (
                <> <CheckCircle /> VÍDEO PRONTO! (REFAZER) </>
              ) : (
                <> <Video /> RENDERIZAR VÍDEO MP4 </>
              )}
            </button>

            {videoUrl && (
              <a 
                href={videoUrl} 
                download={`viral_video_${currentProjectId}.mp4`}
                className="mt-3 block w-full bg-gray-800 hover:bg-gray-700 text-center py-2 rounded text-sm text-gray-300 border border-gray-600 flex items-center justify-center gap-2"
                target="_blank"
              >
                <Download size={16} /> Baixar Arquivo
              </a>
            )}
          </div>
        )}
        
        {status === 'error' && (
          <div className="p-4 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm flex gap-2">
            <AlertCircle className="shrink-0" /> {errorMsg}
          </div>
        )}
      </div>

      {/* 3. Área de Preview */}
      <div className="flex-1 p-6 bg-gray-950 overflow-y-auto h-screen">
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
          <Video size={20} /> Preview da Timeline
        </h2>
        
        {videoUrl && (
          <div className="mb-8 max-w-sm mx-auto border-2 border-green-500 rounded-lg overflow-hidden shadow-2xl shadow-green-900/50">
            <video src={videoUrl} controls autoPlay className="w-full" />
            <div className="bg-green-900 text-center text-xs py-1 text-green-100 font-bold uppercase">Resultado Final - {currentProjectId}</div>
          </div>
        )}

        <div className="grid gap-4 max-w-3xl mx-auto pb-20">
          {data && data.assets && data.assets.map((scene, idx) => {
            const scenePlan = data.plan.scenes.find(s => s.id === scene.id);
            return (
              <div key={idx} className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden flex shadow-lg group">
                <div className="w-32 h-48 bg-black relative flex-shrink-0">
                   {scene.type === 'video' ? (
                     <video key={scene.media_url} src={scene.media_url} className="w-full h-full object-cover opacity-80" muted loop />
                   ) : (
                     <img key={scene.media_url} src={scene.media_url} className="w-full h-full object-cover opacity-80" />
                   )}
                   
                   <button 
                      onClick={() => handleRegenerateScene(scene.id, scenePlan?.visual_search_term || "scene", scenePlan?.visual_ai_prompt || "scene")}
                      disabled={regeneratingId === scene.id}
                      className="absolute top-2 right-2 bg-black/60 hover:bg-yellow-600 p-1.5 rounded-full text-white transition-all z-10 border border-white/20"
                      title="Trocar Cena"
                   >
                      {regeneratingId === scene.id ? <Loader2 size={14} className="animate-spin"/> : <RefreshCw size={14} />}
                   </button>

                   <div className="absolute bottom-0 w-full bg-black/80 text-[10px] text-center py-1 text-gray-400">
                     {scene.duration}s
                   </div>
                </div>
                <div className="p-4 flex flex-col justify-between flex-1">
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-yellow-500 font-bold text-xs uppercase">CENA {idx + 1}</span>
                      <span className="text-[10px] text-gray-500 border border-gray-700 px-1 rounded">{scene.type.toUpperCase()}</span>
                    </div>
                    <p className="text-gray-300 text-sm italic mb-3">"{scene.narration}"</p>
                    <span className="text-xs font-bold bg-white text-black px-2 py-0.5 rounded">{scene.text}</span>
                  </div>
                  <audio controls src={scene.audio_url} className="w-full h-8 block mt-2" />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}