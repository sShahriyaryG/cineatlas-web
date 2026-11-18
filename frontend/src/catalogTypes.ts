export type Movie={id:number;title:string;year:number;genres:string[];synopsis:string;poster_url:string;runtime:number|null;language:string;country:string;average_rating:number|null;rating_count:number};
export type RatedMovie=Movie & {my_score:number};
export type User={id:number;username:string;role:string;bio:string};
export type Review={id:number;username:string;title:string;body:string;spoiler:boolean;created_at:string};
export type Api=(path:string,options?:RequestInit)=>Promise<any>;
export type PersonCredit={movie_id:number;title:string;year:number;poster_url:string;role:string;character:string};
export type Person={id:number;name:string;biography:string;credits:PersonCredit[]};
export const roleLabel:Record<string,string>={actor:'Actor',director:'Director',writer:'Writer',producer:'Producer'};
export function groupFilmography(credits:PersonCredit[]){
  const films=new Map<number,{movie_id:number;title:string;year:number;poster_url:string;credits:PersonCredit[]}>();
  for(const credit of credits){let film=films.get(credit.movie_id);if(!film){film={movie_id:credit.movie_id,title:credit.title,year:credit.year,poster_url:credit.poster_url,credits:[]};films.set(credit.movie_id,film)}film.credits.push(credit)}
  return [...films.values()];
}
