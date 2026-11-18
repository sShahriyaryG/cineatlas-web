import {Search, Filter, X} from 'lucide-react';
import {useState} from 'react';
import {initialSearch, searchError, filterGroups, type SearchOptions, type FilterOptions, type MatchMode} from './searchOptions';
import type {Result} from './useResource';
export {initialSearch, searchError, searchParams, type SearchOptions} from './searchOptions';
function ClassificationFilter({label,items,selected,mode,onChange,onMode}:{label:string;items:{id:number;name:string}[];selected:number[];mode:MatchMode;onChange:(ids:number[])=>void;onMode:(mode:MatchMode)=>void}){
 const [q,setQ]=useState('');
 const visible=items.filter(x=>x.name.toLowerCase().includes(q.trim().toLowerCase()));
 return <fieldset><legend>{label}</legend><div className="genre-tools"><label className="search-select"><span>Match</span><select value={mode} onChange={e=>onMode(e.target.value as MatchMode)}><option value="and">All selected (AND)</option><option value="or">Any selected (OR)</option></select></label><span>{selected.length} of 20 selected</span></div><input className="vocabulary-search" type="search" aria-label={`Find ${label.toLowerCase()} filter`} placeholder={`Find ${label.toLowerCase()}…`} value={q} onChange={e=>setQ(e.target.value)}/><div className="genre-options">{visible.length?visible.map(x=><label key={x.id}><input type="checkbox" checked={selected.includes(x.id)} disabled={selected.length>=20&&!selected.includes(x.id)} onChange={e=>onChange(e.target.checked?[...selected,x.id]:selected.filter(id=>id!==x.id))}/>{x.name}</label>):<span className="muted">No matching options.</span>}</div></fieldset>;
}
export function SearchFilters({value,options,retryOptions,onChange,expanded,onExpandedChange}:{value:SearchOptions;options:Result<FilterOptions>;retryOptions:()=>void;onChange:(s:SearchOptions)=>void;expanded:boolean;onExpandedChange:(v:boolean)=>void}) {
  const genres=options.status==='ready'?options.data.genres.map(g=>g.name):[];
  const update=(patch:Partial<SearchOptions>)=>onChange({...value,...patch});
  const error=searchError(value);
  const filterCount=value.genres.length+value.languages.length+value.countries.length+value.tags.length+Number(!!(value.yearMin||value.yearMax))+Number(!!(value.ratingMin||value.ratingMax));
  const active=filterCount>0||value.q!==''||value.sort!=='relevance'||value.mode!=='title'||value.genreMode!=='and'||filterGroups.some(g=>value[g.mode]!=='and');
  const hints:Record<string,string>={title:'Search movie titles…',synopsis:'Search plot summaries…',actor:'Search actor names…',director:'Search director names…',all:'Search titles, stories and people…'};
  return <div className="discovery-filters">
    <div className="search-primary">
      <div className="searchbox"><Search size={19}/><input aria-label="Search films" maxLength={200} value={value.q} placeholder={hints[value.mode]} onChange={e=>update({q:e.target.value})}/>{value.q&&<button className="search-clear" type="button" aria-label="Clear search" onClick={()=>update({q:''})}><X size={18}/></button>}</div>
      <label className="search-select"><span>Search in</span><select value={value.mode} onChange={e=>update({mode:e.target.value})}><option value="title">Movie titles</option><option value="synopsis">Synopses</option><option value="actor">Actors</option><option value="director">Directors</option><option value="all">All fields</option></select></label>
      <label className="search-select"><span>Sort by</span><select value={value.sort} onChange={e=>update({sort:e.target.value})}><option value="relevance">Best match</option><option value="title">Title A–Z</option><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="rating">Highest rated</option><option value="most_rated">Most rated</option></select></label>
      <button type="button" className="search-secondary" aria-expanded={expanded} aria-controls="advanced-filters" onClick={()=>onExpandedChange(!expanded)}><Filter size={17}/> Filters{filterCount>0?` (${filterCount})`:''}</button>
      {active&&<button className="search-reset" type="button" onClick={()=>onChange({...initialSearch,genres:[]})}>Reset all</button>}
    </div>
    {expanded&&<div className="advanced-panel" id="advanced-filters">
      <p className="filter-help muted">Different filter groups are combined (AND). Choose All or Any within each group.</p>
      {options.status==='error'&&<p role="alert">Could not load classification filters. <button type="button" onClick={retryOptions}>Retry</button></p>}{options.status==='loading'&&<p role="status">Loading classification filters…</p>}
      <fieldset><legend>Genres</legend><div className="genre-tools"><label className="search-select"><span>Match</span><select value={value.genreMode} onChange={e=>update({genreMode:e.target.value as SearchOptions['genreMode']})}><option value="and">All selected (AND)</option><option value="or">Any selected (OR)</option></select></label><span>{value.genres.length} of 20 selected</span></div><div className="genre-options">{genres.length?genres.map(g=><label key={g}><input type="checkbox" checked={value.genres.includes(g)} disabled={value.genres.length>=20&&!value.genres.includes(g)} onChange={e=>update({genres:e.target.checked?[...value.genres,g]:value.genres.filter(x=>x!==g)})}/>{g}</label>):<span className="muted">No genres available.</span>}</div></fieldset>
      <fieldset><legend>Release year</legend><div className="range-inputs"><label>From<input type="number" min={1888} max={2200} step={1} placeholder="1888" value={value.yearMin} onChange={e=>update({yearMin:e.target.value})}/></label><label>To<input type="number" min={1888} max={2200} step={1} placeholder="2200" value={value.yearMax} onChange={e=>update({yearMax:e.target.value})}/></label></div></fieldset>
      <fieldset><legend>Community rating</legend><div className="range-inputs"><label>Minimum<input type="number" min={1} max={10} step="any" placeholder="1" value={value.ratingMin} onChange={e=>update({ratingMin:e.target.value})}/></label><label>Maximum<input type="number" min={1} max={10} step="any" placeholder="10" value={value.ratingMax} onChange={e=>update({ratingMax:e.target.value})}/></label></div><p className="muted">Rating filters exclude unrated movies.</p></fieldset>
      {options.status==='ready'&&filterGroups.map(g=><ClassificationFilter key={g.key} label={g.label} items={options.data[g.key]} selected={value[g.key]} mode={value[g.mode]} onChange={ids=>update({[g.key]:ids})} onMode={mode=>update({[g.mode]:mode})}/>)}
    </div>}
    {value.genres.length>0&&<div className="active-genres">{value.genres.map(g=><button key={g} type="button" onClick={()=>update({genres:value.genres.filter(x=>x!==g)})} aria-label={`Remove ${g} filter`}>{g}<X size={13}/></button>)}</div>}
    {filterGroups.some(g=>value[g.key].length>0)&&<div className="active-genres">{filterGroups.flatMap(g=>value[g.key].map(id=><button key={`${g.key}-${id}`} type="button" aria-label={`Remove ${g.label} filter: ${options.status==='ready'?options.data[g.key].find(x=>x.id===id)?.name||id:id}`} onClick={()=>update({[g.key]:value[g.key].filter(x=>x!==id)})}>{options.status==='ready'?options.data[g.key].find(x=>x.id===id)?.name||`${g.label} #${id}`:`${g.label} #${id}`}<X size={13}/></button>))}</div>}
    {error&&<p className="error" role="alert">{error}</p>}
  </div>;
}
