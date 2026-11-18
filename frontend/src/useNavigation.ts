import {useCallback,useLayoutEffect,useRef,useState} from 'react';
import {backAction,historyState,historyTarget,newHistoryEntry,parseRoute,readHistoryEntry,type HistoryEntry} from './navigation';

export type BackNavigation={goBack:()=>void;hasPrevious:boolean};
type Location={path:string;entry:HistoryEntry;restore:boolean};
export function useNavigation(scope:string,signal:AbortSignal){
  const [location,setLocation]=useState<Location>(()=>({path:window.location.pathname,entry:readHistoryEntry(window.history.state,scope)??newHistoryEntry(scope),restore:false}));
  const active=useRef(location);
  const positions=useRef(new Map<string,number>());
  const mainRef=useRef<HTMLElement>(null);
  const rendered=useRef(location.entry.key);
  const commit=useCallback((next:Location)=>{active.current=next;setLocation(next)},[]);
  useLayoutEffect(()=>{
    const old=window.history.scrollRestoration;
    window.history.scrollRestoration='manual';
    if(!readHistoryEntry(window.history.state,scope))window.history.replaceState(historyState(active.current.entry),'',active.current.path+window.location.search+window.location.hash);
    const pop=(event:PopStateEvent)=>{
      if(signal.aborted)return;
      positions.current.set(active.current.entry.key,window.scrollY);
      const next=historyTarget(scope,event.state,window.location.pathname);
      if(next.replace)window.history.replaceState(historyState(next.entry),'','/');
      commit({path:next.path,entry:next.entry,restore:!next.replace});
    };
    window.addEventListener('popstate',pop);
    return()=>{window.removeEventListener('popstate',pop);window.history.scrollRestoration=old};
  },[scope,signal,commit]);
  const navigate=useCallback((path:string)=>{
    if(signal.aborted||path===active.current.path)return;
    positions.current.set(active.current.entry.key,window.scrollY);
    const entry=newHistoryEntry(scope,active.current.entry.index+1);
    window.history.pushState(historyState(entry),'',path);
    commit({path,entry,restore:false});
  },[scope,signal,commit]);
  const goBack=useCallback(()=>{
    if(signal.aborted)return;
    if(backAction(active.current.entry)==='back'){window.history.back();return;}
    // A direct link has no known in-app predecessor. Never send the user off-site.
    if(active.current.path==='/')return;
    const entry=newHistoryEntry(scope);
    window.history.replaceState(historyState(entry),'','/');
    commit({path:'/',entry,restore:false});
  },[scope,signal,commit]);
  useLayoutEffect(()=>{
    const titles:Record<string,string>={discover:'Discover',watchlist:'My watchlist',recommended:'For you',admin:'Admin Studio',editor:'Editor Workspace',movie:'Movie',person:'Person','not-found':'Page not found'};
    document.title=`${titles[parseRoute(location.path).kind]} — CineAtlas`;
    if(rendered.current===location.entry.key)return;
    rendered.current=location.entry.key;
    mainRef.current?.focus({preventScroll:true});
    window.scrollTo(0,location.restore?(positions.current.get(location.entry.key)??0):0);
  },[location]);
  return {path:location.path,mainRef,navigate,back:{goBack,hasPrevious:backAction(location.entry)==='back'} satisfies BackNavigation};
}
