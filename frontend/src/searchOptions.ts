export type MatchMode='and'|'or';
export type FilterGroup='languages'|'countries'|'tags';
export type ModeKey='languageMode'|'countryMode'|'tagMode';
export const filterGroups=[{key:'languages',label:'Languages',param:'language',mode:'languageMode'},{key:'countries',label:'Production countries',param:'country',mode:'countryMode'},{key:'tags',label:'Tags',param:'tag',mode:'tagMode'}] as const;
export type FilterOptions=Record<FilterGroup|'genres',{id:number;name:string}[]>;
export type SearchOptions = {q:string; mode:string; genres:string[]; genreMode:'and'|'or'; sort:string; yearMin:string; yearMax:string; ratingMin:string; ratingMax:string;languages:number[];countries:number[];tags:number[];languageMode:MatchMode;countryMode:MatchMode;tagMode:MatchMode};
export const initialSearch:SearchOptions = {q:'', mode:'title', genres:[], genreMode:'and', sort:'relevance', yearMin:'', yearMax:'', ratingMin:'', ratingMax:'',languages:[],countries:[],tags:[],languageMode:'and',countryMode:'and',tagMode:'and'};
export function searchError(s:SearchOptions):string {
  const ranges = [[s.yearMin,s.yearMax,1888,2200,'Release year'],[s.ratingMin,s.ratingMax,1,10,'Rating']] as const;
  for (const [min,max,low,high,label] of ranges) {
    for (const v of [min,max]) if(v!=='' && (!Number.isFinite(Number(v)) || Number(v)<low || Number(v)>high || (label==='Release year' && !Number.isInteger(Number(v))))) return `${label} must be ${low}–${high}${label==='Release year'?' (whole years)':''}.`;
    if(min!=='' && max!=='' && Number(min)>Number(max)) return `${label}: minimum must not exceed maximum.`;
  }
  return '';
}
export function searchParams(s:SearchOptions,page:number,size=12):URLSearchParams {
  const p=new URLSearchParams({q:s.q,mode:s.mode,genre_mode:s.genreMode,sort:s.sort,page:String(page),size:String(size)});
  s.genres.forEach(g=>p.append('genres',g));
  for(const group of filterGroups){s[group.key].forEach(id=>p.append(`${group.param}_ids`,String(id)));p.set(`${group.param}_mode`,s[group.mode]);}
  for(const [k,v] of Object.entries({year_min:s.yearMin,year_max:s.yearMax,rating_min:s.ratingMin,rating_max:s.ratingMax})) if(v!=='') p.set(k,v);
  return p;
}
