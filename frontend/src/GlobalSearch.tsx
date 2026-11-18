import {useEffect} from 'react';
import {Search} from 'lucide-react';
import {NavigationLink,type Navigate} from './NavigationLink';
import {CatalogPager} from './CatalogPager';
import {useResource} from './useResource';
import {moviePath,personPath,classificationPath,type Category} from './navigation';
import {Portrait} from './ArchiveMetadata';
import {Poster} from './CatalogCards';
import {roleLabel,type Api,type Movie,type DirectoryPerson,type DirectoryClassification,type Page} from './catalogTypes';
const groups=['films','people','genres','countries','languages','tags'] as const;
type Group=typeof groups[number];
type EntityPage=Page<Movie|DirectoryPerson|DirectoryClassification>;
type Preview=Record<Group,EntityPage>;
export type GlobalState={query:string;tab:Group|'all';pages:Partial<Record<Group,number>>};
const labels:Record<Group,string>={films:'Films',people:'People',genres:'Genres',countries:'Countries',languages:'Languages',tags:'Tags'};
function ResultList({group,data,navigate}:{group:Group;data:EntityPage;navigate:Navigate}){
 return <ul className="global-result-list">{data.items.map(item=>{const href=group==='films'?moviePath(item.id):group==='people'?personPath(item.id):classificationPath(group as Category,item.id);const title='title'in item?`${item.title} (${item.year})`:item.name;return <li key={item.id}><NavigationLink href={href} navigate={navigate}><div className="global-result-title">{'title'in item?<Poster title={item.title} src={item.poster_url} id={item.id}/>: 'profile_url'in item?<Portrait name={item.name} src={item.profile_url}/>:null}<div><strong>{title}</strong>{'roles'in item&&<p className="muted">{item.roles.map(r=>roleLabel[r]||r).join(' · ')||'Catalog person'}</p>}</div></div>{'film_count'in item&&<span className="muted">{item.film_count} {item.film_count===1?'film':'films'}</span>}</NavigationLink></li>})}</ul>;
}
function GroupResults({group,query,request,navigate,revision,page,onPage}:{group:Group;query:string;request:Api;navigate:Navigate;revision:number;page:number;onPage:(p:number)=>void}){
 const size=20;const params=new URLSearchParams({q:query.trim(),page:String(page),size:String(size),sort:'relevance'});if(group==='films')params.set('mode','title');
 const endpoint=group==='films'?'/movies':group==='people'?'/directory/people':`/directory/classifications/${group}`;
 const {result,retry}=useResource<EntityPage>(request,`${endpoint}?${params}`,revision,250);
 useEffect(()=>{if(result.status==='ready'){const last=Math.max(1,Math.ceil(result.data.total/size));if(page>last)onPage(last)}},[result,page,onPage]);
 return <section className="global-group"><h2>{labels[group]}{result.status==='ready'&&<span className="muted"> ({result.data.total})</span>}</h2>{result.status==='loading'?<p role="status">Searching…</p>:result.status==='error'?<p role="alert">Could not load {labels[group].toLowerCase()}. <button type="button" onClick={retry}>Retry</button></p>:<>{result.data.items.length===0?<p className="muted">No matches in this category.</p>:<ResultList group={group} data={result.data} navigate={navigate}/>}<CatalogPager page={page} total={result.data.total} size={size} onPage={onPage}/></>}</section>;
}
function AllResults({query,request,navigate,revision,onOpen}:{query:string;request:Api;navigate:Navigate;revision:number;onOpen:(g:Group)=>void}){
 const {result,retry}=useResource<Preview>(request,`/search?${new URLSearchParams({q:query.trim()})}`,revision,250);
 if(result.status==='loading')return <p className="shell-state" role="status">Searching the archive…</p>;
 if(result.status==='error')return <div className="empty" role="alert"><h2>Could not search the archive</h2><p>{result.message}</p><button className="secondary-button" onClick={retry}>Try again</button></div>;
 const matching=groups.filter(g=>result.data[g].total>0);
 if(!matching.length)return <div className="empty"><h2>No matches</h2><p>Try another title, name or classification.</p></div>;
 return <div className="global-results">{matching.map(g=><section key={g} className="global-group"><h2>{labels[g]} <span className="muted">({result.data[g].total})</span></h2><ResultList group={g} data={result.data[g]} navigate={navigate}/>{result.data[g].total>result.data[g].size&&<button type="button" className="secondary-button" onClick={()=>onOpen(g)}>View all {labels[g].toLowerCase()}</button>}</section>)}</div>;
}
export function GlobalSearch({request,navigate,state,onChange,revision}:{request:Api;navigate:Navigate;state:GlobalState;onChange:(state:GlobalState)=>void;revision:number}){
 const {query,tab,pages}=state;const setTab=(tab:GlobalState['tab'])=>onChange({...state,tab});
 return <section className="main-content archive-page"><div className="archive-heading"><span className="overline">THE CINEMA ARCHIVE</span><h1>Search the archive<span className="accent">.</span></h1><p>Find films by title, people by name, and classifications by name. Use Explore to narrow a film collection with filters.</p></div><div className="searchbox global-query"><Search size={19}/><input type="search" aria-label="Search entire archive" maxLength={200} value={query} onChange={e=>onChange({...state,query:e.target.value,pages:{}})} placeholder="Search films, people and classifications…"/></div><nav className="archive-nav global-tabs" aria-label="Search result categories">{(['all',...groups] as const).map(g=><button type="button" key={g} aria-pressed={tab===g} className={`archive-tab ${tab===g?'selected':''}`} onClick={()=>setTab(g)}>{g==='all'?'All':labels[g]}</button>)}</nav>{query.trim()?(tab==='all'?<AllResults query={query} request={request} navigate={navigate} revision={revision} onOpen={g=>onChange({...state,tab:g,pages:{...pages,[g]:1}})}/>:<GroupResults key={tab} group={tab} query={query} request={request} navigate={navigate} revision={revision} page={pages[tab]||1} onPage={p=>onChange({...state,pages:{...pages,[tab]:p}})}/>):<p className="shell-state">Enter a title, name or classification to begin.</p>}</section>;
}
