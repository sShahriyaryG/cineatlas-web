// A session boundary owns every request and every piece of mounted UI state.
// This is client-side isolation; durable server-side sessions are a separate feature.
export type SessionScope={id:string;token:string;controller:AbortController};
let serial=0;
export function createSession(token:string):SessionScope{
  return {id:`${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${++serial}`,token,controller:new AbortController()};
}
export function replaceSession(current:SessionScope,expected:SessionScope,token:string):SessionScope|null{
  if(current!==expected||current.controller.signal.aborted)return null;
  current.controller.abort();
  return createSession(token);
}
export async function sessionRequest(scope:SessionScope,url:string,options:RequestInit={},onUnauthorized?:()=>void,fetcher:typeof fetch=fetch){
  const own=scope.controller.signal;
  const signal=options.signal?AbortSignal.any([own,options.signal]):own;
  signal.throwIfAborted();
  const headers=new Headers(options.headers);
  if(!headers.has('Content-Type'))headers.set('Content-Type','application/json');
  if(scope.token)headers.set('Authorization',`Bearer ${scope.token}`);
  else headers.delete('Authorization');
  const r=await fetcher(url,{...options,headers,signal,cache:'no-store'});
  signal.throwIfAborted();
  if(r.status===401&&scope.token){onUnauthorized?.();signal.throwIfAborted();}
  if(r.status===204)return null;
  const data=await r.json();
  signal.throwIfAborted();
  if(!r.ok)throw Object.assign(new Error(typeof data?.detail==='string'?data.detail:'Request failed'),{status:r.status});
  return data;
}
// Logout runs separately from the cancelled UI scope, with the captured old token.
export async function revokeSession(url:string,token:string,fetcher:typeof fetch=fetch){
  if(!token)return;
  const r=await fetcher(url,{method:'POST',headers:{Authorization:`Bearer ${token}`},keepalive:true,signal:AbortSignal.timeout(8000),cache:'no-store'});
  if(!r.ok&&r.status!==401)throw new Error('Server sign-out could not be confirmed');
}
