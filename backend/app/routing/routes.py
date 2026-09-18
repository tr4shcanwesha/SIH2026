import random
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.auth import (
    active_sessions,
    activate_beekeeper_session,
    create_beekeeper,
    get_session_beekeeper_id,
    get_session_email,
    new_beekeeper_id,
    router as auth_router,
    supabase,
)
from app.routing.router import router as page_router
from app.services.batches import (
    add_hive as add_hive_record,
    create_batch,
    list_batches,
    list_hive_iot_data as list_hive_iot_data_records,
    list_hives as list_hive_records,
    remove_hive as remove_hive_record,
    update_batch_status_admin,
)
from app.services.blockchain import get_batch_certificate, get_batch_verification
from app.services.beekeepers import (
    delete_beekeeper_account,
    get_beekeeper_profile,
    save_uploaded_file,
    update_beekeeper_profile,
    update_beekeeper_profile_with_uploads,
)
from app.services.assistant import answer_question

router = APIRouter()


class HiveCreate(BaseModel):
    location: str
    bee_species: str
    hive_type: str
    installation_date: str
    status: str = "Healthy"


class HoneyBatchCreate(BaseModel):
    hive_id: str
    honey_type: str = "Golden Canopy Reserve"
    quantity: float = Field(default_factory=lambda: round(random.uniform(10, 50), 2), gt=0)


