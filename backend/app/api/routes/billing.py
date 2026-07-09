# api/routes/billing.py
#
# Billing and plan management endpoints.
#
# CURRENT STATE:
# Stripe is not integrated yet. Plan gating is enforced via the
# check_repo_limit dependency in repos.py and the profiles.plan column
# in Supabase. These endpoints return real usage data and stub out
# the Stripe checkout URLs for later integration.
#
# WHEN ADDING STRIPE:
# 1. pip install stripe
# 2. Add STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET to .env
# 3. Replace the stub responses in upgrade() and portal() with
#    real stripe.checkout.Session.create() and stripe.billing_portal
#    calls. The endpoint structure stays the same.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.core.supabase import supabase_admin, execute
from app.core.config import settings
from app.models.user import UserProfile

import structlog

log = structlog.get_logger(__name__)

router = APIRouter()


# Response models 

class PlanResponse(BaseModel):
    plan:                  str
    repos_used:            int
    repos_limit:           int
    is_pro:                bool


class CheckoutResponse(BaseModel):
    checkout_url: str
    message:      str


# ── GET /billing/plan ──────────────────────────────────────────────────────

@router.get("/billing/plan", response_model=PlanResponse)
async def get_plan(current_user: UserProfile = Depends(get_current_user)):
    """
    Returns the current user's plan and usage.
    Called by the frontend to decide whether to show upgrade prompts
    and to display usage stats in the dashboard.
    """
    repos_limit = (
        999999 if current_user.plan == "pro"
        else settings.FREE_TIER_REPOS_LIMIT
    )

    return PlanResponse(
        plan=current_user.plan,
        repos_used=current_user.repos_used,
        repos_limit=repos_limit,
        is_pro=current_user.plan == "pro",
    )


# POST /billing/upgrade 

@router.post("/billing/upgrade", response_model=CheckoutResponse)
async def upgrade(current_user: UserProfile = Depends(get_current_user)):
    """
    Returns a Stripe checkout URL for upgrading to pro.

    Currently returns a placeholder since Stripe is not integrated.
    When Stripe is added, replace the body with:

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": "price_YOUR_PRICE_ID", "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL}/billing/success",
            cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
            client_reference_id=current_user.id,
        )
        return CheckoutResponse(checkout_url=session.url, message="Redirecting to Stripe")
    """
    if current_user.plan == "pro":
        raise HTTPException(status_code=400, detail="You are already on the pro plan.")

    log.info("upgrade_requested", user_id=current_user.id)

    return CheckoutResponse(
        checkout_url=f"{settings.FRONTEND_URL}/billing/coming-soon",
        message="Billing integration coming soon. Contact us to upgrade manually.",
    )


# POST /billing/portal

@router.post("/billing/portal", response_model=CheckoutResponse)
async def billing_portal(current_user: UserProfile = Depends(get_current_user)):
    """
    Returns a Stripe customer portal URL for managing subscriptions.

    When Stripe is added, replace with:

        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/dashboard",
        )
        return CheckoutResponse(checkout_url=session.url, message="Redirecting to portal")
    """
    if current_user.plan != "pro":
        raise HTTPException(
            status_code=400,
            detail="Billing portal is only available for pro users.",
        )

    return CheckoutResponse(
        checkout_url=f"{settings.FRONTEND_URL}/dashboard",
        message="Billing portal not yet integrated.",
    )


# Admin: manually upgrade a user (useful before Stripe is integrated)

@router.post("/billing/admin/upgrade/{user_id}")
async def admin_upgrade_user(
    user_id: str,
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Manually upgrades a user to pro. Admin only.

    Useful during the pre-Stripe phase for manually upgrading early users
    or testers without needing a payment flow.

    Currently restricted to the first admin user whose ID you hardcode
    in the ADMIN_USER_ID env var. Replace with a proper role system later.
    """
    import os
    admin_id = os.getenv("ADMIN_USER_ID", "")
    if not admin_id or current_user.id != admin_id:
        raise HTTPException(status_code=403, detail="Admin only.")

    execute(
        supabase_admin.table("profiles").update({
            "plan": "pro"
        }).eq("id", user_id).execute()
    )

    log.info("user_manually_upgraded", user_id=user_id, upgraded_by=current_user.id)
    return {"message": f"User {user_id} upgraded to pro."}
