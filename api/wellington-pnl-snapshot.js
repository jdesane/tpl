import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

// PRODUCTION VOLUME IS NOT INCOME — see handoff §1
// The snapshot accepts arbitrary JSON, but we enforce that income only
// contains the two allowed categories.
const ALLOWED_INCOME_KEYS = new Set(['desk_fees', 'vendor_fees'])

async function verifyToken(token) {
  if (!token || typeof token !== 'string') return false
  const { data: row } = await supabase
    .from('wellington_access_tokens')
    .select('token, expires_at')
    .eq('token', token)
    .maybeSingle()
  if (!row) return false
  if (row.expires_at && new Date(row.expires_at) < new Date()) return false
  return true
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST') return res.status(405).json({ ok: false })

  const { token, label, payload } = req.body || {}
  const valid = await verifyToken(token)
  if (!valid) return res.status(401).json({ ok: false, error: 'Invalid token' })

  if (!payload || typeof payload !== 'object') {
    return res.status(400).json({ ok: false, error: 'Missing payload' })
  }

  // Guardrail — refuse any income line outside the allowed categories.
  // This is the hard rule from the handoff: production volume cannot be income.
  if (payload.today?.income) {
    for (const k of Object.keys(payload.today.income)) {
      if (!ALLOWED_INCOME_KEYS.has(k.replace(/_(count|rate|revenue|fees)$/, ''))) {
        // Allow prefixed keys like desk_fees_count, desk_fees_rate, vendor_revenue
        const base = k.startsWith('desk_fees') ? 'desk_fees'
                  : k.startsWith('vendor') ? 'vendor_fees'
                  : k
        if (!ALLOWED_INCOME_KEYS.has(base)) {
          return res.status(400).json({
            ok: false,
            error: `Income key not allowed: ${k}. Income = desk_fees + vendor_fees only.`
          })
        }
      }
    }
  }

  try {
    const { data: row, error } = await supabase
      .from('wellington_pnl_snapshots')
      .insert({
        label: label || `Snapshot ${new Date().toISOString().slice(0,16).replace('T',' ')}`,
        payload
      })
      .select()
      .single()

    if (error) {
      console.error('Snapshot insert error:', error)
      return res.status(500).json({ ok: false })
    }

    return res.status(200).json({ ok: true, id: row.id, created_at: row.created_at })
  } catch (e) {
    console.error('Snapshot handler error:', e)
    return res.status(500).json({ ok: false })
  }
}
