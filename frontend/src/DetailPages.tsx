import {useEffect,useState} from 'react';
import {ArrowLeft,Bookmark,Star,Clock,UserRound,Film,ChevronRight} from 'lucide-react';
import {NavigationLink,type Navigate} from './NavigationLink';
import {moviePath} from './navigation';
import {Poster} from './CatalogCards';
import {MovieCredits} from './MovieCredits';
import {ReviewForm} from './ReviewForm';
import {ReviewReport} from './ReviewReport';
import {groupFilmography,roleLabel,type Api,type Movie,type User,type Review,type Person} from './catalogTypes';

type Result<T>={status:'loading'}|{status:'error';message:string;notFound:boolean}|{status:'ready';data:T};
function useResource<T>(request:Api,path:string,revision=0){
  const [result,setResult]=useState<Result<T>>({status:'loading'});
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let active=true;const controller=new AbortController();setResult({status:'loading'});
    request(path,{signal:controller.signal}).then(data=>{if(active)setResult({status:'ready',data})}).catch(e=>{if(active)setResult({status:'error',message:e instanceof Error?e.message:'Request failed',notFound:e?.status===404})});
    return ()=>{active=false;controller.abort()};
  },[request,path,revision,attempt]);
  return {result,retry:()=>setAttempt(v=>v+1),replace:(data:T)=>setResult({status:'ready',data})};
}
function Back({navigate}:{navigate:Navigate}){return <NavigationLink className="back-link" href="/" navigate={navigate}><ArrowLeft size={17}/> Discover films</NavigationLink>}
export function PageMessage({title,description,navigate,retry}:{title:string;description:string;navigate:Navigate;retry?:()=>void}){return <section className="main-content subpage"><Back navigate={navigate}/><div className="empty" role="status"><Film size={36}/><h1>{title}</h1><p>{description}</p>{retry&&<button className="primary" onClick={retry}>Try again</button>}</div></section>}
function DetailLoading({navigate}:{navigate:Navigate}){return <section className="main-content subpage"><Back navigate={navigate}/><div className="detail-loading" role="status" aria-label="Loading details"><div className="skeleton poster"/><div><div className="skeleton skeleton-line short"/><div className="skeleton skeleton-heading"/><div className="skeleton skeleton-line"/><div className="skeleton skeleton-line"/></div><span className="sr-only">Loading details…</span></div></section>}
export function MoviePage({id,request,navigate,user,saved,watchState,onSignIn,onWatch,onRating,notify}:{id:number;request:Api;navigate:Navigate;user:User|null;saved:boolean;watchState:'loading'|'ready'|'error';onSignIn:()=>void;onWatch:(movie:Movie)=>Promise<void>;onRating:(movie:Movie)=>void;notify:(message:string)=>void}){
  const movie=useResource<Movie>(request,`/movies/${id}`);
  const [busy,setBusy]=useState(false);
  const [score,setScore]=useState('');
  const [watchBusy,setWatchBusy]=useState(false);
  const title=movie.result.status==='ready'?movie.result.data.title:null;
  useEffect(()=>{if(title)document.title=`${title} — CineAtlas`},[title]);
  if(movie.result.status==='loading')return <DetailLoading navigate={navigate}/>;
  if(movie.result.status==='error')return <PageMessage title={movie.result.notFound?'Film not found':'Could not load this film'} description={movie.result.message} navigate={navigate} retry={movie.result.notFound?undefined:movie.retry}/>;
  const m=movie.result.data;
  async function rate(){if(!user){onSignIn();return}if(!score)return;setBusy(true);try{const updated:Movie=await request(`/movies/${id}/rating`,{method:'PUT',body:JSON.stringify({score:Number(score)})});movie.replace(updated);onRating(updated);setScore('');notify('Your rating was saved')}catch(e){notify((e as Error).message)}finally{setBusy(false)}}
  return <article className="movie-page main-content">
    <Back navigate={navigate}/>
    <section className="movie-feature" aria-labelledby="film-heading"><div className="feature-poster"><Poster title={m.title} src={m.poster_url} id={m.id} eager/></div><div className="feature-content">
      <span className="overline">FILM / {m.year}</span><h1 id="film-heading">{m.title}</h1><div className="feature-facts"><span>{m.year}</span>{m.runtime&&<span><Clock size={16}/>{m.runtime} min</span>}{m.language&&<span>{m.language}</span>}{m.country&&<span>{m.country}</span>}</div>
      <div className="genre-tags">{m.genres.map(g=><span key={g}>{g}</span>)}</div>
      <div className="feature-rating"><Star size={24} fill="currentColor"/><strong>{m.average_rating??'Unrated'}{m.average_rating!==null&&<small> / 10</small>}</strong><span>{m.rating_count} {m.rating_count===1?'community rating':'community ratings'}</span></div>
      <h2 className="synopsis-heading">Synopsis</h2><p className="synopsis">{m.synopsis||'No synopsis is available yet.'}</p>
      <div className="feature-actions"><button className={saved?'secondary-button':'primary'} disabled={watchBusy||watchState==='loading'} aria-pressed={saved} onClick={async()=>{setWatchBusy(true);try{await onWatch(m)}finally{setWatchBusy(false)}}}><Bookmark size={18} fill={saved?'currentColor':'none'}/>{watchState==='loading'?'Loading watchlist…':watchState==='error'?'Retry watchlist':saved?'Saved to watchlist':'Add to watchlist'}</button><form className="rate-form" onSubmit={e=>{e.preventDefault();void rate()}}><label className="rating-select">Your rating<select value={score} onChange={e=>setScore(e.target.value)} required><option value="" disabled>1–10</option>{Array.from({length:10},(_,i)=><option key={i+1} value={i+1}>{i+1} / 10</option>)}</select></label><button className="secondary-button" disabled={!score||busy}>{busy?'Saving…':'Rate film'}</button></form></div>
    </div></section>
    <div className="detail-layout"><MovieCredits movieId={id} request={request} navigate={navigate}/><Reviews movieId={id} request={request} user={user} onSignIn={onSignIn} notify={notify}/></div>
  </article>;
}
function Reviews({movieId,request,user,onSignIn,notify}:{movieId:number;request:Api;user:User|null;onSignIn:()=>void;notify:(message:string)=>void}){
  const reviews=useResource<Review[]>(request,`/movies/${movieId}/reviews`);
  const result=reviews.result;
  return <section className="reviews-section" aria-labelledby="reviews-heading"><div className="reviews-header"><h2 id="reviews-heading">Community reviews {result.status==='ready'&&<span>{result.data.length}</span>}</h2></div>
  {user?<ReviewForm key={user.id} onSubmit={async payload=>{await request(`/movies/${movieId}/reviews`,{method:'POST',body:JSON.stringify(payload)});reviews.retry();notify('Review published')}}/>:<div className="review-signin"><p className="muted">Sign in to share your thoughts on this film.</p><button className="secondary-button" onClick={onSignIn}>Sign in</button></div>}
  {result.status==='loading'?<p role="status" className="muted">Loading reviews…</p>:result.status==='error'?<div role="alert" className="muted">Reviews could not be loaded. <button className="text-link" onClick={reviews.retry}>Try again</button></div>:result.data.length===0?<p className="muted">No reviews yet. Start the conversation.</p>:result.data.map(r=><div className="review" key={r.id}><div className="review-top"><strong>{r.username}</strong><span>{new Date(r.created_at).toLocaleDateString()}</span></div><h4>{r.title}</h4>{r.spoiler?<details><summary>Contains spoilers — reveal review</summary><p>{r.body}</p></details>:<p>{r.body}</p>}<ReviewReport key={`${user?.id??'guest'}-${r.id}`} reviewId={r.id} signedIn={!!user} onSignIn={onSignIn} onReport={reason=>request(`/reviews/${r.id}/reports`,{method:'POST',body:JSON.stringify({reason})})}/></div>)}
  </section>;
}
export function PersonPage({id,request,navigate}:{id:number;request:Api;navigate:Navigate}){
  const person=useResource<Person>(request,`/persons/${id}`);
  const title=person.result.status==='ready'?person.result.data.name:null;
  useEffect(()=>{if(title)document.title=`${title} — CineAtlas`},[title]);
  if(person.result.status==='loading')return <DetailLoading navigate={navigate}/>;
  if(person.result.status==='error')return <PageMessage title={person.result.notFound?'Person not found':'Could not load this person'} description={person.result.message} navigate={navigate} retry={person.result.notFound?undefined:person.retry}/>;
  const p=person.result.data;const films=groupFilmography(p.credits);const roles=[...new Set(p.credits.map(c=>roleLabel[c.role]||c.role))];
  return <article className="main-content person-page"><Back navigate={navigate}/><section className="person-feature"><div className="person-avatar" aria-hidden="true"><UserRound size={50}/><span>{p.name.split(/\s+/).slice(0,2).map(n=>n[0]).join('').toUpperCase()}</span></div><div><span className="overline">PEOPLE / CINEATLAS</span><h1>{p.name}</h1><p className="feature-facts">{roles.join(' · ')||'Catalog person'}</p><p className="synopsis">{p.biography||'A biography has not been added to CineAtlas yet.'}</p><span className="muted">{films.length} {films.length===1?'film':'films'} in the CineAtlas catalog</span></div></section>
    <section className="filmography" aria-labelledby="filmography-heading"><div className="section-title"><div><span className="overline">IN OUR COLLECTION</span><h2 id="filmography-heading">Filmography<span className="accent">.</span></h2></div></div><p className="muted">Credits available in CineAtlas, not a complete career history.</p>{films.length? <div className="filmography-list">{films.map(f=><NavigationLink key={f.movie_id} className="filmography-card" href={moviePath(f.movie_id)} navigate={navigate}><Poster title={f.title} src={f.poster_url} id={f.movie_id}/><div><h3>{f.title}</h3><span className="muted">{f.year}</span><ul>{f.credits.map((c,i)=><li key={`${c.role}-${c.character}-${i}`}>{roleLabel[c.role]||c.role}{c.character?` · ${c.character}`:''}</li>)}</ul></div><ChevronRight size={18}/></NavigationLink>)}</div>:<div className="empty"><Film size={30}/><h3>No film credits yet</h3><p>Credits will appear here when added to the catalog.</p></div>}</section>
  </article>;
}
