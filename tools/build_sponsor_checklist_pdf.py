#!/usr/bin/env python3
"""Build the LPT Sponsor Checklist PDF from markdown source."""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = Path.home() / "Library" / "Fonts"
OUT = Path("/Users/desane/Desktop/tpl/downloads/lpt-sponsor-checklist.pdf")

# Brand palette
BG_DARK = (0.039, 0.039, 0.059)   # #0a0a0f
SURFACE = (0.071, 0.071, 0.102)   # #12121a
ACCENT = (0.424, 0.388, 1.0)      # #6c63ff
ACCENT_HI = (0.545, 0.522, 1.0)   # #8b85ff
TEXT = (0.910, 0.910, 0.941)      # #e8e8f0
MUTED = (0.533, 0.533, 0.667)     # #8888aa
GOLD = (0.941, 0.753, 0.251)      # #f0c040

# Register Montserrat
for weight, file in [
    ("Mont", "Montserrat-Regular.ttf"),
    ("MontLight", "Montserrat-Light.ttf"),
    ("MontMed", "Montserrat-Medium.ttf"),
    ("MontSemi", "Montserrat-SemiBold.ttf"),
    ("MontBold", "Montserrat-Bold.ttf"),
    ("MontBlack", "Montserrat-Black.ttf"),
]:
    pdfmetrics.registerFont(TTFont(weight, str(FONTS_DIR / file)))

PAGE_W, PAGE_H = letter

def draw_page_bg(c, dark=True):
    if dark:
        c.setFillColorRGB(*BG_DARK)
    else:
        c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

def draw_footer(c, page_num, total_pages):
    c.setFillColorRGB(*MUTED)
    c.setFont("MontLight", 8)
    c.drawString(0.75*inch, 0.5*inch, "THE LPT SPONSOR CHECKLIST")
    c.drawRightString(PAGE_W - 0.75*inch, 0.5*inch, f"{page_num} / {total_pages}")
    c.setStrokeColorRGB(*MUTED)
    c.setLineWidth(0.25)
    c.line(0.75*inch, 0.65*inch, PAGE_W - 0.75*inch, 0.65*inch)

def cover_page(c):
    draw_page_bg(c, dark=True)

    # Accent glow bar at top
    c.setFillColorRGB(*ACCENT)
    c.rect(0, PAGE_H - 0.25*inch, PAGE_W, 0.08*inch, fill=1, stroke=0)

    # Eyebrow
    c.setFillColorRGB(*ACCENT)
    c.setFont("MontMed", 9)
    c.drawString(0.75*inch, PAGE_H - 1.5*inch, "TPL COLLECTIVE  //  LEAD MAGNET")

    # Title
    c.setFillColorRGB(1, 1, 1)
    c.setFont("MontBlack", 54)
    c.drawString(0.75*inch, PAGE_H - 2.8*inch, "The LPT")
    c.drawString(0.75*inch, PAGE_H - 3.5*inch, "Sponsor")
    c.drawString(0.75*inch, PAGE_H - 4.2*inch, "Checklist.")

    # Accent underline
    c.setFillColorRGB(*ACCENT)
    c.rect(0.75*inch, PAGE_H - 4.5*inch, 1.5*inch, 0.05*inch, fill=1, stroke=0)

    # Subhead
    c.setFillColorRGB(*TEXT)
    c.setFont("MontLight", 14)
    c.drawString(0.75*inch, PAGE_H - 5.1*inch, "12 questions every agent should ask")
    c.drawString(0.75*inch, PAGE_H - 5.4*inch, "before picking a sponsor at LPT Realty.")

    # Bottom band
    c.setFillColorRGB(*SURFACE)
    c.rect(0, 0, PAGE_W, 1.4*inch, fill=1, stroke=0)

    c.setFillColorRGB(*ACCENT_HI)
    c.setFont("MontSemi", 10)
    c.drawString(0.75*inch, 1.0*inch, "TPLCOLLECTIVE.AI")
    c.setFillColorRGB(*MUTED)
    c.setFont("MontLight", 9)
    c.drawString(0.75*inch, 0.75*inch, "Built for agents researching LPT Realty in 2026.")
    c.drawString(0.75*inch, 0.55*inch, "Free to share with any agent making the same decision.")

