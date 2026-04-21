import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

const SITE_ORIGIN = 'https://tplcollective.ai'

// Map magnet slug -> { filename, title, funnel_id for research-stage enrollment }
const MAGNETS = {
  'sponsor-checklist': {
    filename: 'lpt-sponsor-checklist.pdf',
    title: 'The LPT Sponsor Checklist',
    funnel_id: 22, // "Research Stage - Sponsor Checklist"
    first_email_subject: 'Your LPT Sponsor Checklist (download inside)',
  },
}

function buildMagnetEmail({ firstName, magnet, downloadUrl }) {
  const name = firstName || 'there';
  const title = magnet.title;
  return {
    subject: magnet.first_email_subject,
    html: `<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#1a1a26;line-height:1.6;">
  <p>Hey ${name},</p>
  <p>Thanks for grabbing the Sponsor Checklist. Here's your download link:</p>
  <p style="margin:24px 0;">
    <a href="${downloadUrl}" style="display:inline-block;background:#6c63ff;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:600;">Download the checklist (PDF)</a>
  </p>
  <p>Or paste this into your browser:<br><span style="color:#6c63ff;word-break:break-all;">${downloadUrl}</span></p>
  <p>The link's good for 30 days. Save the PDF somewhere you'll actually look at it, because the twelve questions only work if you run them on every sponsor conversation you have.</p>
  <p>Quick note on how to use it. Don't hand the list to a sponsor and ask them to fill it out. Use it as your own interview framework. The answers you get in real time - how specific, how confident, how honest - tell you more than any written response would.</p>
  <p>I built this after watching too many agents pick a sponsor on vibes, then spend year two wishing they'd asked better questions.</p>
  <p>If anything on the checklist sparks a question, just reply to this email. It comes straight to me.</p>
  <p>Joe<br><span style="color:#8888aa;font-size:13px;">Joe DeSane / TPL Collective / joe@tplcollective.co</span></p>
</div>`,
    text: `Hey ${name},

Thanks for grabbing the Sponsor Checklist. Here's your download link:

${downloadUrl}

The link's good for 30 days. Save the PDF somewhere you'll actually look at it, because the twelve questions only work if you run them on every sponsor conversation you have.

Quick note on how to use it. Don't hand the list to a sponsor and ask them to fill it out. Use it as your own interview framework. The answers you get in real time - how specific, how confident, how honest - tell you more than any written response would.

I built this after watching too many agents pick a sponsor on vibes, then spend year two wishing they'd asked better questions.

If anything on the checklist sparks a question, just reply to this email. It comes straight to me.

Joe

Joe DeSane
TPL Collective
joe@tplcollective.co`,
  };
}

async function sendResend({ to, from, replyTo, subject, html, text }) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return { ok: false, error: 'RESEND_API_KEY missing' };
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ from, to: Array.isArray(to) ? to : [to], reply_to: replyTo, subject, html, text })
  });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}

