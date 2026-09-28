/* Shared helpers for /trainings, /watch and /book. */
(function () {
  // Mission Control serves the data. Local previews talk to their own origin.
  var host = location.hostname;
  window.TPL_API = /tplcollective\.ai$/.test(host)
    ? 'https://mission.tplcollective.ai/api'
    : location.origin + '/api';

  // The weekly email's per-recipient token (?t=). Carried onto our own links so
  // /trainings -> /watch -> /book stays attributed to the same agent.
  var params = new URLSearchParams(location.search);
  var t = params.get('t') || '';
  window.TPL_TOKEN = /^[0-9a-f-]{36}$/i.test(t) ? t : '';

  window.tplLink = function (path, extra) {
    var u = new URL(path, location.origin);
    if (window.TPL_TOKEN) u.searchParams.set('t', window.TPL_TOKEN);
    Object.keys(extra || {}).forEach(function (k) { if (extra[k]) u.searchParams.set(k, extra[k]); });
    return u.pathname + u.search;
  };

  window.tplEsc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };

  window.tplFmtDuration = function (sec) {
    sec = parseInt(sec, 10) || 0;
    return sec > 0 ? Math.max(1, Math.round(sec / 60)) + ' min' : '';
  };

  window.tplTrack = function (name, params) {
    try { if (window.gtag) gtag('event', name, params || {}); } catch (e) {}
  };

  document.addEventListener('DOMContentLoaded', function () {
    var h = document.getElementById('hamburger'), m = document.getElementById('mobile-menu');
    if (h && m) h.addEventListener('click', function () { h.classList.toggle('open'); m.classList.toggle('open'); });
    // keep attribution on internal links that opt in
    document.querySelectorAll('a[data-keep-t]').forEach(function (a) { a.setAttribute('href', window.tplLink(a.getAttribute('href'))); });
  });
})();
