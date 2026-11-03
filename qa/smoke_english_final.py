"""Deterministic browser QA against mocked RPC/API. No real wallet or network transactions."""
from pathlib import Path
import threading, json, functools, http.server, re
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OWNER='0x'+'11'*20; TOKEN='0x'+'22'*20; SPENDER='0x'+'33'*20
CAL='0x095ea7b3'+SPENDER[2:].rjust(64,'0')+'0'*64
REPORT={
 'address':OWNER,'timestamp':1793701529,'version':'2.4.2-beta','requested_chains':['bsc'],
 'summary':{'audit_quality':'INCOMPLETE','risk_level':'not_assessed','active_approvals_discovered':1},
 'chains':[{'chain':'bsc','name':'BNB Smart Chain','chain_id':56,'native_status':'verified','native_balance':'0.02','symbol':'BNB','native_usd':None,'block':131416513,
 'tokens':[], 'approvals':[{'kind':'erc20_allowance','token_contract':TOKEN,'token_symbol':'QA_TOKEN','spender':SPENDER,'raw_allowance':'42','allowance':'42','unlimited':False,'active':True}],
 'delegation':{'status':'none_detected'}, 'sweeper':{'status':'not_checked'},
 'coverage':{'approvals_completeness':'partial_historical_discovery','rpc':'live_head_checked'},
 'quality':{'status':'incomplete','unresolved':['Indexer unavailable']}}]
}
INTENT={'verified':True,'status':'LIVE_ACTIVE','from':OWNER,'chain':'bsc','chain_id':56,'kind':'erc20','token_contract':TOKEN,'spender':SPENDER,'token_id':None,'to':TOKEN,'data':CAL,'current_permission':'42','read_method':'allowance(address,address)','verified_at':1793701529,'expires_at':4999999999}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def start_server():
    handler=functools.partial(Quiet,directory=str(ROOT/'docs'))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    t=threading.Thread(target=server.serve_forever,daemon=True)
    t.start();return server

def api(route):
    u=route.request.url
    if '/api/scan' in u: data=REPORT
    elif '/api/health' in u:data={'status':'ok'}
    elif '/api/revoke/verify' in u:data=INTENT
    elif '/api/analytics/summary' in u:data={'all_scans_aggregate':4,'opted_in_unique_browsers':1,'consented_visits':2,'returning_browsers_last_14d':1,'history_14d':[]}
    elif '/api/analytics/event' in u:data={'counted':True}
    else:data={'ok':True}
    route.fulfill(status=200,content_type='application/json',headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body=json.dumps(data))

MOCK_WALLET=f'''window.__walletCalls=[];window.ethereum={{isMetaMask:true,request:async({{method}})=>{{window.__walletCalls.push(method);
if(method==='eth_requestAccounts'||method==='eth_accounts')return ['{OWNER}'];
if(method==='eth_chainId')return '0x38';
if(method==='eth_call')return '0x'+(42n).toString(16).padStart(64,'0');
if(method==='eth_estimateGas')return '0x12000';
if(method==='eth_sendTransaction')throw new Error('BUG: transaction send must be disabled in local beta');
throw new Error('unexpected '+method);}}}};'''

def run():
    server=start_server()
    results=[]
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        for width,height in ((1440,900),(390,844),(320,700)):
            page=browser.new_page(viewport={'width':width,'height':height})
            errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
            # Self-contained fetch fixtures; no outgoing HTTP or real blockchain requests.
            html=(ROOT/'docs/index.html').read_text()
            html=re.sub(r'<script[^>]+src="[^"]+"[^>]*></script>','',html)
            html=re.sub(r'<link[^>]+href="styles.css[^"]*"[^>]*>','',html)
            page.set_content(html)
            page.add_style_tag(content=(ROOT/'docs/styles.css').read_text())
            page.add_script_tag(content=MOCK_WALLET)
            page.add_script_tag(content="window.GUARDIAN_API_URL='http://127.0.0.1:8000'; window.GUARDIAN_PUBLIC_PREVIEW=false; window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS=false;")
            page.add_script_tag(content="""window.__mockReports={scan:%s,verify:%s};
              window.fetch = async(url,options={}) => {
                const u=String(url);let payload={ok:true};
                if(u.endsWith('/api/scan')) payload=window.__mockReports.scan;
                else if(u.endsWith('/api/revoke/verify'))payload=window.__mockReports.verify;
                else if(u.endsWith('/api/health'))payload={ok:true};
                else if(u.endsWith('/api/analytics/event'))payload={counted:true};
                return {ok:true,status:200,json:async()=>payload};
              };""" % (json.dumps(REPORT), json.dumps(INTENT)))
            for script in ('app.js','revoke.js','analytics.js','readability.js'):
                page.add_script_tag(content=(ROOT/'docs'/script).read_text())
            page.wait_for_function("document.getElementById('apiStatus').textContent === 'ENGINE ONLINE'")
            assert page.locator('html').get_attribute('lang')=='en'
            assert 'V2.4.2' in page.locator('.brandtag').inner_text()
            assert 'SpaceAIFinance' in page.locator('.footer-copyright').inner_text()
            assert page.locator('#revokeDialog').is_hidden()
            assert page.evaluate('window.__walletCalls.length')==0
            page.fill('#wallet',OWNER)
            page.click('#scanButton')
            page.wait_for_selector('#report:not([hidden])')
            assert page.evaluate('window.__walletCalls.length')==0
            assert 'EVIDENCE-BASED FINDINGS' in page.locator('#stats').inner_text()
            assert 'Incomplete' in page.locator('#stats').inner_text().title()
            page.locator('[data-tab="revoke"]').click()
            page.wait_for_selector('[data-revoke-id="0"]')
            assert 'Wallet disconnected' in page.locator('#tabcontent').inner_text() or 'Backend findings are candidates' in page.locator('#tabcontent').inner_text()
            page.locator('[data-revoke-id="0"]').click()
            assert page.evaluate('window.__walletCalls.length')==0
            page.locator('#revokeNext').click()
            page.wait_for_function("document.querySelector('#revokeDialogStatus').textContent.includes('active permission was verified')")
            assert page.evaluate('window.__walletCalls.length')==0
            page.locator('#revokeNext').click()
            page.wait_for_function("document.querySelector('#revokeDialogStatus').textContent.includes('PREFLIGHT PASS')")
            assert 'eth_requestAccounts' in page.evaluate('window.__walletCalls')
            page.locator('#revokeNext').click()
            page.wait_for_function("document.querySelector('#revokeDialogStatus').textContent.includes('TRANSACTION DISABLED')")
            assert 'eth_sendTransaction' not in page.evaluate('window.__walletCalls')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),f'horizontal overflow at {width}'
            assert not errs,errs
            results.append(f'{width}x{height} English scan/verify/preflight/no-send: PASS')
            page.close()
        # UI for international users using browser translation
        page=browser.new_page()
        html=(ROOT/'docs/index.html').read_text()
        html=re.sub(r'<script[^>]+src="[^"]+"[^>]*></script>','',html)
        html=re.sub(r'<link[^>]+href="styles.css[^"]*"[^>]*>','',html)
        page.set_content(html)
        page.add_script_tag(content=(ROOT/'docs/readability.js').read_text())
        page.click('#translateHelp')
        assert page.locator('#translatePanel').is_visible()
        assert 'browser' in page.locator('#translatePanel').inner_text().lower()
        page.close()
        browser.close()
    finally:server.shutdown();server.server_close()
    for row in results:print(row)
    print('TOTAL UI SMOKE: PASS (3 viewports; mock data only, no on-chain transactions)')

if __name__=='__main__':run()
