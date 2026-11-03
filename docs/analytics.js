/* Optional participation analytics — default OFF, no wallet/IP data sent. */
(()=>{'use strict';
const API=(window.GUARDIAN_API_URL||(['localhost','127.0.0.1'].includes(location.hostname)?'http://127.0.0.1:8000':location.origin)).replace(/\/$/,'');
const consent=document.getElementById('analyticsConsent'), status=document.getElementById('analyticsStatus');
const consentKey='guardian.analytics.consent.v1', idKey='guardian.analytics.id.v1';
function enabled(){try{return localStorage.getItem(consentKey)==='yes';}catch{return false;}}
async function post(path,payload){const r=await fetch(API+'/api/analytics/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),keepalive:true});if(!r.ok)throw Error('Telemetry server unavailable');return r.json();}
function id(){let value=localStorage.getItem(idKey);if(!value){if(!crypto.randomUUID)throw Error('Secure origin required');value=crypto.randomUUID();localStorage.setItem(idKey,value);}return value;}
async function event(name){if(!['localhost','127.0.0.1'].includes(location.hostname))return;if(!enabled()||!['visit','scan_complete'].includes(name))return;try{await post('event',{visitor_id:id(),event:name});status.textContent='OPT-IN ON · Wallet addresses are not collected by telemetry.';}catch{status.textContent='Telemetry is temporarily unavailable; scanning still works.';}}
async function disable(){consent.checked=false;try{localStorage.setItem(consentKey,'no');const current=localStorage.getItem(idKey);if(current){await post('erase',{visitor_id:current});localStorage.removeItem(idKey);status.textContent='OPT-OUT · Erasure requested for this browser’s analytics events.';}else status.textContent='OPT-OUT · No identifier was stored.';}catch{status.textContent='OPT-OUT · Server-side erasure could not be confirmed. Retry when the service is available.';}}
consent.checked=['localhost','127.0.0.1'].includes(location.hostname)&&enabled();
consent.addEventListener('change',async()=>{if(consent.checked){try{localStorage.setItem(consentKey,'yes');await event('visit');}catch{consent.checked=false;status.textContent='Cannot enable analytics in this browser.';}}else await disable();});
if(enabled())event('visit');
window.GuardianAnalytics={event};
})();
