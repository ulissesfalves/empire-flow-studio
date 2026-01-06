import os
import json
import random
import glob
import math
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts
import requests

# --- CORREÇÃO DO ERRO ANTIALIAS ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
# ----------------------------------

from moviepy.config import change_settings
# Seu caminho do ImageMagick (Mantenha o que funcionou para você)
caminho_magick = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

if os.path.exists(caminho_magick):
    change_settings({"IMAGEMAGICK_BINARY": caminho_magick})
else:
    print(f"⚠️ ERRO CRÍTICO: Não achei o ImageMagick em: {caminho_magick}")

from moviepy.editor import *
from dotenv import load_dotenv

load_dotenv()

PROJECTS_DIR = "backend/projects"
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs("backend/static", exist_ok=True) 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/projects", StaticFiles(directory=PROJECTS_DIR), name="projects")
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# --- MODELOS ---
class Asset(BaseModel):
    id: int
    type: str
    media_url: str
    audio_filename: str = ""
    duration: float
    text: str
    narration: str

class ProjectData(BaseModel):
    id: str
    created_at: str
    prompt: str
    plan: dict
    assets: list[Asset]
    video_filename: str | None = None

class DirectorPrompt(BaseModel):
    raw_prompt: str

class RegenerateRequest(BaseModel):
    project_id: str
    scene_id: int
    visual_search_term: str
    visual_ai_prompt: str

class RenderRequest(BaseModel):
    project_id: str
    assets: list[Asset]
    # NOVA OPÇÃO: 'static' (título) ou 'karaoke' (dinâmico)
    subtitle_style: str = "static" 

# --- FUNÇÕES AUXILIARES ---
def get_next_project_id():
    today = datetime.now().strftime("%Y%m%d")
    existing = glob.glob(os.path.join(PROJECTS_DIR, f"{today}_*"))
    count = len(existing) + 1
    return f"{today}_{count:03d}"

def save_project_state(project_id, prompt, plan, assets, video_filename=None):
    folder = os.path.join(PROJECTS_DIR, project_id)
    assets_data = []
    for a in assets:
        if isinstance(a, Asset): assets_data.append(a.dict())
        elif isinstance(a, dict): assets_data.append(a)
            
    data = {
        "id": project_id,
        "created_at": datetime.now().isoformat(),
        "prompt": prompt,
        "plan": plan,
        "assets": assets_data,
        "video_filename": video_filename
    }
    with open(os.path.join(folder, "project.json"), "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

def find_best_model():
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        r = requests.get(url)
        data = r.json()
        modelos_validos = []
        for m in data.get('models', []):
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                modelos_validos.append(m['name'])
        preferidos = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-pro']
        for pref in preferidos:
            if pref in modelos_validos: return pref
        if modelos_validos: return modelos_validos[0]
    except: pass
    return None

def call_gemini_api(prompt_text):
    model_name = find_best_model()
    if not model_name: return {"error": "Sem modelo válido"}
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.json()
    except: return None

def get_stock_video(query, page=1):
    if not PEXELS_API_KEY: return None
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&page={page}&orientation=portrait&size=medium"
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        if data.get('videos') and len(data['videos']) > 0:
            return data['videos'][0]['video_files'][0]['link']
    except: pass
    return None

def resize_to_fill(clip, target_width=720, target_height=1280):
    ratio_w = target_width / clip.w
    ratio_h = target_height / clip.h
    scale_factor = max(ratio_w, ratio_h)
    new_width = int(clip.w * scale_factor)
    new_height = int(clip.h * scale_factor)
    resized = clip.resize(newsize=(new_width, new_height))
    x_center = new_width / 2
    y_center = new_height / 2
    cropped = resized.crop(
        x1=int(x_center - target_width / 2),
        y1=int(y_center - target_height / 2),
        width=target_width,
        height=target_height
    )
    return cropped

# --- ROTAS DA API ---

@app.get("/api/projects")
def list_projects():
    projects = []
    folders = sorted(glob.glob(os.path.join(PROJECTS_DIR, "*")), reverse=True)
    for folder in folders:
        json_path = os.path.join(folder, "project.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    projects.append({
                        "id": data['id'],
                        "prompt": data.get('prompt', '')[:50] + "...",
                        "created_at": data.get('created_at'),
                        "has_video": bool(data.get('video_filename'))
                    })
            except: pass
    return projects

