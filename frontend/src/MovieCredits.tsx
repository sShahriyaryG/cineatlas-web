import {useEffect, useState} from 'react';

type Credit = { id:number; person_id:number; name:string; role:string; character:string };
type Request = (path:string, options?:RequestInit)=>Promise<unknown>;
const groups = [{key:'director',label:'Directed by'},{key:'writer',label:'Written by'}, {key:'actor',label:'Cast'}, {key:'producer',label:'Produced by'}];

export function MovieCredits({movieId,request}:{movieId:number;request:Request}) {
  const [credits,setCredits]=useState<Credit[]>([]);
  const [status,setStatus]=useState<'loading'|'ready'|'error'>('loading');
  useEffect(()=>{
    let active=true;
    setStatus('loading'); setCredits([]);
    request(`/movies/${movieId}/credits`).then(data=>{
      if (!Array.isArray(data)) throw new Error('Invalid credits');
      if(active){setCredits(data as Credit[]);setStatus('ready')}
    }).catch(()=>{if(active)setStatus('error')});
    return ()=>{active=false};
  },[movieId,request]);
  return <section className="film-credits" aria-label="Cast and crew">
    <h3>Cast &amp; crew</h3>
    {status==='loading'&&<p className="muted" role="status">Loading credits…</p>}
    {status==='error'&&<p className="muted">Credits could not be loaded.</p>}
    {status==='ready'&&!credits.length&&<p className="muted">No credits have been added yet.</p>}
    {status==='ready'&&groups.map(group=>{
      const items=credits.filter(c=>c.role===group.key);
      return items.length>0&&<div key={group.key} className="credit-group"><h4>{group.label}</h4><ul>{items.map(c=><li key={c.id}><strong>{c.name}</strong>{c.character&&<span>{c.character}</span>}</li>)}</ul></div>;
    })}
  </section>;
}

export function DataCredits(){
  const [logoMissing,setLogoMissing]=useState(false);
  return <section className="data-credits" aria-label="About and data credits">
    <strong>Data credits</strong>
    <a href="https://www.themoviedb.org" target="_blank" rel="noreferrer">
      {!logoMissing?<img src="/tmdb-logo.svg" alt="TMDB" onError={()=>setLogoMissing(true)}/>: 'TMDB'}
    </a>
    <span>This product uses the TMDB API but is not endorsed or certified by TMDB.</span>
    <a href="https://www.wikidata.org/" target="_blank" rel="noreferrer">Structured data from Wikidata</a>
  </section>;
}
