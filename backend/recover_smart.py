import os
import re
import json
import asyncio
import subprocess
from dotenv import load_dotenv

# --- IMPORTAÇÕES DO MAIN (REUTILIZAÇÃO) ---
# Isso vai carregar o modelo Whisper e as configurações, 
# mas não vai iniciar o servidor web. Pode demorar alguns segundos.
print("⏳ Carregando ferramentas do sistema principal...")
try:
    from main import (
        generate_visuals_and_audio, 
        render_scene_optimized, 
        stitch_video_files, 
        generate_text, 
        clean_text_for_tts,
        SETTINGS,
        PROJECTS_DIR,
        CURRENT_PROFILE,
        ASPECT_RATIOS
    )
    print("✅ Ferramentas carregadas com sucesso!")
except ImportError as e:
    print(f"❌ Erro fatal: Não foi possível importar do main.py. Verifique se este arquivo está na pasta backend.\nErro: {e}")
    exit(1)

# ==========================================
# ⚙️ CONFIGURAÇÃO DO RESGATE
# ==========================================

# 1. Copie o ID da pasta do projeto travado (ex: "20260123_132115")
PROJECT_ID = "20260123_132115"

# 2. Copie o Título/Tópico exato para a IA saber como terminar (se necessário)
TOPIC = "Why productivity no longer guarantees progress"

# 3. Configurações que você usou (tente manter igual)
VOICE_CONFIG = "elevenlabs"     # ou openai_onyx, edge_tts...
VOICE_STYLE = "authoritative"   # ou documentary, hype...
IMAGE_PROVIDER = "flux_pro"     # ou pollinations, dalle3...
VISUAL_STYLE = "documentary"
ASPECT_RATIO = "horizontal"     # ou vertical

# ==========================================
# 🧠 CÉREBRO DE RECUPERAÇÃO
# ==========================================

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

async def generate_conclusion_script(topic):
    """Gera apenas o ato final do roteiro"""
    print("\n🧠 Solicitando à IA um final épico para o roteiro...")
    
    prompt = f"""
Role: YouTube Script Doctor.
Context: We are recovering a crashed video project about: "{topic}".
Task: Write ONE FINAL ACT (The Payoff/Conclusion) to wrap up this video perfectly.

Requirements:
1. Focus: Emotional, Motivational, Call to Action.
2. Length: Short and punchy (3-4 scenes max).
3. Language: English Only.
4. Format: JSON.

Output JSON: {{ "scenes": [ {{ "narration": "text...", "visual_search_term": "keyword", "visual_ai_prompt": "prompt" }} ] }}
"""
    # Usa o provider configurado no main (ou fallback para openai/gpt-4 se preferir)
    # Assumindo que o generate_text do main suporta os parâmetros
    res = await generate_text("openai", "gpt-4o", prompt)
    
    if "error" in res:
        print(f"❌ Erro ao gerar roteiro: {res['error']}")
        return []
    
    try:
        clean_json = res['text'].replace("```json","").replace("```","").strip()
        data = json.loads(clean_json)
        return data.get('scenes', [])
    except Exception as e:
        print(f"❌ Erro ao processar JSON da IA: {e}")
        return []

