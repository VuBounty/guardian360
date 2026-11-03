from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'docs/index.html').read_text()
config=(ROOT/'docs/config.js').read_text()
revoke=(ROOT/'docs/revoke.js').read_text()
assert '<html lang="en">' in html
assert '@SpaceAIFinance. All rights reserved.' in html
assert 'NOT AUDITED' in html
assert 'WALLET SECURITY OPERATIONS / V2.4.2' in html
assert 'GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false' in config
assert 'if(window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS!==true)' in revoke
assert 'GUARDIAN_PUBLIC_PREVIEW' in config
assert 'async function submitTx()' in revoke
for path in ('docs/index.html','docs/app.js','docs/revoke.js','docs/analytics.js','docs/admin.html','docs/readability.js'):
    text=(ROOT/path).read_text()
    # Product UI should not contain Vietnamese script from the earlier release.
    assert not re.search(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐ]',text,re.I),path
assert 'window.GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false' in config
print('ENGLISH RELEASE POLICY / SOURCE GUARDS: PASS')
