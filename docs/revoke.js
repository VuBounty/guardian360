/* Guardian 360 V2.4: opt-in browser-wallet revoke; NO background wallet connections. */
(()=>{'use strict';
const API=(window.GUARDIAN_API_URL||(['localhost','127.0.0.1'].includes(location.hostname)?'http://127.0.0.1:8000':location.origin)).replace(/\/$/,'');
const $=id=>document.getElementById(id);
const addressRE=/^0x[0-9a-fA-F]{40}$/;
const permit2='0x000000000022D473030F116dDEE9F6B43aC78BA3';
const chainNames={bsc:'BNB Smart Chain',ethereum:'Ethereum',base:'Base',arbitrum:'Arbitrum One'};
const chainIds={bsc:56,ethereum:1,base:8453,arbitrum:42161};
const supportedKinds={erc20:'ERC-20 / BEP-20',nft_operator:'NFT operator (721/1155)',nft_token:'ERC-721 single token',permit2:'Permit2 internal allowance'};
const escapeHTML=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short=x=>String(x||'').length>18?String(x).slice(0,10)+'…'+String(x).slice(-8):x;
const lower=x=>String(x||'').toLowerCase();
const word=x=>{if(!addressRE.test(x))throw Error('Invalid address');return x.slice(2).toLowerCase().padStart(64,'0');};
const uintWord=x=>{if(!/^\d+$/.test(String(x)))throw Error('Invalid integer');return BigInt(x).toString(16).padStart(64,'0');};
const decodeBig=x=>{if(!/^0x[0-9a-fA-F]{64,}$/.test(x||''))throw Error('Malformed onchain approval response');return BigInt('0x'+x.slice(2,66));};
const decodeAddr=x=>'0x'+decodeBig(x).toString(16).padStart(40,'0');
const setStatus=(msg,cls='')=>{const el=$('revokeDialogStatus');el.textContent=msg;el.dataset.tone=cls;};
const state={report:null,chains:[],found:[],spec:null,intent:null,provider:null,gas:null,txHash:null,phase:'idle',busy:false};
function setBusy(yes){state.busy=yes;$('revokeNext').disabled=yes;$('revokeCancel').disabled=false;}
function provider(){const list=window.ethereum?.providers||[window.ethereum];const found=list.find(p=>p?.isMetaMask&&typeof p.request==='function');if(!found)throw Error('MetaMask provider not found. Use the official MetaMask browser or extension.');return found;}
async function api(path,payload){const res=await fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let data;try{data=await res.json();}catch{data={};}if(!res.ok)throw Error((typeof data.detail==='string'?data.detail:'API verification unavailable')+` (HTTP ${res.status})`);return data;}
function isSpec(obj){return obj&&addressRE.test(obj.address)&&addressRE.test(obj.token_contract)&&addressRE.test(obj.spender)&&chainNames[obj.chain]&&supportedKinds[obj.kind]&&(obj.kind!=='nft_token'||/^\d+$/.test(String(obj.token_id)));}
function showDialog(spec){if(window.GUARDIAN_PUBLIC_PREVIEW)throw Error('Wallet actions are disabled in public source preview');if(!isSpec(spec))throw Error('Invalid revoke target');state.spec=spec;state.intent=null;state.provider=null;state.gas=null;state.phase='verify';state.txHash=null;const el=$('revokeDialog');el.hidden=false;
 $('revokeDialogInfo').replaceChildren();for(const [title,value] of [['NETWORK',chainNames[spec.chain]],['PERMISSION',supportedKinds[spec.kind]],['TOKEN / COLLECTION',spec.token_contract],['SPENDER / OPERATOR',spec.spender],...(spec.kind==='nft_token'?[['TOKEN ID',spec.token_id]]:[])]){
 const row=document.createElement('div');row.className='revoke-meta';const key=document.createElement('span');key.textContent=title;const val=document.createElement('code');val.textContent=value;row.append(key,val);$('revokeDialogInfo').append(row);}
 $('revokeNext').hidden=false;$('revokeNext').textContent='VERIFY CURRENT ON-CHAIN PERMISSION';setStatus('Wallet disconnected. First, verify the current permission on-chain.');$('revokeNext').focus();document.body.classList.add('dialog-open');}
function close(){if(state.busy)return;$('revokeDialog').hidden=true;document.body.classList.remove('dialog-open');state.spec=null;state.intent=null;state.provider=null;state.phase='idle';}
$('revokeCancel').addEventListener('click',close);
document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&!$('revokeDialog').hidden&&!state.busy)close();});
function mapFound(a,c){if(!a||a.active!==true)return null;const kinds={erc20_allowance:'erc20',nft_operator:'nft_operator',permit2_spender:'permit2'};const kind=kinds[a.kind];if(!kind)return null;return {address:state.report.address,chain:c.chain,kind,token_contract:a.token_contract,spender:a.spender,token_id:null};}
function render(report,chainReports){if(!['localhost','127.0.0.1'].includes(location.hostname))return '<div class="empty-state"><strong>PUBLIC READ-ONLY BETA — REVOKE DISABLED</strong><p>Wallet connection and permission revocation are unavailable on the public site. View approvals and independently verify contracts using a trusted source; do not sign any transaction here.</p></div>';state.report=report;state.chains=chainReports;state.found=[];let rows='';for(const c of chainReports){for(const a of(c.approvals||[])){
 const spec=mapFound(a,c);if(!spec)continue;const id=state.found.push(spec)-1;
 rows+=`<div class="resultrow"><div><b>${escapeHTML(a.token_symbol||a.kind)}</b><small>${escapeHTML(chainNames[c.chain])} · spender ${escapeHTML(short(a.spender))} · ${escapeHTML(a.kind)}</small></div><div class="colmid">${escapeHTML(a.unlimited?'UNLIMITED':a.allowance||a.raw_allowance||'ACTIVE')}</div><div class="right"><button type="button" class="button button-small button-quiet" data-revoke-id="${id}">VERIFY & REVOKE</button></div></div>`;
 }}if(!rows)rows='<div class="empty-state"><strong>NO ACTIVE TARGET IN SCANNED CANDIDATES</strong><p>This does not prove the wallet has no approvals. Supply a contract and spender from Revoke.cash for direct verification.</p></div>';
 const options=chainReports.map(c=>`<option value="${escapeHTML(c.chain)}">${escapeHTML(chainNames[c.chain]||c.chain)}</option>`).join('');
 return `<div class="eyebrow">PROTECTION MODE / DISCONNECTED BY DEFAULT</div>
 <p class="content-desc">Backend findings are candidates only. Recheck the live allowance before action and perform a MetaMask preflight. Signing never occurs on the server.</p>
 <div class="revoke-safety">⚠ Only revoke permissions you understand. Revoking may interrupt DApp functionality; gas is nonrefundable. It cannot restore stolen funds or a compromised private key.</div>
 <div class="section-mark">DISCOVERED PERMISSIONS / REVERIFY BEFORE ACTION</div>${rows}
 <div class="section-mark">MANUAL ON-CHAIN PERMISSION CHECK</div>
 <p class="content-desc">Use this when an indexer misses a permission but you have the contract and spender from an independent source.</p>
 <form id="manualRevokeForm" class="manual-revoke-form" novalidate>
  <label>NETWORK<select name="chain">${options}</select></label>
  <label>PERMISSION TYPE<select name="kind"><option value="erc20">ERC-20 / BEP-20 allowance</option><option value="nft_operator">NFT operator</option><option value="nft_token">ERC-721 token approval</option><option value="permit2">Permit2 internal allowance</option></select></label>
  <label>TOKEN / COLLECTION CONTRACT<input required name="token_contract" placeholder="0x..." spellcheck="false" maxlength="42"></label>
  <label>SPENDER / OPERATOR<input required name="spender" placeholder="0x..." spellcheck="false" maxlength="42"></label>
  <label class="token-id-input" hidden>TOKEN ID (ERC-721 ONLY)<input name="token_id" inputmode="numeric" placeholder="e.g. 1450"></label>
  <button type="submit" class="button button-small button-primary">VERIFY TARGET — NO WALLET CONNECTION</button>
 </form>
 <div class="explain"><strong>IMPORTANT /</strong> EIP-7702 account delegation is NOT an ERC-20 approval and is NOT supported in this revoke panel. Manage it inside your wallet app. Full approval discovery remains incomplete.</div>`;
}
$('tabcontent').addEventListener('click',ev=>{const btn=ev.target.closest('[data-revoke-id]');if(!btn||!state.report)return;const spec=state.found[Number(btn.dataset.revokeId)];try{showDialog(spec);}catch(err){alert(String(err.message||err));}});
$('tabcontent').addEventListener('change',ev=>{if(ev.target.name==='kind'){const input=ev.target.closest('form').querySelector('.token-id-input');input.hidden=ev.target.value!=='nft_token';}});
$('tabcontent').addEventListener('submit',ev=>{if(ev.target.id!=='manualRevokeForm'||!state.report)return;ev.preventDefault();const d=new FormData(ev.target);try{
 const spec={address:state.report.address,chain:d.get('chain'),kind:d.get('kind'),token_contract:String(d.get('token_contract')||'').trim(),spender:String(d.get('spender')||'').trim(),token_id:d.get('kind')==='nft_token'?String(d.get('token_id')||'').trim():null};showDialog(spec);
 }catch(err){alert('Invalid verification target: '+err.message);}});