def page_intro(c):
    draw_page_bg(c, dark=False)

    c.setFillColorRGB(*ACCENT)
    c.setFont("MontMed", 9)
    c.drawString(0.75*inch, PAGE_H - 0.9*inch, "INTRODUCTION")

    c.setFillColorRGB(0.05, 0.05, 0.10)
    c.setFont("MontBlack", 28)
    c.drawString(0.75*inch, PAGE_H - 1.4*inch, "Why the sponsor decision")
    c.drawString(0.75*inch, PAGE_H - 1.8*inch, "matters more than you think.")

    body_text = [
        "When you join LPT Realty, the agent who brings you in is your sponsor. They",
        "collect revenue share from your production for as long as you're in the",
        "brokerage. That makes sponsor selection one of the most financially",
        "significant decisions of your entire career.",
        "",
        "The right sponsor turns that line item into real leverage. Systems, coaching,",
        "lead flow, and a team building alongside you. The wrong sponsor is just a",
        "name on paperwork.",
        "",
        "Use this checklist on every sponsor conversation. If the answers feel thin,",
        "keep looking.",
    ]
    c.setFillColorRGB(0.18, 0.18, 0.22)
    c.setFont("Mont", 11.5)
    y = PAGE_H - 2.5*inch
    for line in body_text:
        c.drawString(0.75*inch, y, line)
        y -= 16

    # Accent block with key line
    c.setFillColorRGB(*ACCENT)
    c.rect(0.75*inch, y - 0.8*inch, 0.08*inch, 0.7*inch, fill=1, stroke=0)
    c.setFillColorRGB(0.10, 0.10, 0.16)
    c.setFont("MontSemi", 14)
    c.drawString(1.0*inch, y - 0.3*inch, "Picking a sponsor who's actively building")
    c.drawString(1.0*inch, y - 0.55*inch, "alongside you turns a line item into leverage.")

def section_header(c, y, eyebrow, title):
    c.setFillColorRGB(*ACCENT)
    c.setFont("MontMed", 9)
    c.drawString(0.75*inch, y, eyebrow)

    c.setFillColorRGB(0.05, 0.05, 0.10)
    c.setFont("MontBlack", 22)
    c.drawString(0.75*inch, y - 0.45*inch, title)
    return y - 0.95*inch