@app.get("/api/projects/{project_id}")
def load_project(project_id: str):
    json_path = os.path.join(PROJECTS_DIR, project_id, "project.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        base_url = f"http://localhost:8000/projects/{project_id}"
        if 'assets' not in data: data['assets'] = []
        for asset in data['assets']:
            if 'id' not in asset: continue
            if 'audio_filename' not in asset or not asset['audio_filename']:
                asset['audio_filename'] = f"audio_{asset['id']}.mp3"
            asset['audio_url'] = f"{base_url}/{asset['audio_filename']}"
        if data.get('video_filename'):
            data['video_url'] = f"{base_url}/{data['video_filename']}"
        return data
    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao abrir projeto {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/direct-video")
async def direct_video(req: DirectorPrompt):
    project_id = get_next_project_id()
    project_path = os.path.join(PROJECTS_DIR, project_id)
    os.makedirs(project_path, exist_ok=True)
    
    print(f"Novo projeto iniciado: {project_id}")
    prompt_sistema = """
    Aja como um Editor de Vídeo Profissional.
    REGRAS: Retorne JSON válido. Máximo 40s.
    Estrutura: {"scenes": [{"id": 1, "duration": 3.0, "narration": "...", "visual_search_term": "...", "visual_ai_prompt": "...", "overlay_text": "..."}]}
    USER PROMPT: """ + req.raw_prompt
    
    api_response = call_gemini_api(prompt_sistema)
    if not api_response or 'candidates' not in api_response:
        return {"error": "Erro no Gemini. Tente novamente."}
    try:
        raw_text = api_response['candidates'][0]['content']['parts'][0]['text']
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(clean_text)
    except Exception as e:
        return {"error": f"Erro JSON: {str(e)}"}

    assets = []
    for scene in plan['scenes']:
        scene_id = scene['id']
        voice = "en-US-ChristopherNeural"
        audio_filename = f"audio_{scene_id}.mp3"
        audio_path = os.path.join(project_path, audio_filename)
        communicate = edge_tts.Communicate(scene['narration'], voice)
        await communicate.save(audio_path)
        
        video_url = get_stock_video(scene['visual_search_term'])
        media_type = "video"
        if not video_url:
            clean_prompt = scene['visual_ai_prompt'].replace(" ", "%20")
            video_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?model=flux&width=720&height=1280&nologo=true"
            media_type = "image"
            
        assets.append(Asset(
            id=scene_id,
            type=media_type,
            media_url=video_url,
            audio_filename=audio_filename,
            duration=scene['duration'],
            text=scene['overlay_text'],
            narration=scene['narration']
        ))

    project_data = save_project_state(project_id, req.raw_prompt, plan, assets)
    base_url = f"http://localhost:8000/projects/{project_id}"
    for asset in project_data['assets']:
        asset['audio_url'] = f"{base_url}/{asset['audio_filename']}"
    return project_data

@app.post("/regenerate-scene")
def regenerate_scene(req: RegenerateRequest):
    print(f"Regenerando cena {req.scene_id} no projeto {req.project_id}...")
    random_page = random.randint(1, 15)
    video_url = get_stock_video(req.visual_search_term, page=random_page)
    media_type = "video"
    if not video_url:
        random_seed = random.randint(1, 99999)
        clean_prompt = req.visual_ai_prompt.replace(" ", "%20")
        video_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?model=flux&width=720&height=1280&nologo=true&seed={random_seed}"
        media_type = "image"
    return {"media_url": video_url, "type": media_type}

@app.post("/render-video")
def render_video(req: RenderRequest):
    print(f"Renderizando projeto {req.project_id} | Estilo: {req.subtitle_style}...")
    project_path = os.path.join(PROJECTS_DIR, req.project_id)
    clips = []
    TARGET_W, TARGET_H = 720, 1280
    
    for asset in req.assets:
        try:
            # 1. Carregar Audio
            audio_path = os.path.join(project_path, asset.audio_filename)
            if not os.path.exists(audio_path): continue
            
            audio_clip = AudioFileClip(audio_path)
            scene_duration = audio_clip.duration + 0.1

            # 2. Carregar Visual
            ext = 'mp4' if asset.type == 'video' else 'jpg'
            media_filename = f"media_{asset.id}.{ext}"
            media_path = os.path.join(project_path, media_filename)
            
            try:
                response = requests.get(asset.media_url, timeout=15)
                with open(media_path, 'wb') as f: f.write(response.content)
            except: continue

            if asset.type == 'video':
                raw = VideoFileClip(media_path)
                clip = resize_to_fill(raw, TARGET_W, TARGET_H)
                if clip.duration < scene_duration: clip = vfx.loop(clip, duration=scene_duration)
                clip = clip.subclip(0, scene_duration)
            else:
                raw = ImageClip(media_path)
                clip = resize_to_fill(raw, TARGET_W, TARGET_H).set_duration(scene_duration)
                clip = clip.resize(lambda t: 1 + 0.03*t)

            # 3. LÓGICA DE LEGENDAS (Static vs Karaoke)
            try:
                text_clips = []
                
                if req.subtitle_style == "karaoke":
                    # --- CORREÇÃO AQUI ---
                    # No Karaokê, usamos a NARRAÇÃO (texto longo), não o título curto.
                    texto_base = asset.narration 
                    
                    # Limpa pontuação básica para não ficar estranho
                    import re
                    texto_limpo = re.sub(r'[^\w\s]', '', texto_base)
                    
                    words = texto_limpo.split()
                    
                    # Agrupa em pedaços de 2 palavras (mais rápido/dinâmico)
                    chunk_size = 2
                    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                    
                    if not chunks: chunks = [""]
                    
                    # Distribui o tempo da cena igualmente
                    chunk_duration = scene_duration / len(chunks)
                    
                    for i, chunk_text in enumerate(chunks):
                        txt_clip = TextClip(
                            chunk_text.upper(), 
                            fontsize=80, # Fonte maior
                            color='yellow', 
                            font='Arial-Bold', 
                            stroke_color='black', 
                            stroke_width=4, 
                            size=(680, None), 
                            method='caption', 
                            align='center'
                        )
                        start_time = i * chunk_duration
                        # Define tempo e garante que apareça no centro
                        txt_clip = txt_clip.set_start(start_time).set_duration(chunk_duration).set_position(('center', 'center'))
                        text_clips.append(txt_clip)
                        
                    clip = CompositeVideoClip([clip, *text_clips])
                    
                else:
                    # --- ESTILO CLÁSSICO (TÍTULO) ---
                    # Aqui sim usamos o overlay_text (Título curto)
                    txt_clip = TextClip(
                        asset.text, 
                        fontsize=55, 
                        color='white', 
                        font='Arial-Bold', 
                        stroke_color='black', 
                        stroke_width=2, 
                        size=(680, None), 
                        method='caption', 
                        align='center'
                    )
                    txt_clip = txt_clip.set_position(('center', 'center')).set_duration(scene_duration)
                    clip = CompositeVideoClip([clip, txt_clip])
                    
            except Exception as e: 
                print(f"Erro na legenda: {e}")
                pass

            clip = clip.set_audio(audio_clip)
            clips.append(clip)
            
        except Exception as e:
            print(f"Erro cena {asset.id}: {e}")

    if clips:
        output_filename = "final_video.mp4"
        output_path = os.path.join(project_path, output_filename)
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac", ffmpeg_params=['-crf', '23'], threads=1)
        
        json_path = os.path.join(project_path, "project.json")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['video_filename'] = output_filename
        assets_data = []
        for a in req.assets:
            if isinstance(a, Asset): assets_data.append(a.dict())
            elif isinstance(a, dict): assets_data.append(a)
        data['assets'] = assets_data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return {"video_url": f"http://localhost:8000/projects/{req.project_id}/{output_filename}"}
    else:
        return {"error": "Falha no render"}