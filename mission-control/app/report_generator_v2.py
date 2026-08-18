"""
Commission Report PDF Generator v2 — TPL brand colors + overflow-safe layout
Endpoint: POST /api/generate-report

Add to main.py:
    from report_generator_v2 import router as report_router
    app.include_router(report_router)

Requirements: reportlab, httpx
"""
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
import io, base64, httpx, os
from datetime import datetime

router = APIRouter()

def _get_resend_key():
    try:
        import json
        with open("/data/settings.json") as f:
            return json.load(f).get("smtp",{}).get("pass","")
    except Exception:
        return ""

BG_DARK=HexColor("#0a0a0f"); ACCENT=HexColor("#6c63ff"); GOLD=HexColor("#f0c040")
GREEN=HexColor("#34d399"); RED=HexColor("#f87171"); TEXT_LIGHT=HexColor("#e8e8f0")
MUTED=HexColor("#8888aa"); DIM=HexColor("#55556a"); WHITE=white
BODY=HexColor("#333333"); SUBTLE=HexColor("#f4f4f8"); RULE=HexColor("#dddddd")
W,H=letter; L=50; R=W-50; CV=400; RH=16; SG=12; FT=44

class ReportRequest(BaseModel):
    name:str; email:EmailStr; brokerage:str; agent_split:float; brokerage_cap:float
    desk_fee_monthly:float; tx_fee:float; royalty_pct:float; royalty_cap:float
    avg_price:float; annual_deals:int; comm_rate:float

def fmt(n):
    return f"-${abs(n):,.0f}" if n<0 else f"${n:,.0f}"

def calc_cur(r):
    gci=r.avg_price*(r.comm_rate/100)*r.annual_deals
    bf=min(gci*(1-r.agent_split/100),r.brokerage_cap) if r.brokerage_cap>0 else gci*(1-r.agent_split/100)
    rf=min(gci*(r.royalty_pct/100),r.royalty_cap) if r.royalty_cap>0 else gci*(r.royalty_pct/100)
    da=r.desk_fee_monthly*12; tt=r.tx_fee*r.annual_deals; tf=bf+rf+da+tt
    return dict(gci=gci,bf=bf,rf=rf,da=da,tt=tt,tf=tf,net=gci-tf)

def calc_bb(gci,d):
    bf=min(d*500,5000);tx=d*195;tf=bf+tx+500;return dict(bf=bf,tx=tx,tf=tf,net=gci-tf)

def calc_bp(gci,d):
    bf=min(gci*.2,15000);tx=d*195;tf=bf+tx+500;return dict(bf=bf,tx=tx,tf=tf,net=gci-tf)

def _hdr(c):
    c.setFillColor(BG_DARK);c.rect(0,H-72,W,72,fill=1,stroke=0)
    c.setFillColor(ACCENT);c.rect(0,H-74,W,2,fill=1,stroke=0)
    c.setFillColor(TEXT_LIGHT);c.setFont("Helvetica-Bold",18);c.drawString(L,H-42,"The $27,000 Question")
    c.setFillColor(MUTED);c.setFont("Helvetica",10);c.drawString(L,H-58,"Your Personalized Brokerage Cost Report")
    c.setFillColor(ACCENT);c.setFont("Helvetica-Bold",10);c.drawRightString(R,H-42,"TPL COLLECTIVE")
    c.setFillColor(MUTED);c.setFont("Helvetica",8);c.drawRightString(R,H-55,"tplcollective.ai")

def _ftr(c):
    c.setFillColor(BG_DARK);c.rect(0,0,W,FT,fill=1,stroke=0)
    c.setFillColor(GOLD);c.setFont("Helvetica-Bold",8);c.drawString(L,18,"Ready for the full picture?")
    c.setFillColor(TEXT_LIGHT);c.setFont("Helvetica",8);c.drawString(205,18,"Book a free strategy call: calendly.com/discovertpl")

def _sec(c,y,t):
    c.setFillColor(ACCENT);c.rect(L-10,y-2,4,16,fill=1,stroke=0)
    c.setFillColor(BG_DARK);fs=12
    while stringWidth(t,"Helvetica-Bold",fs)>(R-L) and fs>8: fs-=.5
    c.setFont("Helvetica-Bold",fs);c.drawString(L,y,t);return y-22

def _row(c,y,lbl,val,bold=False,clr=None):
    c.setFillColor(clr or BODY);c.setFont("Helvetica-Bold" if bold else "Helvetica",9)
    c.drawString(L+20,y,lbl);c.drawRightString(CV,y,str(val));return y-RH

def _box(c,top,bot):
    c.setFillColor(SUBTLE);c.roundRect(L+5,bot-6,CV-L+10,(top-bot)+20,4,fill=1,stroke=0)

def _rule(c,y):
    c.setStrokeColor(RULE);c.setLineWidth(.5);c.line(L+20,y+7,CV,y+7)

