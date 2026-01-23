import os
import json
import re
import time
import asyncio
import subprocess
import multiprocessing
from datetime import datetime
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts
import requests
from duckduckgo_search import DDGS
import PIL.Image
import numpy as np
import whisper
from moviepy.config import change_settings
from moviepy.editor import *
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import random

# ==========================================
# OTIMIZAÇÃO #7: CONFIGURAÇÕES GLOBAIS
# ==========================================

# Limitar threads do NumPy/OpenCV (evita sobrecarga)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

# Configurações do Whisper
os.environ["WHISPER_CPP_THREADS"] = str(max(1, multiprocessing.cpu_count() - 1))

# Garbage Collector menos agressivo
import gc
gc.set_threshold(700, 10, 10)

# Prioridade baixa para FFmpeg no Windows
if os.name == 'nt':
    original_subprocess_run = subprocess.run
    def run_with_low_priority(*args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = subprocess.BELOW_NORMAL_PRIORITY_CLASS
        return original_subprocess_run(*args, **kwargs)
    subprocess.run = run_with_low_priority

# Cache de transformações PIL
Image.MAX_IMAGE_PIXELS = None

# ==========================================
# PERFIS DE PERFORMANCE
# ==========================================

PERFORMANCE_PROFILES = {
    "ultra_low": {
        "description": "Máximo desempenho, qualidade mínima",
        "resolution": (854, 480),
        "fps": 20,
        "preset": "ultrafast",
        "bitrate": "800k",
        "crf": "28",
        "threads": 1,
        "whisper_model": "tiny",
        "enable_subtitles": False,
    },
    "low": {
        "description": "Hardware modesto (padrão recomendado)",
        "resolution": (1280, 720),
        "fps": 24,
        "preset": "veryfast",
        "bitrate": "1500k",
        "crf": "25",
        "threads": max(1, multiprocessing.cpu_count() // 2),
        "whisper_model": "tiny",
        "enable_subtitles": True,
    },
    "balanced": {
        "description": "Balanceado (CPUs 4+ núcleos)",
        "resolution": (1280, 720),
        "fps": 30,
        "preset": "fast",
        "bitrate": "2500k",
        "crf": "23",
        "threads": max(2, multiprocessing.cpu_count() - 1),
        "whisper_model": "base",
        "enable_subtitles": True,
    },
    "quality": {
        "description": "Máxima qualidade (hardware potente)",
        "resolution": (1920, 1080),
        "fps": 30,
        "preset": "medium",
        "bitrate": "5000k",
        "crf": "20",
        "threads": multiprocessing.cpu_count() - 1,
        "whisper_model": "base",
        "enable_subtitles": True,
    }
}

# ==========================================
# FORMATOS DE ASPECT RATIO
# ==========================================

ASPECT_RATIOS = {
    "vertical": {
        "name": "Vertical (Shorts/TikTok/Reels)",
        "ratio": "9:16",
        "resolutions": {
            "ultra_low": (480, 854),
            "low": (720, 1280),
            "balanced": (720, 1280),
            "quality": (1080, 1920)
        }
    },
    "horizontal": {
        "name": "Horizontal (YouTube/TV)",
        "ratio": "16:9",
        "resolutions": {
            "ultra_low": (854, 480),
            "low": (1280, 720),
            "balanced": (1280, 720),
            "quality": (1920, 1080)
        }
    }
}

def detect_optimal_profile():
    """Detecta hardware e retorna perfil recomendado"""
    cpu_count = multiprocessing.cpu_count()
    
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024**3)
    except:
        ram_gb = 4
    
    if cpu_count <= 2 or ram_gb < 4:
        return "ultra_low"
    elif cpu_count <= 4 or ram_gb < 8:
        return "low"
    elif cpu_count <= 8 or ram_gb < 16:
        return "balanced"
    else:
        return "quality"

CURRENT_PROFILE = os.getenv("PERFORMANCE_PROFILE", detect_optimal_profile())
SETTINGS = PERFORMANCE_PROFILES[CURRENT_PROFILE].copy()

# Aspect ratio padrão (será sobrescrito via parâmetro da API)
CURRENT_ASPECT_RATIO = "horizontal"

print(f"""
╔════════════════════════════════════════╗
║   PERFIL DE PERFORMANCE: {CURRENT_PROFILE.upper():^12}  ║
╠════════════════════════════════════════╣
║ FPS: {SETTINGS['fps']}                              ║
║ Preset: {SETTINGS['preset']:^10}                ║
║ Threads: {SETTINGS['threads']}                            ║
║ Legendas: {'✅ Sim' if SETTINGS['enable_subtitles'] else '❌ Não':^5}                      ║
╚════════════════════════════════════════╝
""")

# --- CONFIGURAÇÃO ORIGINAL ---
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

caminho_magick = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
if os.path.exists(caminho_magick):
    change_settings({"IMAGEMAGICK_BINARY": caminho_magick})

load_dotenv()

PROJECTS_DIR = "backend/projects"
os.makedirs(PROJECTS_DIR, exist_ok=True)

# --- CHAVES ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LUMA_API_KEY = os.getenv("LUMA_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")  # ✅ NOVO

# --- CONFIGURAÇÕES DE GERAÇÃO DE IMAGENS ---
IMAGE_PROVIDERS = {
    "flux_pro": {
        "name": "Flux Pro (Replicate)",
        "quality": "⭐⭐⭐⭐⭐",
        "cost": "$0.055/img",
        "requires_api": True,
        "api_key_var": "REPLICATE_API_KEY",
        "supports_aspect_ratio": True,
        "supports_seed": True
    },
    "dalle3": {
        "name": "DALL-E 3 (OpenAI)",
        "quality": "⭐⭐⭐⭐",
        "cost": "$0.040/img",
        "requires_api": True,
        "api_key_var": "OPENAI_API_KEY",
        "supports_aspect_ratio": False,
        "supports_seed": False
    },
    "sdxl": {
        "name": "Stable Diffusion XL (Replicate)",
        "quality": "⭐⭐⭐⭐",
        "cost": "$0.0025/img",
        "requires_api": True,
        "api_key_var": "REPLICATE_API_KEY",
        "supports_aspect_ratio": True,
        "supports_seed": True
    },
    "banana": {
        "name": "Nano Banana (Replicate)",
        "quality": "⭐⭐⭐",
        "cost": "$0.002/img",
        "requires_api": True,
        "api_key_var": "REPLICATE_API_KEY",
        "supports_aspect_ratio": True,
        "supports_seed": True
    },
    "pollinations": {
        "name": "Pollinations (Gratuito)",
        "quality": "⭐⭐",
        "cost": "Grátis",
        "requires_api": False,
        "api_key_var": None,
        "supports_aspect_ratio": True,
        "supports_seed": False
    }
}

# Template de prompt universal para consistência visual
VISUAL_STYLE_TEMPLATES = {
    "documentary": """Cinematic documentary photography, 8k resolution, photorealistic, 
professional color grading, National Geographic quality, dramatic natural lighting, 
shallow depth of field, award-winning composition.

SUBJECT: {scene_description}

Style: Professional documentary, no text, no watermarks, highly detailed.""",
    
    "cinematic": """Hollywood cinematic shot, IMAX quality, 8k, photorealistic rendering,
professional cinematography, dramatic lighting, anamorphic lens, film grain,
color graded like a blockbuster movie.

SUBJECT: {scene_description}

Style: Cinematic masterpiece, no text, ultra detailed, epic composition.""",
    
    "photorealistic": """Ultra-realistic photography, 8k RAW, professional DSLR,
perfect exposure, natural lighting, Leica quality, hyperrealistic details,
National Geographic award winner.

SUBJECT: {scene_description}

Style: Photorealistic, no CGI, authentic, highly detailed."""
}

# --- CONFIGURAÇÕES DE VOZ ---
VOICE_CONFIGS = {
    # OpenAI TTS Voices
    "openai_onyx": {
        "provider": "openai",
        "voice": "onyx",
        "name": "Onyx (Deep)",
        "description": "Voz masculina profunda e autoritária"
    },
    "openai_alloy": {
        "provider": "openai",
        "voice": "alloy",
        "name": "Alloy (Neutral)",
        "description": "Voz neutra e versátil"
    },
    "openai_echo": {
        "provider": "openai",
        "voice": "echo",
        "name": "Echo (Soft)",
        "description": "Voz suave e calma"
    },
    "openai_nova": {
        "provider": "openai",
        "voice": "nova",
        "name": "Nova (Energetic)",
        "description": "Voz energética e jovem"
    },
    # ElevenLabs (usa ELEVENLABS_VOICE_ID do .env)
    "elevenlabs": {
        "provider": "elevenlabs",
        "voice": None,  # Usa ELEVENLABS_VOICE_ID
        "name": "ElevenLabs (Premium)",
        "description": "Voz configurada no .env"
    },
    # Edge TTS
    "edge_tts": {
        "provider": "edge",
        "voice": "en-US-ChristopherNeural",
        "name": "Edge TTS (Gratuito)",
        "description": "Voz gratuita da Microsoft"
    },
    # Gemini TTS (experimental)
    "gemini_tts": {
        "provider": "gemini",
        "voice": "en-US-Neural2-J",
        "name": "Gemini TTS",
        "description": "Síntese de voz do Google AI"
    }
}

# Estilos de narração
VOICE_STYLES = {
    "hype": {
        "name": "Hype/Fast",
        "speed": 1.15,
        "pitch": "+5Hz",
        "instruction": "Speak with high energy, enthusiasm, and fast pacing. Perfect for viral content and hype moments."
    },
    "storyteller": {
        "name": "Storyteller",
        "speed": 1.0,
        "pitch": "0Hz",
        "instruction": "Speak like a captivating storyteller with varied tone, dramatic pauses, and emotional inflection."
    },
    "documentary": {
        "name": "Documentary",
        "speed": 0.95,
        "pitch": "-3Hz",
        "instruction": "Speak with authoritative clarity, measured pacing, and professional documentary tone."
    },
    "asmr": {
        "name": "ASMR/Calm",
        "speed": 0.85,
        "pitch": "-5Hz",
        "instruction": "Speak in a soft, soothing, calm whisper with gentle pacing and relaxing tone."
    },
    "authoritative": {
        "name": "Authoritative",
        "speed": 0.90,
        "pitch": "-8Hz",
        "instruction": "Speak with commanding authority, deep resonance, and confident assertiveness."
    }
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/projects", StaticFiles(directory=PROJECTS_DIR), name="projects")

# --- MODELOS WHISPER ---
print(f"⏳ Carregando modelo Whisper ({SETTINGS['whisper_model']})...")
whisper_model = whisper.load_model(SETTINGS['whisper_model'])
print(f"✅ Whisper {SETTINGS['whisper_model']} Carregado!")

# --- UTILITÁRIOS ---
def clean_text_for_tts(text):
    if not text: return ""
    text = re.sub(r'(?i)(voiceover|narrator|speaker|tone|style)\s*[:\-]\s*', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'[\*#]', '', text)
    text = text.replace("'", "'").replace(""", '"').replace(""", '"')
    return text.strip()

async def send_log(msg: str):
    return f"data: {json.dumps({'log': msg})}\n\n"

# ==========================================
# OTIMIZAÇÃO #6: STITCH OTIMIZADO
# ==========================================

def stitch_video_files(video_files, output_path):
    """Versão otimizada com stream copy garantido"""
    if not video_files:
        print("❌ Nenhum arquivo para concatenar")
        return False
    
    list_file = os.path.join(os.path.dirname(output_path), "files.txt")
    
    # Valida que todos os arquivos existem e diagnóstico
    valid_files = []
    print(f"\n🔍 DIAGNÓSTICO DE VÍDEOS INDIVIDUAIS:")
    for v in video_files:
        if os.path.exists(v):
            size = os.path.getsize(v)
            print(f"  ✅ {os.path.basename(v)} - {size/1024:.1f}KB")
            
            # Testa se o vídeo é válido com ffprobe (timeout maior)
            try:
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                           "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", v]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                duration = float(result.stdout.strip())
                print(f"     Duração: {duration:.2f}s")
                valid_files.append(v)
            except subprocess.TimeoutExpired:
                print(f"     ⏱️ Timeout na verificação (mas arquivo existe, incluindo)")
                valid_files.append(v)
            except Exception as e:
                print(f"     ⚠️ Erro na verificação: {str(e)[:50]} (incluindo mesmo assim)")
                valid_files.append(v)  # Inclui mesmo com erro
        else:
            print(f"  ❌ AUSENTE: {os.path.basename(v)}")
    
    if not valid_files:
        print("❌ Nenhum arquivo válido encontrado")
        return False
    
    print(f"\n📝 Criando lista de concatenação com {len(valid_files)} vídeos...")
    with open(list_file, 'w', encoding='utf-8') as f:
        for v in valid_files:
            abs_path = os.path.abspath(v).replace('\\', '/')
            f.write(f"file '{abs_path}'\n")
    
    # Mostra conteúdo do arquivo de lista
    with open(list_file, 'r', encoding='utf-8') as f:
        print(f"Conteúdo de files.txt:\n{f.read()}")
    
    # PASSO 1: Tenta stream copy direto (RÁPIDO)
    print("\n🔄 Tentando concatenação com stream copy...")
    cmd_fast = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd_fast, check=True, capture_output=True, text=True)
        print("✅ Stream copy SUCESSO")
        
        # Valida arquivo de saída
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"   Arquivo final: {size/1024:.1f}KB")
            
            # Testa o arquivo final
            try:
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", 
                           "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_path]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                duration = float(result.stdout.strip())
                print(f"   Duração total: {duration:.2f}s")
            except subprocess.TimeoutExpired:
                print("   ⏱️ Timeout na verificação (mas arquivo foi criado)")
            except:
                print("   ⚠️ Não foi possível verificar duração (mas arquivo existe)")
        
        if os.path.exists(list_file):
            os.remove(list_file)
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Stream copy FALHOU")
        print(f"STDERR: {e.stderr[:500]}")
        print("\n🔄 Tentando re-encoding com codec compatível...")
        
        # PASSO 2: Fallback com re-encoding otimizado e compatível
        cmd_slow = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264",
            "-preset", SETTINGS['preset'],
            "-crf", SETTINGS['crf'],
            "-pix_fmt", "yuv420p",
            "-profile:v", "baseline",  # Máxima compatibilidade
            "-level", "3.0",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            "-threads", str(SETTINGS['threads']),
            output_path
        ]
        
        try:
            result = subprocess.run(cmd_slow, check=True, capture_output=True, text=True)
            print("✅ Re-encoding SUCESSO")
            
            # Valida arquivo de saída
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                print(f"   Arquivo final: {size/1024:.1f}KB")
            
            return True
        except subprocess.CalledProcessError as e2:
            print(f"❌ Re-encoding FALHOU")
            print(f"STDERR: {e2.stderr[:500]}")
            return False
    
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

