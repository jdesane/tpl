export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).end();

  const { name, email, brokerage, phone, deals_per_year, avg_price, source } = req.body;

  // Save lead to VPS
  try {
    const auth = Buffer.from('joe:YourPasswordHere').toString('base64');
    await fetch('https://mission.tplcollective.ai/api/leads', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${auth}`
      },
      body: JSON.stringify({ name, email, brokerage, phone, deals_per_year, avg_price, source: source || 'Web' })
    });
  } catch(e) {
    console.error('Failed to save lead to VPS:', e);
  }

  // Send email notification via Resend
  try {
    const apiKey = process.env.RESEND_API_KEY;
    if (apiKey) {
      await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          from: 'TPL Mission Control <notifications@tplcollective.ai>',
          to: ['joe@desaneteam.com'],
          subject: `New Lead: ${name} — TPL Mission Control`,
          html: `
            <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#0a0a0f;color:#fff;padding:32px;border-radius:12px;">
              <h2 style="color:#6c63ff;margin:0 0 24px;">✦ New Lead Captured</h2>
              <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px 0;color:#888;">Name</td><td style="padding:8px 0;">${name}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Email</td><td style="padding:8px 0;">${email}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Phone</td><td style="padding:8px 0;">${phone || '—'}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Brokerage</td><td style="padding:8px 0;">${brokerage}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Deals/Year</td><td style="padding:8px 0;">${deals_per_year || '—'}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Avg Price</td><td style="padding:8px 0;">${avg_price || '—'}</td></tr>
                <tr><td style="padding:8px 0;color:#888;">Source</td><td style="padding:8px 0;">${source || 'Web'}</td></tr>
              </table>
              <a href="https://mission.tplcollective.ai" style="display:inline-block;margin-top:24px;padding:12px 24px;background:#6c63ff;color:#fff;text-decoration:none;border-radius:6px;">View in Mission Control</a>
            </div>
          `
        })
      });
    }
  } catch(e) {
    console.error('Failed to send email notification:', e);
  }

  return res.status(200).json({ success: true });
}
