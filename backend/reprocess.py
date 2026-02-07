# Salve como: backend/reprocess.py
import os
import sys
import glob
# Importa configurações do main original
from main import render_scene_optimized, stitch_video_files, PROJECTS_DIR, whisper

# --- CONFIGURAÇÃO ---
# Se não passar ID via comando, usa este:
DEFAULT_PROJECT_ID = "20260201_142001"  # ID que aparece no seu print
FORCED_MODEL = "base" # 'base' ou 'small' para melhor sincronia

def reprocess_project(pid):
    project_path = os.path.join(PROJECTS_DIR, pid)
    
    # Verifica se a pasta existe
    if not os.path.exists(project_path):
        print(f"❌ ERRO CRÍTICO: Pasta do projeto não encontrada:")
        print(f"   Caminho buscado: {project_path}")
        return

    print(f"🔄 Reprocessando projeto: {pid}")
    print(f"📂 Diretório: {project_path}")
    
    # 1. Forçar modelo Whisper melhor
    print(f"⏳ Carregando Whisper '{FORCED_MODEL}'...")
    import main
    main.whisper_model = whisper.load_model(FORCED_MODEL)

    # 2. Listar arquivos de áudio
    audio_files = sorted(glob.glob(os.path.join(project_path, "*.mp3")))
    
    if not audio_files:
        print("❌ Nenhum arquivo .mp3 encontrado na pasta!")
        return

    print(f"🔎 Encontrados {len(audio_files)} arquivos de áudio.")
    generated_files = []

    for audio_path in audio_files:
        # Pega o nome do arquivo: "act0_scene0.mp3"
        filename_full = os.path.basename(audio_path)
        # Pega só o nome: "act0_scene0"
        filename_base = os.path.splitext(filename_full)[0]
        
        # --- CORREÇÃO DA LÓGICA DE NOME DA IMAGEM ---
        # Troca 'scene' por 'media' e ADICIONA .png explicitamente
        image_name = filename_base.replace('scene', 'media') + ".png"
        media_path = os.path.join(project_path, image_name)
        
        # Debug para verificar caminho
        # print(f"   Processando: {filename_base} -> Buscando imagem: {image_name}")

        if not os.path.exists(media_path):
            print(f"⚠️ AVISO: Imagem não encontrada: {image_name}")
            # Tenta verificar se existe com o mesmo nome do áudio (fallback)
            fallback_name = filename_base + ".png"
            fallback_path = os.path.join(project_path, fallback_name)
            if os.path.exists(fallback_path):
                 print(f"   ↳ Encontrado fallback: {fallback_name}")
                 media_path = fallback_path
            else:
                 print(f"   ❌ Pulando cena {filename_base} (imagem ausente)")
                 continue

        output_scene_path = os.path.join(project_path, f"reprocessed_{filename_base}.mp4")
        
        try:
            print(f"🎬 Renderizando: {filename_base}...")
            video_path = render_scene_optimized(
                audio_path, 
                media_path, 
                output_scene_path, 
                aspect_ratio="horizontal" 
            )
            generated_files.append(video_path)
        except Exception as e:
            print(f"❌ Erro na cena {filename_base}: {e}")

    # 3. Juntar tudo
    if generated_files:
        print(f"\n🧵 Costurando {len(generated_files)} cenas...")
        final_output = os.path.join(project_path, "final_viral_REMASTERED.mp4")
        
        # Remove arquivo anterior se existir para evitar erro
        if os.path.exists(final_output):
            os.remove(final_output)
            
        stitch_video_files(generated_files, final_output)
        print(f"\n✅ SUCESSO! Vídeo salvo em:\n{final_output}")
    else:
        print("\n❌ Nenhuma cena foi gerada. Verifique os nomes dos arquivos.")

if __name__ == "__main__":
    # Pega argumento do terminal ou usa o padrão
    target_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROJECT_ID
    reprocess_project(target_id)