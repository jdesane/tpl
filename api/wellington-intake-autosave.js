import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

// Lightweight autosave endpoint. No email, no validation, just upsert by session_token.
// Two event types:
//   - "open"   : first hit when the page loads
//   - "input"  : debounced form snapshot as the user types
//
// We upsert into wellington_intake_submissions with status='draft'.
// When the final POST /api/wellington-intake comes in, status flips to 'submitted'.

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST') return res.status(405).json({ ok: false })

  const body = req.body || {}
  const { session_token, event, payload, keystroke_count } = body
  if (!session_token || typeof session_token !== 'string' || session_token.length > 128) {
    return res.status(400).json({ ok: false, error: 'bad session_token' })
  }
  if (!['open', 'input'].includes(event)) {
    return res.status(400).json({ ok: false, error: 'bad event' })
  }

  const ip = (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || null
  const ua = req.headers['user-agent'] || null
  const now = new Date().toISOString()

  try {
    // Check if a row already exists for this session_token
    const { data: existing } = await supabase
      .from('wellington_intake_submissions')
      .select('id, status, opened_at, keystroke_count')
      .eq('session_token', session_token)
      .maybeSingle()

    if (existing) {
      // Don't downgrade a submitted row
      if (existing.status === 'submitted') {
        return res.status(200).json({ ok: true, status: 'submitted' })
      }
      const update = { last_updated_at: now }
      if (event === 'input' && payload) {
        update.payload = payload
        update.keystroke_count = keystroke_count || (existing.keystroke_count || 0)
      }
      const { error } = await supabase
        .from('wellington_intake_submissions')
        .update(update)
        .eq('id', existing.id)
      if (error) {
        console.error('autosave update error:', error)
        return res.status(500).json({ ok: false })
      }
    } else {
      // First touch — insert a draft row
      const row = {
        session_token,
        status: 'draft',
        submitted_by_name: 'Lily Cho',
        payload: payload || { sections: {} },
        opened_at: event === 'open' ? now : now,
        last_updated_at: now,
        ip_address: ip,
        user_agent: ua,
        keystroke_count: keystroke_count || 0
      }
      const { error } = await supabase
        .from('wellington_intake_submissions')
        .insert(row)
      if (error) {
        console.error('autosave insert error:', error)
        return res.status(500).json({ ok: false })
      }
    }

    return res.status(200).json({ ok: true })
  } catch (e) {
    console.error('autosave handler error:', e)
    return res.status(500).json({ ok: false })
  }
}