async function chainAndOwner(p,intent){const accounts=await p.request({method:'eth_accounts'});if(!Array.isArray(accounts)||lower(accounts[0])!==lower(intent.from))throw Error('The MetaMask account does not match the scanned wallet.');const chain=await p.request({method:'eth_chainId'});if(Number(BigInt(chain))!==intent.chain_id)throw Error('Wrong network. Switch to the specified chain before signing.');}
async function recheckPermission(p,intent){const owner=intent.from,token=intent.token_contract,spender=intent.spender;
 const call=async(to,data)=>p.request({method:'eth_call',params:[{to,from:owner,data},'latest']});
 if(intent.kind==='erc20'){
  const out=await call(token,'0xdd62ed3e'+word(owner)+word(spender));if(decodeBig(out)===0n)throw Error('Allowance is already zero. Revocation is unnecessary.');return;
 }
 if(intent.kind==='nft_operator'){
  const out=await call(token,'0xe985e9c5'+word(owner)+word(spender));if(decodeBig(out)!==1n)throw Error('Operator permission is no longer active.');return;
 }
 if(intent.kind==='nft_token'){
  const tid=uintWord(intent.token_id);
  const approved=decodeAddr(await call(token,'0x081812fc'+tid));const ownerNow=decodeAddr(await call(token,'0x6352211e'+tid));
  if(lower(approved)!==lower(spender)||lower(ownerNow)!==lower(owner))throw Error('The ERC-721 approval does not match the current owner and spender.');return;
 }
 if(intent.kind==='permit2'){
  const out=await call(permit2,'0x927da105'+word(owner)+word(token)+word(spender));
  if(!/^0x[0-9a-fA-F]{192,}$/.test(out))throw Error('Permit2 allowance reply invalid');
  const amount=BigInt('0x'+out.slice(2,66)), expiry=BigInt('0x'+out.slice(66,130));
  if(amount===0n||expiry<=BigInt(Math.floor(Date.now()/1000)))throw Error('Permit2 permission has expired or is zero.');return;
 }
 throw Error('Unsupported permission kind');
}
function locallyEncodedIntent(spec){
 const sw=word(spec.spender),tw=word(spec.token_contract);
 if(spec.kind==='erc20')return {to:spec.token_contract,data:'0x095ea7b3'+sw+uintWord(0)};
 if(spec.kind==='nft_operator')return {to:spec.token_contract,data:'0xa22cb465'+sw+uintWord(0)};
 if(spec.kind==='nft_token')return {to:spec.token_contract,data:'0x095ea7b3'+uintWord(0)+uintWord(spec.token_id)};
 if(spec.kind==='permit2')return {to:permit2,data:'0x87517c45'+tw+sw+uintWord(0)+uintWord(0)};
 throw Error('Unsupported permission type');
}
function assertExactCalldata(intent,spec){
 const expected=locallyEncodedIntent(spec);
 if(lower(expected.to)!==lower(intent.to)||lower(expected.data)!==lower(intent.data))
  throw Error('Transaction calldata does NOT match local zero-permission encoder. Refusing wallet transaction.');
}
function matchIntent(a,b){return a&&b&&a.to?.toLowerCase()===b.to?.toLowerCase()&&a.data?.toLowerCase()===b.data?.toLowerCase()&&a.from?.toLowerCase()===b.from?.toLowerCase()&&a.chain_id===b.chain_id&&a.kind===b.kind&&a.spender?.toLowerCase()===b.spender?.toLowerCase();}
async function verify(){setBusy(true);try{setStatus('Verifying the current permission through the backend RPC…');
 const intent=await api('/api/revoke/verify',state.spec);
 if(!intent.verified||intent.status!=='LIVE_ACTIVE'||!addressRE.test(intent.to)||!/^0x[0-9a-fA-F]+$/.test(intent.data)||lower(intent.from)!==lower(state.spec.address)||intent.chain!==state.spec.chain||intent.chain_id!==chainIds[state.spec.chain]||intent.kind!==state.spec.kind||lower(intent.token_contract)!==lower(state.spec.token_contract)||lower(intent.spender)!==lower(state.spec.spender))throw Error('Permission verification mismatch; request refused.');
 assertExactCalldata(intent,state.spec);state.intent=intent;state.phase='preflight';$('revokeNext').textContent='CONNECT METAMASK & SIMULATE';
 $('revokeDialogInfo').insertAdjacentHTML('beforeend',`<div class="revoke-meta"><span>ONCHAIN PERMISSION</span><code>${escapeHTML(intent.current_permission)}</code></div><div class="revoke-meta"><span>CONTRACT TO CALL</span><code>${escapeHTML(intent.to)}</code></div><div class="revoke-meta"><span>SELECTOR</span><code>${escapeHTML(intent.data.slice(0,10))}</code></div>`);
 setStatus('An active permission was verified. No wallet connection or signature yet. The next step requires your explicit MetaMask approval.','ok');
 }catch(err){setStatus('VERIFY FAILED / '+String(err.message||err),'fail');}finally{setBusy(false);}}