# --- LOGGER ---
class ProjectLogger:
    def __init__(self, project_path, topic, writer_config, critic_config, duration, voice_config, voice_style):
        self.filepath = os.path.join(project_path, "production_log.json")
        self.data = {
            "meta": {
                "project_id": os.path.basename(project_path),
                "topic": topic,
                "duration_mode": duration,
                "voice_config": voice_config,
                "voice_style": voice_style,
                "performance_profile": CURRENT_PROFILE,
                "agents": {"writer": writer_config, "critic": critic_config},
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "in_progress"
            },
            "timeline": []
        }
        self.save()

    def log_event(self, stage, status, details=None):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "status": status,
            "details": details or {}
        }
        self.data["timeline"].append(entry)
        self.save()

    def finish(self, status="completed", error=None):
        self.data["meta"]["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data["meta"]["status"] = status
        if error: self.data["meta"]["error_msg"] = str(error)
        self.save()

    def save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

# --- PDF GENERATOR ---
class PDFGenerator:
    def safe_encode(self, text):
        clean = text.replace("'", "'").replace(""", '"').replace(""", '"').replace("–", "-")
        return clean.encode('latin-1', 'replace').decode('latin-1')

    def save_script(self, project_path, topic, script_data):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, txt=self.safe_encode(f"ROTEIRO VIRAL: {topic}"), ln=1, align='C')
        pdf.ln(10)

        for act in script_data:
            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, txt=self.safe_encode(f"ATO: {act['title']}"), ln=1)
            pdf.ln(2)

            for i, scene in enumerate(act['scenes']):
                pdf.set_font("Arial", 'I', 10)
                pdf.set_text_color(100, 100, 100)
                visual_text = f"[Visual: {scene.get('visual_search_term', 'N/A')}]"
                pdf.multi_cell(0, 5, txt=self.safe_encode(visual_text))
                pdf.set_font("Arial", '', 12)
                pdf.set_text_color(0, 0, 0)
                narration_text = f"Narrador: {scene.get('narration', '')}"
                pdf.multi_cell(0, 8, txt=self.safe_encode(narration_text))
                pdf.ln(5)
            pdf.ln(5)

        filename = "roteiro_viral.pdf"
        full_path = os.path.join(project_path, filename)
        pdf.output(full_path)
        return filename

