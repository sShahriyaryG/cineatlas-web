import {useState} from 'react';
import {Search, Filter, X} from 'lucide-react';
export type SearchOptions = {q:string; mode:string; genres:string[]; genreMode:'and'|'or'; sort:string; yearMin:string; yearMax:string; ratingMin:string; ratingMax:string};
export const initialSearch:SearchOptions = {q:'', mode:'title', genres:[], genreMode:'and', sort:'relevance', yearMin:'', yearMax:'', ratingMin:'', ratingMax:''};
export function searchError(s:SearchOptions):string {
  const ranges = [[s.yearMin,s.yearMax,1888,2200,'Release year'],[s.ratingMin,s.ratingMax,1,10,'Rating']] as const;
  for (const [min,max,low,high,label] of ranges) {
    for (const v of [min,max]) if(v!=='' && (!Number.isFinite(Number(v)) || Number(v)<low || Number(v)>high || (label==='Release year' && !Number.isInteger(Number(v))))) return `${label} must be ${low}–${high}${label==='Release year'?' (whole years)':''}.`;
    if(min!=='' && max!=='' && Number(min)>Number(max)) return `${label}: minimum must not exceed maximum.`;
  }
  return '';
}
export function searchParams(s:SearchOptions,page:number):URLSearchParams {
  const p=new URLSearchParams({q:s.q,mode:s.mode,genre_mode:s.genreMode,sort:s.sort,page:String(page),size:'12'});
  s.genres.forEach(g=>p.append('genres',g));
  for(const [k,v] of Object.entries({year_min:s.yearMin,year_max:s.yearMax,rating_min:s.ratingMin,rating_max:s.ratingMax})) if(v!=='') p.set(k,v);
  return p;
}
export function SearchFilters({value,genres,onChange}:{value:SearchOptions;genres:string[];onChange:(s:SearchOptions)=>void}) {
  const [expanded,setExpanded]=useState(false);
  const update=(patch:Partial<SearchOptions>)=>onChange({...value,...patch});
  const error=searchError(value);
  const filterCount=value.genres.length+Number(!!(value.yearMin||value.yearMax))+Number(!!(value.ratingMin||value.ratingMax));
  const active=filterCount>0||value.q!==''||value.sort!=='relevance'||value.mode!=='title'||value.genreMode!=='and';
  const hints:Record<string,string>={title:'Search movie titles…',synopsis:'Search plot summaries…',actor:'Search actor names…',director:'Search director names…',all:'Search titles, stories and people…'};
  return <div className="discovery-filters">
    <div className="search-primary">
      <div className="searchbox"><Search size={19}/><input aria-label="Search films" maxLength={200} value={value.q} placeholder={hints[value.mode]} onChange={e=>update({q:e.target.value})}/>{value.q&&<button className="search-clear" type="button" aria-label="Clear search" onClick={()=>update({q:''})}><X size={18}/></button>}</div>
      <label className="search-select"><span>Search in</span><select value={value.mode} onChange={e=>update({mode:e.target.value})}><option value="title">Movie titles</option><option value="synopsis">Synopses</option><option value="actor">Actors</option><option value="director">Directors</option><option value="all">All fields</option></select></label>
      <label className="search-select"><span>Sort by</span><select value={value.sort} onChange={e=>update({sort:e.target.value})}><option value="relevance">Best match</option><option value="title">Title A–Z</option><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="rating">Highest rated</option><option value="most_rated">Most rated</option></select></label>
      <button type="button" className="search-secondary" aria-expanded={expanded} aria-controls="advanced-filters" onClick={()=>setExpanded(v=>!v)}><Filter size={17}/> Filters{filterCount>0?` (${filterCount})`:''}</button>
      {active&&<button className="search-reset" type="button" onClick={()=>onChange({...initialSearch,genres:[]})}>Reset all</button>}
    </div>
    {expanded&&<div className="advanced-panel" id="advanced-filters">
      <fieldset><legend>Genres</legend><div className="genre-tools"><label className="search-select"><span>Match</span><select value={value.genreMode} onChange={e=>update({genreMode:e.target.value as SearchOptions['genreMode']})}><option value="and">All selected (AND)</option><option value="or">Any selected (OR)</option></select></label><span>{value.genres.length} of 20 selected</span></div><div className="genre-options">{genres.length?genres.map(g=><label key={g}><input type="checkbox" checked={value.genres.includes(g)} disabled={value.genres.length>=20&&!value.genres.includes(g)} onChange={e=>update({genres:e.target.checked?[...value.genres,g]:value.genres.filter(x=>x!==g)})}/>{g}</label>):<span className="muted">No genres available.</span>}</div></fieldset>
      <fieldset><legend>Release year</legend><div className="range-inputs"><label>From<input type="number" min={1888} max={2200} step={1} placeholder="1888" value={value.yearMin} onChange={e=>update({yearMin:e.target.value})}/></label><label>To<input type="number" min={1888} max={2200} step={1} placeholder="2200" value={value.yearMax} onChange={e=>update({yearMax:e.target.value})}/></label></div></fieldset>
      <fieldset><legend>Community rating</legend><div className="range-inputs"><label>Minimum<input type="number" min={1} max={10} step="any" placeholder="1" value={value.ratingMin} onChange={e=>update({ratingMin:e.target.value})}/></label><label>Maximum<input type="number" min={1} max={10} step="any" placeholder="10" value={value.ratingMax} onChange={e=>update({ratingMax:e.target.value})}/></label></div><p className="muted">Rating filters exclude unrated movies.</p></fieldset>
    </div>}
    {value.genres.length>0&&<div className="active-genres">{value.genres.map(g=><button key={g} type="button" onClick={()=>update({genres:value.genres.filter(x=>x!==g)})} aria-label={`Remove ${g} filter`}>{g}<X size={13}/></button>)}</div>}
    {error&&<p className="error" role="alert">{error}</p>}
  </div>;
}