def generate_pdf(r):
    buf=io.BytesIO();c=canvas.Canvas(buf,pagesize=letter)
    _hdr(c);_ftr(c)
    cur=calc_cur(r);bb=calc_bb(cur["gci"],r.annual_deals);bp=calc_bp(cur["gci"],r.annual_deals)
    best=max(bb["net"],bp["net"]);bbw=bb["net"]>=bp["net"];diff=best-cur["net"]
    bplan="Business Builder" if bbw else "Brokerage Partner"
    bfees=bb["tf"] if bbw else bp["tf"]

    y=H-96
    c.setFillColor(HexColor("#555"));c.setFont("Helvetica",10)
    c.drawString(L,y,f"Prepared for {r.name}  |  {datetime.now().strftime('%B %d, %Y')}");y-=26

    y=_sec(c,y,"YOUR PRODUCTION")
    y=_row(c,y,"Average Sale Price",fmt(r.avg_price))
    y=_row(c,y,"Annual Transactions",str(r.annual_deals))
    y=_row(c,y,"Commission Rate",f"{r.comm_rate}%")
    y=_row(c,y,"Gross Commission Income (GCI)",fmt(cur["gci"]),bold=True);y-=SG

    y=_sec(c,y,f"CURRENT: {r.brokerage.upper()}")
    rows=[ ("Total GCI",fmt(cur["gci"]),False,None) ]
    if cur["bf"]>0:
        cn=f", capped {fmt(r.brokerage_cap)}" if r.brokerage_cap>0 else ""
        rows.append((f"Brokerage Split ({100-r.agent_split:.0f}%{cn})",f"-{fmt(cur['bf'])}",False,RED))
    if cur["rf"]>0:
        rn=f", capped {fmt(r.royalty_cap)}" if r.royalty_cap>0 else ""
        rows.append((f"Franchise/Royalty ({r.royalty_pct}%{rn})",f"-{fmt(cur['rf'])}",False,RED))
    if cur["da"]>0: rows.append((f"Monthly Fees ({fmt(r.desk_fee_monthly)}/mo x 12)",f"-{fmt(cur['da'])}",False,RED))
    if cur["tt"]>0: rows.append((f"Tx Fees ({fmt(r.tx_fee)} x {r.annual_deals} deals)",f"-{fmt(cur['tt'])}",False,RED))
    bt=y;_box(c,bt,bt-len(rows)*RH)
    for l,v,b,cl in rows: y=_row(c,y,l,v,bold=b,clr=cl)
    _rule(c,y);y=_row(c,y,"YOUR ANNUAL TAKE-HOME",fmt(cur["net"]),bold=True)
    y=_row(c,y,"Total Fees Paid",fmt(cur["tf"]),clr=RED);y-=SG

    y=_sec(c,y,"LPT REALTY — BUSINESS BUILDER  (100% Commission)")
    br=[("Total GCI",fmt(cur["gci"]),False,None),("Flat Fee ($500/deal, capped $5,000)",f"-{fmt(bb['bf'])}",False,RED),
        (f"Processing Fee ($195 x {r.annual_deals} deals)",f"-{fmt(bb['tx'])}",False,RED),("Annual Fee","-$500",False,RED)]
    bt=y;_box(c,bt,bt-len(br)*RH)
    for l,v,b,cl in br: y=_row(c,y,l,v,bold=b,clr=cl)
    _rule(c,y);y=_row(c,y,"YOUR ANNUAL TAKE-HOME",fmt(bb["net"]),bold=True,clr=GREEN if bbw else BODY);y-=SG

    y=_sec(c,y,"LPT REALTY — BROKERAGE PARTNER  (80/20 Split)")
    pr=[("Total GCI",fmt(cur["gci"]),False,None),("20% Split (capped $15,000)",f"-{fmt(bp['bf'])}",False,RED),
        (f"Processing Fee ($195 x {r.annual_deals} deals)",f"-{fmt(bp['tx'])}",False,RED),("Annual Fee","-$500",False,RED)]
    bt=y;_box(c,bt,bt-len(pr)*RH)
    for l,v,b,cl in pr: y=_row(c,y,l,v,bold=b,clr=cl)
    _rule(c,y);y=_row(c,y,"YOUR ANNUAL TAKE-HOME",fmt(bp["net"]),bold=True,clr=GREEN if not bbw else BODY);y-=20

    if diff>0:
        gh=64 if y-64>FT+80 else 48
        c.setFillColor(ACCENT);c.roundRect(L-10,y-gh,R-L+20,gh,8,fill=1,stroke=0)
        c.setFillColor(WHITE);c.setFont("Helvetica-Bold",14);c.drawCentredString(W/2,y-16,f"YOU'D KEEP {fmt(diff)} MORE PER YEAR")
        c.setFont("Helvetica",9);c.drawCentredString(W/2,y-32,f"with LPT {bplan}  |  {fmt(diff/r.annual_deals)} more per deal  |  {fmt(diff/12)} more per month")
        if gh>=64:
            c.setFillColor(HexColor("#d4d0ff"));c.setFont("Helvetica",8)
            c.drawCentredString(W/2,y-46,f"{r.brokerage} fees: {fmt(cur['tf'])}   vs.   LPT fees: {fmt(bfees)}")
        y-=gh+14
    else:
        c.setFillColor(SUBTLE);c.roundRect(L-10,y-40,R-L+20,44,8,fill=1,stroke=0)
        c.setFillColor(BODY);c.setFont("Helvetica-Bold",10);c.drawCentredString(W/2,y-12,"Your current brokerage is competitive on commission math.")
        c.setFillColor(HexColor("#666"));c.setFont("Helvetica",8);c.drawCentredString(W/2,y-26,"LPT may still offer advantages in tools, AI, and income diversification.")
        y-=52

    if y>FT+60:
        c.setFillColor(HexColor("#666"));c.setFont("Helvetica",8);c.drawCentredString(W/2,y,"This doesn't include HybridShare income, stock awards, or included AI tools.");y-=20
        bw,bh=300,28;c.setFillColor(GOLD);c.roundRect((W-bw)/2,y-6,bw,bh,6,fill=1,stroke=0)
        c.setFillColor(BG_DARK);c.setFont("Helvetica-Bold",10);c.drawCentredString(W/2,y+3,"Book a free strategy call: calendly.com/discovertpl");y-=34
    if y>FT+20:
        c.setFillColor(HexColor("#aaa"));c.setFont("Helvetica",6.5);c.drawCentredString(W/2,y,"TPL Collective is a recruiting, coaching, and community platform. LPT Realty is the brokerage.");y-=10
        c.setFont("Helvetica",6);c.drawCentredString(W/2,y,f"Generated {datetime.now().strftime('%B %d, %Y')}. Verify terms with your broker.")
    c.save();buf.seek(0);return buf.read()

