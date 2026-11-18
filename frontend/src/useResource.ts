import {useEffect,useState} from 'react';
import type {Api} from './catalogTypes';
export type Result<T>={status:'loading'}|{status:'error';message:string;notFound:boolean}|{status:'ready';data:T};
export function useResource<T>(request:Api,path:string|null,revision=0,delay=0){
  const [attempt,setAttempt]=useState(0);
  const [snapshot,setSnapshot]=useState<{request:Api;path:string|null;revision:number;attempt:number;result:Result<T>}|null>(null);
  const result:Result<T>=snapshot&&snapshot.request===request&&snapshot.path===path&&snapshot.revision===revision&&snapshot.attempt===attempt?snapshot.result:{status:'loading'};
  useEffect(()=>{
    if(path===null)return;
    let active=true;const controller=new AbortController();
    const publish=(result:Result<T>)=>{if(active)setSnapshot({request,path,revision,attempt,result})};
    const load=()=>request(path,{signal:controller.signal}).then(data=>publish({status:'ready',data})).catch(e=>publish({status:'error',message:e instanceof Error?e.message:'Request failed',notFound:e?.status===404}));
    const timer=delay?window.setTimeout(load,delay):undefined;if(timer===undefined)void load();
    return ()=>{active=false;window.clearTimeout(timer);controller.abort()};
  },[request,path,revision,attempt,delay]);
  return {result,retry:()=>setAttempt(v=>v+1),replace:(data:T)=>setSnapshot({request,path,revision,attempt,result:{status:'ready',data}})};
}
