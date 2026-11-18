export type MatchMode='and'|'or';
export type FilterGroup='genres'|'languages'|'countries'|'tags';
export type ModeKey='genreMode'|'languageMode'|'countryMode'|'tagMode';
export const filterGroups=[{key:'genres',ids:'genreIds',label:'Genres',param:'genre',mode:'genreMode'},{key:'languages',ids:'languages',label:'Languages',param:'language',mode:'languageMode'},{key:'countries',ids:'countries',label:'Production countries',param:'country',mode:'countryMode'},{key:'tags',ids:'tags',label:'Tags',param:'tag',mode:'tagMode'}] as const;
export type FilterOptions=Record<FilterGroup,{id:number;name:string}[]>;
export type CreditFilter={id:number;name:string;role:string;exclude:boolean};
export type Certification={country_id:number;country:string;rating:string};
export type SearchOptions = {q:string; mode:string; genres:string[]; genreIds:number[]; genreMode:MatchMode; sort:string; yearMin:string; yearMax:string; ratingMin:string; ratingMax:string;runtimeMin:string;runtimeMax:string;languages:number[];countries:number[];tags:number[];languageMode:MatchMode;countryMode:MatchMode;tagMode:MatchMode;excluded:Record<FilterGroup,number[]>;credits:CreditFilter[];creditMode:MatchMode;certificationCountry:string;certificationRating:string};
export const initialSearch:SearchOptions = {q:'', mode:'title', genres:[],genreIds:[],genreMode:'and', sort:'auto', yearMin:'', yearMax:'', ratingMin:'', ratingMax:'',runtimeMin:'',runtimeMax:'',languages:[],countries:[],tags:[],languageMode:'and',countryMode:'and',tagMode:'and',excluded:{genres:[],languages:[],countries:[],tags:[]},credits:[],creditMode:'and',certificationCountry:'',certificationRating:''};
export function searchError(s:SearchOptions):string {
  const ranges = [[s.yearMin,s.yearMax,1888,2200,'Release year'],[s.ratingMin,s.ratingMax,1,10,'Rating'],[s.runtimeMin,s.runtimeMax,1,10080,'Runtime']] as const;
  for (const [min,max,low,high,label] of ranges) {
    for (const v of [min,max]) if(v!=='' && (!Number.isFinite(Number(v)) || Number(v)<low || Number(v)>high || (label!=='Rating' && !Number.isInteger(Number(v))))) return `${label} must be ${low}–${high}${label!=='Rating'?' (whole numbers)':''}.`;
    if(min!=='' && max!=='' && Number(min)>Number(max)) return `${label}: minimum must not exceed maximum.`;
  }
  return '';
}
export function searchParams(s:SearchOptions,page:number,size=12):URLSearchParams {
  const p=new URLSearchParams({q:s.q,mode:s.mode,genre_mode:s.genreMode,sort:s.sort==='auto'?(s.q.trim()?'relevance':'title'):s.sort,page:String(page),size:String(size)});
  s.genres.forEach(g=>p.append('genres',g));
  for(const group of filterGroups){s[group.ids].forEach(id=>p.append(`${group.param}_ids`,String(id)));s.excluded[group.key].forEach(id=>p.append(`exclude_${group.param}_ids`,String(id)));p.set(`${group.param}_mode`,s[group.mode]);}
  for(const c of s.credits)p.append(c.exclude?'exclude_credit':'credit',`${c.id}:${c.role}`);
  p.set('credit_mode',s.creditMode);
  for(const [k,v] of Object.entries({year_min:s.yearMin,year_max:s.yearMax,rating_min:s.ratingMin,rating_max:s.ratingMax,runtime_min:s.runtimeMin,runtime_max:s.runtimeMax,certification_country:s.certificationCountry,certification_rating:s.certificationRating})) if(v!=='') p.set(k,v);
  return p;
}
export function resetFilters(s:SearchOptions):SearchOptions{return {...initialSearch,q:s.q,sort:s.sort};}
export function setClassification(s:SearchOptions,key:FilterGroup,id:number,choice:'neutral'|'include'|'exclude'):SearchOptions{
 const group=filterGroups.find(g=>g.key===key)!;
 return {...s,[group.ids]:[...s[group.ids].filter(x=>x!==id),...(choice==='include'?[id]:[])],excluded:{...s.excluded,[key]:[...s.excluded[key].filter(x=>x!==id),...(choice==='exclude'?[id]:[])]}};
}

export function hasFilmFilters(s:SearchOptions):boolean{return !!(s.genres.length||filterGroups.some(g=>s[g.ids].length||s.excluded[g.key].length)||s.credits.length||s.yearMin||s.yearMax||s.ratingMin||s.ratingMax||s.runtimeMin||s.runtimeMax||s.certificationCountry);}
