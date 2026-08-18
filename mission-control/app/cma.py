"""
Phase 22 - CMA Tool (FlexCMA) module.

Comparative Market Analysis builder for TPL agents. Replaces CloudCMA.

Session 1 (this file):
  - JWT-gated CRUD on cmas + cma_comps
  - ZIP ingest: agent uploads a Flex CMA export bundle from their MLS
    (textCma.csv + <MLS#>_<n>.jpg photos). We parse the CSV, upload the
    photos to the Supabase Storage `cma-photos` bucket, and insert one
    cma_comps row per listing.

Sessions 2 + 3 will add:
  - Pricing engine (_compute_pricing)
  - Public /cma/<share_token> report route + PDF generation

Wired from main.py the same way coaching.py / prospect_engagement.py are:
  import cma as _cma_mod
  _cma_mod.setup(db, supabase)
  app.include_router(_cma_mod.router)

And cmas + cma_comps are added to TENANT_TABLES so db() auto-scopes them.
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Callable, Any, List, Dict, Tuple
from datetime import datetime, date, timezone
import csv
import io
import json
import re
import zipfile


router = APIRouter(prefix="/api/cmas", tags=["cma"])
# Public router — no JWT. Whitelisted in main.py via PUBLIC_API_PREFIXES = "/api/cma-public/".
public_router = APIRouter(prefix="/api/cma-public", tags=["cma-public"])

_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None

STORAGE_BUCKET = "cma-photos"
MAX_PHOTOS_PER_COMP = 6  # first N in filename order; CMA report only needs a handful


def setup(db_callable, supabase_client):
    global _db, _supabase
    _db = db_callable
    _supabase = supabase_client


# ════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════

class CMACreate(BaseModel):
    subject_address: Optional[str] = None
    subject_city: Optional[str] = None
    subject_state: Optional[str] = None
    subject_zip: Optional[str] = None
    client_first_name: Optional[str] = None
    client_last_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    lead_id: Optional[int] = None
    subject: Optional[Dict[str, Any]] = None


class CMAUpdate(BaseModel):
    subject_address: Optional[str] = None
    subject_city: Optional[str] = None
    subject_state: Optional[str] = None
    subject_zip: Optional[str] = None
    subject: Optional[Dict[str, Any]] = None
    client_first_name: Optional[str] = None
    client_last_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    additional_clients: Optional[List[Dict[str, Any]]] = None
    lead_id: Optional[int] = None
    status: Optional[str] = None
    agent_notes: Optional[str] = None
    marketing_notes: Optional[str] = None


class CompUpdate(BaseModel):
    included: Optional[bool] = None
    agent_notes: Optional[str] = None
    adjustments: Optional[List[Dict[str, Any]]] = None
    agent_override: Optional[Dict[str, Any]] = None
    # Direct field edits (agent can also tweak parsed values)
    address: Optional[str] = None
    beds: Optional[int] = None
    baths_total: Optional[float] = None
    sqft_living: Optional[int] = None
    lot_size: Optional[float] = None
    year_built: Optional[int] = None
    current_price: Optional[float] = None
    list_price: Optional[float] = None
    dom: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


# ════════════════════════════════════════════════════════════
# Flex CSV → cma_comps field mapping
# ════════════════════════════════════════════════════════════

# CSV column headers from the Flex/Cloud CMA export
CSV_TO_COL = {
    "ML#": "mls_number",
    "Property Type": "property_type",
    "Type": "style",
    "Status": "status",
    "List Price": "list_price",
    "Original List Price": "original_list_price",
    "Current Price": "current_price",
    "Short Address": "address",
    "Street Number": "street_number",
    "Street Name": "street_name",
    "Unit Number": "unit_number",
    "City Name": "city",
    "County": "county",
    "State": "state",
    "Zip Code": "zip",
    "Subdivision Name": "subdivision",
    "#Beds": "beds",
    "#Baths Total": "baths_total",
    "#FBaths": "baths_full",
    "#HBaths": "baths_half",
    "Year Built": "year_built",
    "#Garage Spaces": "garage_spaces",
    "Sq Ft Living": "sqft_living",
    "Sq Ft Total": "sqft_total",
    "Approximate Lot Size": "lot_size",
    "Days On Market": "dom",
    "Listing Agent's Name": "listing_agent",
    "Agent Phone": "listing_agent_phone",
    "Agent Email Address": "listing_agent_email",
    "Pending Date": "pending_date",
    "Closing Date": "closing_date",
    "Expiration Date": "expiration_date",
    "Entry Date": "entry_date",
    "Status Change Date": "status_change_date",
    "Remarks": "remarks",
    "#Stories": "stories",
}

# These get bundled into the features JSONB
FEATURE_COLS = {
    "Construction Type": "construction_type",
    "Cooling Description": "cooling",
    "Exterior Features": "exterior",
    "Floor Description": "floor",
    "Pool Description": "pool_desc",
    "Security Information": "security",
    "Roof Description": "roof",
    "View": "view",
    "Waterfront Description": "waterfront_desc",
    "Windows/Treatment": "windows",
    "Subdivision Information": "subdivision_info",
    "Equipment/Appliances": "appliances",
    "Interior Features": "interior_features",
    "Front Exposure": "front_exposure",
    "Pets Allowed": "pets_allowed",
    "Property Condition": "property_condition",
    "Zoning Information": "zoning",
    "Association Fee": "hoa_fee",
    "Building Name/Number": "building",
    "#Carport Spaces": "carport_spaces",
    "Covered Spaces": "covered_spaces",
    "Elementary School": "elementary_school",
    "Middle School": "middle_school",
    "Senior High School": "high_school",
    "Development Name": "development",
    "Tax Amount": "tax_amount",
    "Possession Information": "possession",
    "Parcel Number": "parcel",
}


INT_COLS = {"beds", "baths_full", "baths_half", "year_built", "sqft_living", "sqft_total", "dom"}
FLOAT_COLS = {"list_price", "original_list_price", "current_price", "baths_total", "garage_spaces", "lot_size", "stories"}
DATE_COLS = {"pending_date", "closing_date", "expiration_date", "status_change_date"}
TS_COLS = {"entry_date"}
BOOL_COLS_YES_NO = {"Private Pool": "pool", "Waterfront": "waterfront"}


MLS_FILE_RE = re.compile(r"^([A-Za-z]?\d+)_(\d+)\.(?:jpg|jpeg|png)$", re.IGNORECASE)


def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _to_date(v: Any) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Flex format is YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(s.split(".")[0][:19] if "." in s else s[:19] if len(s) > 10 else s, fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    # Last resort: take first 10 chars if they look date-ish
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def _to_ts(v: Any) -> Optional[str]:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Try to keep as-is; PostgREST accepts ISO8601. Strip fractional-second junk if malformed.
    try:
        # Accept "2026-06-28 16:31:47.617643" or "2026-06-28T16:31:47Z"
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        if not s.endswith("Z") and "+" not in s and "T" in s:
            s = s + "Z"
        # Validate loosely
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None


def _yn_to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def _parse_csv_row(row: Dict[str, str]) -> Dict[str, Any]:
    """Map one CSV row to a cma_comps insert dict."""
    out: Dict[str, Any] = {}

    for csv_key, col in CSV_TO_COL.items():
        raw = row.get(csv_key, "")
        if raw is None:
            continue
        raw = raw.strip() if isinstance(raw, str) else raw
        if raw == "":
            continue
        if col in INT_COLS:
            out[col] = _to_int(raw)
        elif col in FLOAT_COLS:
            out[col] = _to_float(raw)
        elif col in DATE_COLS:
            out[col] = _to_date(raw)
        elif col in TS_COLS:
            out[col] = _to_ts(raw)
        else:
            out[col] = raw

    for csv_key, col in BOOL_COLS_YES_NO.items():
        raw = row.get(csv_key, "")
        b = _yn_to_bool(raw)
        if b is not None:
            out[col] = b

    # Features JSONB
    features: Dict[str, Any] = {}
    for csv_key, feat_key in FEATURE_COLS.items():
        raw = row.get(csv_key, "")
        if raw and str(raw).strip():
            features[feat_key] = str(raw).strip()
    if features:
        out["features"] = features

    # If pool is unset but Pool Description says something other than "None"/"" infer true
    if out.get("pool") is None:
        pd = (features.get("pool_desc") or "").strip().lower()
        if pd and pd not in ("none", "no"):
            out["pool"] = True

    return {k: v for k, v in out.items() if v not in (None, "")}


def _group_photos_by_mls(zf: zipfile.ZipFile) -> Dict[str, List[Tuple[int, str]]]:
    """Group photo filenames in the zip by MLS number. Returns {mls: [(index, name), ...]} sorted by index."""
    grouped: Dict[str, List[Tuple[int, str]]] = {}
    for name in zf.namelist():
        base = name.rsplit("/", 1)[-1]
        m = MLS_FILE_RE.match(base)
        if not m:
            continue
        mls = m.group(1).upper()
        idx = int(m.group(2))
        grouped.setdefault(mls, []).append((idx, name))
    for mls in grouped:
        grouped[mls].sort(key=lambda t: t[0])
    return grouped


def _upload_photo(cma_id: int, mls: str, idx: int, data: bytes, content_type: str = "image/jpeg") -> Optional[str]:
    """Upload one photo to the cma-photos bucket. Returns public URL or None on failure."""
    path = f"{cma_id}/{mls}_{idx}.jpg"
    try:
        # supabase-py v2: storage.from_(bucket).upload(path, file, file_options={...})
        _supabase.storage.from_(STORAGE_BUCKET).upload(
            path,
            data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        # If it already exists, upsert handles it; anything else, log and skip.
        msg = str(e)
        if "already exists" not in msg.lower() and "duplicate" not in msg.lower():
            print(f"[cma] photo upload failed {path}: {e}")
            return None
    try:
        url = _supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
        # supabase-py returns the URL as a string; some versions wrap in {"publicURL": ...}
        if isinstance(url, dict):
            url = url.get("publicUrl") or url.get("publicURL")
        return url
    except Exception as e:
        print(f"[cma] get_public_url failed {path}: {e}")
        return None


# ════════════════════════════════════════════════════════════
# CMA CRUD
# ════════════════════════════════════════════════════════════

@router.get("")
async def list_cmas(request: Request, status: Optional[str] = None, limit: int = 100):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    q = _db("cmas").select("*").order("created_at", desc=True).limit(min(limit, 500))
    if status:
        q = q.eq("status", status)
    rows = q.execute().data or []
    # Attach comp counts
    for cma in rows:
        try:
            cnt = (_db("cma_comps").select("id", count="exact").eq("cma_id", cma["id"]).execute())
            cma["comp_count"] = cnt.count or 0
        except Exception:
            cma["comp_count"] = 0
    return {"cmas": rows}


@router.post("")
async def create_cma(payload: CMACreate, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    user = getattr(request.state, "user", None)
    row = {
        "subject_address": payload.subject_address,
        "subject_city": payload.subject_city,
        "subject_state": payload.subject_state,
        "subject_zip": payload.subject_zip,
        "subject": payload.subject or {},
        "client_first_name": payload.client_first_name,
        "client_last_name": payload.client_last_name,
        "client_email": payload.client_email,
        "client_phone": payload.client_phone,
        "lead_id": payload.lead_id,
        "created_by_user_id": (user.sub if user and hasattr(user, "sub") else None),
    }
    row = {k: v for k, v in row.items() if v is not None}
    r = _db("cmas").insert(row).execute()
    return (r.data or [{}])[0]


@router.get("/{cma_id}")
async def get_cma(cma_id: int, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    r = _db("cmas").select("*").eq("id", cma_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    cma = r.data[0]
    comps = (_db("cma_comps").select("*")
             .eq("cma_id", cma_id)
             .order("status", desc=False)
             .order("current_price", desc=False)
             .execute()).data or []
    cma["comps"] = comps
    return cma


@router.patch("/{cma_id}")
async def update_cma(cma_id: int, payload: CMAUpdate, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(400, "no fields to update")
    r = _db("cmas").update(data).eq("id", cma_id).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    return r.data[0]


@router.delete("/{cma_id}")
async def delete_cma(cma_id: int, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    # Best-effort storage cleanup (bucket is public; orphans are cheap if this fails)
    try:
        objs = _supabase.storage.from_(STORAGE_BUCKET).list(str(cma_id))
        if objs:
            names = [f"{cma_id}/{o['name']}" for o in objs if o.get("name")]
            if names:
                _supabase.storage.from_(STORAGE_BUCKET).remove(names)
    except Exception as e:
        print(f"[cma] storage cleanup skipped for cma {cma_id}: {e}")
    _db("cmas").delete().eq("id", cma_id).execute()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# ZIP INGEST
# ════════════════════════════════════════════════════════════

@router.post("/{cma_id}/import-zip")
async def import_zip(cma_id: int, request: Request, file: UploadFile = File(...)):
    if _db is None:
        raise HTTPException(500, "module not initialized")

    # Verify the CMA exists (and is in-workspace via db())
    exists = _db("cmas").select("id").eq("id", cma_id).limit(1).execute()
    if not exists.data:
        raise HTTPException(404, "cma not found")

    raw = await file.read()
    if len(raw) > 250 * 1024 * 1024:  # 250MB safety cap
        raise HTTPException(413, "ZIP too large (250MB max)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "not a valid ZIP file")

    # Locate the CSV (case-insensitive, tolerates nested folder)
    csv_name = None
    for name in zf.namelist():
        base = name.rsplit("/", 1)[-1].lower()
        if base == "textcma.csv":
            csv_name = name
            break
    if not csv_name:
        raise HTTPException(400, "textCma.csv not found in ZIP")

    try:
        csv_bytes = zf.read(csv_name)
        text = csv_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(400, f"failed to parse textCma.csv: {e}")

    if not rows:
        raise HTTPException(400, "textCma.csv had no rows")

    # Group photos by MLS number
    photos_by_mls = _group_photos_by_mls(zf)

    # Wipe existing comps for this CMA — re-import replaces prior state.
    _db("cma_comps").delete().eq("cma_id", cma_id).execute()

    inserted = 0
    photos_uploaded = 0
    warnings: List[str] = []

    for row in rows:
        try:
            comp = _parse_csv_row(row)
        except Exception as e:
            warnings.append(f"row parse failed: {e}")
            continue

        mls = (comp.get("mls_number") or "").upper()
        if not mls:
            warnings.append("row missing ML#")
            continue

        # Upload photos for this comp (first MAX_PHOTOS_PER_COMP in filename order)
        urls: List[str] = []
        for idx, zip_path in photos_by_mls.get(mls, [])[:MAX_PHOTOS_PER_COMP]:
            try:
                data = zf.read(zip_path)
            except Exception as e:
                warnings.append(f"{mls}: could not read photo {zip_path}: {e}")
                continue
            url = _upload_photo(cma_id, mls, idx, data)
            if url:
                urls.append(url)
                photos_uploaded += 1

        comp["cma_id"] = cma_id
        if urls:
            comp["photos"] = urls
            comp["primary_photo_url"] = urls[0]

        try:
            _db("cma_comps").insert(comp).execute()
            inserted += 1
        except Exception as e:
            warnings.append(f"{mls}: insert failed: {e}")

    # Bump CMA state
    _db("cmas").update({"status": "draft"}).eq("id", cma_id).execute()

    return {
        "ok": True,
        "imported": inserted,
        "photos_uploaded": photos_uploaded,
        "photos_matched_mls_numbers": len([m for m in photos_by_mls.keys()]),
        "warnings": warnings[:20],
        "warning_count": len(warnings),
    }


# ════════════════════════════════════════════════════════════
# COMP CRUD
# ════════════════════════════════════════════════════════════

@router.get("/{cma_id}/comps")
async def list_comps(cma_id: int, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    comps = (_db("cma_comps").select("*")
             .eq("cma_id", cma_id)
             .order("status", desc=False)
             .order("current_price", desc=False)
             .execute()).data or []
    return {"comps": comps}


@router.patch("/{cma_id}/comps/{comp_id}")
async def update_comp(cma_id: int, comp_id: int, payload: CompUpdate, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(400, "no fields to update")
    r = _db("cma_comps").update(data).eq("id", comp_id).eq("cma_id", cma_id).execute()
    if not r.data:
        raise HTTPException(404, "comp not found")
    return r.data[0]


@router.delete("/{cma_id}/comps/{comp_id}")
async def delete_comp(cma_id: int, comp_id: int, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    _db("cma_comps").delete().eq("id", comp_id).eq("cma_id", cma_id).execute()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# SESSION 2 — PRICING ENGINE
# ════════════════════════════════════════════════════════════

def _median(nums):
    nums = sorted([n for n in nums if n is not None])
    n = len(nums)
    if n == 0:
        return None
    if n % 2 == 1:
        return nums[n // 2]
    return (nums[n // 2 - 1] + nums[n // 2]) / 2.0


def _mean(nums):
    nums = [n for n in nums if n is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _adjusted_price(comp):
    """current_price plus any per-line adjustments the agent added."""
    base = comp.get("current_price") or comp.get("list_price") or 0
    try:
        base = float(base)
    except (TypeError, ValueError):
        base = 0.0
    adjs = comp.get("adjustments") or []
    if isinstance(adjs, str):
        try:
            adjs = json.loads(adjs)
        except Exception:
            adjs = []
    total_adj = 0.0
    for a in adjs:
        try:
            total_adj += float(a.get("amount") or 0)
        except (TypeError, ValueError):
            pass
    return base + total_adj


def _segment_stats(comps):
    """Compute pricing stats for a set of comps (already filtered by status + included)."""
    if not comps:
        return {"count": 0}
    prices = []
    ppsfs = []
    doms = []
    for c in comps:
        eff = _adjusted_price(c)
        prices.append(eff)
        sqft = c.get("sqft_living")
        if sqft and eff:
            try:
                ppsfs.append(eff / float(sqft))
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        d = c.get("dom")
        if d is not None:
            try:
                doms.append(int(d))
            except (TypeError, ValueError):
                pass
    return {
        "count": len(comps),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "price_median": _median(prices),
        "price_mean": _mean(prices),
        "ppsf_median": _median(ppsfs),
        "ppsf_mean": _mean(ppsfs),
        "dom_median": _median(doms),
        "dom_mean": _mean(doms),
    }


def _compute_pricing(comps, subject):
    """Segment included comps by status, produce suggested list price band.

    Suggested band strategy:
      - Preferred source: Closed comps (adjusted). These are truth.
      - Fallback: Pending, then Active if no Closed data exists.
      - target = median $/sqft of source segment * subject sqft_living
      - low  = target * 0.95
      - high = target * 1.05
      - Everything rounded to nearest $1,000.
    """
    included = [c for c in comps if c.get("included", True)]
    by_status = {"active": [], "pending": [], "closed": []}
    for c in included:
        s = (c.get("status") or "").strip().lower()
        if s in by_status:
            by_status[s].append(c)

    active = _segment_stats(by_status["active"])
    pending = _segment_stats(by_status["pending"])
    closed = _segment_stats(by_status["closed"])

    # Pick source segment for suggested-price math
    source_key = None
    source_stats = None
    for k in ("closed", "pending", "active"):
        seg = {"closed": closed, "pending": pending, "active": active}[k]
        if seg.get("count", 0) > 0 and seg.get("ppsf_median"):
            source_key = k
            source_stats = seg
            break

    subject_sqft = None
    try:
        subject_sqft = float((subject or {}).get("sqft_living") or 0) or None
    except (TypeError, ValueError):
        subject_sqft = None

    suggested = None
    if source_stats and subject_sqft:
        base_ppsf = source_stats["ppsf_median"]
        target = base_ppsf * subject_sqft
        rounded_target = int(round(target / 1000.0)) * 1000
        rounded_low = int(round(target * 0.95 / 1000.0)) * 1000
        rounded_high = int(round(target * 1.05 / 1000.0)) * 1000
        suggested = {
            "low": rounded_low,
            "target": rounded_target,
            "high": rounded_high,
            "basis": source_key,
            "basis_ppsf": round(base_ppsf, 2),
            "subject_sqft": int(subject_sqft),
            "formula": (
                f"Median $/sqft of {source_stats['count']} {source_key} comp"
                f"{'s' if source_stats['count'] != 1 else ''} = ${round(base_ppsf, 2)}/sqft "
                f"× {int(subject_sqft):,} sqft subject = ${rounded_target:,} target "
                f"(±5% → ${rounded_low:,} - ${rounded_high:,})"
            ),
        }
    elif not subject_sqft:
        suggested = {"error": "Subject sq ft living is required to compute the suggested price."}
    else:
        suggested = {"error": "No included comps with $/sqft data yet."}

    return {
        "active": active,
        "pending": pending,
        "closed": closed,
        "suggested": suggested,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "included_count": len(included),
        "total_count": len(comps),
    }


@router.post("/{cma_id}/compute-pricing")
async def compute_pricing_endpoint(cma_id: int, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    r = _db("cmas").select("*").eq("id", cma_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    cma = r.data[0]
    comps = (_db("cma_comps").select("*").eq("cma_id", cma_id).execute()).data or []
    pricing = _compute_pricing(comps, cma.get("subject") or {})
    # Only bump status to 'ready' if we produced a real suggested band
    updates = {"pricing": pricing}
    if pricing.get("suggested", {}).get("target"):
        updates["status"] = "ready"
    _db("cmas").update(updates).eq("id", cma_id).execute()
    return {"ok": True, "pricing": pricing}


# ════════════════════════════════════════════════════════════
# PUBLIC SHAREABLE REPORT (no JWT)
# ════════════════════════════════════════════════════════════

@public_router.get("/{share_token}")
async def get_public_report(share_token: str, request: Request):
    """Public read of a CMA by share_token. Serves the interactive report data."""
    if _supabase is None:
        raise HTTPException(500, "module not initialized")
    # Use raw supabase (not db()) — public route, no workspace context.
    r = _supabase.table("cmas").select("*").eq("share_token", share_token).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    cma = r.data[0]

    # Bump view counter (best-effort)
    try:
        _supabase.table("cmas").update({
            "view_count": (cma.get("view_count") or 0) + 1,
            "last_viewed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", cma["id"]).execute()
    except Exception:
        pass

    comps = (_supabase.table("cma_comps").select("*")
             .eq("cma_id", cma["id"])
             .eq("included", True)
             .order("status", desc=False)
             .order("current_price", desc=False)
             .execute()).data or []

    # Look up agent info from created_by_user_id (name + email + phone for the "Agent" block)
    agent = None
    uid = cma.get("created_by_user_id")
    if uid:
        try:
            u = _supabase.table("users").select("id,name,email,phone").eq("id", uid).limit(1).execute()
            if u.data:
                agent = u.data[0]
        except Exception:
            pass

    # Strip agent-only + PII fields we don't want in the public payload
    cma_public = {
        "id": cma["id"],
        "share_token": cma.get("share_token"),
        "subject_address": cma.get("subject_address"),
        "subject_city": cma.get("subject_city"),
        "subject_state": cma.get("subject_state"),
        "subject_zip": cma.get("subject_zip"),
        "subject": cma.get("subject") or {},
        "client_first_name": cma.get("client_first_name"),
        "client_last_name": cma.get("client_last_name"),
        "additional_clients": cma.get("additional_clients") or [],
        "pricing": cma.get("pricing"),
        "created_at": cma.get("created_at"),
    }
    return {"cma": cma_public, "comps": comps, "agent": agent}


# ════════════════════════════════════════════════════════════
# SESSION 3 — PDF + EMAIL DELIVERY
# ════════════════════════════════════════════════════════════

def _prepared_for_line(cma):
    """Build a 'Prepared for X and Y' string from primary + additional clients."""
    names = []
    p = ((cma.get("client_first_name") or "") + " " + (cma.get("client_last_name") or "")).strip()
    if p:
        names.append(p)
    for c in (cma.get("additional_clients") or []):
        n = ((c.get("first_name") or "") + " " + (c.get("last_name") or "")).strip()
        if n:
            names.append(n)
    if not names:
        return ""
    if len(names) == 1:
        return f"Prepared for {names[0]}"
    if len(names) == 2:
        return f"Prepared for {names[0]} and {names[1]}"
    return "Prepared for " + ", ".join(names[:-1]) + f", and {names[-1]}"


def _client_emails(cma):
    emails = []
    if cma.get("client_email"):
        emails.append(cma["client_email"].strip())
    for c in (cma.get("additional_clients") or []):
        e = (c.get("email") or "").strip()
        if e:
            emails.append(e)
    # de-dupe while preserving order
    seen = set()
    out = []
    for e in emails:
        el = e.lower()
        if el not in seen and "@" in el:
            seen.add(el)
            out.append(e)
    return out


def _build_cma_pdf(cma, comps, agent):
    """Branded CMA PDF using reportlab. Dark luxe accents on light background for print."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    INK = colors.HexColor("#1a1a26")
    ACCENT = colors.HexColor("#6c63ff")
    MUTED = colors.HexColor("#6b7280")
    LIGHT = colors.HexColor("#f6f6fb")
    GREEN = colors.HexColor("#059669")
    AMBER = colors.HexColor("#d97706")
    VIOLET = colors.HexColor("#7c3aed")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=22, textColor=INK, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=ACCENT, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10, textColor=INK, leading=14)
    sub = ParagraphStyle("sub", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, textColor=MUTED, leading=12)
    big = ParagraphStyle("big", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=28, textColor=ACCENT, leading=32)

    story = []

    # ── COVER
    story.append(Paragraph("Comparative Market Analysis", h1))
    addr_parts = [cma.get("subject_address") or ""]
    city_line = ", ".join([x for x in [cma.get("subject_city"), cma.get("subject_state")] if x])
    if city_line:
        addr_parts.append(city_line + (" " + (cma.get("subject_zip") or "") if cma.get("subject_zip") else ""))
    story.append(Paragraph(" &middot; ".join([p for p in addr_parts if p]), body))
    prep = _prepared_for_line(cma)
    if prep:
        story.append(Spacer(1, 8))
        story.append(Paragraph(prep, ParagraphStyle("prep", parent=body, fontSize=12, textColor=ACCENT)))
    story.append(Spacer(1, 6))
    story.append(Paragraph(datetime.now().strftime("%B %d, %Y"), sub))

    # ── SUBJECT PROPERTY
    story.append(Paragraph("Subject Property", h2))
    s = cma.get("subject") or {}
    rows = [
        ["Beds", str(s.get("beds") or "-"), "Baths", str(s.get("baths_total") or "-")],
        ["Sq Ft Living", f"{int(s.get('sqft_living')):,}" if s.get("sqft_living") else "-",
         "Sq Ft Total", f"{int(s.get('sqft_total')):,}" if s.get("sqft_total") else "-"],
        ["Lot Size", f"{int(s.get('lot_size')):,}" if s.get("lot_size") else "-",
         "Year Built", str(s.get("year_built") or "-")],
        ["Garage", str(s.get("garage_spaces") or "-"),
         "Pool / Waterfront", ("Yes" if s.get("pool") else "No") + " / " + ("Yes" if s.get("waterfront") else "No")],
    ]
    tbl = Table(rows, colWidths=[1.4 * inch, 2.1 * inch, 1.4 * inch, 2.1 * inch])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LIGHT),
    ]))
    story.append(tbl)

    notes = (s.get("condition_notes") or "").strip()
    if notes:
        story.append(Spacer(1, 6))
        story.append(Paragraph("<b>Notes / Upgrades:</b> " + notes, body))

    # ── SUGGESTED PRICE BAND
    pricing = cma.get("pricing") or {}
    suggested = pricing.get("suggested") or {}
    story.append(Paragraph("Suggested List Price", h2))
    if suggested.get("target"):
        band_row = [[
            Paragraph(f"<b>${suggested['low']:,}</b><br/><font size=8 color='#6b7280'>LOW</font>", body),
            Paragraph(f"<font color='#6c63ff' size=22><b>${suggested['target']:,}</b></font><br/><font size=8 color='#6b7280'>TARGET</font>", body),
            Paragraph(f"<b>${suggested['high']:,}</b><br/><font size=8 color='#6b7280'>HIGH</font>", body),
        ]]
        bt = Table(band_row, colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch])
        bt.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))
        story.append(bt)
        story.append(Spacer(1, 8))
        story.append(Paragraph("<i>" + suggested.get("formula", "") + "</i>", sub))
    else:
        story.append(Paragraph(suggested.get("error") or "Pricing not yet computed.", body))

    # ── MARKET SNAPSHOT
    story.append(Paragraph("Market Snapshot", h2))
    snap_cells = [[
        Paragraph(f"<font size=18 color='#059669'><b>{pricing.get('active', {}).get('count', 0)}</b></font><br/><font size=8 color='#6b7280'>ACTIVE COMPETITION</font>", body),
        Paragraph(f"<font size=18 color='#d97706'><b>{pricing.get('pending', {}).get('count', 0)}</b></font><br/><font size=8 color='#6b7280'>PENDING TRENDING</font>", body),
        Paragraph(f"<font size=18 color='#7c3aed'><b>{pricing.get('closed', {}).get('count', 0)}</b></font><br/><font size=8 color='#6b7280'>CLOSED SOLD</font>", body),
    ]]
    st = Table(snap_cells, colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch])
    st.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(st)

    # ── COMP GRID
    def _comp_rows(seg_comps, label, color):
        if not seg_comps:
            return
        story.append(PageBreak())
        story.append(Paragraph(label + f" ({len(seg_comps)})",
                               ParagraphStyle("seghd", parent=h2, textColor=color, spaceBefore=0)))
        header = ["MLS#", "Address", "Bd/Ba", "Sqft", "Price", "$/sqft", "DOM"]
        rows = [header]
        for c in seg_comps:
            price = _adjusted_price(c)
            sqft = c.get("sqft_living")
            ppsf = int(round(price / float(sqft))) if (price and sqft) else "-"
            rows.append([
                (c.get("mls_number") or "-")[:14],
                (c.get("address") or "-")[:34],
                f"{c.get('beds') or '-'}/{c.get('baths_total') or '-'}",
                f"{int(sqft):,}" if sqft else "-",
                f"${int(price):,}" if price else "-",
                (f"${ppsf}" if isinstance(ppsf, int) else "-"),
                str(c.get("dom") if c.get("dom") is not None else "-"),
            ])
        t = Table(rows, colWidths=[0.9 * inch, 2.6 * inch, 0.7 * inch, 0.7 * inch, 1.0 * inch, 0.7 * inch, 0.5 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, MUTED),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(t)

    by_status = {"active": [], "pending": [], "closed": [], "other": []}
    for c in comps:
        s = (c.get("status") or "").strip().lower()
        by_status.get(s, by_status["other"]).append(c)

    _comp_rows(by_status["active"], "Active (Competition)", GREEN)
    _comp_rows(by_status["pending"], "Pending (Trending)", AMBER)
    _comp_rows(by_status["closed"], "Closed (Sold)", VIOLET)

    # ── AGENT BLOCK (last page)
    if agent:
        story.append(Spacer(1, 20))
        story.append(Paragraph("Prepared By", h2))
        agent_lines = [f"<b>{agent.get('name') or 'Agent'}</b>"]
        contact_bits = [agent.get("email"), agent.get("phone")]
        contact = " &middot; ".join([b for b in contact_bits if b])
        if contact:
            agent_lines.append(f"<font color='#6b7280'>{contact}</font>")
        agent_lines.append("<font color='#6b7280'>TPL Collective &middot; LPT Realty</font>")
        for line in agent_lines:
            story.append(Paragraph(line, body))

    doc.build(story)
    return buf.getvalue()


class SendReportPayload(BaseModel):
    to: Optional[List[str]] = None  # override recipients; defaults to all client emails
    subject_override: Optional[str] = None
    message_override: Optional[str] = None


@router.get("/{cma_id}/pdf")
async def download_cma_pdf(cma_id: int, request: Request):
    """Return the CMA as an inline PDF for the agent to review/download."""
    from fastapi.responses import Response
    if _db is None:
        raise HTTPException(500, "module not initialized")
    r = _db("cmas").select("*").eq("id", cma_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    cma = r.data[0]
    comps = (_db("cma_comps").select("*")
             .eq("cma_id", cma_id).eq("included", True)
             .order("status").order("current_price").execute()).data or []
    agent = None
    uid = cma.get("created_by_user_id")
    if uid:
        try:
            u = _supabase.table("users").select("id,name,email,phone").eq("id", uid).limit(1).execute()
            if u.data:
                agent = u.data[0]
        except Exception:
            pass
    pdf_bytes = _build_cma_pdf(cma, comps, agent)
    filename = f"CMA_{(cma.get('subject_address') or 'report').replace(' ', '_')[:60]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{cma_id}/send-report")
async def send_cma_report(cma_id: int, payload: SendReportPayload, request: Request):
    """Email the CMA PDF to primary + additional client emails via send_email() rail."""
    import base64
    if _db is None:
        raise HTTPException(500, "module not initialized")
    r = _db("cmas").select("*").eq("id", cma_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "cma not found")
    cma = r.data[0]
    comps = (_db("cma_comps").select("*")
             .eq("cma_id", cma_id).eq("included", True)
             .order("status").order("current_price").execute()).data or []

    recipients = payload.to or _client_emails(cma)
    if not recipients:
        raise HTTPException(400, "no client email on file; add one under 'Prepared For' first")

    # Pull agent info
    agent = None
    uid = cma.get("created_by_user_id")
    if uid:
        try:
            u = _supabase.table("users").select("id,name,email,phone").eq("id", uid).limit(1).execute()
            if u.data:
                agent = u.data[0]
        except Exception:
            pass

    pdf_bytes = _build_cma_pdf(cma, comps, agent)
    fname = f"CMA_{(cma.get('subject_address') or 'report').replace(' ', '_')[:60]}.pdf"

    # Compose email
    from main import send_email as _send, load_settings as _load_settings
    settings = _load_settings() or {}
    smtp_cfg = settings.get("smtp") or {}
    share_url = f"https://mission.tplcollective.ai/cma/{cma['share_token']}"
    addr = cma.get("subject_address") or "Your property"
    subject = payload.subject_override or f"Your Comparative Market Analysis — {addr}"
    prep = _prepared_for_line(cma) or "Hi there"
    suggested = ((cma.get("pricing") or {}).get("suggested") or {})
    band_html = ""
    if suggested.get("target"):
        band_html = (
            f"<p style='margin:16px 0'>Based on {suggested.get('basis','closed')} comps, my suggested list price range is "
            f"<strong>${suggested['low']:,} – ${suggested['high']:,}</strong> "
            f"with a target of <strong>${suggested['target']:,}</strong>.</p>"
        )
    message = payload.message_override or ""
    html = f"""
    <div style="font-family:-apple-system,sans-serif;padding:24px;max-width:620px;color:#1a1a26">
      <h2 style="color:#6c63ff;margin:0 0 12px">Your CMA is ready</h2>
      <p>{prep.replace('Prepared for ', 'Hi ')},</p>
      <p>Attached is the Comparative Market Analysis I put together for <strong>{addr}</strong>.
      It covers active competition, recent pending activity, and the last comparable sales in your area.</p>
      {band_html}
      {("<p style='margin:16px 0'>" + message + "</p>") if message else ""}
      <p style="margin:20px 0">
        <a href="{share_url}" style="display:inline-block;background:#6c63ff;color:#fff;padding:11px 20px;border-radius:6px;text-decoration:none;font-weight:600">
          View interactive report
        </a>
      </p>
      <p style="color:#6b7280;font-size:13px;margin-top:24px">
        {(agent or {}).get('name') or 'Your agent'}<br>
        TPL Collective · LPT Realty
      </p>
    </div>
    """
    attachments = [{"filename": fname, "content": base64.b64encode(pdf_bytes).decode()}]

    sent_count = 0
    failures = []
    for recipient in recipients:
        try:
            ok, err = _send(
                smtp_cfg, recipient, subject, html,
                from_address=f"{(agent or {}).get('name') or 'TPL Collective'} <cma@tplcollective.ai>",
                reply_to=(agent or {}).get("email") or "",
                campaign="cma-report",
                attachments=attachments,
            )
            if ok:
                sent_count += 1
            else:
                failures.append({"to": recipient, "error": err})
        except Exception as e:
            failures.append({"to": recipient, "error": str(e)})

    if sent_count:
        _db("cmas").update({
            "status": "sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "sent_to": ", ".join(recipients),
        }).eq("id", cma_id).execute()

    return {
        "ok": sent_count > 0,
        "sent_count": sent_count,
        "recipients": recipients,
        "failures": failures,
        "share_url": share_url,
    }


# ════════════════════════════════════════════════════════════
# SESSION 4 — CUSTOM MLS EXPORT MERGE (BeachesMLS "customexport")
# ════════════════════════════════════════════════════════════
# Column set is a superset of what Flex/Cloud CMA gives us. Notably:
#   - Row 1 (Listing Number = "Subject Property") gives us the subject property
#     characteristics (beds, baths, sqft, lot, year built, pool) which the
#     Flex ZIP never included.
#   - "Close Price" is separate from "List Price" for Closed comps (Flex only
#     has "Current Price"). Merge overwrites current_price with close_price
#     when available.
#   - "Living Area Main" / "Building Area Main" / "Lot Size Area" are usually
#     more accurate than the Flex equivalents (which sometimes have wrong units).

CUSTOM_CSV_STATUS = {"A": "Active", "P": "Pending", "C": "Closed", "X": "Expired", "W": "Withdrawn"}

CUSTOM_CSV_COLS = {
    "Listing Number": "mls_number",
    "Short Address": "address",
    "City": "city",
    "Property Type": "property_type",
    "Original List Price": "original_list_price",
    "List Price": "list_price",
    "Close Price": "close_price",
    "Listing Date": "entry_date",
    "Under Contract Date": "pending_date",
    "Close Date": "closing_date",
    "Days On Market": "dom",
    "Year Built": "year_built",
    "Bedrooms Total": "beds",
    "Bathrooms Total": "baths_total",
    "Living Area Main": "sqft_living",
    "Building Area Main": "sqft_total",
    "Garage Spaces": "garage_spaces",
    "Lot Size Area": "lot_size",
}


def _to_iso_us_date(s):
    """Parse M/D/YY or M/D/YYYY into ISO YYYY-MM-DD."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            # 2-digit years: strptime already handles the century, but python's default
            # rolls YY < 69 into 20YY which is what we want here.
            return d.isoformat()
        except (ValueError, TypeError):
            continue
    return None


def _parse_customexport_row(row):
    """Map one customexport row to a comp dict (does NOT touch cma_id / features / photos)."""
    out = {}
    for csv_key, col in CUSTOM_CSV_COLS.items():
        raw = row.get(csv_key)
        if raw is None:
            continue
        raw = str(raw).strip()
        if raw == "":
            continue
        if col in ("original_list_price", "list_price", "close_price"):
            v = _to_float(raw)
            if v is not None:
                out[col] = v
        elif col in ("beds", "sqft_living", "sqft_total", "dom", "year_built"):
            v = _to_int(raw)
            if v is not None:
                out[col] = v
        elif col in ("baths_total", "garage_spaces", "lot_size"):
            v = _to_float(raw)
            if v is not None:
                out[col] = v
        elif col in ("entry_date", "pending_date", "closing_date"):
            d = _to_iso_us_date(raw)
            if d:
                out[col] = d
        else:
            out[col] = raw

    # Status abbrev -> full name
    st = (row.get("Status") or "").strip().upper()
    if st in CUSTOM_CSV_STATUS:
        out["status"] = CUSTOM_CSV_STATUS[st]
    elif st:
        out["status"] = st

    # Pool Y/N
    pool_raw = (row.get("Pool Private YN") or "").strip().upper()
    if pool_raw:
        out["pool"] = pool_raw.startswith("Y")

    # current_price: prefer close_price (closed), else list_price
    if out.get("close_price"):
        out["current_price"] = out["close_price"]
    elif out.get("list_price"):
        out["current_price"] = out["list_price"]

    # close_price isn't a DB column — drop it after transferring
    out.pop("close_price", None)

    return out


def _subject_json_from_row(row):
    """Extract subject-property JSONB fields from the customexport Subject Property row."""
    def _s(v):
        return str(v).strip() if v not in (None, "") else None
    def _i(v):
        try: return int(float(str(v).strip())) if v not in (None, "") else None
        except: return None
    def _f(v):
        try: return float(str(v).strip()) if v not in (None, "") else None
        except: return None
    pool_raw = (row.get("Pool Private YN") or "").strip().upper()
    subj = {
        "beds": _i(row.get("Bedrooms Total")),
        "baths_total": _f(row.get("Bathrooms Total")),
        "sqft_living": _i(row.get("Living Area Main")),
        "sqft_total": _i(row.get("Building Area Main")),
        "lot_size": _f(row.get("Lot Size Area")),
        "year_built": _i(row.get("Year Built")),
        "garage_spaces": _f(row.get("Garage Spaces")),
        "pool": pool_raw.startswith("Y") if pool_raw else None,
    }
    return {k: v for k, v in subj.items() if v is not None}


@router.post("/{cma_id}/import-custom-csv")
async def import_custom_csv(cma_id: int, request: Request, file: UploadFile = File(...)):
    """Merge a BeachesMLS 'customexport' CSV into an existing CMA.

    Behavior:
      - Subject Property row (Listing Number = 'Subject Property') updates the CMA's
        subject_address, subject_city, subject_state, subject_zip, and subject JSONB.
      - For each comp row: match by Listing Number to an existing cma_comp (usually
        already imported from the Flex ZIP) and PATCH the fields customexport is more
        authoritative on (prices, dates, sqft, dom). If no match, insert as a new comp.
      - Never overwrites the photos/features/remarks/listing_agent fields the Flex
        import provided — customexport doesn't have those.
    """
    if _db is None:
        raise HTTPException(500, "module not initialized")

    exists = _db("cmas").select("id").eq("id", cma_id).limit(1).execute()
    if not exists.data:
        raise HTTPException(404, "cma not found")

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "CSV too large (20MB max)")
    try:
        text = raw.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        raise HTTPException(400, f"failed to parse CSV: {e}")
    if not rows:
        raise HTTPException(400, "CSV had no rows")

    subject_updated = False
    merged = 0
    inserted = 0
    warnings: List[str] = []

    for row in rows:
        listing_num = (row.get("Listing Number") or "").strip()

        # SUBJECT PROPERTY row
        if listing_num.lower() == "subject property":
            subj_json = _subject_json_from_row(row)
            addr = (row.get("Short Address") or "").strip() or None
            city = (row.get("City") or "").strip() or None
            top_updates = {}
            if addr:
                top_updates["subject_address"] = addr
            if city:
                top_updates["subject_city"] = city
                top_updates["subject_state"] = "FL"  # BeachesMLS is FL-only
            if subj_json:
                # Merge with existing subject JSONB rather than replacing
                cur = _db("cmas").select("subject").eq("id", cma_id).limit(1).execute()
                existing_subj = ((cur.data or [{}])[0].get("subject")) or {}
                merged_subj = {**existing_subj, **subj_json}
                top_updates["subject"] = merged_subj
            if top_updates:
                _db("cmas").update(top_updates).eq("id", cma_id).execute()
                subject_updated = True
            continue

        if not listing_num:
            warnings.append("row missing Listing Number")
            continue

        parsed = _parse_customexport_row(row)
        if not parsed:
            warnings.append(f"{listing_num}: nothing parsed")
            continue

        # Look up existing comp by MLS# (case-insensitive)
        existing_comp = (_db("cma_comps").select("id")
                         .eq("cma_id", cma_id)
                         .ilike("mls_number", listing_num)
                         .limit(1).execute())
        if existing_comp.data:
            comp_id = existing_comp.data[0]["id"]
            _db("cma_comps").update(parsed).eq("id", comp_id).execute()
            merged += 1
        else:
            # New comp from customexport — no photos/features yet
            parsed["cma_id"] = cma_id
            _db("cma_comps").insert(parsed).execute()
            inserted += 1

    return {
        "ok": True,
        "subject_updated": subject_updated,
        "merged": merged,
        "inserted": inserted,
        "warning_count": len(warnings),
        "warnings": warnings[:20],
    }


# ════════════════════════════════════════════════════════════
# SESSION 5 — STANDARD FLORIDA CMA ADJUSTMENTS
# ════════════════════════════════════════════════════════════
# Source: Joe's Florida Residential CMA Adjustment Guide.
# Each band uses midpoint values from Joe's ranges. His explicit "$700k-$900k
# starting numbers" override for that sweet spot.

FL_ADJUSTMENT_BANDS = [
    # (max_price, rates)
    (500_000, {
        "pool": 27_500, "age_per_year": 750, "bedroom": 10_000, "full_bath": 10_000,
        "sqft": 62.50, "garage_per_space": 10_000, "quarter_acre": 7_500,
    }),
    (750_000, {
        "pool": 37_500, "age_per_year": 1_125, "bedroom": 12_500, "full_bath": 13_750,
        "sqft": 82.50, "garage_per_space": 12_500, "quarter_acre": 11_250,
    }),
    (1_000_000, {
        "pool": 50_000, "age_per_year": 1_500, "bedroom": 16_000, "full_bath": 18_750,
        "sqft": 102.50, "garage_per_space": 16_000, "quarter_acre": 15_000,
    }),
    (1_500_000, {
        "pool": 65_000, "age_per_year": 2_000, "bedroom": 22_500, "full_bath": 25_000,
        "sqft": 125.00, "garage_per_space": 20_000, "quarter_acre": 22_500,
    }),
]

# Joe's personal defaults — override the FL_ADJUSTMENT_BANDS guide. These are
# the rates Joe uses on his own listings. Applied to all price levels ≤ $1.5M
# (which covers virtually every CMA he'll run). The FL_ADJUSTMENT_BANDS above
# stay in place as reference; if we ever need to auto-scale to $2M+ ultra-luxury
# ranges, we can restore band-based selection.
#
# Bedroom + lot use SPECIAL logic (not simple diff × rate) — see
# _compute_standard_adjustments below.
JOE_SWEET_SPOT_RATES = {
    "pool": 35_000,          # was $45k in guide; Joe's preference
    "age_per_year": 1_250,   # per Joe's guide (unchanged)
    "bedroom": 5_000,        # ONLY applied when abs(diff) >= 2 bedrooms
    "full_bath": 10_000,     # was $17.5k in guide; Joe's preference
    "sqft": 75.00,           # was $100/sqft in guide; Joe's preference
    "garage_per_space": 15_000,   # per Joe's guide (unchanged)
    "quarter_acre": 15_000,  # ONLY applied when abs(lot diff) >= 10,000 sqft
}


def _pick_adjustment_rates(target_price):
    """Return the rate table appropriate for the neighborhood's price level.
    Joe's overrides win for anything under $1.5M."""
    if target_price is None or target_price <= 0 or target_price <= 1_500_000:
        return JOE_SWEET_SPOT_RATES
    # Ultra-luxury falls back to the guide (edit here if Joe gives $1.5M+ rates).
    for max_price, rates in FL_ADJUSTMENT_BANDS:
        if target_price <= max_price:
            return rates
    return FL_ADJUSTMENT_BANDS[-1][1]


def _compute_standard_adjustments(subject, comp, rates):
    """Return a list of adjustment lines (label + amount) that would normalize
    this comp to match the subject property.

    Sign convention: POSITIVE amount = adjust comp price UP (comp is inferior
    in that feature, so we add value to make it comparable). NEGATIVE = comp
    is superior, subtract to normalize.
    """
    adj = []

    def _f(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    # ── Private Pool
    s_pool = bool(subject.get("pool"))
    c_pool = bool(comp.get("pool"))
    if s_pool != c_pool:
        amt = rates["pool"] if s_pool else -rates["pool"]
        adj.append({"label": "Pool (subject: " + ("Yes" if s_pool else "No") + ", comp: " + ("Yes" if c_pool else "No") + ")", "amount": int(amt), "auto": True})

    # ── Age (per year)
    s_year = _f(subject.get("year_built"))
    c_year = _f(comp.get("year_built"))
    if s_year and c_year and int(s_year) != int(c_year):
        age_diff = int(s_year - c_year)  # positive = subject newer, comp older, +
        amt = age_diff * rates["age_per_year"]
        adj.append({"label": f"Age (subject {int(s_year)} vs comp {int(c_year)})", "amount": int(amt), "auto": True})

    # ── Bedrooms — Joe's rule: skip ±1 diff; only apply when abs(diff) >= 2
    s_beds = _f(subject.get("beds"))
    c_beds = _f(comp.get("beds"))
    if s_beds is not None and c_beds is not None:
        diff = int(s_beds - c_beds)
        if abs(diff) >= 2:
            amt = diff * rates["bedroom"]
            adj.append({"label": f"Bedrooms (subject {int(s_beds)} vs comp {int(c_beds)})", "amount": int(amt), "auto": True})

    # ── Full baths (treat baths_total as full baths for now; MLS often reports 2.5 as 2F+1H)
    s_baths = _f(subject.get("baths_total"))
    c_baths = _f(comp.get("baths_total"))
    if s_baths is not None and c_baths is not None and abs(s_baths - c_baths) >= 0.5:
        diff = s_baths - c_baths
        amt = diff * rates["full_bath"]
        adj.append({"label": f"Baths (subject {s_baths} vs comp {c_baths})", "amount": int(round(amt)), "auto": True})

    # ── Living Area (sqft) — ignore trivial differences <50 sqft
    s_sqft = _f(subject.get("sqft_living"))
    c_sqft = _f(comp.get("sqft_living"))
    if s_sqft and c_sqft and abs(s_sqft - c_sqft) >= 50:
        diff = s_sqft - c_sqft
        amt = diff * rates["sqft"]
        adj.append({"label": f"Sqft (subject {int(s_sqft):,} vs comp {int(c_sqft):,})", "amount": int(round(amt)), "auto": True})

    # ── Garage
    s_gar = _f(subject.get("garage_spaces"))
    c_gar = _f(comp.get("garage_spaces"))
    if s_gar is not None and c_gar is not None and int(s_gar) != int(c_gar):
        diff = int(s_gar - c_gar)
        amt = diff * rates["garage_per_space"]
        adj.append({"label": f"Garage (subject {int(s_gar)} vs comp {int(c_gar)})", "amount": int(amt), "auto": True})

    # ── Lot Size — Joe's rule: no adjustment unless abs(diff) >= 10,000 sqft
    s_lot = _f(subject.get("lot_size"))
    c_lot = _f(comp.get("lot_size"))
    if s_lot and c_lot and abs(s_lot - c_lot) >= 10_000:
        diff_sf = s_lot - c_lot
        quarter_acres = diff_sf / (43_560.0 / 4.0)  # 43,560 sqft/acre → /4 for quarter
        amt = quarter_acres * rates["quarter_acre"]
        adj.append({"label": f"Lot (subject {int(s_lot):,}sf vs comp {int(c_lot):,}sf)", "amount": int(round(amt)), "auto": True})

    return adj


# Labels that _compute_standard_adjustments produces always start with one
# of these prefixes. Used to identify + drop stale auto-generated rows on
# re-run, even if the `auto` flag got stripped somewhere in the round-trip.
STANDARD_ADJ_PREFIXES = ("Pool ", "Age ", "Bedrooms ", "Baths ", "Sqft ", "Garage ", "Lot ")


def _is_standard_adjustment(a):
    """A row is a standard/auto adjustment if either the flag says so OR its
    label matches the standard prefix set. Belt AND suspenders — the flag
    alone was letting duplicates slip through."""
    if not isinstance(a, dict):
        return False
    if a.get("auto") is True or a.get("auto") == "true":
        return True
    label = (a.get("label") or "").strip()
    return any(label.startswith(p) for p in STANDARD_ADJ_PREFIXES)


class AutoAdjustPayload(BaseModel):
    # Optional override — if agent wants to force a specific band's rates.
    price_band_target: Optional[float] = None
    # Only apply to comps that don't already have adjustments (default: overwrite all auto-generated).
    only_missing: Optional[bool] = False


@router.post("/{cma_id}/auto-adjust")
async def auto_adjust(cma_id: int, payload: AutoAdjustPayload, request: Request):
    """Compute + persist standard FL adjustments on every included comp."""
    if _db is None:
        raise HTTPException(500, "module not initialized")
    cma_r = _db("cmas").select("*").eq("id", cma_id).limit(1).execute()
    if not cma_r.data:
        raise HTTPException(404, "cma not found")
    cma = cma_r.data[0]
    subject = cma.get("subject") or {}
    comps = (_db("cma_comps").select("*").eq("cma_id", cma_id).execute()).data or []

    # Determine which price band to use — median of comp prices (close_price where available)
    if payload.price_band_target:
        target = float(payload.price_band_target)
    else:
        prices = []
        for c in comps:
            if not c.get("included", True):
                continue
            p = c.get("current_price") or c.get("list_price")
            if p:
                try:
                    prices.append(float(p))
                except (TypeError, ValueError):
                    pass
        target = _median(prices) or 800_000  # default to Joe's sweet spot midpoint

    rates = _pick_adjustment_rates(target)

    updated = 0
    skipped = 0
    for comp in comps:
        if not comp.get("included", True):
            skipped += 1
            continue
        existing_adj = comp.get("adjustments") or []
        if isinstance(existing_adj, str):
            try:
                existing_adj = json.loads(existing_adj)
            except Exception:
                existing_adj = []
        # Preserve any MANUAL (non-standard) adjustments the agent added.
        # Filter by BOTH the auto flag AND the standard-label prefix so we
        # can't accumulate dupes if the flag ever gets stripped in the
        # JSONB round-trip.
        manual_adj = [a for a in existing_adj if not _is_standard_adjustment(a)]

        if payload.only_missing and any(_is_standard_adjustment(a) for a in existing_adj):
            skipped += 1
            continue

        auto_adj = _compute_standard_adjustments(subject, comp, rates)
        merged = auto_adj + manual_adj
        _db("cma_comps").update({"adjustments": merged}).eq("id", comp["id"]).execute()
        updated += 1

    return {
        "ok": True,
        "updated": updated,
        "skipped": skipped,
        "rates_used": rates,
        "target_price_band_center": int(target),
    }
