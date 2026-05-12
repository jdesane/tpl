import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

const TO_EMAIL = 'joe@desaneteam.com'
const FROM_EMAIL = 'TPL Mission Control <notifications@tplcollective.ai>'

function esc(v) {
  if (v === null || v === undefined || v === '') return '<span style="color:#9ca3af;">&mdash;</span>'
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>')
}

function plain(v) {
  if (v === null || v === undefined || v === '') return '-'
  return String(v)
}

function row(label, value) {
  return `<tr>
    <td style="padding:8px 12px;color:#6b7280;font-size:13px;border-bottom:1px solid #e5e7eb;width:55%;vertical-align:top;">${esc(label)}</td>
    <td style="padding:8px 12px;color:#1a1a26;font-size:14px;border-bottom:1px solid #e5e7eb;font-weight:500;">${esc(value)}</td>
  </tr>`
}

function sectionHeader(title) {
  return `<tr><td colspan="2" style="padding:18px 12px 8px;color:#1F3864;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #1F3864;">${esc(title)}</td></tr>`
}

function subHeader(title) {
  return `<tr><td colspan="2" style="padding:14px 12px 6px;color:#1F3864;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">${esc(title)}</td></tr>`
}

function buildEmailHtml(p) {
  const s = p.sections || {}
  const agents = s.agents || {}
  const vendors = s.vendors || {}
  const exp = s.expenses || {}
  const space = s.space || {}

  // vendor rows
  const allVendorRows = [
    ...(vendors.rows || []),
    ...(vendors.custom_rows || [])
  ].map(v => `<tr>
    <td style="padding:6px 12px;font-size:13px;border-bottom:1px solid #f0f2f7;width:40%;">${esc(v.name)}</td>
    <td style="padding:6px 12px;font-size:12px;color:#6b7280;border-bottom:1px solid #f0f2f7;width:30%;">${esc(v.category)}</td>
    <td style="padding:6px 12px;font-size:13px;border-bottom:1px solid #f0f2f7;font-weight:600;text-align:right;width:30%;">${esc(v.amount)}</td>
  </tr>`).join('')

  return `<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:680px;margin:0 auto;background:#f5f6fa;padding:24px;">
  <div style="background:#1F3864;color:#fff;padding:24px 22px;border-radius:12px 12px 0 0;">
    <h1 style="margin:0;font-size:20px;font-weight:700;">Wellington Office Snapshot</h1>
    <div style="font-size:13px;opacity:0.85;margin-top:4px;">Submitted by Lily Cho &middot; ${esc(new Date(p.submitted_at).toLocaleString('en-US', { timeZone: 'America/New_York' }))} ET</div>
  </div>
  <div style="background:#fff;border-radius:0 0 12px 12px;padding:0 0 20px;">
    <table style="width:100%;border-collapse:collapse;">

      ${sectionHeader('1. Agents')}
      ${row('Current monthly fee per agent', agents.fee_per_agent)}
      ${row('Total agents on Wellington branch roster', agents.total_roster)}
      ${row('Agents currently paying the monthly fee', agents.paying)}
      ${row('Agents using the office but NOT paying', agents.using_not_paying)}
      ${row('LPT agents using MLS / address only (NOT paying)', agents.mls_only_not_paying)}
      ${row('Total monthly $ collected from agent fees', agents.total_collected)}
      ${row('Other', agents.other)}

      ${sectionHeader('2. Vendors — Monthly $')}
    </table>
    <table style="width:100%;border-collapse:collapse;margin-top:6px;">
      <thead>
        <tr style="background:#f0f2f7;">
          <th style="padding:8px 12px;text-align:left;color:#1F3864;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Vendor</th>
          <th style="padding:8px 12px;text-align:left;color:#1F3864;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Category</th>
          <th style="padding:8px 12px;text-align:right;color:#1F3864;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;">Monthly $</th>
        </tr>
      </thead>
      <tbody>
        ${allVendorRows}
      </tbody>
    </table>
    <table style="width:100%;border-collapse:collapse;">
      ${row('Total monthly vendor revenue', vendors.total)}
      ${row('Other vendors or notes', vendors.other)}

      ${sectionHeader('3. Monthly Expenses')}
      ${subHeader('Rent & Utilities')}
      ${row('Base rent', exp.rent_utilities?.base_rent)}
      ${row('CAM charges', exp.rent_utilities?.cam)}
      ${row('Electric', exp.rent_utilities?.electric)}
      ${row('Water / sewer', exp.rent_utilities?.water_sewer)}
      ${row('Internet / WiFi', exp.rent_utilities?.internet)}

      ${subHeader('Office Operations')}
      ${row('Cleaning service', exp.office_operations?.cleaning)}
      ${row('Coffee, snacks, kitchen supplies', exp.office_operations?.kitchen)}
      ${row('Paper, toner, printer supplies', exp.office_operations?.printer)}
      ${row('Office supplies general', exp.office_operations?.supplies_general)}

      ${subHeader('People')}
      ${row("Molly's monthly pay total", exp.people?.molly_pay)}
      ${row("Molly's hours / schedule", exp.people?.molly_hours)}
      ${row('Other staff or contractor cost', exp.people?.other_staff)}

      ${subHeader('Other')}
      ${row('Office liability / contents insurance', exp.other?.insurance)}
      ${row('Calendly + other software', exp.other?.software)}
      ${row('Anything else paid monthly', exp.other?.other_monthly)}

      ${row('TOTAL MONTHLY EXPENSES', exp.total)}

      ${sectionHeader('4. Space')}
      ${row('Total open desks', space.total_desks)}
      ${row('Currently rented', space.rented)}
      ${row('Available / unrented', space.available)}
      ${row('Notes about the space', space.notes)}

    </table>
  </div>
  <div style="text-align:center;color:#9ca3af;font-size:11px;padding:14px 0;">
    Sent from the Wellington Intake Form &middot; tplcollective.ai
  </div>
</div>`
}

