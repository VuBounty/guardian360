/* GUARDIAN 360: no API keys, secrets, or RPC credentials belong in this file. */
window.GUARDIAN_API_URL = ['localhost','127.0.0.1'].includes(location.hostname) ? '' : 'https://guardian360-vubounty-readonly.onrender.com';
window.GUARDIAN_PUBLIC_PREVIEW = !['localhost','127.0.0.1'].includes(location.hostname) && !window.GUARDIAN_API_URL;
/* Remain false until testnet E2E and independent security assessment are complete. */
window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false; // SERVER ALSO EXCLUDES ALL REVOKE ROUTES
if (window.GUARDIAN_PUBLIC_PREVIEW) {
  document.addEventListener('DOMContentLoaded', () => {
    const banner=document.querySelector('.beta-banner');
    if(banner)banner.innerHTML='<strong>⚠ OPEN-SOURCE UI PREVIEW — LIVE SCAN UNAVAILABLE</strong><span>GitHub Pages cannot host the Python backend. Security scan and wallet transactions are disabled until a reviewed HTTPS backend is configured.</span>';
    const scan=document.getElementById('scanButton'); if(scan){scan.disabled=true;scan.title='Live API not configured';}
    const status=document.getElementById('apiStatus'); if(status)status.textContent='BACKEND NOT DEPLOYED';
    const analytics=document.getElementById('analyticsConsent'); if(analytics)analytics.disabled=true;
    const admin=document.querySelector('a[href="admin.html"]'); if(admin)admin.hidden=true;
  });
}

// Public release intentionally suspends analytics until a durable consent-based datastore exists.
if (!['localhost','127.0.0.1'].includes(location.hostname)) {
  document.addEventListener('DOMContentLoaded', () => {
    const a=document.getElementById('analyticsConsent');if(a){a.checked=false;a.disabled=true;}
    const b=document.getElementById('analyticsStatus');if(b)b.textContent='Public telemetry paused pending durable privacy-first storage.';
    const admin=document.querySelector('a[href="admin.html"]');if(admin)admin.hidden=true;
  });
}

// GUARDIAN_PUBLIC_LIVE_UI_V242
// Display public beta status without enabling wallet signing or analytics.
if (!window.GUARDIAN_PUBLIC_PREVIEW && !['localhost','127.0.0.1'].includes(location.hostname)) {
  document.addEventListener('DOMContentLoaded', () => {
    const banner=document.querySelector('.beta-banner');
    if (banner) banner.innerHTML='<strong>⚠ PUBLIC READ-ONLY BETA — NOT AUDITED</strong><span>Live blockchain scans are available. Token and approval coverage can be incomplete. Wallet connections and Revoke transactions are disabled.</span>';
    const tag=document.querySelector('.brandtag');
    if (tag) tag.textContent='WALLET SECURITY OPERATIONS / V2.4.2 · PUBLIC BETA';
    const badge=document.querySelector('.testtag');
    if (badge) badge.textContent='◉ PUBLIC BETA';
  });
}
