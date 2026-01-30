# frontend/utils/session_manager.py - Gestion avancée des sessions
import streamlit as st
from datetime import datetime, timedelta
import time

class SessionManager:
    @staticmethod
    def check_for_updates():
        """Vérifie les mises à jour périodiques et gère les retours Stripe"""
        
        # Vérifier les paramètres d'URL pour les retours Stripe
        query_params = st.query_params
        
        # Gestion des retours Stripe
        if "checkout" in query_params:
            checkout_status = query_params["checkout"]
            
            if checkout_status == "success":
                st.toast("✅ Paiement réussi ! Mise à jour de vos données...", icon="🎉")
                SessionManager._handle_stripe_return()
                
            elif checkout_status == "canceled":
                st.toast("❌ Paiement annulé", icon="⚠️")
                st.query_params.clear()
                
        elif "portal_return" in query_params:
            st.toast("🔄 Retour du portail de gestion", icon="⚙️")
            SessionManager._handle_stripe_return()
        
        # Vérifier le rafraîchissement périodique (toutes les 2 minutes)
        last_check = st.session_state.get("last_session_check")
        now = datetime.now()
        
        if not last_check or (now - last_check).seconds > 120:
            st.session_state["last_session_check"] = now
            
            # Vérifier si le token est toujours valide
            if st.session_state.get("access_token"):
                SessionManager._check_token_validity()
    
    @staticmethod
    def _handle_stripe_return():
        """Gère le retour de Stripe (checkout ou billing portal)"""
        # Marquer pour rafraîchissement
        st.session_state["force_refresh"] = True
        
        # Effacer le cache des données utilisateur
        cache_keys = ["user_data_cache", "cache_time"]
        for key in cache_keys:
            if key in st.session_state:
                del st.session_state[key]
        
        # Effacer les paramètres d'URL
        st.query_params.clear()
        
        # Attendre un peu pour laisser Stripe traiter le webhook
        time.sleep(2)
        
        # Rafraîchir
        SessionManager.refresh_session()
    
    @staticmethod
    def _check_token_validity():
        """Vérifie si le token JWT est toujours valide"""
        # Ici, vous pourriez implémenter une vérification du token
        # Pour l'instant, on se contente de vérifier la présence
        
        token = st.session_state.get("access_token")
        if not token:
            return
        
        # Vérifier l'expiration (timestamp dans le payload JWT)
        # Note: Ceci est un exemple simplifié
        try:
            import jwt
            # Essayer de décoder le token
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Vérifier l'expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                st.warning("Session expirée. Veuillez vous reconnecter.")
                SessionManager.logout()
                
        except Exception:
            # En cas d'erreur, ne rien faire
            pass
    
    @staticmethod
    def refresh_session():
        """Rafraîchit la session sans déconnexion"""
        if not st.session_state.get("force_refresh"):
            return
        
        print("🔄 Rafraîchissement de la session...")
        
        # Sauvegarder l'essentiel
        essentials = {
            "access_token": st.session_state.get("access_token"),
            "refresh_token": st.session_state.get("refresh_token"),
            "email": st.session_state.get("email"),
            "logged_in": st.session_state.get("logged_in", False),
            "user": st.session_state.get("user"),
            "lang_radio": st.session_state.get("lang_radio", "FR")
        }
        
        # Liste des clés à conserver
        keys_to_keep = set(essentials.keys())
        
        # Effacer tout sauf l'essentiel
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]
        
        # Restaurer l'essentiel
        for key, value in essentials.items():
            if value is not None:
                st.session_state[key] = value
        
        # Effacer le flag de rafraîchissement
        if "force_refresh" in st.session_state:
            del st.session_state["force_refresh"]
        
        # Enregistrer le moment du rafraîchissement
        st.session_state["last_refresh"] = datetime.now()
        
        print("✅ Session rafraîchie")
        st.rerun()
    
    @staticmethod
    def force_refresh():
        """Marque la session pour rafraîchissement manuel"""
        st.session_state["force_refresh"] = True
        st.rerun()
    
    @staticmethod
    def logout():
        """Déconnecte complètement l'utilisateur"""
        print("🚪 Déconnexion...")
        
        # Effacer toute la session
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Effacer les paramètres d'URL
        if hasattr(st, 'query_params'):
            st.query_params.clear()
        
        print("✅ Déconnexion réussie")
        st.rerun()
    
    @staticmethod
    def get_session_info():
        """Retourne des informations sur la session"""
        return {
            "logged_in": bool(st.session_state.get("access_token")),
            "user_email": st.session_state.get("email"),
            "last_refresh": st.session_state.get("last_refresh"),
            "language": st.session_state.get("lang_radio", "FR"),
            "plan": st.session_state.get("user", {}).get("subscription_type", "free")
        }
    
    @staticmethod
    def show_session_status():
        """Affiche le statut de la session dans la sidebar"""
        if st.session_state.get("logged_in"):
            info = SessionManager.get_session_info()
            
            st.sidebar.markdown("---")
            st.sidebar.markdown("**📊 Statut Session**")
            
            col1, col2 = st.sidebar.columns([1, 1])
            with col1:
                st.metric("Plan", info["plan"].upper())
            with col2:
                st.metric("Langue", info["language"])
            
            if info["last_refresh"]:
                delta = datetime.now() - info["last_refresh"]
                st.sidebar.caption(f"Dernier rafraîchissement: {delta.seconds // 60} min")
            
            # Bouton de rafraîchissement manuel
            if st.sidebar.button("🔄 Rafraîchir session", use_container_width=True):
                SessionManager.force_refresh()


# Fonction pour tester
if __name__ == "__main__":
    print("🧪 SessionManager module chargé")
    print("Fonctions disponibles:")
    print("  - check_for_updates()")
    print("  - refresh_session()")
    print("  - force_refresh()")
    print("  - logout()")
    print("  - get_session_info()")
    print("  - show_session_status()")