// TPL Collective — Visitor Tracking
// Add to every page: <script src="/tpl-tracking.js" defer></script>
(function(){
  var MC = 'https://mission.tplcollective.ai';

  // Check for cid in URL params or cookie
  var params = new URLSearchParams(window.location.search);
  var cid = params.get('cid') || getCookie('tpl_cid');
  var ref = params.get('ref') || params.get('utm_campaign') || '';
  var utm_source = params.get('utm_source') || '';

  // If cid found in URL, save to cookie for cross-page tracking
  if (params.get('cid')) {
    setCookie('tpl_cid', cid, 30); // 30 day cookie
    setCookie('tpl_ref', ref, 30);
    setCookie('tpl_utm_source', utm_source, 30);
  }

  // If no cid, check if they're a known contact by email in sessionStorage
  if (!cid) {
    var savedEmail = sessionStorage.getItem('tpl_gate_email');
    if (savedEmail) {
      // We'll match by email on the next form submission
    }
    return; // Can't track without a cid
  }

  // Track this page view
  try {
    fetch(MC + '/api/tracking/pageview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cid: cid,
        page: window.location.pathname,
        referrer: document.referrer,
        utm_source: utm_source || getCookie('tpl_utm_source') || '',
        utm_campaign: ref || getCookie('tpl_ref') || ''
      })
    }).catch(function(){});
  } catch(e) {}

  // Expose cid globally for calculator and other scripts
  window.__tpl_cid = cid;
  window.__tpl_ref = ref;

  function setCookie(name, value, days) {
    var d = new Date();
    d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = name + '=' + value + ';expires=' + d.toUTCString() + ';path=/;SameSite=Lax';
  }

  function getCookie(name) {
    var v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }
})();
