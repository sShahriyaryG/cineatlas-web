import type {Route} from './navigation';
export type ShellRole='member'|'editor'|'admin'|string|null;
export type NavItem={label:string;href:string;kind:string;icon:'home'|'explore'|'library'|'recommended'|'editor'|'admin';group:'workspace'|'management'};
export function shellNavigation(role:ShellRole):NavItem[]{
  const items:NavItem[]=[
    ...(role?[{label:'Home',href:'/',kind:'home',icon:'home',group:'workspace'} as const]:[]),
    {label:'Explore',href:'/discover',kind:'discover',icon:'explore',group:'workspace'},
    {label:'My Library',href:'/library',kind:'watchlist',icon:'library',group:'workspace'},
    {label:'For You',href:'/for-you',kind:'recommended',icon:'recommended',group:'workspace'}
  ];
  if(role==='editor'||role==='admin')items.push({label:'Editor Workspace',href:'/editor',kind:'editor',icon:'editor',group:'management'});
  if(role==='admin')items.push({label:'Admin Studio',href:'/admin',kind:'admin',icon:'admin',group:'management'});
  return items;
}
export function shellView(route:Route,authReady:boolean,signedIn:boolean):Route['kind']|'checking-session'{
  if(route.kind!=='home')return route.kind;
  return !authReady?'checking-session':signedIn?'home':'discover';
}
export function isSectionActive(item:NavItem,view:string){return item.kind===view||(item.kind==='discover'&&['directory','classification','movie','person'].includes(view))||(item.kind==='watchlist'&&view==='ratings');}
export type LoadState='loading'|'ready'|'error';
export function visibleCount(state:LoadState, items:readonly unknown[]):number|null{return state==='ready'?items.length:null;}