# --- SUBTITLE GENERATOR ---
class SubtitleGenerator:
    def get_font(self, size):
        fonts = ["arialbd.ttf", "ariblk.ttf", "SegoeUI-Bold.ttf", "impact.ttf", "DejaVuSans-Bold.ttf"]
        for name in fonts:
            try: return ImageFont.truetype(name, size)
            except: continue
        return ImageFont.load_default()

    def split_text_into_lines(self, words, font, max_width, draw, space_width_buffer):
        lines = []
        current_line = []
        current_w = 0
        space_w = draw.textlength(" ", font=font) + space_width_buffer

        for word_data in words:
            word = word_data['word'].strip()
            word_w = draw.textlength(word, font=font)
            if current_w + word_w <= max_width:
                current_line.append(word_data)
                current_w += word_w + space_w
            else:
                if current_line: lines.append(current_line)
                current_line = [word_data]
                current_w = word_w + space_w
        if current_line: lines.append(current_line)
        return lines

    def generate_karaoke(self, audio_path, video_w, video_h):
        try:
            # Transcrição otimizada
            result = whisper_model.transcribe(
                audio_path,
                word_timestamps=True,
                language="en",
                beam_size=1,
                best_of=1,
                fp16=False,
                temperature=0.0
            )
            segments = result['segments']
        except Exception as e:
            print(f"Erro Whisper: {e}")
            return []

        subtitle_clips = []
        
        # Adapta tamanho da fonte baseado na altura do vídeo
        base_font_size = int(video_h * 0.055)  # Reduzido de 0.085 para melhor fit vertical
        pop_font_size = int(base_font_size * 1.25)
        
        # Margens adaptativas
        margin_x = int(video_w * 0.10)  # 10% nas laterais
        margin_y = int(video_h * 0.10)  # 10% superior e inferior
        
        max_text_width = video_w - (margin_x * 2)
        font_normal = self.get_font(base_font_size)
        font_large = self.get_font(pop_font_size)
        text_color = (255, 255, 255, 255)
        highlight_color = (255, 215, 0, 255)
        stroke_color = (0, 0, 0, 255)
        stroke_width = 6
        SPACE_BUFFER = 25

        for segment in segments:
            all_words = segment['words']
            if not all_words: continue
            dummy_img = Image.new('RGBA', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            lines = self.split_text_into_lines(all_words, font_normal, max_text_width, dummy_draw, SPACE_BUFFER)
            line_height = base_font_size * 1.6
            total_block_height = len(lines) * line_height
            
            # CORREÇÃO: Posicionamento seguro com margens
            # Centraliza verticalmente com margem de segurança
            start_y = (video_h - total_block_height) / 2
            
            # Garante que não ultrapasse os limites
            if start_y < margin_y:
                start_y = margin_y  # Não passa do topo
            if start_y + total_block_height > video_h - margin_y:
                start_y = video_h - margin_y - total_block_height  # Não passa do fundo
            
            flat_words = [w for line in lines for w in line]

            for i, active_word in enumerate(flat_words):
                start_t = active_word['start']
                end_t = active_word['end']
                img = Image.new('RGBA', (video_w, video_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                current_y = start_y
                word_global_index = 0

                for line in lines:
                    line_total_w = 0
                    normal_space_w = dummy_draw.textlength(" ", font=font_normal) + SPACE_BUFFER
                    words_in_line = [w['word'].strip() for w in line]
                    for w_str in words_in_line:
                        line_total_w += dummy_draw.textlength(w_str, font=font_normal)
                    if len(words_in_line) > 1:
                        line_total_w += (len(words_in_line) - 1) * normal_space_w
                    current_x = (video_w - line_total_w) / 2

                    for word_data in line:
                        word_txt = word_data['word'].strip()
                        if word_global_index > i:
                            w_len = dummy_draw.textlength(word_txt, font=font_normal)
                            current_x += w_len + normal_space_w
                            word_global_index += 1
                            continue

                        is_active = (word_global_index == i)
                        current_font = font_large if is_active else font_normal
                        current_color = highlight_color if is_active else text_color
                        normal_w = dummy_draw.textlength(word_txt, font=font_normal)
                        draw_x = current_x
                        draw_y = current_y

                        if is_active:
                            large_w = dummy_draw.textlength(word_txt, font=font_large)
                            offset_x = (large_w - normal_w) / 2
                            offset_y = (pop_font_size - base_font_size) / 1.3
                            draw_x = current_x - offset_x
                            draw_y = current_y - offset_y

                        for adj_x in range(-stroke_width, stroke_width+1):
                            for adj_y in range(-stroke_width, stroke_width+1):
                                if abs(adj_x) >= stroke_width-1 or abs(adj_y) >= stroke_width-1:
                                    draw.text((draw_x+adj_x, draw_y+adj_y), word_txt, font=current_font, fill=stroke_color)
                        draw.text((draw_x, draw_y), word_txt, font=current_font, fill=current_color)

                        current_x += normal_w + normal_space_w
                        word_global_index += 1
                    current_y += line_height

                img_np = np.array(img)
                txt_clip = ImageClip(img_np).set_start(start_t).set_end(end_t).set_duration(end_t - start_t)
                subtitle_clips.append(txt_clip)

        return subtitle_clips

# --- API WRAPPERS ---
def call_gemini_api(prompt_text, model, max_retries=3):
    if not GEMINI_API_KEY: return {"error": "Chave Gemini não configurada"}
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}], "generationConfig": {"temperature": 0.7}}
    
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if r.status_code == 429: 
                return {"error": "ERRO DE COTA (429): Limite do Gemini excedido."}
            
            if r.status_code != 200: 
                return {"error": f"Erro Gemini ({r.status_code}): {r.text}"}
            
            # Parse robusto da resposta
            response_data = r.json()
            
            # Verifica se há candidates
            if 'candidates' not in response_data or not response_data['candidates']:
                # Pode ser bloqueio de segurança
                if 'promptFeedback' in response_data:
                    feedback = response_data['promptFeedback']
                    block_reason = feedback.get('blockReason', 'UNKNOWN')
                    return {"error": f"Gemini bloqueou o conteúdo: {block_reason}. Tente outro modelo ou prompt."}
                return {"error": f"Resposta vazia do Gemini. Response: {response_data}"}
            
            # Extrai o texto
            candidate = response_data['candidates'][0]
            
            if 'content' not in candidate:
                return {"error": f"Candidate sem 'content'. Data: {candidate}"}
            
            if 'parts' not in candidate['content']:
                return {"error": f"Content sem 'parts'. Data: {candidate['content']}"}
            
            if not candidate['content']['parts']:
                return {"error": "Parts vazio"}
            
            text = candidate['content']['parts'][0].get('text', '')
            
            if not text:
                return {"error": "Texto vazio na resposta"}
            
            return {"text": text}
        
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"⚠️ Timeout no Gemini (tentativa {attempt+1}/{max_retries}). Retentando em 2s...")
                time.sleep(2)
                continue
            else:
                return {"error": f"TIMEOUT: Gemini não respondeu após {max_retries} tentativas (120s cada)."}
        
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Erro de conexão Gemini (tentativa {attempt+1}/{max_retries}). Retentando...")
                time.sleep(2)
                continue
            else:
                return {"error": f"Erro de conexão: {str(e)}"}
        
        except KeyError as e:
            # Erro de parsing - mostra resposta completa para debug
            return {"error": f"Erro parsing Gemini (campo '{e}' ausente). Response: {r.text[:500]}"}
        
        except Exception as e: 
            return {"error": f"Erro inesperado: {str(e)}"}
    
    return {"error": "Falha após todas as tentativas"}

def call_openai_api(prompt_text, model, max_retries=3):
    if not OPENAI_API_KEY: return {"error": "Chave OpenAI não configurada"}
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model, 
                messages=[{"role": "user", "content": prompt_text}], 
                temperature=0.7,
                timeout=120  # Timeout de 120s
            )
            return {"text": response.choices[0].message.content}
        
        except Exception as e:
            error_str = str(e)
            
            if "429" in error_str or "quota" in error_str.lower():
                return {"error": "ERRO DE COTA (429): Limite da OpenAI excedido."}
            
            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                if attempt < max_retries - 1:
                    print(f"⚠️ Timeout na OpenAI (tentativa {attempt+1}/{max_retries}). Retentando em 2s...")
                    time.sleep(2)
                    continue
                else:
                    return {"error": f"TIMEOUT: OpenAI não respondeu após {max_retries} tentativas."}
            
            if attempt < max_retries - 1:
                print(f"⚠️ Erro OpenAI (tentativa {attempt+1}/{max_retries}). Retentando...")
                time.sleep(2)
                continue
            
            return {"error": f"Erro OpenAI: {error_str}"}
    
    return {"error": "Falha após todas as tentativas"}