function buildEmailText(p) {
  const s = p.sections || {}
  const agents = s.agents || {}
  const vendors = s.vendors || {}
  const exp = s.expenses || {}
  const space = s.space || {}

  const vendorLines = [
    ...(vendors.rows || []),
    ...(vendors.custom_rows || [])
  ].map(v => `  ${v.name} (${v.category}): ${plain(v.amount)}`).join('\n')

  return `WELLINGTON OFFICE SNAPSHOT
Submitted by Lily Cho
${new Date(p.submitted_at).toLocaleString('en-US', { timeZone: 'America/New_York' })} ET

=== 1. AGENTS ===
Fee per agent: ${plain(agents.fee_per_agent)}
Total roster: ${plain(agents.total_roster)}
Paying: ${plain(agents.paying)}
Using but not paying: ${plain(agents.using_not_paying)}
MLS-only, not paying: ${plain(agents.mls_only_not_paying)}
Total monthly $ collected: ${plain(agents.total_collected)}
Other: ${plain(agents.other)}

=== 2. VENDORS - MONTHLY $ ===
${vendorLines}

Total vendor revenue: ${plain(vendors.total)}
Other vendor notes: ${plain(vendors.other)}

=== 3. MONTHLY EXPENSES ===
-- Rent & Utilities --
Base rent: ${plain(exp.rent_utilities?.base_rent)}
CAM: ${plain(exp.rent_utilities?.cam)}
Electric: ${plain(exp.rent_utilities?.electric)}
Water/sewer: ${plain(exp.rent_utilities?.water_sewer)}
Internet: ${plain(exp.rent_utilities?.internet)}

-- Office Operations --
Cleaning: ${plain(exp.office_operations?.cleaning)}
Kitchen: ${plain(exp.office_operations?.kitchen)}
Printer: ${plain(exp.office_operations?.printer)}
Supplies: ${plain(exp.office_operations?.supplies_general)}

-- People --
Molly's pay: ${plain(exp.people?.molly_pay)}
Molly's hours: ${plain(exp.people?.molly_hours)}
Other staff: ${plain(exp.people?.other_staff)}

-- Other --
Insurance: ${plain(exp.other?.insurance)}
Software: ${plain(exp.other?.software)}
Other monthly: ${plain(exp.other?.other_monthly)}

TOTAL MONTHLY EXPENSES: ${plain(exp.total)}

=== 4. SPACE ===
Total desks: ${plain(space.total_desks)}
Rented: ${plain(space.rented)}
Available: ${plain(space.available)}
Notes: ${plain(space.notes)}
`
}

async function sendResend({ to, from, subject, html, text }) {
  const apiKey = process.env.RESEND_API_KEY
  if (!apiKey) return { ok: false, error: 'RESEND_API_KEY missing' }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from,
      to: Array.isArray(to) ? to : [to],
      subject,
      html,
      text
    })
  })
  const body = await res.json().catch(() => ({}))
  return { ok: res.ok, status: res.status, body }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST') return res.status(405).json({ success: false, error: 'Method not allowed' })

  const payload = req.body || {}
  if (!payload.sections) {
    return res.status(400).json({ success: false, error: 'Missing form data' })
  }

  const ip = (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || null
  const ua = req.headers['user-agent'] || null

  try {
    // Store in Supabase
    const { data: row, error: dbError } = await supabase
      .from('wellington_intake_submissions')
      .insert({
        submitted_by_name: payload.submitted_by_name || 'Lily Cho',
        payload,
        ip_address: ip,
        user_agent: ua
      })
      .select()
      .single()

    if (dbError) {
      console.error('Supabase insert error:', dbError)
      // Don't block on storage error — try email anyway
    }

    // Send email to Joe
    const subject = `Wellington Office Snapshot — from Lily Cho`
    const html = buildEmailHtml(payload)
    const text = buildEmailText(payload)

    const sendRes = await sendResend({
      to: TO_EMAIL,
      from: FROM_EMAIL,
      subject,
      html,
      text
    })

    if (!sendRes.ok) {
      console.error('Resend email failed:', sendRes)
      // If we stored successfully, still return success — Joe can pull it from DB
      if (!dbError) {
        return res.status(200).json({ success: true, id: row?.id, warning: 'stored but email failed' })
      }
      return res.status(500).json({ success: false, error: 'Could not deliver submission' })
    }

    return res.status(200).json({ success: true, id: row?.id })
  } catch (e) {
    console.error('Wellington intake handler error:', e)
    return res.status(500).json({ success: false, error: 'Internal error' })
  }
}
