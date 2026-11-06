/* GUARDIAN 360 V2.6: LIVE READ-ONLY. No secrets in frontend. */
window.GUARDIAN_API_URL = 'https://guardian360-vubounty-readonly.onrender.com';
window.GUARDIAN_PUBLIC_PREVIEW = false;
window.GUARDIAN_REQUIRED_API_VERSION = '2.6.0-public-readonly';
window.GUARDIAN_REQUIRED_RELEASE_ID = '20261106T135757Z-39d632c9';
window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false;
/* Public telemetry is disabled until consent and data retention are reviewed. */
document.addEventListener('DOMContentLoaded', () => {
  const analytics = document.getElementById('analyticsConsent');
  if (analytics) {analytics.checked=false; analytics.disabled=true;}
  const status = document.getElementById('analyticsStatus');
  if (status) status.textContent='Public telemetry disabled.';
  const admin=document.querySelector('a[href="admin.html"]');
  if (admin) admin.hidden=true;
});
