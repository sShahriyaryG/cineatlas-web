import {test} from 'node:test';
import assert from 'node:assert/strict';
import {newHistoryEntry,historyState,readHistoryEntry,historyTarget,backAction} from '../src/navigation.ts';
import {createSession,replaceSession,sessionRequest,revokeSession} from '../src/session.ts';

const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r});return {promise,resolve}};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});

test('a directly opened movie has no known predecessor and uses Discover fallback',()=>{
  const entry=newHistoryEntry('guest');
  assert.equal(backAction(entry),'discover');
  assert.equal(readHistoryEntry(null,'guest'),null);
});
test('history follows movie/person/film chain and retains distinct visit keys',()=>{
  const scope='member';const root=newHistoryEntry(scope);const movie=newHistoryEntry(scope,1);const person=newHistoryEntry(scope,2);const revisit=newHistoryEntry(scope,3);
  assert.notEqual(movie.key,revisit.key);
  assert.equal(backAction(person),'back');
  const stack=[['/',root],['/movies/4',movie],['/people/9',person],['/movies/4',revisit]];
  for(const [path,entry] of [...stack].reverse())assert.deepEqual(historyTarget(scope,historyState(entry),path),{path,entry,replace:false});
  assert.equal(backAction(root),'discover');
});
test('history from a different account or unmarked entry returns a fresh public root',()=>{
  const old=historyState(newHistoryEntry('account-a',3));
  for(const invalid of [old,null,{cineatlas:{scope:'account-b',index:-1,key:'account-b:1'}},{cineatlas:{scope:'account-b',index:1,key:'wrong:1'}}]){
    const result=historyTarget('account-b',invalid,'/admin');
    assert.equal(result.path,'/');assert.equal(result.replace,true);assert.equal(result.entry.index,0);assert.equal(result.entry.scope,'account-b');
  }
});
test('changing session invalidates old scope and rejects a late second transition',()=>{
  const a=createSession('a');const b=replaceSession(a,a,'b');
  assert.ok(b);assert.notEqual(a.id,b.id);assert.equal(a.controller.signal.aborted,true);assert.equal(b.controller.signal.aborted,false);
  assert.equal(replaceSession(b,a,'stale'),null);assert.equal(replaceSession(a,a,'stale'),null);
  const guest=replaceSession(b,b,'');assert.ok(guest);assert.equal(guest.token,'');assert.ok(b.controller.signal.aborted);
});
test('a late response from account A is discarded even if transport ignores cancellation',async()=>{
  const a=createSession('a');const pending=deferred();let oldHeaders;
  const result=sessionRequest(a,'https://example.test/me/watchlist',{},undefined,async(_url,init)=>{oldHeaders=init.headers;return pending.promise});
  const b=replaceSession(a,a,'b');assert.ok(b);
  pending.resolve(json([{id:123}]));await assert.rejects(result,{name:'AbortError'});
  assert.equal(oldHeaders.get('X-Session-ID'),'a');
  const data=await sessionRequest(b,'https://example.test/me/watchlist',{},undefined,async(_url,init)=>{assert.equal(init.headers.get('X-Session-ID'),'b');assert.equal(init.cache,'no-store');assert.equal(init.credentials,'include');assert.equal(init.headers.get('Authorization'),null);return json([{id:456}])});
  assert.deepEqual(data,[{id:456}]);
});
test('session change during JSON decoding also discards the old result',async()=>{
  const a=createSession('a');const body=deferred();const entered=deferred();
  const result=sessionRequest(a,'https://example.test/me',{},undefined,async()=>({ok:true,status:200,json:()=>{entered.resolve();return body.promise}}));
  await entered.promise;replaceSession(a,a,'');body.resolve({id:1});await assert.rejects(result,{name:'AbortError'});
});
test('cancelled page or auth submission cannot publish a late result',async()=>{
  const scope=createSession('');const caller=new AbortController();const pending=deferred();let networkSignal;
  const result=sessionRequest(scope,'https://example.test/login',{signal:caller.signal},undefined,async(_url,init)=>{networkSignal=init.signal;return pending.promise});
  caller.abort();pending.resolve(json({token:'late'}));await assert.rejects(result,{name:'AbortError'});
  assert.ok(networkSignal.aborted);assert.equal(scope.controller.signal.aborted,false);
});
test('an aborted scope never starts a new network request',async()=>{
  const a=createSession('a');replaceSession(a,a,'');let calls=0;
  await assert.rejects(sessionRequest(a,'https://example.test/me',{},undefined,async()=>{calls++;return json({})}),{name:'AbortError'});assert.equal(calls,0);
});
test('authenticated 401 invalidates the live boundary; guest login 401 does not',async()=>{
  const a=createSession('a');let next;let called=0;
  await assert.rejects(sessionRequest(a,'https://example.test/me',{},()=>{called++;next=replaceSession(a,a,'')},async()=>json({detail:'Expired'},401)),{name:'AbortError'});
  assert.equal(called,1);assert.equal(next.token,'');
  await assert.rejects(sessionRequest(next,'https://example.test/login',{},()=>{called++},async()=>json({detail:'Invalid credentials'},401)),{message:'Invalid credentials',status:401});assert.equal(called,1);
});
test('stale unauthorized response cannot invalidate the new user',async()=>{
  const a=createSession('a');const pending=deferred();let called=false;
  const result=sessionRequest(a,'https://example.test/me',{},()=>{called=true},async()=>pending.promise);
  const b=replaceSession(a,a,'b');pending.resolve(json({detail:'Expired'},401));await assert.rejects(result,{name:'AbortError'});assert.equal(called,false);assert.ok(!b.controller.signal.aborted);
});
test('local logout can revoke the captured old credential independently of UI abort',async()=>{
  const a=createSession('a');const guest=replaceSession(a,a,'');assert.ok(guest);
  for(const status of [204])await revokeSession('https://example.test/logout',a.token,async(_url,init)=>{assert.equal(init.method,'POST');assert.equal(init.headers['X-Session-ID'],'a');assert.equal(init.signal.aborted,false);return new Response(null,{status})});
  for(const status of [401,503])await assert.rejects(revokeSession('https://example.test/logout',a.token,async()=>new Response(null,{status})),/could not be confirmed/);
});
test('temporary network and server errors do not invalidate a valid session',async()=>{
  const a=createSession('a');let calls=0;const unauthorized=()=>calls++;
  await assert.rejects(sessionRequest(a,'https://example.test/me',{},unauthorized,async()=>json({detail:'Unavailable'},503)),{status:503});
  await assert.rejects(sessionRequest(a,'https://example.test/me',{},unauthorized,async()=>{throw new TypeError('Offline')}),/Offline/);
  assert.equal(calls,0);assert.equal(a.controller.signal.aborted,false);
});
test('a guest session cannot accidentally attach a stale authorization header',async()=>{
  const guest=createSession('');
  await sessionRequest(guest,'https://example.test/movies',{headers:{authorization:'Bearer old','X-Test':'ok'}},undefined,async(_url,init)=>{assert.equal(init.headers.get('Authorization'),null);assert.equal(init.headers.get('X-Test'),'ok');return json({items:[]})});
});

test('browser authentication explicitly includes cookies and never sends bearer credentials',async()=>{
  await sessionRequest(createSession('session-marker'),'https://example.test/me', {headers:{Authorization:'Bearer old'}},undefined,async(_url,init)=>{assert.equal(init.credentials,'include');assert.equal(init.headers.get('Authorization'),null);assert.equal(init.headers.get('X-Session-ID'),'session-marker');return json({id:1})});
});
test('guest request removes caller-supplied session marker',async()=>{
  await sessionRequest(createSession(''),'https://example.test/me',{headers:{'X-Session-ID':'old'}},undefined,async(_url,init)=>{assert.equal(init.headers.get('X-Session-ID'),null);return json({})});
});
