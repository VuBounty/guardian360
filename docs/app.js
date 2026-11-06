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
const state={report:null,view:'assets',resultChain:'all',busy:false,scanLog:[],backendOK:false,assetFilter:'all',assetQuery:'',assetPageSize:60};
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
 $id('selectedCount').textContent=`(${picks.length} SELECTED)`;$id('optionCount').textContent=`${picks.length}/${supported().length}`;$id('scanButton').disabled=!picks.length||state.busy||!state.backendOK;
 $id('scanHint').textContent=!state.backendOK?'WAITING FOR V2.6 LIVE API':picks.length?`${picks.map(c=>c.key.toUpperCase()).join(' + ')} // READY TO SCAN`:'NO NETWORK SELECTED';
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
// Values supplied by V2.5 RC1 backend are exact decimal strings per scanned network.
// Add as BigInt to avoid JS Number rounding; round ONCE after summing all networks.
function usdPartial(chains){
 const vals=[];
 for(const c of chains){
  if(Object.prototype.hasOwnProperty.call(c,'priced_usd_partial')){
   if(c.priced_usd_partial!=null)vals.push(String(c.priced_usd_partial));
  }else{
   // Backwards compatibility with read-only V2.4.2 reports.
   if(c.native_usd!=null)vals.push(String(c.native_usd));
   for(const t of(c.tokens||[]))if(t.trusted_usd_eligible&&t.usd_value!=null)vals.push(String(t.usd_value));
  }
 }
 if(!vals.length)return 'NOT PRICED';
 if(vals.some(v=>!/^\d+(?:\.\d+)?$/.test(v)||v.length>170))return 'UNVERIFIED';
 const places=Math.max(...vals.map(v=>(v.split('.')[1]||'').length));
 if(places>100)return 'UNVERIFIED';
 const scale=10n**BigInt(places);
 const sum=vals.reduce((acc,v)=>{
  const [w,f='']=v.split('.');return acc+BigInt(w)*scale+BigInt((f+'0'.repeat(places)).slice(0,places)||'0');
 },0n);
 if(sum>10000000000000n*scale)return 'UNVERIFIED';
 const cents=(sum*100n+scale/2n)/scale;
 if(cents===0n&&sum>0n)return '<$0.01';
 const dollars=(cents/100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g,',');
 return '$'+dollars+'.'+(cents%100n).toString().padStart(2,'0');
}
function collect(chains){return {discovered:chains.reduce((n,c)=>n+(c.tokens||[]).length+(c.nft_assets||[]).length+(c.native_status==='verified'&&Number(c.native_balance)>0?1:0),0),suspect:chains.reduce((n,c)=>n+(c.tokens||[]).filter(t=>['suspected_spam','review','not_verified'].includes(assetCategory(t))).length,0),unpriced:chains.reduce((n,c)=>n+(c.tokens||[]).filter(t=>!t.trusted_usd_eligible||t.usd_value==null).length+(c.nft_assets||[]).length,0),approvals:chains.reduce((n,c)=>n+(c.approvals||[]).length,0),unlimited:chains.reduce((n,c)=>n+(c.approvals||[]).filter(a=>a.unlimited).length,0),tokenReview:chains.reduce((n,c)=>n+(c.tokens||[]).filter(t=>t.classification==='review').length,0),sweeper:chains.filter(c=>c.sweeper?.status==='pattern_detected').length,delegations:chains.filter(c=>c.delegation?.status==='eip7702_delegated').length,known:chains.filter(c=>c.delegation?.identity_status==='known_documented_address').length,rpc:chains.filter(c=>c.native_status==='verified').length,coverageIncomplete:chains.some(c=>c.quality?.status!=='complete'||c.coverage?.approvals_completeness!=='complete'),usd:usdPartial(chains)};}
function metric(head,val,sub,tone='amber'){const mark=({green:'▦',blue:'◈',amber:'◉',red:'!'})[tone]||'◉';return `<article class="panel stat tone-${tone}"><div class="stat-top"><span class="heading">${h(head)}</span><span class="stat-symbol" aria-hidden="true">${mark}</span></div><div class="value ${tone}">${h(val)}</div><div class="sub">${h(sub)}</div><span class="stat-line" aria-hidden="true"></span></article>`;}
function refreshSummary(){const chain=activeChains();const s=collect(chain);
 $id('stats').innerHTML=metric('ASSETS DISCOVERED',String(s.discovered),`${s.unpriced} tokens unpriced or excluded · discovery may be incomplete`,'green')+
 metric('PRICED HOLDINGS (PARTIAL)',s.usd,'Trusted prices only · networks in the current view','blue')+
 metric('NEEDS YOUR REVIEW',String(s.suspect),`${s.tokenReview} heuristic flags · review does not mean scam`,'amber')+
 metric('APPROVALS DISCOVERED',String(s.approvals),`${s.unlimited} unlimited · historical discovery is incomplete`,'amber');
 $id('warningStrip').innerHTML=`<strong>SCAN LIMITATIONS</strong><span>${s.approvals===0?'0 approvals found does not prove none exist. ':''}Token and permission discovery depends on paginated indexers, RPC verification and source availability. Suspected spam is shown, not hidden.</span>`;
 const previous=new Set((state.report.requested_chains||state.report.chains.map(c=>c.chain)));const changed=previous.size!==chosen.size||[...chosen].some(k=>!previous.has(k));$id('warningStrip').dataset.stale=changed?'true':'false';
 $id('workspaceDesc').textContent=`${chain.length} networks displayed / ${state.report.chains.length} scanned · ${new Date(state.report.timestamp*1000).toLocaleString('en-GB')}`;
}
function assetCategory(t){if(t.asset_category)return t.asset_category;if(t.possible_spam===true)return 'suspected_spam';if(t.balance_verification&&t.balance_verification!=='verified')return 'not_verified';if(t.classification==='review')return 'review';return t.contract_recognized?'recognized':'unverified_identity';}
function assetRank(t){return ({recognized:0,unverified_identity:1,not_verified:2,review:3,suspected_spam:4})[assetCategory(t)]??3;}
function assetLabel(t){return ({recognized:'IDENTIFIED CONTRACT',unverified_identity:'IDENTITY UNVERIFIED',not_verified:'BALANCE NOT VERIFIED',review:'REVIEW REQUIRED',suspected_spam:'POTENTIAL SPAM'})[assetCategory(t)]||'UNVERIFIED';}
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
function tokenMonogram(symbol){const clean=String(symbol||'?').replace(/[^A-Za-z0-9]/g,'').toUpperCase();return h((clean.slice(0,2)||'?'));}
function assetStatusClass(t){const cat=assetCategory(t);return cat==='suspected_spam'?'review':cat==='review'?'review':cat==='not_verified'?'unknown':cat==='recognized'?'identified':'unknown';}
function assetCard({symbol,name,chain,contract,amount,value,status,statusTone,type='token',details='',block=''}){
 const safeType=['native','token','nft'].includes(type)?type:'token';
 const s=String(symbol||'?');
 const initials=safeType==='native'?'◇':safeType==='nft'?'NFT':tokenMonogram(s);
 const sub=String(name||s);
 const meta=block?`Block ${h(block)} · Native balance`:short(contract||'');
 return `<article class="asset-entry ${safeType} ${h(statusTone)}"><div class="asset-coin ${safeType} ${h(statusTone)}" aria-hidden="true">${initials}</div><div class="asset-identity"><div class="asset-name-row"><strong class="asset-symbol" title="${h(s)}">${h(s)}</strong><span class="asset-type">${safeType==='nft'?'NFT':safeType==='native'?'Native coin':'Token'}</span></div><div class="asset-full-name" title="${h(sub)}">${h(sub)}</div><div class="asset-contract">${h(chain)} <span aria-hidden="true">·</span> ${h(meta||'Contract not supplied')}</div></div><div class="asset-valuation"><strong class="asset-quantity">${h(amount)}</strong><span class="asset-dollar">${h(value)}</span></div><div class="asset-verdict">${label(status,statusTone==='review'?'warn':statusTone==='identified'?'low':statusTone==='unavailable'?'fail':'low')}</div>${details?`<div class="asset-inspect">${details}</div>`:''}</article>`;
}
function coverageBadge(c){const status=String(c.coverage?.inventory_status||'SOURCE_STATUS_UNKNOWN');const unavailable=status==='SOURCE_UNAVAILABLE';return `<span class="coverage-tag ${unavailable?'unavailable':status==='COMPLETE'?'maybe-complete':'limited'}">${h(unavailable?'INDEXER UNAVAILABLE':status==='COMPLETE'?'SOURCE REPORTED COMPLETE':'DISCOVERY LIMITED')}</span>`;}
function buildAssets(chains){
 let all=chains.flatMap(c=>(c.tokens||[]).map(t=>({chain:c.chain,token:t})));
 const nftCount=chains.reduce((n,c)=>n+(c.nft_assets||[]).length,0);
 const nativeCount=chains.filter(c=>c.native_status==='verified'&&Number(c.native_balance)>0).length;
 const counts={all:all.length+nftCount+nativeCount,recognized:nativeCount,review:0,unpriced:nftCount};
 for(const x of all){if(assetCategory(x.token)==='recognized')counts.recognized++;if(['suspected_spam','review','not_verified'].includes(assetCategory(x.token)))counts.review++;if(!x.token.trusted_usd_eligible||x.token.usd_value==null)counts.unpriced++;}
 let out=`<div class="assets-intro"><div><div class="eyebrow content-title">THE ASSET REGISTER</div><h2>Everything discovered. Nothing silently hidden.</h2><p class="content-desc">Native coins, tokens, suspicious airdrops and indexed NFTs appear together. A missing price never removes a token; unknown identity does not imply fraud.</p></div><div class="inventory-total"><span>ASSET RECORDS</span><strong>${h(counts.all)}</strong></div></div>`;
 const limited=chains.filter(c=>['SOURCE_UNAVAILABLE','PARTIAL_SOURCE_COVERAGE'].includes(c.coverage?.inventory_status));
 if(limited.length)out+=`<div class="inventory-notice" role="status"><span aria-hidden="true">ⓘ</span> Some indexers have partial coverage on ${h(limited.map(c=>displayName(c.chain)).join(', '))}. Assets outside indexed history may still be missing.</div>`;
 out+=`<div class="asset-filter"><label for="assetFilter">Asset view</label><select id="assetFilter"><option value="all" ${state.assetFilter==='all'?'selected':''}>ALL ASSETS (${counts.all})</option><option value="recognized" ${state.assetFilter==='recognized'?'selected':''}>IDENTIFIED (${counts.recognized})</option><option value="review" ${state.assetFilter==='review'?'selected':''}>REVIEW / SPAM (${counts.review})</option><option value="unpriced" ${state.assetFilter==='unpriced'?'selected':''}>UNPRICED (${counts.unpriced})</option></select><label for="assetSearch">Search assets</label><div class="asset-search-wrap"><span aria-hidden="true">⌕</span><input id="assetSearch" type="search" value="${h(state.assetQuery)}" placeholder="Token, name or contract · Enter to filter" aria-label="Search discovered assets" /></div></div>`;
 let shown=0,remaining=0;
 for(const c of chains){
   const inv=c.coverage?.inventory_status||'SOURCE_STATUS_UNKNOWN';
   const sourceSummary=(c.coverage?.inventory_sources||[]).map(x=>`${x.name}: ${x.state}`).join(' · ');
   const nativeMatches=!state.assetQuery||[c.symbol,'native',displayName(c.chain)].some(v=>String(v||'').toLowerCase().includes(state.assetQuery.toLowerCase()));
   let tokens=(c.tokens||[]).filter(t=>!state.assetQuery||[t.symbol,t.name,t.contract].some(v=>String(v||'').toLowerCase().includes(state.assetQuery.toLowerCase()))).filter(t=>state.assetFilter==='all'||(state.assetFilter==='recognized'&&assetCategory(t)==='recognized')||(state.assetFilter==='review'&&['suspected_spam','review','not_verified'].includes(assetCategory(t)))||(state.assetFilter==='unpriced'&&(!t.trusted_usd_eligible||t.usd_value==null)));
   tokens.sort((a,b)=>assetRank(a)-assetRank(b)||String(a.symbol||'').localeCompare(String(b.symbol||''))||String(a.contract||'').localeCompare(String(b.contract||'')));
   const nfts=(c.nft_assets||[]).filter(t=>!state.assetQuery||[t.symbol,t.name,t.contract,t.token_id].some(v=>String(v||'').toLowerCase().includes(state.assetQuery.toLowerCase())));
   const showNfts=state.assetFilter==='all'||state.assetFilter==='unpriced';
   const showNative=state.assetFilter==='all'&&nativeMatches&&c.native_status==='verified'&&Number(c.native_balance)>0;
   out+=`<section class="chain-asset-group"><div class="chain-group-head"><div class="chain-title"><span class="chain-pictogram chain-${h(c.chain)}">${h((displayName(c.chain)[0]||'?').toUpperCase())}</span><div><h3>${h(displayName(c.chain))} <small>Chain ${h(c.chain_id)}</small></h3><span class="chain-source-summary" title="${h(sourceSummary)}">${h(sourceSummary||'No indexed source confirmation')}</span></div></div><div class="chain-group-right"><span class="chain-total">${h((c.tokens||[]).length+(c.nft_assets||[]).length+(c.native_status==='verified'&&Number(c.native_balance)>0?1:0))} records</span>${coverageBadge(c)}</div></div>`;
   if(state.assetFilter==='all'&&nativeMatches&&c.native_status!=='verified')out+=`<div class="chain-footnote">Native balance was not verified by RPC. This is an unknown balance, not proof of zero holdings.</div>`;
   if(showNative){shown++;out+=assetCard({symbol:c.symbol,name:`${displayName(c.chain)} / Native asset`,chain:displayName(c.chain),amount:`${numText(c.native_balance,12)} ${c.symbol}`,value:c.native_usd!=null&&Number(c.native_usd)>=0?usdText(c.native_usd):'Unpriced',status:'BALANCE VERIFIED',statusTone:'identified',type:'native',block:c.block});}
   for(const t of tokens.slice(0,state.assetPageSize)){
     shown++;const cat=assetCategory(t),spam=cat==='suspected_spam',tone=assetStatusClass(t);
     const url=safeLink(t.explorer_url);
     const notes=(t.review_reasons||[]).map(x=>`<li>${h(x)}</li>`).join('');
     const details=`<details class="details"><summary>Evidence & contract details</summary><div class="mono-wrap"><div>Full contract: ${h(t.contract||'—')}</div><div>Balance: ${h(t.balance??'UNVERIFIED')}</div><div>Discovered by: ${h((t.discovered_by||[t.source||'unknown']).join(' + '))}</div><div>RPC: ${h(t.balance_verification||'unknown')}</div>${t.provider_balance_conflict?'<div>Indexer balances disagree; live RPC verification takes precedence</div>':''}${url?anchor('View on explorer',url):''}${notes?`<ul>${notes}</ul>`:''}</div></details>`;
     const value=t.trusted_usd_eligible&&t.usd_value!=null?usdText(t.usd_value):'Unpriced / excluded';
     out+=assetCard({symbol:t.symbol||'UNKNOWN',name:t.name||'Unidentified token',chain:displayName(c.chain),contract:t.contract,amount:t.display_balance||numText(t.balance,8),value,status:assetLabel(t),statusTone:tone,type:'token',details});
   }
   remaining+=Math.max(0,tokens.length-state.assetPageSize);
   if(showNfts){for(const nft of nfts.slice(0,state.assetPageSize)){
       const url=safeLink(nft.explorer_url);
       const details=`<details class="details"><summary>Indexed NFT evidence</summary><div class="mono-wrap">Contract: ${h(nft.contract||'—')} · Token #${h(nft.token_id||'—')} · Source: ${h(nft.source||'indexer')}${url?anchor('View on explorer',url):''}</div></details>`;
       shown++;out+=assetCard({symbol:nft.symbol||'NFT',name:nft.name||'Unknown NFT',chain:displayName(c.chain),contract:nft.contract,amount:`${nft.balance||'1'} item(s)`,value:'Unpriced',status:'INDEXER ONLY',statusTone:'unknown',type:'nft',details});
     }remaining+=Math.max(0,nfts.length-state.assetPageSize);}
   if(!showNative&&!tokens.length&&!(showNfts&&nfts.length))out+=empty('NO MATCHING ASSETS','No matches in this filtered view. Source coverage may be incomplete.');
   const assetMeta=c.coverage?.asset_valuation||{};
   if(assetMeta.candidates_not_checked>0)out+=`<div class="chain-footnote">${h(assetMeta.candidates_not_checked)} contract balances await direct RPC verification and remain visible without a trusted USD value.</div>`;
   out+=`</section>`;
 }
 if(remaining)out+=`<div class="asset-paging"><span><strong>${shown} visible</strong> · ${remaining} more indexed assets in this scan</span><button type="button" class="button button-small button-quiet" data-show-more-assets>LOAD NEXT 60 PER CHAIN</button></div>`;
 out+=`<p class="micro asset-disclaimer">Classification is heuristic. A suspicious token is not proven malicious; a recognized contract is not a safety guarantee. Never sign to claim unsolicited assets.</p>`;
 return out;
}
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
function renderTab(){if(!state.report)return;const chains=activeChains();let out='';switch(state.view){case'overview':out=buildOverview(chains);break;case'assets':out=buildAssets(chains);break;case'approvals':out=buildApprovals(chains);break;case'revoke':out=empty('REVOKE DISABLED IN PUBLIC','No wallet connection, transaction signing or broadcast is available in this build. Testnet plans are evaluated separately and never run in the browser.');break;case'delegation':out=buildDelegations(chains);break;default:out=buildEvidence(chains);} $id('tabcontent').innerHTML=out;
 $$('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===state.view)));
}
function refreshBenchmarks(){const el=$id('referenceLinks');el.innerHTML=anchor('DeBank / portfolio',`https://debank.com/profile/${state.report.address}`);
 for(const c of activeChains())el.innerHTML+=anchor(`Revoke.cash / ${displayName(c.chain)}`,revokeURL(state.report.address, c.chain));
}
function renderCoverage(){const el=$id('networkCoverage');if(!el)return;const chains=activeChains();el.innerHTML='<div class="network-strip-title"><span>NETWORK DISCOVERY</span><small>Coverage is not a security score</small></div>'+chains.map(c=>`<button type="button" class="network-mini" data-coverage-chain="${h(c.chain)}" title="View ${h(displayName(c.chain))} assets"><span class="network-mini-icon chain-${h(c.chain)}">${h(displayName(c.chain).slice(0,1))}</span><span><strong>${h(displayName(c.chain))}</strong><small>${h((c.tokens||[]).length)} tokens · ${h((c.nft_assets||[]).length)} NFTs</small></span>${coverageBadge(c)}</button>`).join('');}
function renderSidebar(){ $$('[data-sidebar-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.sidebarTab===state.view));}
function render(){if(!state.report)return;const rs=activeChains();refreshSummary();renderCoverage();renderTab();renderSidebar();refreshBenchmarks();
 $id('auditScope').textContent=rs.map(c=>c.chain.toUpperCase()).join(' + ')||'NO RESULT';
 $id('auditAddress').textContent=state.report.address;
}
function populateResultFilter(){const sel=$id('resultChain');sel.replaceChildren();for(const c of [{key:'all',name:'ALL SCANNED NETWORKS'},...state.report.chains.map(c=>({key:c.chain,name:displayName(c.chain)}))]){const o=document.createElement('option');o.value=c.key;o.textContent=c.name;sel.appendChild(o);}sel.value='all';}
async function scan(event){event.preventDefault();if(window.GUARDIAN_PUBLIC_PREVIEW){announce('LIVE SCAN UNAVAILABLE: the reviewed V2.6 API is not ready.');return;}if(state.busy)return;if(!state.backendOK){announce('LIVE API V2.6 is not ready. No scan was performed.');return;}const address=$id('wallet').value.trim();const chains=supported().filter(c=>chosen.has(c.key)).map(c=>c.key);
 announce('');if(!walletPattern.test(address)){announce('ERROR 0x01: Wallet address must be 0x followed by 40 hexadecimal characters.');return;}if(!chains.length){announce('ERROR 0x02: Select at least one blockchain.');return;}
 state.report=null;$id('report').hidden=true;$id('report').classList.remove('active');state.scanLog=[];
 log('INIT_FORENSIC_READONLY_ENGINE');log('TARGET_VALIDATED');log('SCOPE = '+chains.join(',').toUpperCase());setBusy(true);
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),180000);
 try{const resp=await fetch(API+'/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address,chains}),signal:controller.signal});
  if(!resp.ok){let message='';try{const err=await resp.json();if(typeof err.detail==='string')message=' — '+err.detail.slice(0,150);}catch{}throw new Error(`HTTP ${resp.status}${message}`);}
  const data=await resp.json();if(!data||!Array.isArray(data.chains)||data.chains.length!==chains.length||data.chains.some(c=>!chains.includes(c.chain))||!walletPattern.test(data.address||'')||data.address.toLowerCase()!==address.toLowerCase())throw new Error('Backend response mismatch');
  state.report=data;state.view='assets';state.resultChain='all';state.assetFilter='all';state.assetQuery='';state.assetPageSize=60;populateResultFilter();
  for(const c of data.chains){log(`${c.chain.toUpperCase()} RPC ${c.native_status==='verified'?'OK':'UNVERIFIED'}`,c.native_status==='verified'?'ok':'warn');if(c.quality?.status!=='complete')log(`${c.chain.toUpperCase()} DATA COVERAGE INCOMPLETE`,'warn');}
  log('NO SAFETY CLEARANCE / EVIDENCE INCOMPLETE','warn');log('REPORT_READY','ok');
  if(window.GuardianAnalytics)window.GuardianAnalytics.event('scan_complete');
  $id('report').hidden=false;$id('report').classList.add('active');render();$id('report').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){log('SCAN_ERROR '+String(e.message||e),'warn');announce('Scan failed: '+(e.name==='AbortError'?'request timed out':e.message)+' — verify the selected scan API is online.');}
 finally{clearTimeout(timer);setBusy(false);}}
$id('scanForm').addEventListener('submit',scan);
$id('resultChain').addEventListener('change',e=>{state.resultChain=e.target.value;state.assetPageSize=60;render();});
$id('tabbar').addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(!b)return;state.view=b.dataset.tab;renderTab();renderSidebar();});
$$('[data-sidebar-tab]').forEach(b=>b.addEventListener('click',()=>{if(!state.report){$id('wallet').focus();$id('scanForm').scrollIntoView({behavior:'smooth'});return;}state.view=b.dataset.sidebarTab;renderTab();renderSidebar();$id('report').scrollIntoView({behavior:'smooth',block:'start'});}));
$id('networkCoverage').addEventListener('click',e=>{const b=e.target.closest('[data-coverage-chain]');if(!b||!state.report)return;state.resultChain=b.dataset.coverageChain;$id('resultChain').value=state.resultChain;state.assetPageSize=60;render();});
$id('tabcontent').addEventListener('change',e=>{if(e.target.id==='assetFilter'){state.assetFilter=e.target.value;state.assetPageSize=60;renderTab();}});
let assetSearchDebounce;
$id('tabcontent').addEventListener('input',e=>{if(e.target.id!=='assetSearch')return;
 const value=String(e.target.value||'').trim().slice(0,100);const pos=e.target.selectionStart??value.length;
 clearTimeout(assetSearchDebounce);
 assetSearchDebounce=setTimeout(()=>{if(value===state.assetQuery)return;state.assetQuery=value;state.assetPageSize=60;renderTab();
  const next=$id('assetSearch');if(next){next.focus({preventScroll:true});try{next.setSelectionRange(Math.min(pos,value.length),Math.min(pos,value.length));}catch{}}},180);
});
$id('tabcontent').addEventListener('change',e=>{if(e.target.id==='assetSearch'){clearTimeout(assetSearchDebounce);state.assetQuery=String(e.target.value||'').trim().slice(0,100);state.assetPageSize=60;renderTab();}});
$id('tabcontent').addEventListener('click',e=>{if(e.target.closest('[data-show-more-assets]')){state.assetPageSize+=60;renderTab();}});
$id('scrollTop').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
$id('pasteWallet').addEventListener('click',async()=>{try{const text=(await navigator.clipboard.readText()).trim();if(!walletPattern.test(text)){announce('Clipboard does not contain a valid EVM address.');return;}$id('wallet').value=text;announce('');}catch{announce('Unable to read the clipboard; use Command + V.');}});
$id('exportJSON').addEventListener('click',()=>{if(!state.report)return;const b=new Blob([JSON.stringify(state.report,null,2)],{type:'application/json'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=`guardian360-v2.6-live-readonly-${state.report.address.slice(0,10)}-${state.report.chains.map(c=>c.chain).join('-')}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000);});
async function health(){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),10000);
 state.backendOK=false;updateChosen();
 try{
  const r=await fetch(API+'/api/health',{signal:controller.signal,cache:'no-store'});
  if(!r.ok)throw Error('HTTP '+r.status);
  const data=await r.json();
  if(!data.ok||data.version!==window.GUARDIAN_REQUIRED_API_VERSION||data.scan_enabled!==true||data.revoke_endpoints!==false||data.wallet_signing!==false||!window.GUARDIAN_REQUIRED_RELEASE_ID||data.release_id!==window.GUARDIAN_REQUIRED_RELEASE_ID){
   throw Error('API release mismatch or scan disabled');
  }
  state.backendOK=true;
  $id('apiLed').classList.remove('off');
  $id('apiStatus').textContent='LIVE READ-ONLY API';
  announce('');
 }catch(e){
  state.backendOK=false;
  $id('apiLed').classList.add('off');
  $id('apiStatus').textContent='LIVE API UNAVAILABLE';
  announce('Live scan blocked: V2.6 backend is unavailable or incompatible. Refresh after the backend deployment.');
 }finally{clearTimeout(timer);updateChosen();}
}
updateChosen();drawOptions();health();
})();