async function preflight(){setBusy(true);try{
 const p=provider();setStatus('Requesting MetaMask access and checking the account and chain…');const accounts=await p.request({method:'eth_requestAccounts'});
 if(!Array.isArray(accounts)||lower(accounts[0])!==lower(state.intent.from))throw Error('Wrong MetaMask account. No transaction will be submitted.');
 let ch=Number(BigInt(await p.request({method:'eth_chainId'})));
 if(ch!==state.intent.chain_id){setStatus('Requesting a switch to the required chain…');await p.request({method:'wallet_switchEthereumChain',params:[{chainId:'0x'+state.intent.chain_id.toString(16)}]});}
 await chainAndOwner(p,state.intent);
 // The server's instruction is never trusted blindly: independently reverify intent from server and wallet RPC.
 const second=await api('/api/revoke/verify',state.spec);
 if(!matchIntent(second,state.intent)||Number(Date.now()/1000)>second.expires_at)throw Error('Verification changed or expired; restart.');
 assertExactCalldata(second,state.spec);state.intent=second;await recheckPermission(p,second);
 const tx={from:second.from,to:second.to,data:second.data,value:'0x0'};
 setStatus('Running eth_call and gas estimation (no signing)…');
 await p.request({method:'eth_call',params:[tx,'latest']});
 const gas=await p.request({method:'eth_estimateGas',params:[tx]});
 if(!/^0x[0-9a-fA-F]+$/.test(gas))throw Error('Invalid gas estimate');
 if(BigInt(gas)>2000000n)throw Error('Estimated gas exceeds 2,000,000; stop for manual contract review.');
 state.gas=gas;state.provider=p;state.phase='send';$('revokeNext').textContent='FINAL CONFIRM — OPEN METAMASK';
 setStatus(`PREFLIGHT PASS. Estimated gas limit: ${BigInt(gas).toString()}. This is NOT a complete security simulation. The wallet determines actual gas. Confirm only if the target and estimated fee are correct.`, 'ok');
 }catch(err){state.provider=null;state.phase='preflight';setStatus('PREFLIGHT STOPPED / '+String(err.message||err),'fail');}finally{setBusy(false);}}
