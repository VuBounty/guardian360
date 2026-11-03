/* GUARDIAN 360 V2.4 — read-only scanning; revoke is an explicit opt-in isolated module. */
(()=>{'use strict';
const $ = (selector,root=document)=>root.querySelector(selector);
const $$ = (selector,root=document)=>[...root.querySelectorAll(selector)];
const CHAINS=[
 {key:'bsc',name:'BNB Smart Chain',id:56,symbol:'BNB',explorer:'https://bscscan.com',enabled:true},
 {key:'ethereum',name:'Ethereum',id:1,symbol:'ETH',explorer:'https://etherscan.io',enabled:true},
 {key:'base',name:'Base',id:8453,symbol:'ETH',explorer:'https://basescan.org',enabled:true},
 {key:'arbitrum',name:'Arbitrum One',id:42161,symbol:'ETH',explorer:'https://arbiscan.io',enabled:true},
 {key:'polygon',name:'Polygon',id:137,enabled:false},
 {key:'optimism',name:'OP Mainnet',id:10,enabled:false},
 {key:'avalanche',name:'Avalanche C-Chain',id:43114,enabled:false},
 {key:'solana',name:'Solana',id:'non-EVM',enabled:false}
];
const byKey=Object.fromEntries(CHAINS.map(c=>[c.key,c]));
const API=(window.GUARDIAN_API_URL||(['localhost','127.0.0.1'].includes(location.hostname)?'http://127.0.0.1:8000':location.origin)).replace(/\/$/,'');
const walletPattern=/^0x[0-9a-fA-F]{40}$/;
const chosen=new Set(['bsc']);
const state={report:null,view:'overview',resultChain:'all',busy:false,scanLog:[],backendOK:false};
const h=(x)=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $id=(x)=>document.getElementById(x);
const label=(str,tone='')=>`<span class="tag ${tone}">${h(str)}</span>`;
const supported=()=>CHAINS.filter(c=>c.enabled);
const displayName=(key)=>byKey[key]?.name||key;
const short=(x,n=12)=>{const s=String(x||'');return s.length>n+8?s.slice(0,n)+'…'+s.slice(-6):s;};
function safeLink(url){try{const u=new URL(String(url));if(u.protocol!=='https:')return null;
 const hosts=['etherscan.io','bscscan.com','basescan.org','arbiscan.io','revoke.cash','debank.com','support.metamask.io','ethereum.org'];
 return hosts.includes(u.hostname)?u.href:null;}catch{return null;}}
function revokeURL(address,chain){const chainId=byKey[chain]?.id;return `https://revoke.cash/address/${address}/approvals?chainId=${chainId}`;}
function anchor(text,url){const u=safeLink(url);return u?`<a class="mini-link" href="${h(u)}" target="_blank" rel="noopener noreferrer">${h(text)} ↗</a>`:'';}
function numText(x,digits=8){if(x==null||x==='')return '—';const s=String(x).trim();if(!/^[+-]?\d+(\.\d+)?(e[+-]?\d+)?$/i.test(s))return '—';
 if(/^[-+]?0(?:\.0*)?$/.test(s))return '0';
 const whole=s.replace(/^[+-]/,'').split('.')[0];
 if(whole.length>16)return s.slice(0,3)+'… ('+whole.length+' digits)';
 const n=Number(s);if(!Number.isFinite(n))return '—';
 if(n!==0&&Math.abs(n)<1e-8)return n.toExponential(3);
 return n.toLocaleString('en-US',{maximumFractionDigits:digits});}
function usdText(x){if(x==null||x==='')return 'UNKNOWN';const n=Number(x);if(!Number.isFinite(n)||n<0||n>1e13)return 'UNVERIFIED';if(n>0&&n<.01)return '<$0.01';return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);}
function activeChains(){return state.report?(state.resultChain==='all'?state.report.chains:state.report.chains.filter(c=>c.chain===state.resultChain)):[];}
function announce(msg,cls=''){ $id('error').textContent=msg; $id('error').dataset.type=cls; }
function updateChosen(){const picks=supported().filter(c=>chosen.has(c.key));$id('networkSummary').textContent=picks.length===0?'SELECT NETWORKS':picks.length===1?picks[0].name:`${picks.length} NETWORKS SELECTED`;
 $id('selectedCount').textContent=`(${picks.length} SELECTED)`;$id('optionCount').textContent=`${picks.length}/${supported().length}`;$id('scanButton').disabled=!picks.length||state.busy;
 $id('scanHint').textContent=picks.length?`${picks.map(c=>c.key.toUpperCase()).join(' + ')} // READY TO SCAN`:'NO NETWORK SELECTED';
 if(state.report){const previous=new Set((state.report.requested_chains||state.report.chains.map(c=>c.chain)));const changed=previous.size!==chosen.size||[...chosen].some(k=>!previous.has(k));$id('scanHint').textContent=changed?'SCOPE CHANGED // PREVIOUS REPORT NOT UPDATED':'SCOPE MATCHES CURRENT REPORT'; if(changed){$id('warningStrip').dataset.stale='true';$id('warningStrip').setAttribute('title','Network selection changed. The report reflects the previous scan.');}else{$id('warningStrip').dataset.stale='false';}}}
function drawOptions(){const q=$id('chainSearch').value.toLowerCase().trim();const html=[];
 for(const [heading,group] of [['LIVE ENGINE / SUPPORTED',CHAINS.filter(c=>c.enabled)],['ROADMAP / UNAVAILABLE',CHAINS.filter(c=>!c.enabled)]]){
 const matches=group.filter(c=>!q||c.name.toLowerCase().includes(q)||c.key.includes(q)||String(c.id).includes(q));if(!matches.length)continue;
 html.push(`<div class="grouphead">${heading}</div>`);
 for(const c of matches)html.push(`<label class="network-opt ${c.enabled?'':'disabled'}"><input type="checkbox" data-chain="${c.key}" ${chosen.has(c.key)?'checked':''} ${c.enabled?'':'disabled'}><span><strong>${h(c.name)}</strong><small>${c.enabled?'AVAILABLE / DATA COVERAGE MAY VARY':'NOT IMPLEMENTED'}</small></span><span class="id">#${h(c.id)}</span></label>`);
 }$id('networkOptions').innerHTML=html.join('')||'<div class="menuempty">No matching networks found.</div>';}
function openMenu(open){$id('networkMenu').hidden=!open;$id('networkTrigger').setAttribute('aria-expanded',String(open));if(open){drawOptions();$id('chainSearch').focus();}}
$id('networkTrigger').addEventListener('click',()=>openMenu($id('networkMenu').hidden));
$id('chainSearch').addEventListener('input',drawOptions);
$id('networkOptions').addEventListener('change',e=>{const t=e.target.closest('[data-chain]');if(!t||!byKey[t.dataset.chain]?.enabled)return;t.checked?chosen.add(t.dataset.chain):chosen.delete(t.dataset.chain);updateChosen();drawOptions();});
$id('selectAll').addEventListener('click',()=>{supported().forEach(c=>chosen.add(c.key));updateChosen();drawOptions();});
$id('clearChains').addEventListener('click',()=>{chosen.clear();updateChosen();drawOptions();});
$id('applyChains').addEventListener('click',()=>openMenu(false));
document.addEventListener('pointerdown',e=>{if(!e.target.closest('#networkWrap'))openMenu(false);});
document.addEventListener('keydown',e=>{if(e.key==='Escape')openMenu(false);});
function log(message,type=''){state.scanLog.push({t:new Date().toLocaleTimeString('en-GB',{hour12:false}),message,type});state.scanLog=state.scanLog.slice(-15);$id('auditLog').innerHTML=state.scanLog.map(x=>`<div><span class="time">[${h(x.t)}]</span> <span class="${h(x.type)}">${h(x.message)}</span></div>`).join('');}
function setBusy(yes){state.busy=yes;$id('busyPanel').hidden=!yes;$id('scanButtonText').textContent=yes?'⌛ SCANNING BLOCKCHAIN…':'▶ RUN SECURITY SCAN';updateChosen();}
function usdPartial(chains){let sum=0,cnt=0;for(const c of chains){if(c.native_usd!=null){const n=Number(c.native_usd);if(Number.isFinite(n)&&n>=0&&n<=1e13){sum+=n;cnt++;}}for(const t of(c.tokens||[])){if(t.trusted_usd_eligible&&t.usd_value!=null){const n=Number(t.usd_value);if(Number.isFinite(n)&&n>=0&&n<=1e13){sum+=n;cnt++;}}}}return cnt?usdText(sum):'NOT PRICED';}
function collect(chains){return {approvals:chains.reduce((n,c)=>n+(c.approvals||[]).length,0),unlimited:chains.reduce((n,c)=>n+(c.approvals||[]).filter(a=>a.unlimited).length,0),tokenReview:chains.reduce((n,c)=>n+(c.tokens||[]).filter(t=>t.classification==='review').length,0),sweeper:chains.filter(c=>c.sweeper?.status==='pattern_detected').length,delegations:chains.filter(c=>c.delegation?.status==='eip7702_delegated').length,known:chains.filter(c=>c.delegation?.identity_status==='known_documented_address').length,rpc:chains.filter(c=>c.native_status==='verified').length,coverageIncomplete:chains.some(c=>c.quality?.status!=='complete'||c.coverage?.approvals_completeness!=='complete'),usd:usdPartial(chains)};}
function metric(head,val,sub,tone='amber'){return `<article class="panel stat"><div class="fline"></div><div class="heading">${h(head)}</div><div class="value ${tone}">${h(val)}</div><div class="sub">${h(sub)}</div></article>`;}
function refreshSummary(){const chain=activeChains();const s=collect(chain);const flagged=s.sweeper||s.unlimited||s.tokenReview;
 const risk=flagged?'REVIEW REQUIRED':'UNDETERMINED';
 $id('stats').innerHTML=metric('EVIDENCE-BASED FINDINGS',risk,flagged?`${flagged} indicators to investigate; not proof of compromise.`:'Insufficient evidence to determine wallet safety.',flagged?'red':'amber')+
 metric('AUDIT COVERAGE',s.coverageIncomplete?'INCOMPLETE':'CHECK SCOPE',`${s.rpc}/${chain.length} RPC accessible · historical permissions may be missing`,'amber')+
 metric('ACTIVE APPROVALS FOUND',String(s.approvals)+' *',`${s.unlimited} unlimited · (*) not a complete permission count`,'green')+
 metric('KNOWN ASSET VALUE',s.usd,'Only priced and recognized holdings are included; not total portfolio value.','blue');
 $id('warningStrip').innerHTML=`<strong>⚠ NO SAFETY CLEARANCE</strong><span>${s.approvals===0?'0 approvals discovered ≠ 0 approvals exist. ':''}ERC-20, NFT, Permit2 and transaction history may not be fully indexed.</span>`;
 const previous=new Set((state.report.requested_chains||state.report.chains.map(c=>c.chain)));const changed=previous.size!==chosen.size||[...chosen].some(k=>!previous.has(k));$id('warningStrip').dataset.stale=changed?'true':'false';
 $id('workspaceDesc').textContent=`${chain.length} networks displayed / ${state.report.chains.length} networks scanned · ${new Date(state.report.timestamp*1000).toLocaleString('en-GB')}`;
}
function row(name,description,middle='',right=''){return `<div class="resultrow"><div><b>${h(name)}</b><small>${h(description)}</small></div><div class="colmid">${middle}</div><div class="right">${right}</div></div>`;}
function empty(title,details){return `<div class="empty-state"><strong>${h(title)}</strong><p>${h(details)}</p></div>`;}
function explainer(title,body){return `<div class="explain"><strong>${h(title)}</strong> ${h(body)}</div>`;}
function heading(title,desc=''){return `<div class="eyebrow content-title">${h(title)}</div>${desc?`<p class="content-desc">${h(desc)}</p>`:''}`;}
function buildOverview(chains){let out=heading('NETWORK INTELLIGENCE / LIVE DATA','Status of scanned networks; not a certificate of safety.');
 for(const c of chains){const quality=c.quality?.status||'unknown';out+=row(displayName(c.chain)+` / #${c.chain_id}`,`Native balance: ${numText(c.native_balance,10)} ${c.symbol} · Block #${c.block||'—'}`,label(c.native_status==='verified'?'RPC VERIFIED':'RPC UNKNOWN',c.native_status==='verified'?'low':'warn'),label(quality==='complete'?'CHECK DETAILS':'HISTORY INCOMPLETE','warn'));}
 const s=collect(chains);
 if(s.sweeper)out+=row('SUSPICIOUS OUTBOUND PATTERN',`${s.sweeper} networks show rapid outgoing-transfer patterns under an experimental heuristic`,label('MANUAL INVESTIGATION','warn'),label('SIGNAL, NOT PROOF','warn'));
 if(s.tokenReview)out+=row('TOKEN INTEGRITY',`${s.tokenReview} tokens require contract review and are excluded from trusted USD totals`,label('REVIEW TOKENS','warn'),label('NO AUTO INTERACTION','warn'));
 if(s.unlimited)out+=row('UNLIMITED ALLOWANCES',`${s.unlimited} unlimited approvals were found in the scanned scope`,label('REVIEW CONTRACT','fail'),label('NO AUTO-REVOKE','warn'));
 out+=explainer('DECISION RULE /', 'Evaluate risk independently from coverage. No detected indicator is not proof of no risk.');return out;}
function buildAssets(chains){let out=heading('ASSET REGISTER / VERIFIED VS UNVERIFIED','Native assets differ from ERC-20 tokens sharing their ticker. Unpriced tokens are excluded from USD totals.');
 for(const c of chains){out+=`<div class="section-mark">${h(displayName(c.chain))} · #${h(c.chain_id)}</div>`;
 out+=row(`${c.symbol} / NATIVE ASSET`,c.native_status==='verified'?`Block #${c.block||'—'} · balanceOf not used`:'RPC unavailable',`<span class="amount">${h(numText(c.native_balance,12))} ${h(c.symbol)}</span>`,label(c.native_status==='verified'?'RPC CONFIRMED':'UNVERIFIED',c.native_status==='verified'?'low':'warn'));
 const tokens=(c.tokens||[]);for(const t of tokens.slice(0,100)){
 const flagged=t.classification==='review';const prefix=flagged?'TOKEN NEEDS REVIEW':t.contract_recognized?'RECOGNIZED CONTRACT':'TOKEN CONTRACT';
 const href=safeLink(t.explorer_url);
 const desc=[prefix,short(t.contract),t.source||'unknown',...(t.review_reasons||[])].filter(Boolean).join(' · ');
 const details=`<details class="details"><summary>RAW BALANCE / CONTRACT</summary><div class="mono-wrap">${h(t.balance||'—')}</div><div class="mono-wrap">${h(t.contract||'—')}</div>${href?anchor('Explorer',href):''}</details>`;
 out+=row(`${t.symbol||'UNKNOWN'} / ${displayName(c.chain)}`,desc+ (t.usd_value!=null&&t.trusted_usd_eligible?' · '+usdText(t.usd_value):''),`<div class="amount">${h(t.display_balance||numText(t.balance,7))}</div>${details}`,label(flagged?'REVIEW':t.contract_recognized?'RECOGNIZED':'UNVERIFIED',flagged?'warn':'low'));
 }if(!tokens.length)out+=empty('TOKEN INDEX EMPTY / NOT COMPREHENSIVE','An empty token list does not prove the wallet holds no tokens.');if(tokens.length>100)out+=`<p class="micro">Showing the first 100 tokens; see exported JSON for the complete response.</p>`;
 }return out;}
function buildApprovals(chains){let out=heading('PERMISSION CONTROL / APPROVAL EVIDENCE','Allowances and spenders are reported only for discovered and queried pairs.');let found=0;
 for(const c of chains){for(const a of(c.approvals||[])){found++;
 const desc=`${displayName(c.chain)} · Token ${short(a.token_contract)} · Spender ${short(a.spender)} · ${a.reason||a.kind||'permission'}`;
 const url=safeLink(a.evidence?.explorer_url);
 const middle=`<div class="mono-wrap">${h(a.allowance??a.raw_allowance??'UNKNOWN')}</div>${url?anchor('VERIFY EVIDENCE',url):''}`;
 out+=row(a.token_symbol||a.kind||'TOKEN APPROVAL',desc,middle,label(a.unlimited?'UNLIMITED':'ACTIVE IN SAMPLE',a.unlimited?'fail':'warn'));
 }}if(!found)out+=empty('0 APPROVALS DISCOVERED','No active permission was found among the checked candidates. This does not prove that no permissions exist.');
 out+=explainer('CRITICAL /','Zero discovered approvals do not establish zero actual approvals. Historical events, indexers, Permit2 and NFT operator permissions may remain unchecked.');
 for(const c of chains){out+=`<div class="ref-row"><strong>${h(displayName(c.chain))}</strong><span>${h(c.coverage?.approvals_completeness||'UNKNOWN')}</span>${anchor('COMPARE ON REVOKE.CASH',revokeURL(state.report.address, c.chain))}</div>`;}
 return out;}
function buildDelegations(chains){let out=heading('ACCOUNT DELEGATION / EIP-7702','Delegation code is not, by itself, evidence of spyware or a compromised private key.');
 for(const c of chains){const d=c.delegation||{};const known=d.identity_status==='known_documented_address';out+=row(displayName(c.chain),d.status==='eip7702_delegated'?`${d.identity||'Delegate unknown'} · ${d.delegate||'—'}`:d.status==='none_detected'?'No EIP-7702 designation detected in the queried state':d.status||'Unknown',known?anchor('OFFICIAL METAMASK DOCS',d.references?.[0]||''):'',label(d.status==='eip7702_delegated'?(known?'KNOWN ADDRESS':'REVIEW DELEGATE'):d.status==='none_detected'?'NOT DETECTED':'NOT VERIFIED',known?'low':'warn'));}
 out+=explainer('TRUST BOUNDARY /','A documented MetaMask delegate is not evidence of compromise; delegated capabilities have not been fully audited.');return out;}
function buildEvidence(chains){let out=heading('DATA COVERAGE / SOURCE LEDGER','Report only successfully retrieved sources. Coverage can vary by network.');
 for(const c of chains){const q=c.quality||{};const v=c.coverage||{};out+=`<div class="section-mark">${h(displayName(c.chain))} / BLOCK #${h(c.block??'N/A')} ${label(q.status||'UNKNOWN','warn')}</div>`;
 const fields=[['RPC live',v.rpc],['Token indexer',v.token_index],['Tx indexer',v.transactions],['USD quotes',v.usd_prices],['Event logs / ERC-20',v.approval_event_logs?.status],['NFT operators',v.nft_operator_event_logs?.status],['Permit2 events',v.permit2_internal?.status],['Approval completeness',v.approvals_completeness],['Allowance probes completed',v.allowances_checked],['Allowance probe errors',v.allowance_probe_errors?.count]];
 for(const [name,val] of fields)out+=`<div class="evidence-line"><span>${h(name)}</span><code>${h(val??'UNAVAILABLE')}</code></div>`;
 if(q.unresolved?.length)out+=`<details class="details"><summary>SHOW ${q.unresolved.length} UNCOVERED LIMITS</summary><div class="mono-wrap">${q.unresolved.map(v=>`<div>• ${h(v)}</div>`).join('')}</div></details>`;
 }out+=explainer('EVIDENCE POLICY /','A wallet address cannot reveal spyware installed on a device. Complete historical approval coverage has not been established.');return out;}
function renderTab(){if(!state.report)return;const chains=activeChains();let out='';switch(state.view){case'overview':out=buildOverview(chains);break;case'assets':out=buildAssets(chains);break;case'approvals':out=buildApprovals(chains);break;case'revoke':out=window.GuardianRevoke?window.GuardianRevoke.render(state.report,chains):empty('REVOKE MODULE UNAVAILABLE','revoke.js did not load');break;case'delegation':out=buildDelegations(chains);break;default:out=buildEvidence(chains);} $id('tabcontent').innerHTML=out;
 $$('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===state.view)));
}
function refreshBenchmarks(){const el=$id('referenceLinks');el.innerHTML=anchor('DeBank / portfolio',`https://debank.com/profile/${state.report.address}`);
 for(const c of activeChains())el.innerHTML+=anchor(`Revoke.cash / ${displayName(c.chain)}`,revokeURL(state.report.address, c.chain));
}
function render(){if(!state.report)return;const rs=activeChains();refreshSummary();renderTab();refreshBenchmarks();
 $id('auditScope').textContent=rs.map(c=>c.chain.toUpperCase()).join(' + ')||'NO RESULT';
 $id('auditAddress').textContent=state.report.address;
}
function populateResultFilter(){const sel=$id('resultChain');sel.replaceChildren();for(const c of [{key:'all',name:'ALL SCANNED NETWORKS'},...state.report.chains.map(c=>({key:c.chain,name:displayName(c.chain)}))]){const o=document.createElement('option');o.value=c.key;o.textContent=c.name;sel.appendChild(o);}sel.value='all';}
async function scan(event){event.preventDefault();if(window.GUARDIAN_PUBLIC_PREVIEW){announce('LIVE SCAN UNAVAILABLE: This is a static source preview; a reviewed HTTPS API is not deployed.');return;}if(state.busy)return;const address=$id('wallet').value.trim();const chains=supported().filter(c=>chosen.has(c.key)).map(c=>c.key);
 announce('');if(!walletPattern.test(address)){announce('ERROR 0x01: Wallet address must be 0x followed by 40 hexadecimal characters.');return;}if(!chains.length){announce('ERROR 0x02: Select at least one blockchain.');return;}
 state.report=null;$id('report').hidden=true;$id('report').classList.remove('active');state.scanLog=[];
 log('INIT_FORENSIC_READONLY_ENGINE');log('TARGET_VALIDATED');log('SCOPE = '+chains.join(',').toUpperCase());setBusy(true);
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),180000);
 try{const resp=await fetch(API+'/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address,chains}),signal:controller.signal});
  if(!resp.ok)throw new Error(`HTTP ${resp.status}`);
  const data=await resp.json();if(!data||!Array.isArray(data.chains)||data.chains.length!==chains.length||data.chains.some(c=>!chains.includes(c.chain))||!walletPattern.test(data.address||'')||data.address.toLowerCase()!==address.toLowerCase())throw new Error('Backend response mismatch');
  state.report=data;state.view='overview';state.resultChain='all';populateResultFilter();
  for(const c of data.chains){log(`${c.chain.toUpperCase()} RPC ${c.native_status==='verified'?'OK':'UNVERIFIED'}`,c.native_status==='verified'?'ok':'warn');if(c.quality?.status!=='complete')log(`${c.chain.toUpperCase()} DATA COVERAGE INCOMPLETE`,'warn');}
  log('NO SAFETY CLEARANCE / EVIDENCE INCOMPLETE','warn');log('REPORT_READY','ok');
  if(window.GuardianAnalytics)window.GuardianAnalytics.event('scan_complete');
  $id('report').hidden=false;$id('report').classList.add('active');render();$id('report').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){log('SCAN_ERROR '+String(e.message||e),'warn');announce('Scan failed: '+(e.name==='AbortError'?'request timed out':e.message)+' — verify that the backend is running at 127.0.0.1:8000.');}
 finally{clearTimeout(timer);setBusy(false);}}
$id('scanForm').addEventListener('submit',scan);
$id('resultChain').addEventListener('change',e=>{state.resultChain=e.target.value;render();});
$id('tabbar').addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(!b)return;state.view=b.dataset.tab;renderTab();});
$id('scrollTop').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
$id('pasteWallet').addEventListener('click',async()=>{try{const text=(await navigator.clipboard.readText()).trim();if(!walletPattern.test(text)){announce('Clipboard does not contain a valid EVM address.');return;}$id('wallet').value=text;announce('');}catch{announce('Unable to read the clipboard; use Command + V.');}});
$id('exportJSON').addEventListener('click',()=>{if(!state.report)return;const b=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=`guardian360-v2.4.2-${state.report.address.slice(0,10)}-${state.report.chains.map(c=>c.chain).join('-')}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000);});
async function health(){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),['localhost','127.0.0.1'].includes(location.hostname)?6500:90000);try{const r=await fetch(API+'/api/health',{signal:controller.signal});if(!r.ok)throw Error('API HTTP '+r.status);const data=await r.json();if(!data.ok)throw Error('Health failed');state.backendOK=true;$id('apiLed').classList.remove('off');$id('apiStatus').textContent='ENGINE ONLINE';}catch{state.backendOK=false;$id('apiLed').classList.add('off');$id('apiStatus').textContent='ENGINE OFFLINE';}finally{clearTimeout(timer);}}
updateChosen();drawOptions();health();
})();