class BeekeeperProfileUpdate(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    location: str = Field(min_length=1)


class AdminDecision(BaseModel):
    status: str


class AssistantMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


@router.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/profile")
def profile(request: Request) -> dict[str, Any]:
    beekeeper_id = get_session_beekeeper_id(request.cookies.get("honeychain_session"))
    if beekeeper_id:
        profile_data = get_beekeeper_profile(beekeeper_id)
        profile_data["beekeeper"]["profile_exists"] = True
        return profile_data
    email = get_session_email(request.cookies.get("honeychain_session"))
    if email:
        return {
            "beekeeper": {
                "email": email,
                "name": "",
                "phone": "",
                "location": "",
                "kyc_status": "pending",
                "profile_exists": False,
            },
            "stats": {"hives": 0, "harvested": 0, "processed": 0, "distributed": 0},
        }
    raise HTTPException(status_code=401, detail="Authentication required")


@router.patch("/api/profile")
async def update_profile(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get("honeychain_session")
    beekeeper_id = get_session_beekeeper_id(session_id)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form_data = await request.form()
        payload: dict[str, Any] = {}
        for key, value in form_data.items():
            if hasattr(value, "filename"):
                payload[key] = value
            else:
                payload[key] = value
        if not beekeeper_id:
            email = get_session_email(session_id)
            if not email:
                raise HTTPException(status_code=401, detail="Authentication required")
            required_fields = (
                "name",
                "phone",
                "location",
                "identity_document_type",
                "certificate_type",
            )
            missing_fields = [field for field in required_fields if not str(payload.get(field, "")).strip()]
            if missing_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Required onboarding fields missing: {', '.join(missing_fields)}",
                )
            identity_document = payload.get("identity_document")
            if identity_document is None or not getattr(identity_document, "filename", ""):
                raise HTTPException(status_code=400, detail="Identity document file is required")
            certificate = payload.get("certificate")
            if certificate is None or not getattr(certificate, "filename", ""):
                raise HTTPException(status_code=400, detail="Certificate file is required")
            new_id = new_beekeeper_id()
            identity_document_path = await save_uploaded_file(identity_document, new_id, "identity_document")
            certificate_path = await save_uploaded_file(certificate, new_id, "certificate")
            profile_fields = {
                field: str(payload[field]).strip()
                for field in (
                    "name",
                    "phone",
                    "location",
                    "identity_document_type",
                    "certificate_type",
                )
            }
            profile_fields["identity_document_path"] = identity_document_path
            profile_fields["certificate_path"] = certificate_path
            profile_fields["beekeeper_id"] = new_id
            beekeeper_id = create_beekeeper(email, profile_fields)
            activate_beekeeper_session(session_id, beekeeper_id)
            payload.pop("identity_document", None)
            payload.pop("certificate", None)
        updated = await update_beekeeper_profile_with_uploads(beekeeper_id, payload)
        return get_beekeeper_profile(beekeeper_id)

    if not beekeeper_id:
        raise HTTPException(status_code=400, detail="Submit the onboarding form to create your profile")
    payload = await request.json()
    update_beekeeper_profile(beekeeper_id, payload)
    return get_beekeeper_profile(beekeeper_id)


@router.delete("/api/profile", status_code=204)
def delete_profile(request: Request) -> None:
    session_id = request.cookies.get("honeychain_session")
    beekeeper_id = current_beekeeper_id(request)
    delete_beekeeper_account(beekeeper_id)
    active_sessions.pop(session_id, None)


def current_beekeeper_id(request: Request) -> str:
    beekeeper_id = get_session_beekeeper_id(request.cookies.get("honeychain_session"))
    if not beekeeper_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return beekeeper_id


@router.post("/api/assistant/chat")
def assistant_chat(payload: AssistantMessage, request: Request) -> dict[str, str]:
    beekeeper_id = current_beekeeper_id(request)
    return {"answer": answer_question(beekeeper_id, payload.message.strip(), payload.history)}


@router.get("/api/hives")
def list_hives(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    return list_hive_records(beekeeper_id)


@router.get("/api/hive-iot-data")
def hive_iot_data(request: Request, limit: int = 8) -> list[dict[str, Any]]:
    return list_hive_iot_data_records(current_beekeeper_id(request), limit)


@router.post("/api/hives", status_code=201)
def add_hive(hive: HiveCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    return add_hive_record(hive.model_dump(), beekeeper_id)


@router.post("/api/honey-batches", status_code=201)
def create_honey_batch(batch: HoneyBatchCreate, request: Request) -> dict[str, Any]:
    beekeeper_id = current_beekeeper_id(request)
    return create_batch(batch.model_dump(mode="json"), beekeeper_id, str(request.base_url).rstrip("/"))


@router.get("/api/honey-batches")
def list_honey_batches(request: Request) -> list[dict[str, Any]]:
    beekeeper_id = current_beekeeper_id(request)
    return list_batches(beekeeper_id, str(request.base_url).rstrip("/"))


@router.patch("/api/admin/beekeepers/{beekeeper_id}")
def decide_beekeeper(beekeeper_id: str, decision: AdminDecision, request: Request) -> dict[str, Any]:
    status = decision.status.strip().lower()
    if status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")
    response = supabase.table("beekeeper").update({"kyc_status": status}).eq("beekeeper_id", beekeeper_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")
    return response.data[0]


@router.patch("/api/admin/batches/{batch_id}")
def advance_batch_as_admin(batch_id: str, decision: AdminDecision, request: Request) -> dict[str, Any]:
    status = decision.status.strip().upper()
    if status not in {"PROCESSED", "DISTRIBUTED"}:
        raise HTTPException(status_code=400, detail="Batch status must be PROCESSED or DISTRIBUTED")
    return update_batch_status_admin(batch_id, status)


@router.get("/api/public/batches/{batch_id}")
def get_public_batch(batch_id: str) -> dict[str, Any]:
    return get_batch_verification(batch_id)


@router.get("/api/public/batches/{batch_id}/certificate")
def get_public_certificate(batch_id: str) -> Response:
    pdf_bytes = get_batch_certificate(batch_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{batch_id}-honeychain-certificate.pdf"'},
    )


@router.delete("/api/hives/{hive_id}", status_code=204)
def remove_hive(hive_id: str, request: Request) -> None:
    beekeeper_id = current_beekeeper_id(request)
    remove_hive_record(hive_id, beekeeper_id)


router.include_router(auth_router)
router.include_router(page_router)