/* GUARDIAN 360: no API keys, secrets, or RPC credentials belong in this file. */
window.GUARDIAN_API_URL = window.GUARDIAN_API_URL || '';
window.GUARDIAN_PUBLIC_PREVIEW = !['localhost','127.0.0.1'].includes(location.hostname) && !window.GUARDIAN_API_URL;
/* Remain false until testnet E2E and independent security assessment are complete. */
window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false;
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
