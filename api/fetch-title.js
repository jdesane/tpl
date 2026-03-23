export default async function handler(req, res) {
  const { url } = req.query;
  if (!url) return res.status(400).json({ error: 'url required' });

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const resp = await fetch(url, {
      signal: controller.signal,
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; TPLBot/1.0)' },
    });
    clearTimeout(timeout);

    const html = await resp.text();
    const match = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = match ? match[1].trim().slice(0, 200) : null;

    res.setHeader('Cache-Control', 's-maxage=3600');
    return res.status(200).json({ title });
  } catch {
    return res.status(200).json({ title: null });
  }
}