async def generate_text(provider, model, prompt):
    if provider == "openai": return call_openai_api(prompt, model)
    return call_gemini_api(prompt, model)

# --- CÉREBRO VIRAL ---
class ViralBrain:
    def __init__(self, writer_provider, writer_model, critic_provider, critic_model, duration_instruction):
        self.writer_provider = writer_provider
        self.writer_model = writer_model
        self.critic_provider = critic_provider
        self.critic_model = critic_model
        self.duration_instruction = duration_instruction

    async def run_writer_critic_loop(self, topic, chapter_title, facts, logger):
        max_iterations = 3
        current_draft_json = None
        feedback = f"Focus on high retention. {self.duration_instruction}"

        for i in range(max_iterations):
            yield {"type": "log", "content": f"   ✍️ Roteirista ({self.writer_model}) - Draft {i+1}..."}
            logger.log_event("roteiro_draft", "in_progress", {"round": i+1, "model": self.writer_model})

            writer_prompt = f"""
Role: World-Class YouTube Scriptwriter.
Topic: {topic}. Chapter: {chapter_title}.
Context Data: {facts}

CRITICAL CONSTRAINTS:
1. LANGUAGE: ENGLISH ONLY. NEVER TRANSLATE.
2. FORMAT: VALID JSON ONLY.
3. DURATION: {self.duration_instruction}

Critique Feedback to fix: {feedback}

OUTPUT JSON: {{ "scenes": [ {{ "narration": "English text...", "visual_search_term": "English keyword", "visual_ai_prompt": "English prompt" }} ] }}
"""

            res_writer = await generate_text(self.writer_provider, self.writer_model, writer_prompt)
            if 'error' in res_writer:
                yield {"type": "error", "content": res_writer['error']}
                return

            # ==========================================
            # OTIMIZAÇÃO #3: FALLBACK PARA JSON INVÁLIDO
            # ==========================================
            try:
                clean_json = res_writer['text'].replace("```json","").replace("```","").strip()
                current_draft_json = json.loads(clean_json)
                script_text = " ".join([s['narration'] for s in current_draft_json.get('scenes', [])])
            except json.JSONDecodeError as json_err:
                yield {"type": "log", "content": f"   ⚠️ JSON inválido detectado. Tentando corrigir..."}
                
                # Tenta corrigir o JSON com o próprio LLM
                fix_prompt = f"""
The following text should be valid JSON but has syntax errors. Fix it and return ONLY the corrected JSON, nothing else.

Broken JSON:
{res_writer['text']}

Return ONLY valid JSON in this exact format:
{{ "scenes": [ {{ "narration": "text", "visual_search_term": "keyword", "visual_ai_prompt": "prompt" }} ] }}
"""
                
                try:
                    res_fix = await generate_text(self.writer_provider, self.writer_model, fix_prompt)
                    if 'error' not in res_fix:
                        fixed_json = res_fix['text'].replace("```json","").replace("```","").strip()
                        current_draft_json = json.loads(fixed_json)
                        script_text = " ".join([s['narration'] for s in current_draft_json.get('scenes', [])])
                        yield {"type": "log", "content": "   ✅ JSON corrigido com sucesso!"}
                    else:
                        yield {"type": "log", "content": "   ⚠️ Falha ao corrigir JSON. Retentando..."}
                        continue
                except:
                    yield {"type": "log", "content": "   ⚠️ Falha ao corrigir JSON. Retentando..."}
                    continue
            except Exception as e:
                yield {"type": "log", "content": f"   ⚠️ Erro inesperado ao processar JSON: {str(e)[:50]}. Retentando..."}
                continue

            yield {"type": "log", "content": f"   🧐 Crítico ({self.critic_model}): Avaliando..."}

            critic_prompt = f"""
Role: Ruthless YouTube Consultant.
Script: "{script_text}"

TASK: Check retention and constraints.
CRITICAL CHECK: IS THE SCRIPT IN ENGLISH? IF NOT, SCORE 0.

Output JSON: {{ "score": (0-100), "feedback": "Fix instructions." }}
"""

            res_critic = await generate_text(self.critic_provider, self.critic_model, critic_prompt)
            if 'error' in res_critic:
                yield {"type": "error", "content": res_critic['error']}
                return

            try:
                clean_critic = res_critic['text'].replace("```json","").replace("```","").strip()
                critic_data = json.loads(clean_critic)
                score = critic_data.get('score', 50)
                feedback = critic_data.get('feedback', '')

                yield {"type": "log", "content": f"   📊 Nota: {score}/100. Feedback: {feedback[:50]}..."}
                logger.log_event("critico_resultado", "completed", {"round": i+1, "score": score})

                if score >= 90:
                    yield {"type": "log", "content": "   ✅ APROVADO PELO CRÍTICO!"}
                    yield {"type": "result", "content": current_draft_json}
                    return
            except:
                # Se o crítico também retornar JSON inválido, assume score mediano
                yield {"type": "log", "content": "   ⚠️ Resposta do crítico inválida. Assumindo score 75..."}
                score = 75
                feedback = "Continue melhorando a retenção e estrutura viral."

        yield {"type": "log", "content": "   ⚠️ Usando melhor versão disponível."}
        yield {"type": "result", "content": current_draft_json}