async function submitTx(){
 if(window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS!==true){setStatus('TRANSACTION DISABLED — Real-wallet testnet E2E and independent review are still pending. No transaction has been sent.','warn');return;}
 setBusy(true);try{
 const p=state.provider,first=state.intent;
 if(!p||!first)throw Error('Missing user-approved preflight');
 await chainAndOwner(p,first);
 const latest=await api('/api/revoke/verify',state.spec);
 if(!matchIntent(first,latest)||Number(Date.now()/1000)>latest.expires_at)throw Error('Permission verification expired or changed. Restart.');
 assertExactCalldata(latest,state.spec);await recheckPermission(p,latest);
 const tx={from:latest.from,to:latest.to,data:latest.data,value:'0x0'};
 setStatus('MetaMask will now show the transaction confirmation. Review the contract and gas before signing.');
 const hash=await p.request({method:'eth_sendTransaction',params:[tx]});
 if(!/^0x[0-9a-fA-F]{64}$/.test(hash))throw Error('Wallet did not return valid transaction hash');
 state.txHash=hash;state.phase='status';$('revokeNext').textContent='VERIFY TX & CURRENT PERMISSION';
 setStatus(`MetaMask submitted transaction: ${hash}. Not complete until on-chain confirmation and permission recheck.`, 'ok');
 }catch(err){state.phase='preflight';$('revokeNext').textContent='CONNECT METAMASK & SIMULATE';setStatus('TRANSACTION NOT VERIFIED / '+String(err.message||err),'fail');}finally{setBusy(false);}}
async function checkStatus(){setBusy(true);try{
 const out=await api('/api/revoke/status',{...state.spec,tx_hash:state.txHash});
 if(out.status==='VERIFIED_REVOKED'&&out.cleared===true){state.phase='complete';$('revokeNext').hidden=true;setStatus('CONFIRMED ONCHAIN — Permission rechecked and confirmed zero or expired. The previous scan is now stale; run a new scan.', 'ok');}
 else if(out.status==='PENDING')setStatus('Waiting for blockchain confirmation. Check again later.','warn');
 else setStatus('NEEDS ATTENTION — '+out.status+'. Revocation status cannot yet be confirmed.','fail');
 }catch(err){setStatus('Cannot verify receipt: '+err.message,'fail');}finally{setBusy(false);}}
$('revokeNext').addEventListener('click',async()=>{if(state.busy)return;if(state.phase==='verify')return verify();if(state.phase==='preflight')return preflight();if(state.phase==='send')return submitTx();if(state.phase==='status')return checkStatus();});
window.GuardianRevoke={render};
})();
