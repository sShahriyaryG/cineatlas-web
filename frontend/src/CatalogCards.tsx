import {useState,type CSSProperties} from 'react';
import {Star,Film} from 'lucide-react';
import {NavigationLink,type Navigate} from './NavigationLink';
import {moviePath} from './navigation';
import type {Movie} from './catalogTypes';
const colors=['#3154bd','#203d35','#545965','#795347'];
export function Poster({title,src,id,eager=false}:{title:string;src:string;id:number;eager?:boolean}){
  const [failed,setFailed]=useState('');
  return <div className="poster" style={{background:`linear-gradient(150deg,${colors[Math.abs(id)%colors.length]},#202421)`}}>
    <span className="poster-placeholder" aria-hidden="true"><Film size={24}/><span>{title.slice(0,1).toUpperCase()}</span></span>
    {src&&failed!==src&&<img key={src} src={src} loading={eager?'eager':'lazy'} decoding="async" alt="" onError={()=>setFailed(src)}/>}
  </div>;
}
export function MovieCard({movie:m,navigate}:{movie:Movie;navigate:Navigate}){
  return <NavigationLink className="movie-card" href={moviePath(m.id)} navigate={navigate} aria-label={`View ${m.title} (${m.year})`}>
    <Poster title={m.title} src={m.poster_url} id={m.id}/><div className="movie-meta"><div className="movie-title">{m.title}</div><div className="movie-info">{m.year} <span>·</span> {m.genres.slice(0,2).join(' / ')||'Film'}{(m.original_language||m.language||m.spoken_languages?.[0]||m.unspecified_languages?.[0])&&<> <span>·</span> {m.original_language||m.language||m.spoken_languages?.[0]||m.unspecified_languages?.[0]}</>}</div><div className="rating"><Star size={13} fill="currentColor"/>{m.average_rating??'Unrated'} <span>{m.rating_count?`(${m.rating_count})`:''}</span></div></div>
  </NavigationLink>;
}
export function CatalogSkeleton({size=12,style}:{size?:number;style?:CSSProperties}={}){return <div role="status" aria-label="Loading films"><span className="sr-only">Loading films…</span><div className="movie-grid" style={style} aria-hidden="true">{Array.from({length:size},(_,i)=><div key={i} className="skeleton-card"><div className="skeleton poster"/><div className="skeleton skeleton-line"/><div className="skeleton skeleton-line short"/></div>)}</div></div>}
