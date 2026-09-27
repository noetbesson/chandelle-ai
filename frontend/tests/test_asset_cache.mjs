import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

// Exercise the real worker with an obsolete UI cache from an earlier release.
const listeners={},deleted=[],cached=[];
let skipped=false,claimed=false;
const context={URL, console,
  self:{location:{origin:'http://localhost'},addEventListener:(name,fn)=>listeners[name]=fn,
    skipWaiting:async()=>{skipped=true;},clients:{claim:async()=>{claimed=true;}}},
  caches:{open:async()=>({addAll:async assets=>cached.push(...assets)}),
    keys:async()=>['chandelle-public-v1','chandelle-public-v2','chandelle-public-v3','chandelle-public-v4','another-app'],
    delete:async key=>deleted.push(key),match:async()=> 'cached-icon'},
};
const source=await readFile(new URL('../app/sw.js',import.meta.url),'utf8');
vm.runInNewContext(source.replace(/^import .*;\n/,''),context);
let pending;
listeners.install({waitUntil:promise=>pending=promise});await pending;
assert.equal(skipped,true);
assert.deepEqual(cached,['/v2-static/icons/chandelle-192.png','/v2-static/icons/chandelle-512.png']);
listeners.activate({waitUntil:promise=>pending=promise});await pending;
assert.deepEqual(deleted,['chandelle-public-v1','chandelle-public-v2','chandelle-public-v3']);assert.equal(claimed,true);
for(const path of ['/','/app','/v2-static/app.mjs','/v2-static/voice.mjs','/v2-static/style.css','/v2-static/style.css?v=chandelier-1','/api/v2/integrations']){
  let intercepted=false;
  listeners.fetch({request:{method:'GET',url:'http://localhost'+path},respondWith:()=>{intercepted=true;}});
  assert.equal(intercepted,false,`${path} must reach the server, not the worker cache`);
}
listeners.fetch({request:{method:'GET',url:'http://localhost/v2-static/icons/chandelle-192.png'},respondWith:p=>pending=p});
assert.equal(await pending,'cached-icon');
console.log('Asset cache PASS: old UI cache removed, worker activated, HTML/modules/styles/API use network, icons retained.');