# --- GERAÇÃO DE IMAGENS ---
async def generate_image_with_provider(prompt, provider, aspect_ratio, seed=None, style_template="documentary"):
    """
    Gera imagem usando o provider especificado
    
    Args:
        prompt: Descrição da cena
        provider: flux_pro, dalle3, sdxl, banana, pollinations
        aspect_ratio: vertical ou horizontal
        seed: Seed para consistência (opcional)
        style_template: documentary, cinematic, photorealistic
    
    Returns:
        tuple: (image_path, provider_used) ou dict com error
    """
    
    # Valida provider
    if provider not in IMAGE_PROVIDERS:
        return {"error": f"Provider inválido: {provider}"}
    
    config = IMAGE_PROVIDERS[provider]
    
    # Verifica API key se necessário
    if config["requires_api"]:
        api_key_var = config["api_key_var"]
        if api_key_var == "OPENAI_API_KEY" and not OPENAI_API_KEY:
            return {"error": f"❌ ERRO CRÍTICO: {provider} selecionado mas OPENAI_API_KEY não configurada. Configure no .env ou troque o provider."}
        elif api_key_var == "REPLICATE_API_KEY" and not REPLICATE_API_KEY:
            return {"error": f"❌ ERRO CRÍTICO: {provider} selecionado mas REPLICATE_API_KEY não configurada. Configure no .env ou troque o provider."}
        
        if api_key_var == "REPLICATE_API_KEY":
            os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY
    
    # Aplica template de estilo
    template = VISUAL_STYLE_TEMPLATES.get(style_template, VISUAL_STYLE_TEMPLATES["documentary"])
    enhanced_prompt = template.format(scene_description=prompt)
    
    # Determina aspect ratio
    aspect = "9:16" if aspect_ratio == "vertical" else "16:9"
    width = 720 if aspect_ratio == "vertical" else 1280
    height = 1280 if aspect_ratio == "vertical" else 720
    
    try:
        # ===== FLUX PRO =====
        if provider == "flux_pro":
            import replicate
            
            input_params = {
                "prompt": enhanced_prompt,
                "aspect_ratio": aspect,
                "output_format": "png",
                "output_quality": 100,
                "safety_tolerance": 2
            }
            
            if seed is not None and config["supports_seed"]:
                input_params["seed"] = seed
            
            output = replicate.run(
                "black-forest-labs/flux-pro",
                input=input_params
            )
            
            # Download da imagem
            # CORREÇÃO: Tratamento para objeto FileOutput do Replicate
            if isinstance(output, list):
                image_url = str(output[0])
            else:
                image_url = str(output) # Converte FileOutput diretamente para URL
            
            image_data = requests.get(image_url, timeout=30).content
            
            return image_data, "Flux Pro"
        
        # ===== STABLE DIFFUSION XL =====
        elif provider == "sdxl":
            import replicate
            
            input_params = {
                "prompt": enhanced_prompt,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "scheduler": "K_EULER",
                "num_inference_steps": 50,
                "guidance_scale": 7.5,
                "refine": "expert_ensemble_refiner"
            }
            
            if seed is not None and config["supports_seed"]:
                input_params["seed"] = seed
            
            output = replicate.run(
                "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                input=input_params
            )
            
            image_url = output[0] if isinstance(output, list) else output
            image_data = requests.get(image_url, timeout=30).content
            
            return image_data, "SDXL"
        
        # ===== BANANA (Nano model) =====
        elif provider == "banana":
            import replicate
            
            input_params = {
                "prompt": enhanced_prompt,
                "width": width,
                "height": height,
                "num_outputs": 1
            }
            
            if seed is not None and config["supports_seed"]:
                input_params["seed"] = seed
            
            output = replicate.run(
                "fofr/sdxl-neon-mecha:c3c9c5f0e4ed4a8c876f15f2af7c4b5f46f12b2fd0dd69a0d54e2d0b6e3e9c0e",
                input=input_params
            )
            
            image_url = output[0] if isinstance(output, list) else output
            image_data = requests.get(image_url, timeout=30).content
            
            return image_data, "Nano Banana"
        
        # ===== DALL-E 3 =====
        elif provider == "dalle3":
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            # DALL-E 3 não suporta seed ou aspect ratio custom
            size = "1024x1792" if aspect_ratio == "vertical" else "1792x1024"
            
            response = client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt[:4000],  # DALL-E tem limite de caracteres
                size=size,
                quality="hd",
                n=1
            )
            
            image_url = response.data[0].url
            image_data = requests.get(image_url, timeout=30).content
            
            return image_data, "DALL-E 3"
        
        # ===== POLLINATIONS =====
        elif provider == "pollinations":
            url = f"https://image.pollinations.ai/prompt/{enhanced_prompt.replace(' ','%20')}?width={width}&height={height}&model=flux&nologo=true"
            
            image_data = requests.get(url, timeout=30).content
            
            return image_data, "Pollinations"
    
    except Exception as e:
        error_msg = str(e)
        
        # Detecta erros específicos
        if "credit" in error_msg.lower() or "quota" in error_msg.lower() or "billing" in error_msg.lower():
            return {"error": f"❌ ERRO CRÍTICO: Créditos esgotados no {config['name']}. Adicione créditos ou troque o provider."}
        
        return {"error": f"Erro ao gerar imagem com {config['name']}: {error_msg}"}
    
    return {"error": f"Provider {provider} não implementado corretamente"}
    narr_text = scene.get('narration') or scene.get('script') or scene.get('text')
    if not narr_text: return None
    
    audio_path = os.path.join(project_path, f"act{act_index}_scene{index}.mp3")
    clean_txt = clean_text_for_tts(narr_text)
    
    # Obtém configurações de voz e estilo
    voice_config = VOICE_CONFIGS.get(voice_config_key, VOICE_CONFIGS["edge_tts"])
    style_config = VOICE_STYLES.get(voice_style, VOICE_STYLES["documentary"])
    
    # Adiciona instrução de estilo ao texto (para TTS que suportam)
    styled_prompt = f"{style_config['instruction']}\n\n{clean_txt}"
    
    tts_model_used = "None"
    provider = voice_config["provider"]
    
    # ===== OPENAI TTS =====
    if provider == "openai":
        if not OPENAI_API_KEY:
            return {"error": "ERRO VOZ: OpenAI TTS selecionado mas sem chave API."}
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.audio.speech.create(
                model="tts-1-hd",  # ou "tts-1" para mais rápido
                voice=voice_config["voice"],
                input=clean_txt,
                speed=style_config["speed"]
            )
            
            response.stream_to_file(audio_path)
            tts_model_used = f"OpenAI TTS ({voice_config['voice']})"
        
        except Exception as e:
            return {"error": f"FALHA OpenAI TTS: {str(e)}"}
    
    # ===== ELEVENLABS =====
    elif provider == "elevenlabs":
        if not ELEVENLABS_API_KEY:
            return {"error": "ERRO VOZ: ElevenLabs selecionado mas sem chave API."}
        
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
            
            # ElevenLabs suporta stability e similarity_boost para controle de estilo
            data = {
                "text": clean_txt,
                "model_id": "eleven_turbo_v2",
                "voice_settings": {
                    "stability": 0.5 if voice_style == "hype" else 0.75,
                    "similarity_boost": 0.75
                }
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=20)
            
            if r.status_code == 200:
                with open(audio_path, 'wb') as f: f.write(r.content)
                tts_model_used = "ElevenLabs"
            else:
                return {"error": f"ElevenLabs Error ({r.status_code}): {r.text}"}
        
        except Exception as e:
            return {"error": f"FALHA ElevenLabs: {str(e)}"}
    
    # ===== GEMINI TTS (usando Google Cloud TTS) =====
    elif provider == "gemini":
        if not GEMINI_API_KEY:
            return {"error": "ERRO VOZ: Gemini TTS selecionado mas sem chave API."}
        
        try:
            # Usa a API do Google Cloud Text-to-Speech via REST
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "input": {"text": clean_txt},
                "voice": {
                    "languageCode": "en-US",
                    "name": voice_config["voice"],
                    "ssmlGender": "MALE"
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": style_config["speed"],
                    "pitch": float(style_config["pitch"].replace("Hz", ""))
                }
            }
            
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if r.status_code == 200:
                import base64
                audio_content = base64.b64decode(r.json()["audioContent"])
                with open(audio_path, 'wb') as f: f.write(audio_content)
                tts_model_used = "Gemini TTS"
            else:
                # Fallback para Edge TTS se Gemini falhar
                await edge_tts.Communicate(clean_txt, "en-US-ChristopherNeural").save(audio_path)
                tts_model_used = "EdgeTTS (Fallback)"
        
        except Exception as e:
            # Fallback para Edge TTS
            await edge_tts.Communicate(clean_txt, "en-US-ChristopherNeural").save(audio_path)
            tts_model_used = "EdgeTTS (Fallback)"
    
    # ===== EDGE TTS (Fallback padrão) =====
    else:
        try:
            # Edge TTS com ajuste de velocidade via SSML
            if voice_style == "hype":
                ssml_text = f'<speak><prosody rate="fast">{clean_txt}</prosody></speak>'
            elif voice_style == "asmr":
                ssml_text = f'<speak><prosody rate="slow" volume="soft">{clean_txt}</prosody></speak>'
            else:
                ssml_text = clean_txt
            
            await edge_tts.Communicate(ssml_text, voice_config["voice"]).save(audio_path)
            tts_model_used = "EdgeTTS"
        except Exception as e:
            return {"error": f"FALHA TOTAL DE VOZ: {str(e)}"}
    
