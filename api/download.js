import { createClient } from '@supabase/supabase-js'
import fs from 'fs'
import path from 'path'

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
)

// magnet slug -> local filename (under private-assets/)
const MAGNET_FILES = {
  'sponsor-checklist': 'lpt-sponsor-checklist.pdf',
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method Not Allowed');

  const token = (req.query && req.query.t) || '';
  if (!token || typeof token !== 'string' || token.length < 16) {
    return res.status(400).send('Invalid download link.');
  }

  try {
    const { data: delivery, error } = await supabase
      .from('magnet_deliveries')
      .select('id, lead_id, magnet, expires_at, downloaded_at')
      .eq('download_token', token)
      .maybeSingle();

    if (error || !delivery) {
      return res.status(404).send('Download link not found or expired.');
    }

    if (new Date(delivery.expires_at) < new Date()) {
      return res.status(410).send('This download link has expired. Please request a new copy.');
    }

    const filename = MAGNET_FILES[delivery.magnet];
    if (!filename) {
      return res.status(404).send('File not available.');
    }

    // Resolve file path: private-assets/<filename> relative to project root
    const filePath = path.join(process.cwd(), 'private-assets', filename);
    if (!fs.existsSync(filePath)) {
      console.error('Missing gated asset:', filePath);
      return res.status(500).send('File not available. Please contact joe@tplcollective.co.');
    }

    const bytes = fs.readFileSync(filePath);

    // Stamp download + update lead magnet_downloaded_at (fire-and-forget)
    const now = new Date().toISOString();
    supabase
      .from('magnet_deliveries')
      .update({ downloaded_at: now })
      .eq('id', delivery.id)
      .then(() => {}, (e) => console.error('update delivery failed:', e));

    if (delivery.lead_id) {
      supabase
        .from('leads')
        .update({ magnet_downloaded_at: now })
        .eq('id', delivery.lead_id)
        .then(() => {}, (e) => console.error('update lead failed:', e));

      supabase
        .from('activity_log')
        .insert({
          type: 'magnet_downloaded',
          message: `Magnet downloaded: ${delivery.magnet}`,
          meta: { lead_id: delivery.lead_id, magnet: delivery.magnet }
        })
        .then(() => {}, () => {});
    }

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('Cache-Control', 'private, no-cache, no-store, must-revalidate');
    return res.status(200).send(bytes);
  } catch (e) {
    console.error('download handler error:', e);
    return res.status(500).send('Server error. Please contact joe@tplcollective.co.');
  }
}
