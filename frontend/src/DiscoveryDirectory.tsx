import {useEffect,useState} from 'react';
import {ArrowLeft,ArrowUpRight,ChevronLeft,ChevronRight,Film,Globe,Languages,Tags,Users,Layers3} from 'lucide-react';
import {NavigationLink,type Navigate} from './NavigationLink';
import {classificationPath,directoryPath,personPath,type Category,type Directory} from './navigation';
import {roleLabel,type Api,type DirectoryPerson,type DirectoryClassification,type Page,type Movie} from './catalogTypes';
import type {BackNavigation} from './useNavigation';
import {useResource,type Result} from './useResource';
import {useGridPaging} from './useGridPaging';
import {pageForOffset} from './gridPaging';
import {SearchFilters} from './SearchFilters';
import {initialSearch,searchError,searchParams,type FilterOptions,type SearchOptions} from './searchOptions';
import {Portrait} from './ArchiveMetadata';
import {MovieCard,CatalogSkeleton} from './CatalogCards';

const sections=[{key:'films',label:'Films',href:'/discover',icon:Film},{key:'people',label:'People',href:directoryPath('people'),icon:Users},{key:'genres',label:'Genres',href:directoryPath('genres'),icon:Layers3},{key:'countries',label:'Countries',href:directoryPath('countries'),icon:Globe},{key:'languages',label:'Languages',href:directoryPath('languages'),icon:Languages},{key:'tags',label:'Tags',href:directoryPath('tags'),icon:Tags}] as const;
export function ArchiveNavigation({active,navigate}:{active:Directory|'films';navigate:Navigate}){
 return <nav className="archive-nav" aria-label="Explore the archive">{sections.map(s=>{const Icon=s.icon;return <NavigationLink key={s.key} className={active===s.key?'archive-tab selected':'archive-tab'} aria-current={active===s.key?'location':undefined} href={s.href} navigate={navigate}><Icon size={17} aria-hidden="true"/>{s.label}</NavigationLink>})}</nav>;
}
const descriptions:Record<Directory,string>={people:'Discover the actors, directors and other professionals behind the films in our collection.',genres:'Explore the cinematic styles represented in our film index.',countries:'Browse films by production country, not filming location.',languages:'Browse films by original, spoken or unspecified catalog language.',tags:'Explore the themes and subjects connecting films in the archive.'};
export type BrowseState={q:string;role:string;offset:number;search?:SearchOptions;expanded?:boolean};
export type BrowseCache=Map<string,BrowseState>;
const initial={q:'',role:'',offset:0};
function useBrowse(cache:BrowseCache,cacheKey:string){
 const [state,setState]=useState<BrowseState>(()=>cache.get(cacheKey)||initial);
 const [draft,setDraft]=useState(state.q);
 function update(next:BrowseState){cache.set(cacheKey,next);setState(next)}
 return {state,draft,setDraft,update};
}
function Pager({page,total,size,onPage}:{page:number;total:number;size:number;onPage:(p:number)=>void}){
 const max=Math.max(1,Math.ceil(total/size));
 return <div className="pagination"><button disabled={page<=1} onClick={()=>onPage(page-1)}><ChevronLeft size={16}/> Previous</button><span>Page {page} of {max}</span><button disabled={page>=max} onClick={()=>onPage(page+1)}>Next <ChevronRight size={16}/></button></div>;
}
function Back({back}:{back:BackNavigation}){return <button className="back-link" onClick={back.goBack}><ArrowLeft size={17}/> {back.hasPrevious?'Back':'Discover films'}</button>}
function LoadError({message,retry}:{message:string;retry:()=>void}){return <div className="empty" role="alert"><h2>Could not load this archive</h2><p>{message}</p><button className="primary" onClick={retry}>Try again</button></div>}
const filmCount=(n:number)=>`${n} ${n===1?'film':'films'}`;
export function DirectoryPage({category,request,navigate,back,cache}:{category:Directory;request:Api;navigate:Navigate;back:BackNavigation;cache:BrowseCache}){
 const {state,draft,setDraft,update}=useBrowse(cache,directoryPath(category));
 const isPeople=category==='people';const grid=useGridPaging(isPeople?'people':'classifications');const page=pageForOffset(state.offset,grid.size);const params=new URLSearchParams({q:state.q,page:String(page),size:String(grid.size)});if(isPeople&&state.role)params.set('role',state.role);
 const endpoint=isPeople?'/directory/people':`/directory/classifications/${category}`;
 const resource=useResource<Page<DirectoryPerson|DirectoryClassification>>(request,`${endpoint}?${params}`);
 const r=resource.result;const section=sections.find(s=>s.key===category)!;
 useEffect(()=>{document.title=`${section.label} — CineAtlas`},[section.label]);
 useEffect(()=>{if(r.status==='ready'){const last=Math.max(1,Math.ceil(r.data.total/grid.size));if(page>last)update({...state,offset:(last-1)*grid.size})}},[r,page,grid.size]);
 return <section className="main-content archive-page" ref={grid.ref}><Back back={back}/><ArchiveNavigation active={category} navigate={navigate}/><div className="archive-heading"><span className="overline">THE CINEMA ARCHIVE / DIRECTORY</span><h1>{section.label}<span className="accent">.</span></h1><p>{descriptions[category]}</p></div>
 <form className="archive-search" onSubmit={e=>{e.preventDefault();update({...state,q:draft.trim(),offset:0})}}><label>Search {section.label.toLowerCase()}<input type="search" maxLength={200} value={draft} onChange={e=>setDraft(e.target.value)} placeholder={isPeople?'Name or alternative name':'Classification name'}/></label>{isPeople&&<label>Credit role<select value={state.role} onChange={e=>update({...state,role:e.target.value,offset:0})}><option value="">All roles</option>{Object.entries(roleLabel).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>}<button className="primary" type="submit">Search</button><button className="secondary-button" type="button" onClick={()=>{setDraft('');update(initial)}}>Clear</button></form>
 {r.status==='loading'?<p role="status" className="shell-state">Loading {section.label.toLowerCase()}…</p>:r.status==='error'?<LoadError message={r.message} retry={resource.retry}/>:<><p className="archive-results" aria-live="polite">{r.data.total} matching {section.label.toLowerCase()}</p>{r.data.items.length===0?<div className="empty"><h2>No results on this page</h2><p>Try a different search or return to the first page.</p><button className="secondary-button" onClick={()=>{setDraft('');update(initial)}}>Reset directory</button></div>:isPeople?<div className="people-grid" style={grid.style}>{(r.data.items as DirectoryPerson[]).map(p=><NavigationLink className="archive-person-card" key={p.id} href={personPath(p.id)} navigate={navigate}><Portrait name={p.name} src={p.profile_url}/><div className="archive-person-copy"><h2>{p.name}</h2><p>{p.roles.map(role=>roleLabel[role]||role).join(' · ')||'Catalog person'}</p><span>{filmCount(p.film_count)}</span></div></NavigationLink>)}</div>:<div className="classification-grid" style={grid.style}>{(r.data.items as DirectoryClassification[]).map(c=><NavigationLink className="classification-card" key={c.id} href={classificationPath(category as Category,c.id)} navigate={navigate}><div><h2>{c.name}</h2><p>{filmCount(c.film_count)}</p></div><ArrowUpRight size={20} aria-hidden="true"/></NavigationLink>)}</div>}<Pager page={page} total={r.data.total} size={grid.size} onPage={p=>update({...state,offset:(p-1)*grid.size})}/></>}
 </section>;
}
export function ClassificationPage({category,id,request,navigate,back,cache,options,retryOptions,revision}:{category:Category;id:number;request:Api;navigate:Navigate;back:BackNavigation;cache:BrowseCache;options:Result<FilterOptions>;retryOptions:()=>void;revision:number}){
 const {state,update}=useBrowse(cache,classificationPath(category,id));
 const grid=useGridPaging('films');const page=pageForOffset(state.offset,grid.size);
 const search=state.search||initialSearch;const error=searchError(search);
 const endpoint=`/directory/classifications/${category}/${id}`;
 const summary=useResource<Page<Movie>&{classification:{id:number;name:string}}>(request,`${endpoint}?size=1`,revision);
 const resource=useResource<Page<Movie>>(request,error?null:`${endpoint}?${searchParams(search,page,grid.size)}`,revision,250);
 const r=resource.result;
 const title=summary.result.status==='ready'?summary.result.data.classification.name:null;
 useEffect(()=>{if(title)document.title=`${title} — CineAtlas`},[title]);
 useEffect(()=>{if(r.status==='ready'){const last=Math.max(1,Math.ceil(r.data.total/grid.size));if(page>last)update({...state,offset:(last-1)*grid.size})}},[r,page,grid.size]);
 return <section className="main-content archive-page" ref={grid.ref}><Back back={back}/><ArchiveNavigation active={category} navigate={navigate}/>
 {summary.result.status==='loading'?<p className="shell-state" role="status">Loading classification…</p>:summary.result.status==='error'?summary.result.notFound?<div className="empty"><h1>Classification not found</h1><NavigationLink className="secondary-button" href={directoryPath(category)} navigate={navigate}>Browse {category}</NavigationLink></div>:<LoadError message={summary.result.message} retry={summary.retry}/>:<>
 <div className="archive-heading"><span className="overline">THE CINEMA ARCHIVE / {category.toUpperCase()}</span><h1>{summary.result.data.classification.name}<span className="accent">.</span></h1><p>{filmCount(summary.result.data.total)} in this classification. Searches and filters stay within it.</p></div>
 <SearchFilters value={search} options={options} retryOptions={retryOptions} onChange={value=>update({...state,search:value,offset:0})} expanded={!!state.expanded} onExpandedChange={expanded=>update({...state,expanded})}/>
 {error?<div className="empty">Adjust the filter ranges to continue.</div>:r.status==='loading'?<CatalogSkeleton size={grid.size} style={grid.style}/>:r.status==='error'?<LoadError message={r.message} retry={resource.retry}/>:<><p className="archive-results" aria-live="polite">{filmCount(r.data.total)} matching</p>{r.data.items.length?<div className="movie-grid" style={grid.style}>{r.data.items.map(m=><MovieCard key={m.id} movie={m} navigate={navigate}/>)}</div>:<div className="empty"><h2>No films found</h2><p>Try another search or reset the filters for this classification.</p><button className="secondary-button" onClick={()=>update({...state,search:initialSearch,offset:0})}>Reset search and filters</button></div>}<Pager page={page} total={r.data.total} size={grid.size} onPage={p=>update({...state,offset:(p-1)*grid.size})}/></>}
 </>}</section>;
}