async function sendInternalNotification(lead) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return;
  const rows = [
    ['Name', lead.name || (lead.first_name || '') + ' ' + (lead.last_name || '')],
    ['Email', lead.email],
    ['Phone', lead.phone || '-'],
    ['Brokerage', lead.brokerage || '-'],
    ['Deals/Year', lead.deals_per_year || '-'],
    ['Avg Price', lead.avg_price || '-'],
    ['Source', lead.source || 'Web'],
    ['Stage', lead.stage || '-'],
    ['Magnet', lead.magnet || '-'],
  ].map(([k, v]) => `<tr><td style="padding:8px 0;color:#888;">${k}</td><td style="padding:8px 0;">${v}</td></tr>`).join('');
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: 'TPL Mission Control <notifications@tplcollective.ai>',
      to: ['joe@desaneteam.com'],
      subject: `New Lead: ${lead.name || lead.email} - TPL Mission Control`,
      html: `<div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0a0a0f;color:#fff;padding:32px;border-radius:12px;">
        <h2 style="color:#6c63ff;margin:0 0 24px;">✦ New Lead Captured</h2>
        <table style="width:100%;border-collapse:collapse;">${rows}</table>
        <a href="https://mission.tplcollective.ai" style="display:inline-block;margin-top:24px;padding:12px 24px;background:#6c63ff;color:#fff;text-decoration:none;border-radius:6px;">View in Mission Control</a>
      </div>`
    })
  });
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).end();

  const body = req.body || {};
  const {
    // existing fields (keep backward compatible)
    name, email, brokerage, phone, deals_per_year, avg_price, source, notes,
    // new optional fields
    first_name, last_name, stage, magnet, tags,
  } = body;

  if (!email) return res.status(400).json({ success: false, error: 'Email is required' });

  // Derive name
  const fullName = name || [first_name, last_name].filter(Boolean).join(' ').trim() || email;
  const derivedFirstName = first_name || (name ? name.split(' ')[0] : '');
  const derivedStage = stage || 'unknown';
  const magnetConfig = magnet ? MAGNETS[magnet] : null;

  try {
    // Insert lead
    const { data: lead, error: leadError } = await supabase
      .from('leads')
      .insert({
        name: fullName,
        email,
        phone: phone || '',
        brokerage: brokerage || '',
        deals_per_year: deals_per_year || '',
        avg_price: avg_price || '',
        source: source || 'Web',
        notes: notes || '',
        status: 'new',
        stage: derivedStage,
        magnet: magnet || null,
      })
      .select()
      .single();

    if (leadError) {
      console.error('Supabase insert error:', leadError);
      return res.status(500).json({ success: false, error: 'Failed to save lead' });
    }

    // Log activity
    await supabase.from('activity_log').insert({
      type: 'lead',
      message: `New lead: ${fullName} from ${magnet || brokerage || source || 'Web'}`,
      meta: { lead_id: lead.id, source: source || 'Web', magnet: magnet || null, stage: derivedStage, tags: tags || [] }
    });

    // Magnet flow
    let downloadUrl = null;
    if (magnetConfig) {
      const downloadToken = crypto.randomUUID().replace(/-/g, '') + crypto.randomBytes(6).toString('hex');
      const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

      const { error: dError } = await supabase
        .from('magnet_deliveries')
        .insert({
          lead_id: lead.id,
          magnet,
          download_token: downloadToken,
          expires_at: expiresAt,
        });
      if (dError) console.error('magnet_deliveries insert error:', dError);

      downloadUrl = `${SITE_ORIGIN}/api/download?t=${downloadToken}`;

      // Send delivery email
      const mail = buildMagnetEmail({ firstName: derivedFirstName, magnet: magnetConfig, downloadUrl });
      const sendRes = await sendResend({
        to: email,
        from: 'Joe DeSane <joe@tplcollective.co>',
        replyTo: 'joe@tplcollective.co',
        subject: mail.subject,
        html: mail.html,
        text: mail.text,
      });
      if (!sendRes.ok) console.error('Magnet delivery email failed:', sendRes);

      // Log email_send_log entry for tracking
      await supabase.from('email_send_log').insert({
        lead_id: lead.id,
        to_email: email,
        subject: mail.subject,
        funnel_id: magnetConfig.funnel_id,
        step_order: 0,
        status: sendRes.ok ? 'sent' : 'failed',
      }).then(() => {}, () => {}); // non-fatal if schema differs

      // Enroll in research-stage drip funnel
      const { error: eError } = await supabase
        .from('email_funnel_enrollments')
        .insert({
          lead_id: lead.id,
          funnel_id: magnetConfig.funnel_id,
          current_step: 0,
          status: 'active',
          last_sent_at: new Date().toISOString(),
        });
      if (eError) console.error('Funnel enrollment error:', eError);
    }

    // Internal notification
    sendInternalNotification({ ...lead, name: fullName, stage: derivedStage, magnet }).catch(e => console.error('notify failed:', e));

    return res.status(200).json({
      success: true,
      id: lead.id,
      ...(downloadUrl ? { download_url: downloadUrl } : {}),
    });
  } catch (e) {
    console.error('Failed to save lead:', e);
    return res.status(500).json({ success: false, error: 'Internal error' });
  }
}
