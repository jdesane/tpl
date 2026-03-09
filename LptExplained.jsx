import { useState, useEffect, useRef } from "react";

const COLORS = {
  bg: "#0a0a0f",
  surface: "#12121a",
  surfaceAlt: "#1a1a26",
  border: "#2a2a3d",
  accent: "#6c63ff",
  accentGlow: "rgba(108,99,255,0.15)",
  accentBright: "#8b85ff",
  gold: "#f0c040",
  goldGlow: "rgba(240,192,64,0.12)",
  text: "#e8e8f0",
  textMuted: "#8888aa",
  textDim: "#55556a",
  white: "#ffffff",
};

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: ${COLORS.bg};
    color: ${COLORS.text};
    font-family: 'DM Sans', sans-serif;
    font-weight: 400;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }

  .lpt-page {
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* HERO */
  .hero {
    position: relative;
    padding: 120px 24px 100px;
    text-align: center;
    overflow: hidden;
  }

  .hero-grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(108,99,255,0.06) 1px, transparent 1px),
      linear-gradient(90deg, rgba(108,99,255,0.06) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, black 40%, transparent 100%);
  }

  .hero-glow {
    position: absolute;
    top: -100px;
    left: 50%;
    transform: translateX(-50%);
    width: 700px;
    height: 400px;
    background: radial-gradient(ellipse, rgba(108,99,255,0.18) 0%, transparent 70%);
    pointer-events: none;
  }

  .eyebrow {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: ${COLORS.accent};
    margin-bottom: 20px;
    display: inline-block;
  }

  .hero h1 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(64px, 10vw, 120px);
    line-height: 0.92;
    letter-spacing: 0.02em;
    color: ${COLORS.white};
    margin-bottom: 28px;
  }

  .hero h1 span {
    color: ${COLORS.accent};
  }

  .hero-sub {
    font-size: clamp(16px, 2vw, 20px);
    color: ${COLORS.textMuted};
    max-width: 580px;
    margin: 0 auto 48px;
    font-weight: 300;
    line-height: 1.7;
  }

  .hero-badges {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
  }

  .badge {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 8px 16px;
    border-radius: 4px;
    border: 1px solid ${COLORS.border};
    color: ${COLORS.textMuted};
    background: ${COLORS.surface};
  }

  /* SECTION WRAPPER */
  .section {
    max-width: 1100px;
    margin: 0 auto;
    padding: 80px 24px;
  }

  .section-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: ${COLORS.accent};
    margin-bottom: 16px;
  }

  .section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(40px, 5vw, 64px);
    line-height: 1;
    color: ${COLORS.white};
    margin-bottom: 20px;
    letter-spacing: 0.02em;
  }

  .section-body {
    font-size: 17px;
    color: ${COLORS.textMuted};
    max-width: 680px;
    line-height: 1.75;
    font-weight: 300;
  }

  /* DIVIDER */
  .divider {
    border: none;
    border-top: 1px solid ${COLORS.border};
    margin: 0 24px;
    max-width: 1100px;
    margin-left: auto;
    margin-right: auto;
  }

  /* WHAT IS LPT */
  .what-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 48px;
    margin-top: 56px;
    align-items: start;
  }

  @media (max-width: 640px) {
    .what-grid { grid-template-columns: 1fr; gap: 32px; }
  }

  .what-card {
    background: ${COLORS.surface};
    border: 1px solid ${COLORS.border};
    border-radius: 12px;
    padding: 36px;
  }

  .what-card h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 28px;
    letter-spacing: 0.04em;
    color: ${COLORS.white};
    margin-bottom: 14px;
  }

  .what-card p {
    font-size: 15px;
    color: ${COLORS.textMuted};
    line-height: 1.7;
    font-weight: 300;
  }

  .tag {
    display: inline-block;
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 3px;
    margin-bottom: 16px;
  }

  .tag-brokerage {
    background: rgba(108,99,255,0.12);
    color: ${COLORS.accentBright};
    border: 1px solid rgba(108,99,255,0.25);
  }

  .tag-community {
    background: rgba(240,192,64,0.1);
    color: ${COLORS.gold};
    border: 1px solid rgba(240,192,64,0.2);
  }

  /* CHOICE PHILOSOPHY */
  .philosophy {
    background: ${COLORS.surface};
    border-top: 1px solid ${COLORS.border};
    border-bottom: 1px solid ${COLORS.border};
    padding: 80px 24px;
  }

  .philosophy-inner {
    max-width: 1100px;
    margin: 0 auto;
  }

  .vs-row {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 32px;
    align-items: center;
    margin-top: 56px;
  }

  @media (max-width: 640px) {
    .vs-row { grid-template-columns: 1fr; }
    .vs-divider { display: none; }
  }

  .vs-col-bad {
    background: ${COLORS.surfaceAlt};
    border: 1px solid ${COLORS.border};
    border-radius: 12px;
    padding: 32px;
    opacity: 0.6;
  }

  .vs-col-good {
    background: linear-gradient(135deg, rgba(108,99,255,0.08), rgba(108,99,255,0.03));
    border: 1px solid rgba(108,99,255,0.3);
    border-radius: 12px;
    padding: 32px;
  }

  .vs-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 16px;
  }

  .vs-label-bad { color: ${COLORS.textDim}; }
  .vs-label-good { color: ${COLORS.accentBright}; }

  .vs-col-bad h3, .vs-col-good h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 26px;
    letter-spacing: 0.03em;
    margin-bottom: 16px;
  }

  .vs-col-bad h3 { color: ${COLORS.textMuted}; }
  .vs-col-good h3 { color: ${COLORS.white}; }

  .vs-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .vs-list li {
    font-size: 14px;
    color: ${COLORS.textMuted};
    font-weight: 300;
    padding-left: 20px;
    position: relative;
    line-height: 1.5;
  }

  .vs-list li::before {
    content: attr(data-icon);
    position: absolute;
    left: 0;
  }

  .vs-divider {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 48px;
    color: ${COLORS.border};
    text-align: center;
  }

  /* PLANS */
  .plans-section {
    max-width: 1100px;
    margin: 0 auto;
    padding: 80px 24px;
  }

  .plans-header {
    margin-bottom: 48px;
  }

  .plans-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  @media (max-width: 640px) {
    .plans-grid { grid-template-columns: 1fr; }
  }

  .plan-card {
    border-radius: 16px;
    padding: 44px 40px;
    position: relative;
    overflow: hidden;
  }

  .plan-card-bb {
    background: ${COLORS.surface};
    border: 1px solid ${COLORS.border};
  }

  .plan-card-bp {
    background: linear-gradient(145deg, #13132a, #0f0f1f);
    border: 1px solid rgba(108,99,255,0.35);
  }

  .plan-card-bp::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, ${COLORS.accent}, transparent);
  }

  .plan-name {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 36px;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }

  .plan-name-bb { color: ${COLORS.white}; }
  .plan-name-bp { color: ${COLORS.accentBright}; }

  .plan-tagline {
    font-size: 14px;
    color: ${COLORS.textMuted};
    font-weight: 300;
    margin-bottom: 36px;
    line-height: 1.5;
  }

  .plan-stat {
    margin-bottom: 24px;
  }

  .plan-stat-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: ${COLORS.textDim};
    margin-bottom: 6px;
  }

  .plan-stat-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 42px;
    line-height: 1;
    letter-spacing: 0.02em;
  }

  .plan-stat-value-bb { color: ${COLORS.white}; }
  .plan-stat-value-bp { color: ${COLORS.accentBright}; }

  .plan-stat-sub {
    font-size: 13px;
    color: ${COLORS.textMuted};
    margin-top: 4px;
    font-weight: 300;
  }

  .plan-rule {
    border: none;
    border-top: 1px solid ${COLORS.border};
    margin: 28px 0;
  }

  .plan-features {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .plan-features li {
    font-size: 14px;
    color: ${COLORS.textMuted};
    padding-left: 22px;
    position: relative;
    font-weight: 300;
    line-height: 1.5;
  }

  .plan-features li::before {
    content: '→';
    position: absolute;
    left: 0;
    color: ${COLORS.accent};
    font-size: 12px;
  }

  /* UNIVERSAL FEES */
  .fees-bar {
    background: ${COLORS.surface};
    border-top: 1px solid ${COLORS.border};
    border-bottom: 1px solid ${COLORS.border};
  }

  .fees-inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 56px 24px;
  }

  .fees-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0;
    margin-top: 40px;
    border: 1px solid ${COLORS.border};
    border-radius: 12px;
    overflow: hidden;
  }

  @media (max-width: 640px) {
    .fees-grid { grid-template-columns: 1fr; }
  }

  .fee-item {
    padding: 36px 32px;
    border-right: 1px solid ${COLORS.border};
    position: relative;
  }

  .fee-item:last-child { border-right: none; }

  @media (max-width: 640px) {
    .fee-item { border-right: none; border-bottom: 1px solid ${COLORS.border}; }
    .fee-item:last-child { border-bottom: none; }
  }

  .fee-item-label {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: ${COLORS.textDim};
    margin-bottom: 12px;
  }

  .fee-item-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 48px;
    color: ${COLORS.white};
    line-height: 1;
    margin-bottom: 8px;
  }

  .fee-item-desc {
    font-size: 13px;
    color: ${COLORS.textMuted};
    font-weight: 300;
    line-height: 1.6;
  }

  /* PHILOSOPHY PILLARS */
  .pillars {
    max-width: 1100px;
    margin: 0 auto;
    padding: 80px 24px;
  }

  .pillars-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    margin-top: 48px;
  }

  @media (max-width: 640px) {
    .pillars-grid { grid-template-columns: 1fr; }
  }

  .pillar {
    padding: 36px 32px;
    border: 1px solid ${COLORS.border};
    border-radius: 12px;
    background: ${COLORS.surface};
    position: relative;
    overflow: hidden;
  }

  .pillar::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(108,99,255,0.4), transparent);
  }

  .pillar-number {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 72px;
    line-height: 1;
    color: ${COLORS.border};
    margin-bottom: 16px;
    letter-spacing: 0.02em;
  }

  .pillar h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 26px;
    letter-spacing: 0.04em;
    color: ${COLORS.white};
    margin-bottom: 12px;
  }

  .pillar p {
    font-size: 14px;
    color: ${COLORS.textMuted};
    line-height: 1.7;
    font-weight: 300;
  }

  /* CTA */
  .cta-section {
    background: linear-gradient(135deg, rgba(108,99,255,0.08) 0%, transparent 60%);
    border-top: 1px solid rgba(108,99,255,0.2);
    padding: 100px 24px;
    text-align: center;
  }

  .cta-inner {
    max-width: 640px;
    margin: 0 auto;
  }

  .cta-inner h2 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: clamp(48px, 6vw, 72px);
    color: ${COLORS.white};
    line-height: 1;
    letter-spacing: 0.02em;
    margin-bottom: 20px;
  }

  .cta-inner p {
    font-size: 17px;
    color: ${COLORS.textMuted};
    font-weight: 300;
    margin-bottom: 40px;
    line-height: 1.7;
  }

  .btn-primary {
    display: inline-block;
    background: ${COLORS.accent};
    color: ${COLORS.white};
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 16px 40px;
    border-radius: 6px;
    text-decoration: none;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-right: 12px;
  }

  .btn-primary:hover {
    background: ${COLORS.accentBright};
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(108,99,255,0.35);
  }

  .btn-secondary {
    display: inline-block;
    background: transparent;
    color: ${COLORS.textMuted};
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 16px 32px;
    border-radius: 6px;
    text-decoration: none;
    border: 1px solid ${COLORS.border};
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-secondary:hover {
    border-color: ${COLORS.accent};
    color: ${COLORS.accentBright};
    transform: translateY(-2px);
  }

  /* FADE IN ANIMATION */
  .fade-in {
    opacity: 0;
    transform: translateY(24px);
    transition: opacity 0.6s ease, transform 0.6s ease;
  }

  .fade-in.visible {
    opacity: 1;
    transform: translateY(0);
  }

  .delay-1 { transition-delay: 0.1s; }
  .delay-2 { transition-delay: 0.2s; }
  .delay-3 { transition-delay: 0.3s; }

  /* ── PHONE (≤480px) ── */
  @media (max-width: 480px) {
    .hero { padding: 80px 16px 60px; }
    .hero h1 { font-size: clamp(48px, 14vw, 72px); }
    .hero-sub { font-size: 15px; }
    .hero-badges { gap: 8px; }
    .badge { font-size: 10px; padding: 6px 12px; }
    .section { padding: 52px 16px; }
    .section-title { font-size: clamp(32px, 10vw, 48px); }
    .plan-card { padding: 32px 22px; }
    .plan-stat-value { font-size: 36px; }
    .fees-inner { padding: 44px 16px; }
    .fee-item-value { font-size: 40px; }
    .pillar { padding: 28px 22px; }
    .cta-section { padding: 72px 16px; }
    .cta-inner { padding: 0; }
    .btn-primary, .btn-secondary { display: block; width: 100%; text-align: center; margin: 0 0 12px 0; }
    .btn-primary { margin-right: 0; }
    .calendly-inline-widget { height: 600px !important; }
  }
`;

function useFadeIn() {
  useEffect(() => {
    const els = document.querySelectorAll(".fade-in");
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
      { threshold: 0.1 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
}

export default function LptExplained() {
  useFadeIn();

  return (
    <>
      <style>{styles}</style>
      <div className="lpt-page">

        {/* HERO */}
        <section className="hero">
          <div className="hero-grid" />
          <div className="hero-glow" />
          <div style={{ position: "relative", zIndex: 1 }}>
            <span className="eyebrow">LPT Realty — The Brokerage Behind TPL Collective</span>
            <h1>Your Career.<br /><span>Your Choice.</span></h1>
            <p className="hero-sub">
              Most brokerages hand you one plan and tell you to make it work.
              LPT Realty was built differently — two commission structures, zero desk fees,
              and a model designed to serve you at every stage of your career.
              You pick the plan that fits. You change it as you grow.
            </p>
            <div className="hero-badges">
              <span className="badge">Two Commission Plans</span>
              <span className="badge">Switch Anytime</span>
              <span className="badge">Brokerage for Life</span>
              <span className="badge">No Desk Fees</span>
            </div>
          </div>
        </section>

        {/* WHAT IS LPT */}
        <section className="section">
          <div className="fade-in">
            <span className="section-label">The Basics</span>
            <h2 className="section-title">Two Entities,<br />One Mission</h2>
            <p className="section-body">
              Understanding how LPT Realty and TPL Collective work together is the starting point.
              They're related but distinct — and that distinction matters for your career.
            </p>
          </div>
          <div className="what-grid">
            <div className="what-card fade-in delay-1">
              <span className="tag tag-brokerage">The Brokerage</span>
              <h3>LPT Realty, LLC</h3>
              <p>
                LPT Realty is the licensed real estate brokerage where your license lives.
                Founded by Robert Palmer and built by agents from the start, LPT handles
                your transactions, compliance, E&O coverage, Dotloop access, and commission
                disbursements. When you close a deal, it closes under LPT.
              </p>
            </div>
            <div className="what-card fade-in delay-2">
              <span className="tag tag-community">The Community Layer</span>
              <h3>TPL Collective</h3>
              <p>
                TPL Collective is not a brokerage. It's the community, coaching infrastructure,
                and AI-powered recruiting platform built on top of LPT Realty's model.
                When you join through TPL, you get the brokerage benefits of LPT plus the
                resources, mentorship, and tools of the Collective.
              </p>
            </div>
          </div>
        </section>

        <hr className="divider" />

        {/* PHILOSOPHY */}
        <section className="philosophy">
          <div className="philosophy-inner">
            <div className="fade-in">
              <span className="section-label">The Problem We Solve</span>
              <h2 className="section-title">One Size Fits None</h2>
              <p className="section-body">
                A new agent grinding their first deals has different needs than a 20-year
                producer who's already capped. A team builder chasing passive income wants
                something different than someone who just wants to close and keep everything.
                LPT Realty was designed around that reality — not around a single plan
                that works best for the brokerage.
              </p>
            </div>
            <div className="vs-row fade-in delay-1">
              <div className="vs-col-bad">
                <div className="vs-label vs-label-bad">Traditional Model</div>
                <h3>One Structure. No Choice.</h3>
                <ul className="vs-list">
                  <li data-icon="✗">Fixed splits regardless of your production</li>
                  <li data-icon="✗">Cap resets punish momentum</li>
                  <li data-icon="✗">No path to ownership or revenue share</li>
                  <li data-icon="✗">Technology costs layered on top</li>
                  <li data-icon="✗">Switch brokerages when your needs change</li>
                </ul>
              </div>
              <div className="vs-divider">VS</div>
              <div className="vs-col-good">
                <div className="vs-label vs-label-good">LPT Realty Model</div>
                <h3>Agent Choice. Your Terms.</h3>
                <ul className="vs-list">
                  <li data-icon="→">Two commission plans — you pick the one that fits</li>
                  <li data-icon="→">Low flat fees mean more stays in your pocket</li>
                  <li data-icon="→">Revenue/HybridShare creates income beyond closings</li>
                  <li data-icon="→">$11k+ in tech tools included at no added cost</li>
                  <li data-icon="→">Stay at LPT for your entire career, at any stage</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* THE TWO PLANS */}
        <section className="plans-section">
          <div className="plans-header fade-in">
            <span className="section-label">Two Plans. One Brokerage. You Decide.</span>
            <h2 className="section-title">Pick the Plan<br />That Fits Your Business</h2>
            <p className="section-body">
              Same brokerage. Same support. Same tools. Same compliance.
              What changes is how your commissions are structured — and whether you
              want to build passive income through HybridShare on top of your closings.
              You can switch once per anniversary year. No penalty. No pressure.
            </p>
          </div>
          <div className="plans-grid">
            <div className="plan-card plan-card-bb fade-in delay-1">
              <div className="plan-name plan-name-bb">Business Builder</div>
              <p className="plan-tagline">
                Maximum per-deal take-home. Flat fee per transaction, hard cap, and you're done.
                Built for high-volume producers who want simplicity.
              </p>

              <div className="plan-stat">
                <div className="plan-stat-label">You Keep</div>
                <div className="plan-stat-value plan-stat-value-bb">100%</div>
                <div className="plan-stat-sub">of your Gross Commission Income</div>
              </div>

              <div className="plan-stat">
                <div className="plan-stat-label">LPT Retains Per Core Transaction</div>
                <div className="plan-stat-value plan-stat-value-bb">$500</div>
                <div className="plan-stat-sub">flat admin fee, not a percentage</div>
              </div>

              <div className="plan-stat">
                <div className="plan-stat-label">Annual Cap</div>
                <div className="plan-stat-value plan-stat-value-bb">$5K</div>
                <div className="plan-stat-sub">once hit, you close at 100% for the rest of your plan year</div>
              </div>

              <hr className="plan-rule" />
              <ul className="plan-features">
                <li>10 transactions to cap (at $500 each)</li>
                <li>No revenue/HybridShare earnings while on this plan</li>
                <li>Can switch to Brokerage Partner at any time</li>
                <li>Best for: high-volume, transaction-focused agents</li>
              </ul>
            </div>

            <div className="plan-card plan-card-bp fade-in delay-2">
              <div className="plan-name plan-name-bp">Brokerage Partner</div>
              <p className="plan-tagline">
                Formerly RevShare Partner. Build income beyond your own closings through
                HybridShare — and stay in the revenue pool for life.
              </p>

              <div className="plan-stat">
                <div className="plan-stat-label">You Keep</div>
                <div className="plan-stat-value plan-stat-value-bp">80%</div>
                <div className="plan-stat-sub">of your Gross Commission Income per core transaction</div>
              </div>

              <div className="plan-stat">
                <div className="plan-stat-label">LPT Retains</div>
                <div className="plan-stat-value plan-stat-value-bp">20%</div>
                <div className="plan-stat-sub">per core transaction (the Core Transaction Cost)</div>
              </div>

              <div className="plan-stat">
                <div className="plan-stat-label">Annual Cap</div>
                <div className="plan-stat-value plan-stat-value-bp">$15K</div>
                <div className="plan-stat-sub">once hit, you're capped for the rest of your plan year</div>
              </div>

              <hr className="plan-rule" />
              <ul className="plan-features">
                <li>HybridShare income from your downline's closings (7 tiers)</li>
                <li>Stock grants — 2x multiplier vs Business Builder</li>
                <li>Revenue share unlocked from day one on this plan</li>
                <li>Best for: agents building a team or long-term income</li>
              </ul>
            </div>
          </div>
        </section>

        {/* UNIVERSAL FEES */}
        <section className="fees-bar">
          <div className="fees-inner">
            <div className="fade-in">
              <span className="section-label">Universal Fees — Both Plans</span>
              <h2 className="section-title">What Everyone Pays</h2>
              <p className="section-body">
                Regardless of which plan you're on, these fees apply to every agent.
                No surprises, no hidden splits.
              </p>
            </div>
            <div className="fees-grid fade-in delay-1">
              <div className="fee-item">
                <div className="fee-item-label">Transaction Fee (Core)</div>
                <div className="fee-item-value">$195</div>
                <div className="fee-item-desc">
                  Per core transaction. Collected on the closing disclosure from the client.
                  If not collected, deducted from your commission. Does not count toward cap.
                </div>
              </div>
              <div className="fee-item">
                <div className="fee-item-label">Annual Fee</div>
                <div className="fee-item-value">$500</div>
                <div className="fee-item-desc">
                  Once per anniversary year. Auto-retained from your first closing of the year.
                  Accumulates if you don't close — rolls into the next year.
                </div>
              </div>
              <div className="fee-item">
                <div className="fee-item-label">Everything Else</div>
                <div className="fee-item-value">$0</div>
                <div className="fee-item-desc">
                  No desk fees. No monthly tech fees. Dotloop, Lofty (Chime), Listing Power Tools,
                  and $11k+ in marketing tools are included at no additional cost.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* THREE PILLARS */}
        <section className="pillars">
          <div className="fade-in">
            <span className="section-label">The Philosophy</span>
            <h2 className="section-title">Built for Your Entire Career</h2>
            <p className="section-body">
              LPT Realty's core value proposition isn't just low fees — it's a brokerage
              designed to serve you at every stage.
            </p>
          </div>
          <div className="pillars-grid">
            <div className="pillar fade-in delay-1">
              <div className="pillar-number">01</div>
              <h3>Agent Choice</h3>
              <p>
                No one tells you which plan to be on. You evaluate your production, your goals,
                and your career stage — then you choose. And you can change plans as your
                business evolves.
              </p>
            </div>
            <div className="pillar fade-in delay-2">
              <div className="pillar-number">02</div>
              <h3>Brokerage for Life</h3>
              <p>
                LPT was designed so you never need to leave. Whether you're a new agent finding
                your footing or a top producer capped out every year, this model grows with you.
                Revenue share even survives retirement.
              </p>
            </div>
            <div className="pillar fade-in delay-3">
              <div className="pillar-number">03</div>
              <h3>Your Definition of Success</h3>
              <p>
                Some agents want maximum per-deal income. Others want to build passive revenue
                through a downline. Both are valid. LPT doesn't pick a lane for you — it builds
                infrastructure for both.
              </p>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="cta-section">
          <div className="cta-inner fade-in">
            <h2>Which Plan<br />Is Right for You?</h2>
            <p>
              The answer depends on your production volume, your goals, and where
              you are in your career right now. Book a call and we'll walk through
              both plans with your actual numbers — no pressure, no pitch, just clarity.
            </p>
            <a href="https://calendly.com/joedesane/learn-more-about-lpt-realty-clone" target="_blank" className="btn-primary">Book a Call with Joe</a>
            <a href="/fee-plans" className="btn-secondary">See All Fee Details</a>
          </div>
          <div style={{ maxWidth: "760px", margin: "56px auto 0" }} className="fade-in">
            <div
              className="calendly-inline-widget"
              data-url="https://calendly.com/joedesane/learn-more-about-lpt-realty-clone?hide_gdpr_banner=1&background_color=12121a&text_color=e8e8f0&primary_color=6c63ff"
              style={{ minWidth: "320px", height: "700px" }}
            />
            <script
              type="text/javascript"
              src="https://assets.calendly.com/assets/external/widget.js"
              async
            />
          </div>
        </section>

      </div>
    </>
  );
}
