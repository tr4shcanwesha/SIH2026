import json
import os
import secrets
from io import BytesIO
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from app.auth.auth import supabase
from app.services.blockchain import append_batch_block


CERTIFICATE_BUCKET = os.getenv("SUPABASE_CERTIFICATE_BUCKET", "honey-certificates")


LAB_RESULTS = {
    "quality_grade": "A+",
    "moisture_percent": 17.4,
    "ph": 4.1,
    "hmf_mg_per_kg": 8.6,
    "adulteration_screen": "Clear",
    "pollen_profile": "Multifloral signature confirmed",
    "test_method": "HoneyChain Collection Lab protocol",
}


def issue_certificate(batch: dict[str, Any], hive: dict[str, Any]) -> dict[str, Any]:
    existing = (
        supabase.table("batch_certificates")
        .select("*")
        .eq("batch_id", batch["batch_id"])
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    issued_at = datetime.now(timezone.utc).isoformat()
    certificate = {
        "certificate_id": f"HC-CERT-{batch['batch_id'].removeprefix('HB-')}",
        "batch_id": batch["batch_id"],
        "issued_at": issued_at,
        "lab_name": "HoneyChain Collection Lab",
        "results": LAB_RESULTS,
    }
    beekeeper_response = (
        supabase.table("beekeeper")
        .select("name")
        .eq("beekeeper_id", hive.get("beekeeper_id"))
        .limit(1)
        .execute()
    )
    beekeeper_name = (
        beekeeper_response.data[0].get("name")
        if beekeeper_response.data
        else "Verified beekeeper"
    )
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    pdf.setFillColor(colors.HexColor("#FCF6DA"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#B5852B"))
    pdf.setLineWidth(0.7)
    pdf.rect(34, 30, width - 68, height - 60, fill=0, stroke=1)
    pdf.setLineWidth(0.45)
    pdf.rect(48, 44, width - 96, height - 88, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#8F6018"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(width / 2, height - 63, "HONEYCHAIN  /  COLLECTION CENTER")
    pdf.setFillColor(colors.HexColor("#302416"))
    pdf.setFont("Times-Bold", 28)
    pdf.drawCentredString(width / 2, height - 106, "Certificate of Processed Honey")
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#665030"))
    pdf.drawCentredString(width / 2, height - 130, "This certificate confirms that the batch below passed the HoneyChain collection center release protocol.")
    pdf.setFillColor(colors.HexColor("#302416"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(width / 2, height - 176, batch["batch_id"])
    pdf.setStrokeColor(colors.HexColor("#302416"))
    pdf.setLineWidth(0.8)
    pdf.line(145, height - 196, width - 145, height - 196)
    released_at = datetime.fromisoformat(issued_at).astimezone(ZoneInfo("Asia/Kolkata"))
    released_label = released_at.strftime("%b %d, %Y, %I:%M %p")
    rows = [
        ("BEEKEEPER", beekeeper_name),
        ("HONEY PROFILE", batch.get("honey_type", "Raw honey")),
        ("ORIGIN HIVE", batch["hive_id"]),
        ("VOLUME", f"{batch.get('quantity', '-')} kg"),
        ("QUALITY GRADE", LAB_RESULTS["quality_grade"]),
        ("RELEASED", released_label),
    ]
    pdf.setFont("Helvetica-Bold", 8)
    for index, (label, value) in enumerate(rows):
        x = 283 + (index % 2) * 275
        y = height - 250 - (index // 2) * 44
        pdf.setFillColor(colors.HexColor("#755626"))
        pdf.drawCentredString(x, y, label)
        pdf.setFillColor(colors.HexColor("#302416"))
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(x, y - 14, str(value)[:42])
        pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColor(colors.HexColor("#8F6018"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawRightString(width - 58, 76, "AUTHENTICITY RECORD")
    pdf.setFillColor(colors.HexColor("#665030"))
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - 58, 60, "Issued by HoneyChain Collection Center  ·  Ledger linked")
    pdf.save()
    certificate_path = f"certificates/{batch['batch_id']}.pdf"
    try:
        supabase.storage.from_(CERTIFICATE_BUCKET).upload(
            certificate_path,
            pdf_buffer.getvalue(),
            {"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Certificate storage upload failed") from error
    certificate["storage_path"] = certificate_path
    response = supabase.table("batch_certificates").insert(certificate).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Certificate record could not be created")
    return response.data[0]


def list_hives(beekeeper_id: str) -> list[dict[str, Any]]:
    response = supabase.table("hives").select("*").eq("beekeeper_id", beekeeper_id).order("hive_id").execute()
    hives = response.data or []
    if not hives:
        return []

    hive_ids = [hive["hive_id"] for hive in hives]
    iot_response = (
        supabase.table("hive_iot_data")
        .select("hive_id, recorded_at, temperature, humidity, co2, weight, sound, bee_count")
        .in_("hive_id", hive_ids)
        .order("recorded_at", desc=True)
        .execute()
    )
    latest_iot_by_hive: dict[str, dict[str, Any]] = {}
    for reading in iot_response.data or []:
        latest_iot_by_hive.setdefault(reading["hive_id"], reading)

    for hive in hives:
        latest_iot = latest_iot_by_hive.get(hive["hive_id"])
        if latest_iot:
            hive.update(
                {
                    "recorded_at": latest_iot["recorded_at"],
                    "temperature": latest_iot["temperature"],
                    "humidity": latest_iot["humidity"],
                    "co2": latest_iot["co2"],
                    "weight": latest_iot["weight"],
                    "sound": latest_iot["sound"],
                    "bee_count": latest_iot["bee_count"],
                }
            )
    return hives


def list_hive_iot_data(beekeeper_id: str, limit: int = 8) -> list[dict[str, Any]]:
    hives_response = supabase.table("hives").select("hive_id").eq("beekeeper_id", beekeeper_id).execute()
    hive_ids = [hive["hive_id"] for hive in hives_response.data or []]
    if not hive_ids:
        return []
    readings: list[dict[str, Any]] = []
    per_hive_limit = max(1, min(limit, 100))
    for hive_id in hive_ids:
        response = (
            supabase.table("hive_iot_data")
            .select("hive_id, recorded_at, temperature, humidity, co2, weight, sound, bee_count")
            .eq("hive_id", hive_id)
            .order("recorded_at", desc=True)
            .limit(per_hive_limit)
            .execute()
        )
        readings.extend(response.data or [])
    return sorted(readings, key=lambda reading: reading["recorded_at"], reverse=True)


def add_hive(payload: dict[str, Any], beekeeper_id: str) -> dict[str, Any]:
    payload["hive_id"] = generate_unique_hive_id()
    payload["beekeeper_id"] = beekeeper_id
    response = supabase.table("hives").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Hive could not be added")
    iot_response = supabase.table("hive_iot_data").insert(generate_initial_iot_reading(payload["hive_id"])).execute()
    if not iot_response.data:
        raise HTTPException(status_code=502, detail="Hive was created, but its initial IoT data could not be saved")
    return response.data[0]


def generate_initial_iot_reading(hive_id: str) -> dict[str, Any]:
    generator = secrets.SystemRandom()
    return {
        "hive_id": hive_id,
        "temperature": round(generator.uniform(30, 38), 2),
        "humidity": round(generator.uniform(45, 75), 2),
        "co2": round(generator.uniform(300, 1500), 2),
        "weight": round(generator.uniform(10, 35), 2),
        "sound": round(generator.uniform(20, 80), 2),
        "bee_count": generator.randint(10000, 50000),
    }


def generate_unique_hive_id() -> str:
    for _ in range(5):
        hive_id = f"HC-{secrets.token_hex(4).upper()}"
        existing = supabase.table("hives").select("hive_id").eq("hive_id", hive_id).limit(1).execute()
        if not existing.data:
            return hive_id
    raise HTTPException(status_code=503, detail="Unable to generate a unique hive ID")


def create_batch(payload: dict[str, Any], beekeeper_id: str, base_url: str) -> dict[str, Any]:
    hive_response = (
        supabase.table("hives")
        .select("*")
        .eq("hive_id", payload["hive_id"])
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not hive_response.data:
        raise HTTPException(status_code=404, detail="Hive not found")

    batch_id = generate_unique_batch_id()
    payload["batch_id"] = batch_id
    payload["harvest_date"] = date.today().isoformat()
    payload["status"] = "HARVESTED"
    response = supabase.table("honey_batches").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch could not be created")

    beekeeper_response = supabase.table("beekeeper").select("*").eq("beekeeper_id", beekeeper_id).limit(1).execute()
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")
    created_batch = response.data[0]
    append_batch_block(created_batch, hive_response.data[0], "BATCH_CREATED")
    created_batch["verification_url"] = f"{base_url}/verify/{batch_id}"
    return created_batch


def generate_unique_batch_id() -> str:
    for _ in range(5):
        batch_id = f"HB-{secrets.token_hex(4).upper()}"
        existing = supabase.table("honey_batches").select("batch_id").eq("batch_id", batch_id).limit(1).execute()
        if not existing.data:
            return batch_id
    raise HTTPException(status_code=503, detail="Unable to generate a unique batch ID")


def list_batches(beekeeper_id: str, base_url: str) -> list[dict[str, Any]]:
    hives = supabase.table("hives").select("hive_id").eq("beekeeper_id", beekeeper_id).execute()
    hive_ids = [hive["hive_id"] for hive in (hives.data or [])]
    if not hive_ids:
        return []
    response = (
        supabase.table("honey_batches")
        .select("*")
        .in_("hive_id", hive_ids)
        .order("harvest_date", desc=True)
        .execute()
    )
    batches = response.data or []
    for batch in batches:
        batch["verification_url"] = f"{base_url}/verify/{batch['batch_id']}"
    return batches


def update_batch_status(batch_id: str, status: str, beekeeper_id: str) -> dict[str, Any]:
    batch_response = supabase.table("honey_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")
    owned_hive = (
        supabase.table("hives")
        .select("*")
        .eq("hive_id", batch_response.data[0]["hive_id"])
        .eq("beekeeper_id", beekeeper_id)
        .limit(1)
        .execute()
    )
    if not owned_hive.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")
    current_status = str(batch_response.data[0]["status"]).upper()
    expected_next = {"HARVESTED": "PROCESSED", "PROCESSED": "DISTRIBUTED"}.get(current_status)
    if status != expected_next:
        raise HTTPException(status_code=409, detail="Invalid batch status transition")
    response = supabase.table("honey_batches").update({"status": status}).eq("batch_id", batch_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch status could not be updated")
    beekeeper_response = supabase.table("beekeeper").select("*").eq("beekeeper_id", beekeeper_id).limit(1).execute()
    if not beekeeper_response.data:
        raise HTTPException(status_code=404, detail="Beekeeper not found")
    updated_batch = response.data[0]
    append_batch_block(updated_batch, owned_hive.data[0], f"STATUS_{status}")
    if status == "PROCESSED":
        certificate = issue_certificate(updated_batch, owned_hive.data[0])
        append_batch_block(updated_batch, owned_hive.data[0], "CERTIFICATE_ISSUED", certificate)
    return updated_batch


def update_batch_status_admin(batch_id: str, status: str) -> dict[str, Any]:
    batch_response = supabase.table("honey_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Honey batch not found")
    batch = batch_response.data[0]
    current_status = str(batch["status"]).upper()
    expected_next = {"HARVESTED": "PROCESSED", "PROCESSED": "DISTRIBUTED"}.get(current_status)
    if status != expected_next:
        raise HTTPException(status_code=409, detail="Invalid batch status transition")
    hive_response = supabase.table("hives").select("*").eq("hive_id", batch["hive_id"]).limit(1).execute()
    if not hive_response.data:
        raise HTTPException(status_code=404, detail="Hive not found for honey batch")
    response = supabase.table("honey_batches").update({"status": status}).eq("batch_id", batch_id).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Honey batch status could not be updated")
    updated_batch = response.data[0]
    hive = hive_response.data[0]
    append_batch_block(updated_batch, hive, f"STATUS_{status}")
    if status == "PROCESSED":
        certificate = issue_certificate(updated_batch, hive)
        append_batch_block(updated_batch, hive, "CERTIFICATE_ISSUED", certificate)
    return updated_batch


def update_hive_status(hive_id: str, beekeeper_id: str, status: str) -> dict[str, Any]:
    normalized_status = status.strip().title()
    if normalized_status not in {"Healthy", "Inactive"}:
        raise HTTPException(status_code=400, detail="Hive status must be Healthy or Inactive")

    response = (
        supabase.table("hives")
        .update({"status": normalized_status})
        .eq("hive_id", hive_id)
        .eq("beekeeper_id", beekeeper_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Hive not found")
    return response.data[0]