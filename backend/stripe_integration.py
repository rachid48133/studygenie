# backend/stripe_integration.py
"""
Intégration Stripe pour gestion des abonnements
- Création customers
- Création checkout sessions
- Gestion webhooks
- Synchronisation avec DB
"""

import stripe
import os
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, Optional

load_dotenv()

# Configuration Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Prix Stripe configurés - MIS À JOUR 16 JAN 2026
STRIPE_PRICES = {
    "basic": {
        "price_id": "price_1SqIOJ0n8neEYCaVz6o0oJ92",
        "amount": 999,  # $9.99
        "currency": "cad"
    },
    "pro": {
        "price_id": "price_1SocJi0n8neEYCaVHDMOfTg8",
        "amount": 1999,  # $19.99
        "currency": "usd"
    },
    "premium": {
        "price_id": "price_1SqIa50n8neEYCaVsxML9Szk",  
        "amount": 4999,  # $49.99
        "currency": "usd"
    }
}


# ============================================
# CRÉATION CUSTOMER & CHECKOUT
# ============================================

def create_stripe_customer(email: str, user_id: int) -> str:
    """Crée un customer Stripe"""
    try:
        customer = stripe.Customer.create(
            email=email,
            metadata={"user_id": user_id}
        )
        print(f"✅ Stripe customer créé : {customer.id}")
        return customer.id
    except stripe.error.StripeError as e:
        print(f"❌ Erreur création customer : {e}")
        raise


def create_checkout_session(
    user_id: int,
    email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
    customer_id: Optional[str] = None
) -> str:
    """Crée une session de paiement Stripe"""
    
    if plan not in STRIPE_PRICES:
        raise ValueError(f"Plan {plan} non trouvé")
    
    price_id = STRIPE_PRICES[plan]["price_id"]
    
    try:
        if not customer_id:
            customer_id = create_stripe_customer(email, user_id)
        
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "plan": plan
            }
        )
        
        print(f"✅ Checkout session créée : {session.id}")
        return session.url
    
    except stripe.error.StripeError as e:
        print(f"❌ Erreur création checkout : {e}")
        raise


# ============================================
# WEBHOOKS HANDLERS
# ============================================

def verify_webhook_signature(payload: bytes, sig_header: str) -> Dict:
    """Vérifie la signature du webhook Stripe"""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError as e:
        print(f"❌ Payload invalide : {e}")
        raise
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Signature invalide : {e}")
        raise


def handle_subscription_created(subscription_data: Dict, db: Session):
    """Gère la création d'un abonnement"""
    from main import User
    
    user_id = int(subscription_data["metadata"].get("user_id", 0))
    plan = subscription_data["metadata"].get("plan", "pro")
    
    print(f"📝 Subscription created : User {user_id} → Plan {plan}")
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        print(f"❌ User {user_id} not found")
        return
    
    user.subscription_type = plan
    user.stripe_customer_id = subscription_data["customer"]
    user.stripe_subscription_id = subscription_data["id"]
    
    db.commit()
    print(f"✅ User {user_id} upgraded to {plan}")


def handle_subscription_updated(subscription_data: Dict, db: Session):
    """Gère la mise à jour d'un abonnement"""
    handle_subscription_created(subscription_data, db)


def handle_subscription_deleted(subscription_data: Dict, db: Session):
    """Gère l'annulation d'un abonnement"""
    from main import User
    
    stripe_sub_id = subscription_data["id"]
    print(f"🚫 Subscription deleted : {stripe_sub_id}")
    
    user = db.query(User).filter(
        User.stripe_subscription_id == stripe_sub_id
    ).first()
    
    if not user:
        print(f"❌ User with subscription {stripe_sub_id} not found")
        return
    
    user.subscription_type = "free"
    user.stripe_subscription_id = None
    db.commit()
    print(f"✅ User {user.id} downgraded to free")


def handle_payment_succeeded(invoice_data: Dict, db: Session):
    """Gère un paiement réussi"""
    print(f"💰 Payment succeeded : {invoice_data['id']}")


def handle_payment_failed(invoice_data: Dict, db: Session):
    """Gère un paiement échoué"""
    from main import User
    customer_id = invoice_data["customer"]
    print(f"❌ Payment failed : {customer_id}")
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        print(f"⚠️ User {user.id} payment failed")


def handle_checkout_completed(session_data: Dict, db: Session):
    """Gère la fin d'une session checkout"""
    print(f"✅ Checkout completed : {session_data['id']}")


# ============================================
# GESTION CENTRALE DES WEBHOOKS
# ============================================

def process_webhook_event(event: Dict, db: Session) -> Dict:
    """Traite un événement webhook Stripe"""
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    print(f"\n{'='*60}")
    print(f"📥 WEBHOOK : {event_type}")
    print(f"{'='*60}")
    
    handlers = {
        "customer.subscription.created": handle_subscription_created,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_succeeded": handle_payment_succeeded,
        "invoice.payment_failed": handle_payment_failed,
        "checkout.session.completed": handle_checkout_completed,
    }
    
    handler = handlers.get(event_type)
    
    if handler:
        try:
            handler(data, db)
            return {"status": "success", "message": f"Handled {event_type}"}
        except Exception as e:
            print(f"❌ Erreur traitement webhook : {e}")
            return {"status": "error", "message": str(e)}
    else:
        print(f"ℹ️ Événement {event_type} non géré (OK)")
        return {"status": "ignored", "message": f"Event {event_type} not handled"}


# ============================================
# GESTION ABONNEMENTS
# ============================================

def cancel_subscription(subscription_id: str):
    """Annule un abonnement Stripe"""
    try:
        subscription = stripe.Subscription.delete(subscription_id)
        print(f"✅ Abonnement {subscription_id} annulé")
        return subscription
    except stripe.error.StripeError as e:
        print(f"❌ Erreur annulation : {e}")
        raise


def get_subscription_status(subscription_id: str) -> Dict:
    """Récupère le statut d'un abonnement"""
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end),
            "cancel_at_period_end": subscription.cancel_at_period_end
        }
    except stripe.error.StripeError as e:
        print(f"❌ Erreur récupération : {e}")
        return None


if __name__ == "__main__":
    print("🧪 Module Stripe chargé")
    print(f"✅ Stripe API Key : {stripe.api_key[:20] if stripe.api_key else 'NON CONFIGURÉE'}...")
    print("\n💳 Plans disponibles :")
    for plan_name, plan_data in STRIPE_PRICES.items():
        price = plan_data["amount"] / 100
        print(f"  - {plan_name.upper()}: ${price:.2f}/mois (Price ID: {plan_data['price_id']})")
