# backend/audio_recorder.py - Enregistrement audio en direct
"""
Module pour enregistrer l'audio directement depuis le navigateur
Compatible avec Streamlit
"""

import streamlit as st
from pathlib import Path
import tempfile
import datetime
from typing import Optional
import base64

def audio_recorder_component():
    """
    Composant d'enregistrement audio HTML/JavaScript intégré dans Streamlit
    
    Returns:
        bytes: Audio enregistré en format WAV
    """
    
    # HTML + JavaScript pour enregistrement audio
    audio_recorder_html = """
    <div style="text-align: center; padding: 2rem;">
        <div id="recording-status" style="margin-bottom: 1rem; font-size: 1.2rem; color: var(--text-secondary);">
            🎤 Prêt à enregistrer
        </div>
        
        <div style="margin-bottom: 1rem;">
            <button id="start-btn" onclick="startRecording()" 
                    style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; 
                           border: none; 
                           padding: 1rem 2rem; 
                           border-radius: 50px; 
                           font-size: 1.1rem; 
                           cursor: pointer;
                           margin: 0.5rem;">
                🎤 Démarrer l'enregistrement
            </button>
            
            <button id="stop-btn" onclick="stopRecording()" 
                    style="background: #dc2626; 
                           color: white; 
                           border: none; 
                           padding: 1rem 2rem; 
                           border-radius: 50px; 
                           font-size: 1.1rem; 
                           cursor: pointer;
                           margin: 0.5rem;
                           display: none;">
                ⏹️ Arrêter l'enregistrement
            </button>
        </div>
        
        <div id="timer" style="font-size: 2rem; font-weight: bold; color: #dc2626; display: none;">
            00:00
        </div>
        
        <audio id="audio-playback" controls style="margin-top: 1rem; display: none; width: 100%; max-width: 500px;"></audio>
        
        <input type="hidden" id="audio-data" />
    </div>
    
    <script>
        let mediaRecorder;
        let audioChunks = [];
        let timerInterval;
        let seconds = 0;
        
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                
                audioChunks = [];
                seconds = 0;
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    
                    // Afficher le lecteur audio
                    const audioPlayback = document.getElementById('audio-playback');
                    audioPlayback.src = audioUrl;
                    audioPlayback.style.display = 'block';
                    
                    // Convertir en base64 pour Streamlit
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        const base64data = reader.result;
                        document.getElementById('audio-data').value = base64data;
                        
                        // Déclencher événement pour Streamlit
                        const event = new Event('input', { bubbles: true });
                        document.getElementById('audio-data').dispatchEvent(event);
                    };
                    
                    // Arrêter le stream
                    stream.getTracks().forEach(track => track.stop());
                };
                
                mediaRecorder.start();
                
                // UI updates
                document.getElementById('start-btn').style.display = 'none';
                document.getElementById('stop-btn').style.display = 'inline-block';
                document.getElementById('timer').style.display = 'block';
                document.getElementById('recording-status').innerHTML = '🔴 Enregistrement en cours...';
                document.getElementById('recording-status').style.color = '#dc2626';
                
                // Démarrer le timer
                timerInterval = setInterval(() => {
                    seconds++;
                    const mins = Math.floor(seconds / 60);
                    const secs = seconds % 60;
                    document.getElementById('timer').textContent = 
                        String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
                }, 1000);
                
            } catch (err) {
                alert('Erreur: Impossible d\'accéder au microphone. Vérifiez les permissions.');
                console.error(err);
            }
        }
        
        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
                
                // Arrêter le timer
                clearInterval(timerInterval);
                
                // UI updates
                document.getElementById('start-btn').style.display = 'inline-block';
                document.getElementById('stop-btn').style.display = 'none';
                document.getElementById('recording-status').innerHTML = '✅ Enregistrement terminé';
                document.getElementById('recording-status').style.color = '#059669';
            }
        }
    </script>
    """
    
    # Afficher le composant
    st.components.v1.html(audio_recorder_html, height=400)
    
    # Récupérer les données audio via hidden input
    audio_data = st.text_input("", key="audio_data_input", label_visibility="collapsed")
    
    if audio_data and audio_data.startswith('data:audio'):
        # Extraire les données base64
        audio_base64 = audio_data.split(',')[1]
        audio_bytes = base64.b64decode(audio_base64)
        return audio_bytes
    
    return None


def save_recorded_audio(audio_bytes: bytes, course_id: int, user_id: int) -> Path:
    """
    Sauvegarde l'audio enregistré
    
    Args:
        audio_bytes: Données audio
        course_id: ID du cours
        user_id: ID utilisateur
    
    Returns:
        Path: Chemin du fichier sauvegardé
    """
    # Créer nom de fichier avec timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}.wav"
    
    # Créer dossier
    upload_dir = Path("uploads") / f"user_{user_id}" / f"course_{course_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder
    file_path = upload_dir / filename
    with open(file_path, 'wb') as f:
        f.write(audio_bytes)
    
    return file_path


# ============================================
# COMPOSANT ALTERNATIF (Plus simple)
# ============================================

def simple_audio_recorder():
    """
    Version simplifiée utilisant st.audio_input (Streamlit natif)
    Disponible depuis Streamlit 1.28+
    """
    st.markdown("### 🎤 Enregistrer un cours vocal")
    
    st.info("""
    **Instructions :**
    1. Cliquez sur le micro ci-dessous
    2. Autorisez l'accès au microphone
    3. Parlez clairement
    4. Cliquez sur Stop quand terminé
    """)
    
    # Enregistrement audio natif Streamlit
    audio_bytes = st.audio_input("Enregistrez votre cours")
    
    if audio_bytes:
        st.success("✅ Enregistrement capturé !")
        
        # Afficher le lecteur audio
        st.audio(audio_bytes, format='audio/wav')
        
        # Bouton pour traiter
        if st.button("🚀 Transcrire et Indexer", type="primary"):
            return audio_bytes
    
    return None