# --- GERAÇÃO DE MÍDIA ---
async def generate_visuals_and_audio(scene, index, act_index, project_path, voice_config_key, voice_style, image_provider, project_seed, visual_style):
    narr_text = scene.get('narration') or scene.get('script') or scene.get('text')
    if not narr_text: return None
    
    audio_path = os.path.join(project_path, f"act{act_index}_scene{index}.mp3")
    clean_txt = clean_text_for_tts(narr_text)
    
    # Obtém configurações de voz e estilo
    voice_config = VOICE_CONFIGS.get(voice_config_key, VOICE_CONFIGS["edge_tts"])
    style_config = VOICE_STYLES.get(voice_style, VOICE_STYLES["documentary"])
    
    # Adiciona instrução de estilo ao texto (para TTS que suportam)
    styled_prompt = f"{style_config['instruction']}\n\n{clean_txt}"
    
    tts_model_used = "None"
    provider = voice_config["provider"]
    
    # ===== GERAÇÃO DE ÁUDIO (mantém lógica original) =====
    if provider == "openai":
        if not OPENAI_API_KEY:
            return {"error": "ERRO VOZ: OpenAI TTS selecionado mas sem chave API."}
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice=voice_config["voice"],
                input=clean_txt,
                speed=style_config["speed"]
            )
            
            response.stream_to_file(audio_path)
            tts_model_used = f"OpenAI TTS ({voice_config['voice']})"
        
        except Exception as e:
            return {"error": f"FALHA OpenAI TTS: {str(e)}"}
    
    elif provider == "elevenlabs":
        if not ELEVENLABS_API_KEY:
            return {"error": "ERRO VOZ: ElevenLabs selecionado mas sem chave API."}
        
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
            
            data = {
                "text": clean_txt,
                "model_id": "eleven_turbo_v2",
                "voice_settings": {
                    "stability": 0.5 if voice_style == "hype" else 0.75,
                    "similarity_boost": 0.75
                }
            }
            
            r = requests.post(url, json=data, headers=headers, timeout=20)
            
            if r.status_code == 200:
                with open(audio_path, 'wb') as f: f.write(r.content)
                tts_model_used = "ElevenLabs"
            else:
                return {"error": f"ElevenLabs Error ({r.status_code}): {r.text}"}
        
        except Exception as e:
            return {"error": f"FALHA ElevenLabs: {str(e)}"}
    
    elif provider == "gemini":
        if not GEMINI_API_KEY:
            return {"error": "ERRO VOZ: Gemini TTS selecionado mas sem chave API."}
        
        try:
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "input": {"text": clean_txt},
                "voice": {
                    "languageCode": "en-US",
                    "name": voice_config["voice"],
                    "ssmlGender": "MALE"
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": style_config["speed"],
                    "pitch": float(style_config["pitch"].replace("Hz", ""))
                }
            }
            
            r = requests.post(url, json=payload, headers=headers, timeout=20)
            
            if r.status_code == 200:
                import base64
                audio_content = base64.b64decode(r.json()["audioContent"])
                with open(audio_path, 'wb') as f: f.write(audio_content)
                tts_model_used = "Gemini TTS"
            else:
                await edge_tts.Communicate(clean_txt, "en-US-ChristopherNeural").save(audio_path)
                tts_model_used = "EdgeTTS (Fallback)"
        
        except Exception as e:
            await edge_tts.Communicate(clean_txt, "en-US-ChristopherNeural").save(audio_path)
            tts_model_used = "EdgeTTS (Fallback)"
    
    else:
        try:
            if voice_style == "hype":
                ssml_text = f'<speak><prosody rate="fast">{clean_txt}</prosody></speak>'
            elif voice_style == "asmr":
                ssml_text = f'<speak><prosody rate="slow" volume="soft">{clean_txt}</prosody></speak>'
            else:
                ssml_text = clean_txt
            
            await edge_tts.Communicate(ssml_text, voice_config["voice"]).save(audio_path)
            tts_model_used = "EdgeTTS"
        except Exception as e:
            return {"error": f"FALHA TOTAL DE VOZ: {str(e)}"}
    
    # ===== GERAÇÃO DE IMAGEM (NOVO SISTEMA) =====
    search_term = scene.get('visual_search_term', 'business concept')
    ai_prompt = scene.get('visual_ai_prompt', search_term)
    media_path = os.path.join(project_path, f"act{act_index}_media{index}.png")
    
    if not os.path.exists(media_path):
        # Usa o provider selecionado pelo usuário
        result = await generate_image_with_provider(
            prompt=ai_prompt,
            provider=image_provider,
            aspect_ratio="vertical" if "vertical" in project_path else "horizontal",
            seed=project_seed,
            style_template=visual_style
        )
        
        # Verifica se houve erro crítico
        if isinstance(result, dict) and "error" in result:
            return result  # Retorna erro para parar a execução
        
        # Salva imagem
        image_data, vis_source = result
        with open(media_path, 'wb') as f:
            f.write(image_data)
    else:
        vis_source = "Cache"

    return audio_path, media_path, tts_model_used, vis_source

# ==========================================
# OTIMIZAÇÃO #2: RENDERIZAÇÃO OTIMIZADA
# ==========================================

def render_scene_optimized(audio_path, media_path, output_path, aspect_ratio="horizontal"):
    """Renderização com configurações otimizadas para hardware modesto"""
    try:
        # Verifica se os arquivos de entrada existem
        if not os.path.exists(audio_path):
            raise Exception(f"Áudio não encontrado: {audio_path}")
        if not os.path.exists(media_path):
            raise Exception(f"Imagem não encontrada: {media_path}")
        
        # Obtém resolução baseada no aspect ratio e perfil
        target_w, target_h = ASPECT_RATIOS[aspect_ratio]["resolutions"][CURRENT_PROFILE]
        
        print(f"\n🎬 RENDERIZANDO CENA ({ASPECT_RATIOS[aspect_ratio]['name']}):")
        print(f"   Áudio: {os.path.basename(audio_path)} ({os.path.getsize(audio_path)/1024:.1f}KB)")
        print(f"   Imagem: {os.path.basename(media_path)} ({os.path.getsize(media_path)/1024:.1f}KB)")
        
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration + 0.2
        print(f"   Duração áudio: {duration:.2f}s")

        # Cria clip de imagem e verifica dimensões
        try:
            clip = ImageClip(media_path).set_duration(duration)
            print(f"   Imagem carregada: {clip.w}x{clip.h}")
        except Exception as img_e:
            raise Exception(f"Erro ao carregar imagem: {img_e}")

        # Crop e resize para aspect ratio escolhido
        if clip.w / clip.h > target_w / target_h:
            clip = clip.resize(height=target_h)
        else:
            clip = clip.resize(width=target_w)

        clip = clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=target_w, height=target_h)
        print(f"   Resolução final: {target_w}x{target_h} ({ASPECT_RATIOS[aspect_ratio]['ratio']})")

        # Zoom sutil
        clip = clip.resize(lambda t: 1 + 0.04*t)

        # Legendas (se habilitadas no perfil)
        if SETTINGS['enable_subtitles']:
            try:
                sub_gen = SubtitleGenerator()
                subs = sub_gen.generate_karaoke(audio_path, target_w, target_h)
                print(f"   Legendas: {len(subs)} clips")
                final_scene = CompositeVideoClip([clip] + subs).set_audio(audio_clip)
            except Exception as e:
                print(f"⚠️ Erro legendas: {e}")
                final_scene = clip.set_audio(audio_clip)
        else:
            print(f"   Legendas: desabilitadas")
            final_scene = clip.set_audio(audio_clip)

        print(f"   Renderizando com preset={SETTINGS['preset']}, fps={SETTINGS['fps']}, threads={SETTINGS['threads']}...")
        
        # Renderização com parâmetros otimizados e garantidos para concatenação
        final_scene.write_videofile(
            output_path,
            fps=SETTINGS['fps'],
            codec="libx264",
            audio_codec="aac",
            preset=SETTINGS['preset'],
            threads=SETTINGS['threads'],
            bitrate=SETTINGS['bitrate'],
            # Parâmetros críticos para compatibilidade universal
            ffmpeg_params=[
                "-pix_fmt", "yuv420p",  # Compatibilidade universal
                "-profile:v", "baseline",  # Mudado de 'high' para 'baseline' (máxima compatibilidade)
                "-level", "3.0",  # Mudado de 4.0 para 3.0 (compatível com navegadores antigos)
                "-movflags", "+faststart",  # Stream progressivo
                "-ar", "44100",
                "-ac", "2"
            ],
            logger=None,
            write_logfile=False,
            temp_audiofile=f"{output_path}_temp_audio.m4a",
            remove_temp=True
        )

        # Cleanup
        final_scene.close()
        audio_clip.close()
        clip.close()
        
        print(f"   ✅ Vídeo salvo: {os.path.getsize(output_path)/1024:.1f}KB")

        return output_path

    except Exception as e:
        raise Exception(f"Erro na renderização: {str(e)}")

