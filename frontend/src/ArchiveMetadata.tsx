import {useState,type ReactNode} from 'react';
import {UserRound,ExternalLink} from 'lucide-react';
import {NavigationLink,type Navigate} from './NavigationLink';
import {classificationPath,type Category} from './navigation';
import type {Classification,MovieMetadata,PersonMetadata} from './catalogTypes';
import type {Result} from './useResource';
import {calendarDate,releaseFact,safeExternal} from './archive';

export function Portrait({name,src,eager=false}:{name:string;src?:string|null;eager?:boolean}){
 const [failed,setFailed]=useState<string>();const url=safeExternal(src);
 return <div className="archive-portrait"><div className="portrait-placeholder" aria-hidden="true"><UserRound size={32}/><span>{name.trim().split(/\s+/).slice(0,2).map(n=>n[0]).join('').toUpperCase()}</span></div>{url&&failed!==url&&<img key={url} alt="" src={url} loading={eager?'eager':'lazy'} decoding="async" referrerPolicy="no-referrer" onError={()=>setFailed(url)}/>}</div>;
}
export function ClassificationLinks({category,items,navigate}:{category:Category;items:Classification[];navigate:Navigate}){
 return <>{items.map(item=><NavigationLink className="archive-chip" key={item.id} href={classificationPath(category,item.id)} navigate={navigate}>{item.name}</NavigationLink>)}</>;
}
function Fact({label,children}:{label:string;children:ReactNode}){return <div className="archive-fact"><dt>{label}</dt><dd>{children}</dd></div>}
function External({url,children}:{url:string|null;children:ReactNode}){const href=safeExternal(url);return href?<a className="archive-external" href={href} target="_blank" rel="noopener noreferrer">{children}<ExternalLink size={14} aria-hidden="true"/></a>:null}
export function MetadataStatus({result,retry}:{result:Result<unknown>;retry:()=>void}){
 return result.status==='loading'?<p className="muted" role="status">Loading additional information…</p>:result.status==='error'?<p className="muted" role="alert">Additional information could not be loaded. <button className="text-link" onClick={retry}>Try again</button></p>:null;
}
export function PersonFacts({data:m,name}:{data:PersonMetadata;name:string}){
 return <dl className="archive-facts person-facts">{m.full_name&&m.full_name!==name&&<Fact label="Full name">{m.full_name}</Fact>}{m.birthday&&<Fact label="Born">{calendarDate(m.birthday)}</Fact>}{m.deathday&&<Fact label="Died">{calendarDate(m.deathday)}</Fact>}{m.birthplace&&<Fact label="Birthplace">{m.birthplace}</Fact>}{m.nationalities.length>0&&<Fact label="Nationalities">{m.nationalities.join(' · ')}</Fact>}{m.alternative_names.length>0&&<Fact label="Also known as">{m.alternative_names.join(' · ')}</Fact>}</dl>;
}
export function MovieArchive({data:m,navigate}:{data:MovieMetadata;navigate:Navigate}){
 const release=releaseFact(m.release_date,m.release_status);
 const languageRows=[{label:'Original language',kind:'original',values:m.original_language?[m.original_language]:[]},{label:'Spoken languages',kind:'spoken',values:m.spoken_languages},{label:'Language (unspecified)',kind:'unspecified',values:m.unspecified_languages}];
 const facts=!!(m.original_title||m.alternative_titles.length||release||m.trailer_url||languageRows.some(r=>r.values.length)||m.production_countries.length||m.tags.length||m.certifications.length);
 return <>{facts&&<section className="archive-section"><span className="overline">FROM THE ARCHIVE</span><h2>Film information<span className="accent">.</span></h2><dl className="archive-facts">{m.original_title&&<Fact label="Original title">{m.original_title}</Fact>}{m.alternative_titles.length>0&&<Fact label="Alternative titles">{m.alternative_titles.join(' · ')}</Fact>}{release&&<Fact label={release.label}>{release.value}</Fact>}{languageRows.filter(r=>r.values.length).map(r=>{const links=m.classifications.languages.filter(x=>x.kind===r.kind);return <Fact key={r.kind} label={r.label}>{links.length?<ClassificationLinks category="languages" items={links} navigate={navigate}/>:r.values.join(' · ')}</Fact>})}{m.production_countries.length>0&&<Fact label="Production countries">{m.classifications.countries.length?<ClassificationLinks category="countries" items={m.classifications.countries} navigate={navigate}/>:m.production_countries.join(' · ')}</Fact>}{m.tags.length>0&&<Fact label="Themes and tags"><ClassificationLinks category="tags" items={m.classifications.tags} navigate={navigate}/></Fact>}{safeExternal(m.trailer_url)&&<Fact label="Trailer"><External url={m.trailer_url}>Watch trailer</External></Fact>}</dl>{m.certifications.length>0&&<><h3>Age certifications</h3><ul className="certification-list">{m.certifications.map(c=><li key={`${c.country}:${c.rating}`}><span>{c.country}</span><strong>{c.rating}</strong></li>)}</ul></>}</section>}
 {m.soundtracks.length>0&&<section className="archive-section"><h2>Soundtrack<span className="accent">.</span></h2><ol className="archive-tracks">{m.soundtracks.map((t,i)=><li key={i}><div><strong>{t.title}</strong>{(t.artist||t.composer)&&<p className="muted">{[t.artist,t.composer&&`Composed by ${t.composer}`].filter(Boolean).join(' · ')}</p>}</div><External url={t.external_url}>Listen externally</External></li>)}</ol></section>}
 {m.quotes.length>0&&<section className="archive-section"><h2>Quotations<span className="accent">.</span></h2>{m.quotes.map((q,i)=>{const content=<blockquote><p>{q.quote}</p>{q.speaker&&<cite>— {q.speaker}</cite>}<External url={q.source_url}>Source</External></blockquote>;return q.spoiler?<details className="archive-quote" key={i}><summary>Contains spoilers — reveal quote</summary>{content}</details>:<div className="archive-quote" key={i}>{content}</div>})}</section>}</>;
}
