"""Do not leak a paid indexer credential to unrelated data sources or URLs."""
from pathlib import Path
import asyncio,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx,main


def test_routescan_paid_key_only_in_header(monkeypatch):
    monkeypatch.setenv('BLOCKSCOUT_API_KEY','SECRET_NEVER_IN_URL')
    seen=[]
    def handler(req):
        seen.append(req)
        return httpx.Response(200,json={'ok':True})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await main.indexer_get(client,'https://blockscout.routescan.io/56/api/v2','/stats')
            await main.indexer_get(client,'https://eth.blockscout.com/api/v2','/stats')
            await main.indexer_get(client,'https://third-party.example/api/v2','/stats')
    asyncio.run(run())
    assert len(seen)==3
    assert seen[0].headers.get('x-api-key')=='SECRET_NEVER_IN_URL'
    assert all('SECRET_NEVER_IN_URL' not in str(req.url) for req in seen)
    assert all(req.headers.get('x-api-key') is None for req in seen[1:])


def test_routescan_without_key_fails_closed(monkeypatch):
    monkeypatch.delenv('BLOCKSCOUT_API_KEY',raising=False)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200))) as client:
            try:
                await main.indexer_get(client,'https://blockscout.routescan.io/56/api/v2','/stats')
            except RuntimeError as err:
                assert 'paid API key' in str(err)
                return
            assert False,'No credentials: Routescan must not be called'
    asyncio.run(run())


def test_non_routescan_custom_indexer_does_not_receive_secret(monkeypatch):
    monkeypatch.setenv('BLOCKSCOUT_API_KEY','SECRET123')
    seen=[]
    def handler(req):
        seen.append(req)
        return httpx.Response(200,json={'items':[]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await main.indexer_get(client,'https://my-indexer.example/api/v2','/tokens')
    asyncio.run(run())
    assert seen and 'apikey' not in seen[0].url.params
    assert seen[0].headers.get('x-api-key') is None