# --- STREAMING ---
@app.get("/create-stream")
async def create_documentary_stream(
    topic: str, 
    writer_provider: str, 
    writer_model: str, 
    critic_provider: str, 
    critic_model: str, 
    duration: str = "medium", 
    voice_config: str = "edge_tts", 
    voice_style: str = "documentary", 
    aspect_ratio: str = "horizontal",
    image_provider: str = "pollinations",
    use_consistent_seed: bool = True,
    visual_style: str = "documentary"
):
    async def event_generator():
        try:
            # Validação do aspect ratio
            if aspect_ratio not in ASPECT_RATIOS:
                yield f"data: {json.dumps({'status': 'error', 'message': f'Aspect ratio inválido: {aspect_ratio}'})}\n\n"
                return
            
            # Validação do image provider
            if image_provider not in IMAGE_PROVIDERS:
                yield f"data: {json.dumps({'status': 'error', 'message': f'Image provider inválido: {image_provider}'})}\n\n"
                return
            
            # Verifica se provider requer API key
            provider_config = IMAGE_PROVIDERS[image_provider]
            if provider_config["requires_api"]:
                api_key_var = provider_config["api_key_var"]
                if api_key_var == "OPENAI_API_KEY" and not OPENAI_API_KEY:
                    error_msg = f'{provider_config["name"]} requer OPENAI_API_KEY no .env'
                    yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                    return
                elif api_key_var == "REPLICATE_API_KEY" and not REPLICATE_API_KEY:
                    error_msg = f'{provider_config["name"]} requer REPLICATE_API_KEY no .env'
                    yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                    return
            
            # Gera seed único para o projeto (se consistência habilitada)
            project_seed = random.randint(1000, 99999) if use_consistent_seed else None
            
            aspect_info = ASPECT_RATIOS[aspect_ratio]
            resolution = aspect_info["resolutions"][CURRENT_PROFILE]
            
            voice_info = VOICE_CONFIGS.get(voice_config, VOICE_CONFIGS["edge_tts"])
            style_info = VOICE_STYLES.get(voice_style, VOICE_STYLES["documentary"])
            
            yield await send_log(f"🚀 INICIANDO: {topic}")
            yield await send_log(f"📐 Formato: {aspect_info['name']} ({aspect_info['ratio']}) - {resolution[0]}x{resolution[1]}")
            yield await send_log(f"🎙️ Voz: {voice_info['name']} | Estilo: {style_info['name']}")
            yield await send_log(f"🎨 Imagens: {provider_config['name']} | Seed: {project_seed if use_consistent_seed else 'Desabilitado'}")
            yield await send_log(f"🖼️ Estilo Visual: {visual_style.capitalize()}")
            yield await send_log(f"⚙️ Perfil: {CURRENT_PROFILE}")

            pid = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(PROJECTS_DIR, pid)
            os.makedirs(path, exist_ok=True)

            duration_map = {
                "short": {"structure": "1 ACT.", "constraint": "MAX 150 WORDS. FAST PACED.", "acts_prompt": "Output JSON: { \"acts\": [ { \"title\": \"The Story\", \"focus\": \"Hook\" } ] }"},
                "medium": {"structure": "3 Acts.", "constraint": "Standard Length (400-600 words).", "acts_prompt": "Output JSON: { \"acts\": [ { \"title\": \"Hook\", \"focus\": \"Mystery\" }, { \"title\": \"Body\", \"focus\": \"Analysis\" }, { \"title\": \"Payoff\", \"focus\": \"Conclusion\" } ] }"},
                "long": {"structure": "5 Acts.", "constraint": "Deep Dive (1500+ words).", "acts_prompt": "Output JSON: { \"acts\": [ { \"title\": \"Intro\", \"focus\": \"Hook\" }, { \"title\": \"Context\", \"focus\": \"History\" }, { \"title\": \"Conflict\", \"focus\": \"Drama\" }, { \"title\": \"Climax\", \"focus\": \"Peak\" }, { \"title\": \"Outro\", \"focus\": \"Future\" } ] }"},
                "surprise": {"structure": "AI Choice.", "constraint": "OPTIMIZE FOR RETENTION.", "acts_prompt": "Decide best structure. Output JSON: { \"acts\": [...] }"}
            }
            d_config = duration_map.get(duration, duration_map["medium"])

            writer_conf = {"provider": writer_provider, "model": writer_model}
            critic_conf = {"provider": critic_provider, "model": critic_model}
            logger = ProjectLogger(path, topic, writer_conf, critic_conf, duration, voice_config, voice_style)

            viral_brain = ViralBrain(writer_provider, writer_model, critic_provider, critic_model, d_config['constraint'])
            pdf_gen = PDFGenerator()

            yield await send_log("🕵️ Pesquisando dados...")
            with DDGS() as ddgs:
                facts = "\n".join([f"- {r['title']}: {r['body']}" for r in ddgs.text(topic, max_results=5)])

            yield await send_log("🏗️ Arquitetura Viral...")
            struct_prompt = f"Context: Viral Doc '{topic}'. Data: {facts}. {d_config['structure']} {d_config['acts_prompt']} LANGUAGE: ENGLISH ONLY."

            res = await generate_text(writer_provider, writer_model, struct_prompt)
            if 'error' in res:
                yield await send_log(f"❌ Erro Inicial: {res['error']}")
                yield f"data: {json.dumps({'status': 'error', 'message': res['error']})}\n\n"
                return
            try: acts = json.loads(res['text'].replace("```json","").replace("```","").strip())['acts']
            except: acts = [{"title": "Intro", "focus": "Start"}]

            generated_files = []
            full_script_data = []

            for idx, act in enumerate(acts):
                yield await send_log(f"🎬 Ato {idx+1}: {act['title']}...")

                plan = None
                async for brain_event in viral_brain.run_writer_critic_loop(topic, act['title'], facts, logger):
                    if brain_event["type"] == "log":
                        yield await send_log(brain_event["content"])
                    elif brain_event["type"] == "result":
                        plan = brain_event["content"]
                    elif brain_event["type"] == "error":
                        yield await send_log(f"❌ Erro Fatal: {brain_event['content']}")
                        yield f"data: {json.dumps({'status': 'error', 'message': brain_event['content']})}\n\n"
                        return

                if not plan: continue
                full_script_data.append({"title": act['title'], "scenes": plan.get('scenes', [])})
                scenes = plan.get('scenes', [])

                for i, scene in enumerate(scenes):
                    yield await send_log(f"   🎥 Cena {i+1}: Produzindo assets...")

                    result = await generate_visuals_and_audio(scene, i, idx, path, voice_config, voice_style, image_provider, project_seed, visual_style)

                    if isinstance(result, dict) and "error" in result:
                        yield await send_log(f"❌ Erro Assets: {result['error']}")
                        yield f"data: {json.dumps({'status': 'error', 'message': result['error']})}\n\n"
                        return
                    if not result: continue

                    audio_p, media_p, tts_u, vis_u = result
                    logger.log_event("cena_assets", "completed", {"tts": tts_u, "visual": vis_u})

                    yield await send_log(f"   ⚡ Cena {i+1}: Renderizando ({SETTINGS['preset']}, {SETTINGS['fps']}fps)...")

                    try:
                        temp = os.path.join(path, f"scene_{idx}_{i}.mp4")
                        render_scene_optimized(audio_p, media_p, temp, aspect_ratio)  # Passa aspect_ratio
                        
                        # TESTE: Verifica se o vídeo foi gerado corretamente
                        if os.path.exists(temp):
                            size = os.path.getsize(temp)
                            yield await send_log(f"   📹 Arquivo gerado: {size/1024:.1f}KB")
                            
                            # Testa com ffprobe (timeout maior para arquivos grandes)
                            try:
                                probe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                                           "-show_entries", "stream=codec_name,width,height", 
                                           "-of", "json", temp]
                                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                                info = json.loads(result.stdout)
                                if info.get('streams'):
                                    stream = info['streams'][0]
                                    yield await send_log(f"   🎥 Codec: {stream.get('codec_name')}, Resolução: {stream.get('width')}x{stream.get('height')}")
                                else:
                                    yield await send_log(f"   ⚠️ AVISO: Vídeo sem stream de vídeo!")
                            except subprocess.TimeoutExpired:
                                yield await send_log(f"   ⏱️ Verificação demorada, mas arquivo existe")
                            except Exception as probe_e:
                                yield await send_log(f"   ⚠️ Verificação ignorada: {str(probe_e)[:50]}")
                        
                        generated_files.append(temp)
                        yield await send_log(f"   ✅ Cena {i+1}: Completa!")
                    except Exception as e:
                        yield await send_log(f"⚠️ Erro render cena {i+1}: {e}")

            if full_script_data:
                try: pdf_gen.save_script(path, topic, full_script_data)
                except: pass

            if generated_files:
                yield await send_log(f"🧵 Costurando {len(generated_files)} cenas...")
                output_name = "final_viral.mp4"
                output_path = os.path.join(path, output_name)
                
                success = stitch_video_files(generated_files, output_path)
                
                if success and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    # Pós-processamento: Garante compatibilidade total
                    yield await send_log("🔧 Otimizando compatibilidade do vídeo...")
                    temp_output = output_path.replace(".mp4", "_temp.mp4")
                    
                    try:
                        # Re-encode com parâmetros de máxima compatibilidade
                        compat_cmd = [
                            "ffmpeg", "-y", "-i", output_path,
                            "-c:v", "libx264",
                            "-preset", "fast",
                            "-crf", "23",
                            "-pix_fmt", "yuv420p",
                            "-profile:v", "baseline",
                            "-level", "3.0",
                            "-movflags", "+faststart",
                            "-c:a", "aac",
                            "-b:a", "128k",
                            "-ar", "44100",
                            "-ac", "2",
                            temp_output
                        ]
                        
                        subprocess.run(compat_cmd, check=True, capture_output=True, text=True)
                        
                        # Substitui o arquivo original
                        os.remove(output_path)
                        os.rename(temp_output, output_path)
                        
                        yield await send_log("✅ Vídeo otimizado para navegadores!")
                    except Exception as e:
                        yield await send_log(f"⚠️ Otimização ignorada: {str(e)}")
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                    
                    # Validação final
                    final_size = os.path.getsize(output_path)
                    yield await send_log(f"📊 Tamanho final: {final_size/1024/1024:.2f}MB")
                    
                    full_url = f"http://localhost:8000/projects/{pid}/{output_name}"
                    logger.finish("completed")
                    
                    yield await send_log("🎉 VÍDEO FINALIZADO!")
                    yield await send_log(f"🔗 URL: {full_url}")
                    yield await send_log(f"📁 Pasta: projects/{pid}/")
                    
                    # Retorna JSON final com informações completas
                    yield f"data: {json.dumps({
                        'status': 'done', 
                        'url': full_url,
                        'project_id': pid,
                        'filename': output_name,
                        'size_mb': round(final_size / (1024*1024), 2),
                        'direct_path': f'/projects/{pid}/{output_name}'
                    })}\n\n"
                else:
                    logger.finish("failed", "Falha ao concatenar vídeos")
                    yield await send_log("❌ Erro ao unir vídeos")
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Falha na concatenação'})}\n\n"
            else:
                logger.finish("failed")
                yield f"data: {json.dumps({'status': 'error', 'message': 'Nenhum clipe gerado'})}\n\n"

        except Exception as e:
            yield await send_log(f"❌ Erro Fatal: {str(e)}")
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/available-models")
def get_available_models():
    models = {"gemini": [], "openai": []}
    if GEMINI_API_KEY:
        try:
            data = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}", timeout=5).json()
            if 'error' not in data:
                blacklist = ["tts", "audio", "embedding", "aqa", "vision-only"]
                for m in data.get('models', []):
                    if 'generateContent' in m.get('supportedGenerationMethods', []) and not any(b in m['name'].lower() for b in blacklist):
                        models["gemini"].append({"id": m['name'], "name": m['name'].replace("models/", "")})
                models["gemini"].sort(key=lambda x: x['name'], reverse=True)
        except: pass
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            for m in client.models.list().data:
                if m.id.startswith(("gpt-", "o1-")):
                    models["openai"].append({"id": m.id, "name": m.id})
            models["openai"].sort(key=lambda x: x['name'], reverse=True)
        except: pass
    return models

