# backend/audio_video_processor.py - Traitement Audio/Vidéo StudyGenie
"""
Module pour traiter les fichiers audio et vidéo :
- Extraction audio depuis vidéos
- Transcription (OpenAI Whisper ou AssemblyAI)
- Horodatage des segments
- Formatage pour indexation FAISS
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import tempfile
import openai

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Formats supportés
AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.flac', '.ogg']
VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']


def is_media_file(filename: str) -> bool:
    """Vérifie si le fichier est audio ou vidéo"""
    ext = Path(filename).suffix.lower()
    return ext in AUDIO_FORMATS or ext in VIDEO_FORMATS


def extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> str:
    """
    Extrait l'audio d'une vidéo avec ffmpeg
    
    Args:
        video_path: Chemin vers la vidéo
        output_path: Chemin de sortie (optionnel)
    
    Returns:
        str: Chemin vers le fichier audio extrait
    """
    if output_path is None:
        output_path = str(Path(video_path).with_suffix('.mp3'))
    
    try:
        # Commande ffmpeg pour extraire audio
        command = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # Pas de vidéo
            '-acodec', 'libmp3lame',
            '-ab', '128k',  # Bitrate
            '-ar', '44100',  # Sample rate
            '-y',  # Overwrite
            output_path
        ]
        
        subprocess.run(command, check=True, capture_output=True)
        print(f"✅ Audio extrait: {output_path}")
        return output_path
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur extraction audio: {e}")
        raise Exception(f"Échec extraction audio: {e.stderr.decode()}")
    except FileNotFoundError:
        raise Exception("ffmpeg non installé. Installez avec: apt-get install ffmpeg")


def transcribe_with_whisper(audio_path: str, language: str = "fr") -> Dict:
    """
    Transcrit l'audio avec OpenAI Whisper API
    
    Args:
        audio_path: Chemin vers le fichier audio
        language: Code langue (fr, en, etc.)
    
    Returns:
        dict: {
            "text": str,  # Transcription complète
            "segments": List[{
                "start": float,
                "end": float,
                "text": str
            }]
        }
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY non configurée")
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Ouvrir le fichier audio
        with open(audio_path, 'rb') as audio_file:
            # Appel API Whisper
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                response_format="verbose_json",  # Pour avoir les segments
                timestamp_granularities=["segment"]
            )
        
        # Formater la réponse
        result = {
            "text": response.text,
            "segments": []
        }
        
        # Extraire les segments si disponibles
        if hasattr(response, 'segments') and response.segments:
            result["segments"] = [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text
                }
                for seg in response.segments
            ]
        
        print(f"✅ Transcription terminée: {len(response.text)} caractères")
        return result
    
    except Exception as e:
        print(f"❌ Erreur transcription Whisper: {e}")
        raise


def transcribe_with_assemblyai(audio_path: str, language: str = "fr") -> Dict:
    """
    Transcrit l'audio avec AssemblyAI API
    
    Args:
        audio_path: Chemin vers le fichier audio
        language: Code langue (fr_fr, en_us, etc.)
    
    Returns:
        dict: {
            "text": str,
            "segments": List[dict]
        }
    """
    if not ASSEMBLYAI_API_KEY:
        raise Exception("ASSEMBLYAI_API_KEY non configurée")
    
    try:
        import requests
        
        # 1. Upload le fichier
        headers = {'authorization': ASSEMBLYAI_API_KEY}
        
        with open(audio_path, 'rb') as f:
            upload_response = requests.post(
                'https://api.assemblyai.com/v2/upload',
                headers=headers,
                data=f
            )
        
        audio_url = upload_response.json()['upload_url']
        
        # 2. Demander la transcription
        language_code = "fr" if language.startswith("fr") else "en"
        
        transcript_request = {
            'audio_url': audio_url,
            'language_code': language_code,
            'speaker_labels': False,
            'punctuate': True,
            'format_text': True
        }
        
        transcript_response = requests.post(
            'https://api.assemblyai.com/v2/transcript',
            json=transcript_request,
            headers=headers
        )
        
        transcript_id = transcript_response.json()['id']
        
        # 3. Poll jusqu'à completion
        import time
        while True:
            status_response = requests.get(
                f'https://api.assemblyai.com/v2/transcript/{transcript_id}',
                headers=headers
            )
            
            status = status_response.json()['status']
            
            if status == 'completed':
                result = status_response.json()
                
                return {
                    "text": result['text'],
                    "segments": [
                        {
                            "start": word['start'] / 1000,  # ms → s
                            "end": word['end'] / 1000,
                            "text": word['text']
                        }
                        for word in result.get('words', [])
                    ]
                }
            
            elif status == 'error':
                raise Exception(f"Erreur transcription: {result.get('error')}")
            
            time.sleep(3)
    
    except Exception as e:
        print(f"❌ Erreur transcription AssemblyAI: {e}")
        raise


