import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

// Pre-loaded defaults sourced from Wellington_Claude_Code_Handoff.md
// PRODUCTION VOLUME IS NOT INCOME — see handoff §1
const DEFAULTS = {
  today: {
    income: {
      desk_fees_count: 37,             // June actual funded
      desk_fees_rate: 35,              // current $35/mo
      vendor_revenue: 5920             // Lily's intake form (Bell + lenders + 12 small)
    },
    expenses: {
      rent: 4484.58,                   // Year 5 lease base, default
      rent_delta_lily: 6100,           // Lily reported this — likely CAM/escalations bundled
      electric: 110,
      internet: 110,
      water_sewer: 0,
      cleaning: 100,
      kitchen: 100,
      printer: 250,
      supplies: 75,
      insurance: 100,
      molly: 1200,
      bookkeeping: 183
    }
  },
  restructured: {
    desk_dedicated_count: 4,
    desk_dedicated_rate: 135,
    desk_affiliation_count: 50,
    desk_affiliation_rate: 35,
    producers_recovered: 12,           // of 15 known producing non-payers
    ghost_producers_captured: 25,      // of 38 known
    cut_count: 18,                     // info-only, no revenue impact
    vendor_bell: 3000,                 // up from $2,500
    vendor_lender_rate: 1250,          // up from $1,000 each
    vendor_lender_count: 3,
    vendor_small_total: 420,           // 12 small vendors × $35 (unchanged)
    vendor_new_slots: 2,
    vendor_new_slot_rate: 500,
    molly_new: 1400                    // small bump for expanded role
  },
  audience: {
    // NOT INCOME — see handoff §1
    agents_total: 88,
    active_producers: 57,
    sales_volume_12mo: 180600000,
    listings_closed: 97,
    buyers_closed: 82
  }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST') return res.status(405).json({ ok: false })

  const { token } = req.body || {}
  if (!token || typeof token !== 'string') {
    return res.status(401).json({ ok: false, error: 'Token required' })
  }

  try {
    const { data: row, error } = await supabase
      .from('wellington_access_tokens')
      .select('token, label, expires_at')
      .eq('token', token)
      .maybeSingle()

    if (error) {
      console.error('Token lookup error:', error)
      return res.status(500).json({ ok: false })
    }
    if (!row) {
      return res.status(401).json({ ok: false, error: 'Invalid token' })
    }
    if (row.expires_at && new Date(row.expires_at) < new Date()) {
      return res.status(401).json({ ok: false, error: 'Token expired' })
    }

    // Touch last_used_at
    await supabase
      .from('wellington_access_tokens')
      .update({ last_used_at: new Date().toISOString() })
      .eq('token', token)
      .then(() => {}, () => {})

    // Load latest snapshot if any (so the page picks up where Joe left off)
    const { data: latestSnap } = await supabase
      .from('wellington_pnl_snapshots')
      .select('id, label, payload, created_at')
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    // List recent snapshots for the snapshot picker
    const { data: snapshots } = await supabase
      .from('wellington_pnl_snapshots')
      .select('id, label, created_at')
      .order('created_at', { ascending: false })
      .limit(20)

    return res.status(200).json({
      ok: true,
      label: row.label,
      defaults: DEFAULTS,
      latest_snapshot: latestSnap || null,
      snapshots: snapshots || []
    })
  } catch (e) {
    console.error('Load handler error:', e)
    return res.status(500).json({ ok: false })
  }
}