@app.get("/available-voices")
def get_available_voices():
    """Retorna vozes e estilos disponíveis"""
    voices = []
    
    # Adiciona vozes disponíveis baseado nas chaves API
    for key, config in VOICE_CONFIGS.items():
        # Verifica se a API necessária está disponível
        available = True
        if config["provider"] == "openai" and not OPENAI_API_KEY:
            available = False
        elif config["provider"] == "elevenlabs" and not ELEVENLABS_API_KEY:
            available = False
        elif config["provider"] == "gemini" and not GEMINI_API_KEY:
            available = False
        
        voices.append({
            "id": key,
            "name": config["name"],
            "provider": config["provider"],
            "description": config["description"],
            "available": available
        })
    
    # Retorna vozes e estilos
    styles = []
    for key, info in VOICE_STYLES.items():
        styles.append({
            "id": key,
            "name": info["name"],
            "description": info["instruction"][:80] + "..."
        })
    
    return {
        "voices": voices,
        "styles": styles
    }

@app.get("/available-image-providers")
def get_available_image_providers():
    """Retorna providers de imagem disponíveis"""
    providers = []
    
    for key, config in IMAGE_PROVIDERS.items():
        available = True
        api_status = "Não requer API"
        
        if config["requires_api"]:
            api_key_var = config["api_key_var"]
            if api_key_var == "OPENAI_API_KEY":
                available = bool(OPENAI_API_KEY)
                api_status = "✅ Configurado" if available else "❌ Faltando OPENAI_API_KEY"
            elif api_key_var == "REPLICATE_API_KEY":
                available = bool(REPLICATE_API_KEY)
                api_status = "✅ Configurado" if available else "❌ Faltando REPLICATE_API_KEY"
        
        providers.append({
            "id": key,
            "name": config["name"],
            "quality": config["quality"],
            "cost": config["cost"],
            "supports_seed": config["supports_seed"],
            "supports_aspect_ratio": config["supports_aspect_ratio"],
            "available": available,
            "api_status": api_status
        })
    
    return {
        "providers": providers,
        "visual_styles": [
            {"id": "documentary", "name": "Documentary", "description": "National Geographic quality, professional"},
            {"id": "cinematic", "name": "Cinematic", "description": "Hollywood blockbuster style, dramatic"},
            {"id": "photorealistic", "name": "Photorealistic", "description": "Ultra-realistic DSLR photography"}
        ]
    }

@app.get("/test-video/{project_id}")
def test_video(project_id: str):
    """Endpoint de teste para verificar vídeo"""
    video_path = os.path.join(PROJECTS_DIR, project_id, "final_viral.mp4")
    
    if not os.path.exists(video_path):
        return {"error": "Vídeo não encontrado", "path": video_path}
    
    # Diagnóstico completo do vídeo
    try:
        # Info básica
        size = os.path.getsize(video_path)
        
        # FFprobe detalhado
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration:format=duration,bit_rate",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        info = json.loads(result.stdout)
        
        # Extrai informações
        video_stream = next((s for s in info.get('streams', []) if s.get('codec_name') == 'h264'), None)
        audio_stream = next((s for s in info.get('streams', []) if s.get('codec_name') == 'aac'), None)
        
        diagnosis = {
            "file": {
                "path": video_path,
                "size_mb": round(size / (1024*1024), 2),
                "exists": True
            },
            "video_stream": {
                "codec": video_stream.get('codec_name') if video_stream else None,
                "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}" if video_stream else None,
                "fps": video_stream.get('r_frame_rate') if video_stream else None,
                "duration": video_stream.get('duration') if video_stream else None
            } if video_stream else {"error": "Sem stream de vídeo!"},
            "audio_stream": {
                "codec": audio_stream.get('codec_name') if audio_stream else None,
                "duration": audio_stream.get('duration') if audio_stream else None
            } if audio_stream else {"error": "Sem stream de áudio!"},
            "format": {
                "duration": info.get('format', {}).get('duration'),
                "bitrate": info.get('format', {}).get('bit_rate')
            },
            "url": f"http://localhost:8000/projects/{project_id}/final_viral.mp4"
        }
        
        return diagnosis
        
    except Exception as e:
        return {"error": str(e), "path": video_path}

@app.get("/player/{project_id}")
def video_player(project_id: str):
    """Player HTML5 de teste"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Player - {project_id}</title>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background: #000;
                font-family: Arial, sans-serif;
                color: #fff;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            video {{
                width: 100%;
                max-width: 800px;
                display: block;
                margin: 20px auto;
                background: #000;
            }}
            .info {{
                background: #222;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .success {{ color: #0f0; }}
            .error {{ color: #f00; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Video Test Player</h1>
            <div class="info">
                <p><strong>Project ID:</strong> {project_id}</p>
                <p><strong>Video URL:</strong> <a href="/projects/{project_id}/final_viral.mp4" target="_blank">/projects/{project_id}/final_viral.mp4</a></p>
            </div>
            
            <video id="player" controls autoplay>
                <source src="/projects/{project_id}/final_viral.mp4" type="video/mp4">
                Seu navegador não suporta vídeo HTML5.
            </video>
            
            <div class="info" id="status">
                <p>⏳ Carregando vídeo...</p>
            </div>
        </div>
        
        <script>
            const video = document.getElementById('player');
            const status = document.getElementById('status');
            
            video.addEventListener('loadedmetadata', () => {{
                status.innerHTML = `
                    <p class="success">✅ Vídeo carregado com sucesso!</p>
                    <p>Duração: ${{video.duration.toFixed(2)}}s</p>
                    <p>Dimensões: ${{video.videoWidth}}x${{video.videoHeight}}</p>
                `;
            }});
            
            video.addEventListener('error', (e) => {{
                status.innerHTML = `
                    <p class="error">❌ Erro ao carregar vídeo!</p>
                    <p>Erro: ${{video.error ? video.error.message : 'Desconhecido'}}</p>
                    <p>Code: ${{video.error ? video.error.code : 'N/A'}}</p>
                `;
            }});
            
            video.addEventListener('canplay', () => {{
                console.log('✅ Vídeo pronto para reprodução');
            }});
        </script>
    </body>
    </html>
    """