def format_transcript_for_indexing(transcript: Dict, filename: str) -> str:
    """
    Formate la transcription pour l'indexation FAISS
    
    Args:
        transcript: Résultat de transcription
        filename: Nom du fichier source
    
    Returns:
        str: Texte formaté avec horodatage
    """
    text_parts = [f"# Transcription: {filename}\n\n"]
    
    if transcript.get("segments"):
        # Grouper les segments par minutes
        current_minute = -1
        current_text = []
        
        for seg in transcript["segments"]:
            minute = int(seg["start"] // 60)
            
            if minute != current_minute:
                if current_text:
                    text_parts.append("\n\n")
                
                current_minute = minute
                timestamp = f"{minute:02d}:{int(seg['start'] % 60):02d}"
                text_parts.append(f"[{timestamp}] ")
            
            text_parts.append(seg["text"] + " ")
    
    else:
        # Pas de segments, juste le texte complet
        text_parts.append(transcript["text"])
    
    return "".join(text_parts)


def process_media_file(file_path: str, language: str = "fr", method: str = "whisper") -> Dict:
    """
    Traite un fichier audio/vidéo complet
    
    Args:
        file_path: Chemin vers le fichier
        language: Code langue (fr, en)
        method: "whisper" ou "assemblyai"
    
    Returns:
        dict: {
            "text": str,  # Texte formaté pour indexation
            "raw_transcript": dict,  # Transcription brute
            "duration": float,  # Durée en secondes
            "segments_count": int
        }
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")
    
    # 1. Vérifier le type de fichier
    ext = file_path.suffix.lower()
    
    if ext in VIDEO_FORMATS:
        print(f"🎥 Vidéo détectée: {file_path.name}")
        # Extraire l'audio
        audio_path = extract_audio_from_video(str(file_path))
    
    elif ext in AUDIO_FORMATS:
        print(f"🎵 Audio détecté: {file_path.name}")
        audio_path = str(file_path)
    
    else:
        raise ValueError(f"Format non supporté: {ext}")
    
    # 2. Transcription
    print(f"🎤 Transcription en cours ({method})...")
    
    if method == "whisper":
        transcript = transcribe_with_whisper(audio_path, language)
    elif method == "assemblyai":
        transcript = transcribe_with_assemblyai(audio_path, language)
    else:
        raise ValueError(f"Méthode inconnue: {method}")
    
    # 3. Formater pour indexation
    formatted_text = format_transcript_for_indexing(transcript, file_path.name)
    
    # 4. Calculer durée
    duration = 0
    if transcript.get("segments"):
        last_seg = transcript["segments"][-1]
        duration = last_seg.get("end", 0)
    
    # 5. Nettoyer fichier audio temporaire si créé
    if ext in VIDEO_FORMATS and audio_path != str(file_path):
        try:
            os.remove(audio_path)
            print(f"🗑️ Audio temporaire supprimé")
        except:
            pass
    
    return {
        "text": formatted_text,
        "raw_transcript": transcript,
        "duration": duration,
        "segments_count": len(transcript.get("segments", []))
    }


# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def get_media_info(file_path: str) -> Dict:
    """Obtient les informations d'un fichier média avec ffprobe"""
    try:
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        import json
        return json.loads(result.stdout)
    
    except Exception as e:
        print(f"⚠️ Impossible d'obtenir les infos média: {e}")
        return {}


def estimate_processing_time(file_path: str) -> float:
    """
    Estime le temps de traitement en secondes
    
    Returns:
        float: Temps estimé en secondes
    """
    info = get_media_info(file_path)
    
    try:
        duration = float(info['format']['duration'])
        # Estimation: 1 min de vidéo = ~30s de traitement
        return duration * 0.5
    except:
        # Par défaut
        return 60


# ============================================
# TESTS
# ============================================

if __name__ == "__main__":
    # Test basique
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audio_video_processor.py <fichier_audio_ou_video>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    print(f"\n🎬 Traitement de: {file_path}")
    print("=" * 50)
    
    try:
        result = process_media_file(file_path, language="fr", method="whisper")
        
        print(f"\n✅ Traitement réussi!")
        print(f"📊 Durée: {result['duration']:.1f}s")
        print(f"📝 Segments: {result['segments_count']}")
        print(f"📄 Caractères: {len(result['text'])}")
        print(f"\n📖 Extrait:")
        print(result['text'][:500] + "...")
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)