async def send_email(name,email,pdf,brokerage,diff):
    ak=os.getenv("RESEND_API_KEY") or _get_resend_key()
    if not ak: return False
    b64=base64.b64encode(pdf).decode()
    if diff>0:
        html=f'<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#222"><h2 style="color:#0a0a0f">Hey {name},</h2><p>Your cost comparison — <b>{brokerage} vs. LPT Realty</b>.</p><p>You\'d keep <b style="color:#34d399">${diff:,.0f} more per year</b> at LPT.</p><p>Full report attached. It doesn\'t include HybridShare, stock awards, or AI tools.</p><p><a href="https://calendly.com/discovertpl" style="display:inline-block;background:#f0c040;color:#0a0a0f;font-weight:700;padding:12px 28px;border-radius:6px;text-decoration:none;margin:12px 0">Book a Free Strategy Call</a></p><p style="color:#888;font-size:13px">No pressure. Just numbers.</p><hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0"><p style="color:#999;font-size:11px">TPL Collective is a community platform. LPT Realty is the brokerage.</p></div>'
    else:
        html=f'<div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#222"><h2 style="color:#0a0a0f">Hey {name},</h2><p>Your cost comparison — <b>{brokerage} vs. LPT Realty</b>.</p><p>Commission math is close, but LPT agents also get HybridShare, stock awards, and AI tools included.</p><p><a href="https://calendly.com/discovertpl" style="display:inline-block;background:#f0c040;color:#0a0a0f;font-weight:700;padding:12px 28px;border-radius:6px;text-decoration:none;margin:12px 0">Book a Free Strategy Call</a></p><hr style="border:none;border-top:1px solid #e0e0e0;margin:24px 0"><p style="color:#999;font-size:11px">TPL Collective is a community platform. LPT Realty is the brokerage.</p></div>'
    async with httpx.AsyncClient() as cl:
        r=await cl.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {ak}","Content-Type":"application/json"},
            json={"from":"TPL Collective <reports@tplcollective.ai>","to":[email],"subject":f"Your Brokerage Cost Report — {brokerage} vs. LPT Realty",
                  "html":html,"attachments":[{"filename":"Your-Brokerage-Cost-Report-TPL.pdf","content":b64,"content_type":"application/pdf"}]},timeout=15.0)
    return r.status_code in (200,201)

@router.post("/api/generate-report")
async def generate_report(r:ReportRequest):
    cur=calc_cur(r);bb=calc_bb(cur["gci"],r.annual_deals);bp=calc_bp(cur["gci"],r.annual_deals)
    diff=max(bb["net"],bp["net"])-cur["net"]
    pdf=generate_pdf(r);sent=await send_email(r.name,r.email,pdf,r.brokerage,diff)
    return {"status":"ok","email_sent":sent,"diff":round(diff),"best_plan":"Business Builder" if bb["net"]>=bp["net"] else "Brokerage Partner"}
