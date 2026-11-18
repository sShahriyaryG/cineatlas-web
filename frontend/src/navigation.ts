export type Category = 'genres'|'countries'|'languages'|'tags';
export type Directory = Category|'people';
export type Route = {kind:'home'|'discover'|'search'|'watchlist'|'ratings'|'recommended'|'editor'|'admin'|'not-found'} | {kind:'movie'|'person';id:number} | {kind:'directory';category:Directory} | {kind:'classification';category:Category;id:number};
export function parseRoute(path:string):Route {
  const clean=path.replace(/\/+$/,'')||'/';
  switch(clean){
    case '/': return {kind:'home'};
    case '/search': return {kind:'search'};
    case '/discover': return {kind:'discover'};
    case '/watchlist': case '/library': return {kind:'watchlist'};
    case '/library/ratings': return {kind:'ratings'};
    case '/for-you': return {kind:'recommended'};
    case '/editor': return {kind:'editor'};
    case '/admin': return {kind:'admin'};
  }
  const directory=/^\/discover\/(people|genres|countries|languages|tags)$/.exec(clean);
  if(directory)return {kind:'directory',category:directory[1] as Directory};
  const classification=/^\/discover\/(genres|countries|languages|tags)\/([1-9]\d*)$/.exec(clean);
  if(classification){const id=Number(classification[2]);if(Number.isSafeInteger(id)&&id<=2147483647)return {kind:'classification',category:classification[1] as Category,id};}
  const match=/^\/(movies|people)\/([1-9]\d*)$/.exec(clean);
  if(match){const id=Number(match[2]);if(Number.isSafeInteger(id)&&id<=2147483647)return {kind:match[1]==='movies'?'movie':'person',id};}
  return {kind:'not-found'};
}
export const moviePath=(id:number)=>`/movies/${id}`;
export const directoryPath=(category:Directory)=>`/discover/${category}`;
export const classificationPath=(category:Category,id:number)=>`/discover/${category}/${id}`;
export const personPath=(id:number)=>`/people/${id}`;

// History entries belong to one in-memory application/session boundary.
// Never store a bearer token or personal data in browser history.
export type HistoryEntry={scope:string;index:number;key:string};
let serial=0;
export function newHistoryEntry(scope:string,index=0):HistoryEntry{
  return {scope,index,key:`${scope}:${++serial}`};
}
export function historyState(entry:HistoryEntry){return {cineatlas:entry};}
export function readHistoryEntry(state:unknown,scope:string):HistoryEntry|null{
  if(!state||typeof state!=='object'||!('cineatlas' in state))return null;
  const e=state.cineatlas;
  if(!e||typeof e!=='object'||!('scope' in e)||!('index' in e)||!('key' in e))return null;
  if(e.scope!==scope||typeof e.index!=='number'||!Number.isSafeInteger(e.index)||e.index<0||typeof e.key!=='string'||!e.key.startsWith(`${scope}:`))return null;
  return {scope,index:e.index,key:e.key};
}
export function historyTarget(scope:string,state:unknown,path:string){
  const entry=readHistoryEntry(state,scope);
  return entry?{path,entry,replace:false}:{path:'/',entry:newHistoryEntry(scope),replace:true};
}
export function backAction(entry:HistoryEntry):'back'|'discover'{return entry.index>0?'back':'discover';}