def question(c, y, number, text, detail_lines):
    # Number badge
    c.setFillColorRGB(*ACCENT)
    c.circle(0.95*inch, y + 0.05*inch, 0.16*inch, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("MontBlack", 11)
    c.drawCentredString(0.95*inch, y, str(number))

    # Question text
    c.setFillColorRGB(0.05, 0.05, 0.10)
    c.setFont("MontBold", 12.5)
    c.drawString(1.30*inch, y, text)

    y -= 0.28*inch
    c.setFillColorRGB(0.25, 0.25, 0.30)
    c.setFont("Mont", 10.5)
    for line in detail_lines:
        c.drawString(1.30*inch, y, line)
        y -= 14
    return y - 0.2*inch

def section_1_page(c):
    draw_page_bg(c, dark=False)
    y = section_header(c, PAGE_H - 0.9*inch, "SECTION 1  //  OF 4",
                       "Production and Credibility.")

    intro = "You're picking someone to mentor your business. Start by confirming they have one."
    c.setFillColorRGB(0.35, 0.35, 0.42)
    c.setFont("MontLight", 10.5)
    c.drawString(0.75*inch, y + 0.25*inch, intro)
    y -= 0.15*inch

    y = question(c, y, 1, "Are you an active, producing agent this year?", [
        "A sponsor who isn't closing deals in the current market can't coach you",
        "through the current market. Ask for a rough transaction count in the last",
        "twelve months. Vague answers count as a no.",
    ])

    y = question(c, y, 2, "How long have you been at LPT, and where before?", [
        "You want someone who has lived the switch themselves. Two to three years",
        "in means they've watched revenue share compound and can tell you what",
        "to expect at month six versus month thirty-six.",
    ])

    y = question(c, y, 3, "Share two recent wins from agents you've sponsored.", [
        "Real examples with real names and real numbers. If nobody on their team",
        "has closed their first LPT deal yet, that's the data point. Not a dealbreaker,",
        "but it should shape your expectations.",
    ])

def section_2_page(c):
    draw_page_bg(c, dark=False)
    y = section_header(c, PAGE_H - 0.9*inch, "SECTION 2  //  OF 4",
                       "Systems and Infrastructure.")

    intro = "This is where sponsors separate themselves. A rev share collector has no systems."
    c.setFillColorRGB(0.35, 0.35, 0.42)
    c.setFont("MontLight", 10.5)
    c.drawString(0.75*inch, y + 0.25*inch, intro)
    y -= 0.15*inch

    y = question(c, y, 4, "What systems will I get access to on day one?", [
        "Specifics matter. CRM access, lead intake forms, listing checklists, buyer",
        "agreements, SOPs for common transactions. Ask for a screen share. A real",
        "operation can show a real operation on the call.",
    ])

    y = question(c, y, 5, "Is there a content or marketing engine I can plug into?", [
        "Paid ads, organic content, newsletter, podcast, YouTube, social calendar.",
        "You don't need every asset. You do need to know what leverage is on the",
        "table. Content generates both leads and credibility.",
    ])

    y = question(c, y, 6, "Shared lead pool, or am I on my own for pipeline?", [
        "Some sponsors generate leads and distribute them. Some don't. Both can",
        "be legitimate. You just need to know which one you're walking into so",
        "you can plan your first ninety days accordingly.",
    ])

def section_3_page(c):
    draw_page_bg(c, dark=False)
    y = section_header(c, PAGE_H - 0.9*inch, "SECTION 3  //  OF 4",
                       "Coaching and Accountability.")

    intro = "Systems are worthless without a rhythm of use."
    c.setFillColorRGB(0.35, 0.35, 0.42)
    c.setFont("MontLight", 10.5)
    c.drawString(0.75*inch, y + 0.25*inch, intro)
    y -= 0.15*inch

    y = question(c, y, 7, "How often will we talk in my first ninety days?", [
        "\"Reach out any time\" is not a coaching cadence. You want a weekly call,",
        "a group call, office hours - something structured. First ninety days is",
        "the window where habits set.",
    ])

    y = question(c, y, 8, "Do you run group coaching or an agent community?", [
        "Peer learning is one of the most underrated parts of a brokerage change.",
        "A sponsor who has built a community of agents at your level (or just",
        "ahead) gives you a place to bring questions without burning 1:1 time.",
    ])

    y = question(c, y, 9, "What's your policy on underperforming agents?", [
        "Listen for honesty. \"I ride it out and hope\" tells you how much",
        "accountability to expect. A sponsor who runs real check-ins and hard",
        "conversations helps you avoid the slow fade most year-two agents hit.",
    ])

def section_4_page(c):
    draw_page_bg(c, dark=False)
    y = section_header(c, PAGE_H - 0.9*inch, "SECTION 4  //  OF 4",
                       "Long-Term Alignment.")

    intro = "The point of revenue share is long horizons. Make the math work for both of you."
    c.setFillColorRGB(0.35, 0.35, 0.42)
    c.setFont("MontLight", 10.5)
    c.drawString(0.75*inch, y + 0.25*inch, intro)
    y -= 0.15*inch

    y = question(c, y, 10, "Building a team, or recruiting for rev share?", [
        "Both can work. Know the difference. A team builder invests in your",
        "production because your production is also their reputation. A pure",
        "recruiter's incentive is to sign you and move on to the next name.",
    ])

    y = question(c, y, 11, "How do you handle it if I outgrow this relationship?", [
        "The healthy answer: supportive of agents evolving into their own team",
        "leaders, their own brand, their own rev share. Watch for sponsors who",
        "treat downstream agents as property instead of partners.",
    ])

    y = question(c, y, 12, "What's your five-year vision for your agents?", [
        "You want a vision that includes more than transaction volume. Wealth",
        "building, personal brand, equity, time freedom, family impact. Better",
        "sponsors have thought about where their agents are going.",
    ])

def final_test_page(c):
    draw_page_bg(c, dark=True)

    c.setFillColorRGB(*ACCENT)
    c.setFont("MontMed", 9)
    c.drawString(0.75*inch, PAGE_H - 0.9*inch, "ONE FINAL TEST")

    c.setFillColorRGB(1, 1, 1)
    c.setFont("MontBlack", 28)
    c.drawString(0.75*inch, PAGE_H - 1.5*inch, "After you've asked")
    c.drawString(0.75*inch, PAGE_H - 1.95*inch, "all twelve, ask yourself")
    c.drawString(0.75*inch, PAGE_H - 2.4*inch, "this:")

    # Quote block
    c.setFillColorRGB(*ACCENT)
    c.rect(0.75*inch, PAGE_H - 3.9*inch, 0.08*inch, 1.0*inch, fill=1, stroke=0)
    c.setFillColorRGB(*ACCENT_HI)
    c.setFont("MontSemi", 17)
    c.drawString(1.0*inch, PAGE_H - 3.2*inch, "Could I see myself on this")
    c.drawString(1.0*inch, PAGE_H - 3.5*inch, "person's team in three years")
    c.drawString(1.0*inch, PAGE_H - 3.8*inch, "and still feel good about it?")

    c.setFillColorRGB(*TEXT)
    c.setFont("Mont", 12)
    y = PAGE_H - 4.6*inch
    lines = [
        "If the answer is yes, you have found your sponsor.",
        "",
        "If the answer is \"I think so,\" keep going.",
        "",
        "Revenue share compounds for decades. You have time to pick correctly.",
    ]
    for line in lines:
        c.drawString(0.75*inch, y, line)
        y -= 20

    # Accent signature
    c.setFillColorRGB(*GOLD)
    c.setFont("MontSemi", 10)
    c.drawString(0.75*inch, 1.2*inch, "Take the time.")
    c.setFillColorRGB(*MUTED)
    c.setFont("MontLight", 9)
    c.drawString(0.75*inch, 1.0*inch, "There is no prize for picking a sponsor before you're ready.")

def back_page(c):
    draw_page_bg(c, dark=False)

    c.setFillColorRGB(*ACCENT)
    c.setFont("MontMed", 9)
    c.drawString(0.75*inch, PAGE_H - 0.9*inch, "ABOUT TPL COLLECTIVE")

    c.setFillColorRGB(0.05, 0.05, 0.10)
    c.setFont("MontBlack", 26)
    c.drawString(0.75*inch, PAGE_H - 1.4*inch, "We built this for a reason.")

    c.setFillColorRGB(0.25, 0.25, 0.30)
    c.setFont("Mont", 11)
    about_lines = [
        "TPL Collective is a team and community inside LPT Realty. We built this",
        "checklist because we watched too many agents make the sponsor decision",
        "on vibes alone, then regret it six months in.",
        "",
        "Our operating model is simple: a full marketing engine, a Mission Control",
        "CRM, onboarding SOPs, and a weekly rhythm of coaching. Agents on our",
        "team get the brokerage plus the infrastructure.",
        "",
        "If you want to see what that looks like up close, the fastest way is a",
        "twenty-minute call.",
    ]
    y = PAGE_H - 2.0*inch
    for line in about_lines:
        c.drawString(0.75*inch, y, line)
        y -= 16

    # CTA block
    c.setFillColorRGB(*BG_DARK)
    c.rect(0.75*inch, 2.2*inch, PAGE_W - 1.5*inch, 2.2*inch, fill=1, stroke=0)

    c.setFillColorRGB(*ACCENT)
    c.rect(0.75*inch, 4.35*inch, PAGE_W - 1.5*inch, 0.05*inch, fill=1, stroke=0)

    c.setFillColorRGB(*ACCENT_HI)
    c.setFont("MontMed", 9)
    c.drawString(1.0*inch, 4.0*inch, "NEXT STEP  //  20 MINUTES")

    c.setFillColorRGB(1, 1, 1)
    c.setFont("MontBlack", 22)
    c.drawString(1.0*inch, 3.55*inch, "Book a call with Joe.")

    c.setFillColorRGB(*TEXT)
    c.setFont("MontLight", 12)
    c.drawString(1.0*inch, 3.15*inch, "No pitch. Real answers. A tour of the stack if you want one.")

    c.setFillColorRGB(*ACCENT)
    c.setFont("MontSemi", 13)
    c.drawString(1.0*inch, 2.7*inch, "calendly.com/discovertpl")

    c.setFillColorRGB(*MUTED)
    c.setFont("MontLight", 10)
    c.drawString(1.0*inch, 2.4*inch, "Learn more: tplcollective.ai/why-tpl")

    # Footer
    c.setStrokeColorRGB(0.85, 0.85, 0.90)
    c.setLineWidth(0.5)
    c.line(0.75*inch, 1.3*inch, PAGE_W - 0.75*inch, 1.3*inch)
    c.setFillColorRGB(*MUTED)
    c.setFont("MontLight", 8)
    c.drawString(0.75*inch, 1.0*inch, "TPL Collective is a team inside LPT Realty. We are not LPT Realty, and nothing in this document")
    c.drawString(0.75*inch, 0.85*inch, "should be read as official LPT Realty policy. For financial figures, verify against jdesane.lpt.com.")
    c.drawString(0.75*inch, 0.65*inch, "Free to share with any agent making the same decision.")

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=letter)

    total_pages = 8

    cover_page(c)
    c.showPage()

    page_intro(c)
    draw_footer(c, 2, total_pages)
    c.showPage()

    section_1_page(c)
    draw_footer(c, 3, total_pages)
    c.showPage()

    section_2_page(c)
    draw_footer(c, 4, total_pages)
    c.showPage()

    section_3_page(c)
    draw_footer(c, 5, total_pages)
    c.showPage()

    section_4_page(c)
    draw_footer(c, 6, total_pages)
    c.showPage()

    final_test_page(c)
    c.showPage()

    back_page(c)
    c.showPage()

    c.save()
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
