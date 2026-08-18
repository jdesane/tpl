"""Pydantic models for Mission Control API."""
from pydantic import BaseModel
from typing import Optional, List


# ── AUTH ──

class LoginRequest(BaseModel):
    email: str
    password: str

class SetPasswordRequest(BaseModel):
    password: str


# ── LEADS ──

class LeadIn(BaseModel):
    name: str
    email: str
    phone: Optional[str] = ""
    brokerage: Optional[str] = ""
    deals_per_year: Optional[str] = ""
    avg_price: Optional[str] = ""
    source: Optional[str] = ""
    source_page: Optional[str] = ""
    current_brokerage: Optional[str] = ""
    gci: Optional[str] = ""
    team_or_solo: Optional[str] = ""
    notes: Optional[str] = ""

class LeadUpdate(BaseModel):
    status: Optional[str] = None
    stage: Optional[str] = None
    notes: Optional[str] = None
    lead_score: Optional[int] = None
    lead_temperature: Optional[str] = None
    follow_up_date: Optional[str] = None
    last_contacted_at: Optional[str] = None
    ai_draft: Optional[str] = None
    ai_summary: Optional[str] = None
    assigned_to: Optional[int] = None
    current_brokerage: Optional[str] = None
    gci: Optional[str] = None
    team_or_solo: Optional[str] = None
    motivations: Optional[list] = None
    objections: Optional[list] = None


# ── TASKS ──

class TaskIn(BaseModel):
    task_type: str
    title: str
    description: Optional[str] = ""
    lead_id: Optional[int] = None
    agent_id: Optional[int] = None
    priority: Optional[str] = "normal"
    due_date: Optional[str] = None
    created_by: Optional[str] = "joe"

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


# ── AGENTS ──

class AgentIn(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    previous_brokerage: Optional[str] = ""
    lpt_plan: Optional[str] = ""
    join_date: Optional[str] = None
    sponsor_agent_id: Optional[int] = None
    lead_id: Optional[int] = None

class AgentUpdate(BaseModel):
    status: Optional[str] = None
    lpt_plan: Optional[str] = None
    engagement_score: Optional[int] = None
    transactions_ytd: Optional[int] = None
    volume_ytd: Optional[float] = None
    gci_ytd: Optional[float] = None
    last_closing_date: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


# ── RESOURCES ──

class ResourceIn(BaseModel):
    title: str
    description: Optional[str] = ""
    category: Optional[str] = ""
    file_path: Optional[str] = ""
    file_type: Optional[str] = ""
    access_level: Optional[str] = "agent"

class ResourceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    access_level: Optional[str] = None


# ── REFERRALS ──

class ReferralIn(BaseModel):
    referring_agent_id: int
    referred_name: str
    referred_email: Optional[str] = ""
    referred_phone: Optional[str] = ""

class ReferralUpdate(BaseModel):
    status: Optional[str] = None
    lead_id: Optional[int] = None


# ── RECRUITING LINKS ──

class RecruitingLinkIn(BaseModel):
    target_brokerage: str
    page_type: str
    page_label: str
    base_url: str
    utm_source: Optional[str] = "tpl"
    utm_medium: Optional[str] = "recruiting"
    utm_campaign: Optional[str] = ""


# ── CONTENT POSTS ──

class ContentPostIn(BaseModel):
    title: str
    body: str
    hashtags: Optional[str] = ""
    platform: Optional[str] = "all"
    category: Optional[str] = ""
    image_url: Optional[str] = ""
    recruiting_link_id: Optional[int] = None
    status: Optional[str] = "draft"
    scheduled_at: Optional[str] = None

class ContentPostUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    hashtags: Optional[str] = None
    platform: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    recruiting_link_id: Optional[int] = None
    status: Optional[str] = None
    scheduled_at: Optional[str] = None
    posted_at: Optional[str] = None


# ── AI ACTIONS ──

class DraftDmRequest(BaseModel):
    lead_id: int

class ResearchLeadRequest(BaseModel):
    lead_id: int


# ── NOTIFICATIONS / SETTINGS ──

class NotifSettings(BaseModel):
    newLead: bool = False
    digest: bool = False
    statusChange: bool = False
    email: str = ""
    sources: list = ["all"]

class SmtpConfig(BaseModel):
    host: str = ""
    port: str = "465"
    from_addr: str = ""
    user: str = ""
    password: str = ""

class TestNotifRequest(BaseModel):
    email: str
    smtp: Optional[dict] = {}
