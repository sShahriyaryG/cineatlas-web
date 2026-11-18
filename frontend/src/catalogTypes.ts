export type Movie={id:number;title:string;year:number;genres:string[];synopsis:string;poster_url:string;runtime:number|null;language:string;country:string;original_language?:string|null;spoken_languages?:string[];unspecified_languages?:string[];production_countries?:string[];average_rating:number|null;rating_count:number};
export type RatedMovie=Movie & {my_score:number};
export type User={id:number;username:string;role:string;bio:string};
export type Review={id:number;username:string;title:string;body:string;spoiler:boolean;created_at:string};
export type Api=(path:string,options?:RequestInit)=>Promise<any>;
export type PersonCredit={movie_id:number;title:string;year:number;poster_url:string;role:string;character:string};
export type Person={id:number;name:string;biography:string;credits:PersonCredit[]};
export const roleLabel:Record<string,string>={actor:'Actor',director:'Director',writer:'Writer',producer:'Producer',composer:'Composer',cinematographer:'Cinematographer',editor:'Editor',other:'Other crew'};
export function groupFilmography(credits:PersonCredit[]){
  const films=new Map<number,{movie_id:number;title:string;year:number;poster_url:string;credits:PersonCredit[]}>();
  for(const credit of credits){let film=films.get(credit.movie_id);if(!film){film={movie_id:credit.movie_id,title:credit.title,year:credit.year,poster_url:credit.poster_url,credits:[]};films.set(credit.movie_id,film)}film.credits.push(credit)}
  return [...films.values()];
}

export type Classification={id:number;name:string;kind?:'original'|'spoken'|'unspecified'};
export type MovieMetadata={movie_id:number;original_title:string|null;alternative_titles:string[];release_date:string|null;release_status:string|null;trailer_url:string|null;original_language:string|null;spoken_languages:string[];unspecified_languages:string[];production_countries:string[];tags:string[];certifications:{country:string;rating:string}[];soundtracks:{title:string;artist:string;composer:string;external_url:string|null}[];quotes:{quote:string;speaker:string;spoiler:boolean;source_url:string|null}[];classifications:Record<import('./navigation').Category,Classification[]>};
export type PersonMetadata={person_id:number;full_name:string|null;profile_url:string|null;birthday:string|null;deathday:string|null;birthplace:string|null;alternative_names:string[];nationalities:string[]};
export type DirectoryPerson={id:number;name:string;profile_url:string|null;roles:string[];film_count:number};
export type DirectoryClassification=Classification & {film_count:number};
export type Page<T>={items:T[];total:number;page:number;size:number};