async def recover_and_finish():
    base_path = os.path.join(PROJECTS_DIR, PROJECT_ID)
    
    if not os.path.exists(base_path):
        print(f"❌ Pasta não encontrada: {base_path}")
        return

    # 1. Escaneia o que já existe
    existing_files = [f for f in os.listdir(base_path) if f.startswith("scene_") and f.endswith(".mp4")]
    existing_files.sort(key=natural_sort_key)
    
    print(f"\n📂 Encontrados {len(existing_files)} clipes renderizados.")
    
    # Valida integridade e descobre o último índice
    valid_files = []
    last_act_idx = 0
    last_scene_idx = 0
    
    for f in existing_files:
        path = os.path.join(base_path, f)
        if os.path.getsize(path) > 1000:
            valid_files.append(path)
            # Extrai indices do nome scene_X_Y.mp4
            parts = f.replace("scene_", "").replace(".mp4", "").split("_")
            if len(parts) >= 2:
                a_idx, s_idx = int(parts[0]), int(parts[1])
                if a_idx > last_act_idx: last_act_idx = a_idx
                if s_idx > last_scene_idx: last_scene_idx = s_idx
        else:
            print(f"⚠️ Arquivo corrompido (ignorando): {f}")

    print(f"✅ {len(valid_files)} clipes válidos recuperados.")
    print(f"📍 Paramos aproximadamente no Ato {last_act_idx}, Cena {last_scene_idx}")

    # 2. Pergunta se quer completar
    print("\n" + "="*40)
    print("🤖 MODO DE AUTO-COMPLETAR")
    print("="*40)
    print("O sistema pode gerar um 'Ato Final' agora para garantir que o vídeo tenha um desfecho.")
    choice = input("Deseja gerar e renderizar o final automaticamente? (s/n): ").lower()

    new_files = []

    if choice == 's':
        new_scenes = await generate_conclusion_script(TOPIC)
        
        if new_scenes:
            print(f"\n🎬 Iniciando produção de {len(new_scenes)} novas cenas finais...")
            
            # O próximo ato será o atual + 1
            new_act_idx = last_act_idx + 1
            
            for i, scene in enumerate(new_scenes):
                print(f"\n🎥 Produzindo Cena Final {i+1}/{len(new_scenes)}...")
                
                # Chamada direta às funções do main.py
                # Nota: generate_visuals_and_audio espera 'scene' como dict
                result = await generate_visuals_and_audio(
                    scene=scene,
                    index=i,
                    act_index=new_act_idx,
                    project_path=base_path,
                    voice_config_key=VOICE_CONFIG,
                    voice_style=VOICE_STYLE,
                    image_provider=IMAGE_PROVIDER,
                    project_seed=None, # Seed aleatório para o final
                    visual_style=VISUAL_STYLE
                )

                if result and not (isinstance(result, dict) and "error" in result):
                    audio_p, media_p, _, _ = result
                    output_filename = f"scene_{new_act_idx}_{i}.mp4"
                    output_path = os.path.join(base_path, output_filename)
                    
                    print(f"⚡ Renderizando Cena Final {i+1}...")
                    try:
                        render_scene_optimized(audio_p, media_p, output_path, ASPECT_RATIO)
                        if os.path.exists(output_path):
                            new_files.append(output_path)
                            print("✅ Cena salva!")
                    except Exception as e:
                        print(f"❌ Falha ao renderizar cena: {e}")
                else:
                    print(f"❌ Erro ao gerar assets: {result}")
        else:
            print("⚠️ IA não retornou cenas. Costurando apenas o que existe.")

    # 3. Costura final
    all_files = valid_files + new_files
    
    if not all_files:
        print("❌ Nenhum vídeo para costurar.")
        return

    print(f"\n🧵 Costurando total de {len(all_files)} cenas...")
    
    # Limpa nome do arquivo
    safe_title = re.sub(r'[\\/*?:"<>|]', "", TOPIC).strip().replace(" ", "_")
    output_name = f"{safe_title}_RECOVERED.mp4"
    final_output_path = os.path.join(base_path, output_name)
    
    success = stitch_video_files(all_files, final_output_path)
    
    if success:
        print("\n" + "█"*50)
        print("✅✅ VÍDEO RECUPERADO COM SUCESSO! ✅✅")
        print(f"📁 Arquivo: {final_output_path}")
        print("█"*50)
        
        # Abre a pasta (funciona no Windows)
        if os.name == 'nt':
            os.startfile(base_path)
    else:
        print("❌ Falha na costura final.")

if __name__ == "__main__":
    asyncio.run(recover_and_finish())