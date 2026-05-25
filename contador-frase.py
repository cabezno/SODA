import os
import re
import whisper
from yt_dlp import YoutubeDL
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# --- CONFIGURACIÓN ---
URL_YOUTUBE = "URL_DE_TU_VIDEO_AQUÍ"
FRASE_A_BUSCAR = "la palabra clave" # Ejemplo: "fútbol"
MARGEN_EXTRA = 0.5 # Segundos antes y después de la frase para que no sea tan brusco
OUTPUT_NAME = "supercut_final.mp4"

def download_youtube(url):
    print(f"📥 Descargando video de YouTube...")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'video_descargado.%(ext)s',
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return "video_descargado.mp4"

def create_supercut():
    # 1. Descarga
    video_path = download_youtube(URL_YOUTUBE)

    # 2. Transcripción Local (Whisper)
    print(f"🎙️ Transcribiendo y buscando la frase: '{FRASE_A_BUSCAR}'...")
    model = whisper.load_model("small") # 'small' es un buen balance entre velocidad y precisión
    result = model.transcribe(video_path, language="es")

    # 3. Filtrar fragmentos donde aparece la frase
    segments_to_cut = []
    for segment in result['segments']:
        if FRASE_A_BUSCAR.lower() in segment['text'].lower():
            segments_to_cut.append({
                'start': max(0, segment['start'] - MARGEN_EXTRA),
                'end': segment['end'] + MARGEN_EXTRA
            })

    if not segments_to_cut:
        print("❌ No se encontró la frase en el video.")
        return

    print(f"✅ Se encontraron {len(segments_to_cut)} menciones. Procesando clips...")

    # 4. Cortar, añadir contador y unir
    final_clips = []
    video_full = VideoFileClip(video_path)
    
    for i, timeframe in enumerate(segments_to_cut):
        count = i + 1
        print(f"🎬 Procesando clip {count}...")

        # Cortar el fragmento
        clip = video_full.subclip(timeframe['start'], timeframe['end'])

        # Crear el contador visual
        # Nota: Si da error aquí, es por falta de ImageMagick
        txt_clip = TextClip(
            str(count), 
            fontsize=70, 
            color='white', 
            font='Arial-Bold',
            stroke_color='black',
            stroke_width=2,
            method='caption'
        ).set_duration(clip.duration).set_position(("right", "top")).margin(right=20, top=20, opacity=0)

        # Superponer el texto al video
        clip_with_text = CompositeVideoClip([clip, txt_clip])
        final_clips.append(clip_with_text)

    # 5. Concatenar todo en un solo video
    print(f"🧬 Uniendo todos los fragmentos...")
    video_final = concatenate_videoclips(final_clips)
    video_final.write_videofile(OUTPUT_NAME, codec="libx264", audio_codec="aac")

    # Limpieza
    video_full.close()
    # os.remove(video_path) # Opcional: borrar el video original descargado
    print(f"✨ ¡HECHO! Video guardado como: {OUTPUT_NAME}")

if __name__ == "__main__":
    create_supercut()