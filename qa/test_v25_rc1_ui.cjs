/* No libraries, no browser, no network: ensure the real UI helper stays precision-safe. */
const fs=require('fs'),assert=require('assert');
const js=fs.readFileSync(require('path').join(__dirname,'../docs/app.js'),'utf8');
const start=js.indexOf('function usdPartial(chains){');
const end=js.indexOf('\nfunction collect(',start);
assert(start>=0&&end>start,'Cannot find production UI summary function');
const usdPartial=new Function(js.slice(start,end)+';return usdPartial;')();
assert.strictEqual(usdPartial([{priced_usd_partial:'7.15'},{priced_usd_partial:'526.702661111459184'}]),'$533.85');
assert.strictEqual(usdPartial([{priced_usd_partial:'526.702661111459184'}]),'$526.70');
assert.strictEqual(usdPartial([{priced_usd_partial:'7.15'}]),'$7.15');
assert.strictEqual(usdPartial([{priced_usd_partial:null}]),'NOT PRICED');
assert.strictEqual(usdPartial([{priced_usd_partial:'0.0000001'}]),'<$0.01');
assert.strictEqual(usdPartial([{priced_usd_partial:'0'}]),'$0.00');
assert.strictEqual(usdPartial([{priced_usd_partial:'0.004'},{priced_usd_partial:'0.004'}]),'$0.01');
assert.strictEqual(usdPartial([{priced_usd_partial:'NaN'}]),'UNVERIFIED');
assert.strictEqual(usdPartial([{priced_usd_partial:'10000000000001'}]),'UNVERIFIED');
assert.strictEqual(usdPartial([{native_usd:'7.15',tokens:[{usd_value:'526.702661111459184',trusted_usd_eligible:true}]}]),'$533.85');
console.log('UI EXACT MULTI-CHAIN PARTIAL USD: 10/10 PASS');
