import {useEffect, useState, type FormEvent} from 'react';
import {Check, ClipboardCheck, Film, Pencil, Plus, ShieldCheck, Trash2, Users, X} from 'lucide-react';

type Api = (path: string, options?: RequestInit) => Promise<any>;
type Movie = {id: number; title: string; year: number; genres: string[]; synopsis: string; poster_url: string; runtime: number | null; language: string; country: string};
type FormFields = {title: string; year: string; genres: string; synopsis: string; poster_url: string; runtime: string; language: string; country: string};
type Suggestion = {id: number; movie_id: number; movie_title?: string; current_synopsis?: string; submitted_by?: string; synopsis: string; reason: string; status: string};
type Report = {id: number; review_id: number; review_title?: string; review_body?: string; movie_title?: string; reported_by?: string; reason: string; status: string};
type UserEntry = {id: number; username: string; email: string; role: string; is_active: boolean};
const emptyForm: FormFields = {title: '', year: String(new Date().getFullYear()), genres: 'Drama', synopsis: '', poster_url: '', runtime: '', language: '', country: ''};
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong';

export function AdminStudio({request, onCatalogChange}: {request: Api; onCatalogChange: () => void}) {
  const [tab, setTab] = useState<'movies'|'suggestions'|'reports'|'users'>('movies');
  const [items, setItems] = useState<Movie[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<number | 'new' | null>(null);
  const [form, setForm] = useState<FormFields>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [users, setUsers] = useState<UserEntry[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [busyId, setBusyId] = useState('');

  useEffect(() => {
    let valid = true;
    const params = new URLSearchParams({q, page: String(page), size: '20'});
    request('/movies?' + params).then(data => {if (valid) {setItems(data.items);setTotal(data.total);}}).catch(e => {if (valid) setError(messageOf(e));});
    return () => {valid = false;};
  }, [q, page, revision, request]);
  useEffect(() => {
    let valid = true;
    Promise.all([request('/admin/stats'),request('/admin/suggestions'),request('/admin/reports'),request('/admin/users')])
      .then(([s, edits, flags, people]) => {if(valid){setStats(s);setSuggestions(edits);setReports(flags);setUsers(people);}})
      .catch(e=>{if(valid)setError(messageOf(e));});
    return () => {valid = false;};
  }, [revision, request]);
  const refresh = (catalog = false) => {setRevision(v=>v+1); if(catalog) onCatalogChange();};
  const startNew = () => {setEditing('new');setForm({...emptyForm});setError('');setNotice('');};
  const edit = (m: Movie) => {
    setEditing(m.id);
    setForm({title:m.title,year:String(m.year),genres:m.genres.join(', '),synopsis:m.synopsis,poster_url:m.poster_url,runtime:m.runtime===null?'':String(m.runtime),language:m.language,country:m.country});
    setError('');setNotice('');
  };
  const update = (field: keyof FormFields, value: string) => setForm(f=>({...f,[field]:value}));
  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();setError('');setNotice('');setSaving(true);
    const isNew = editing==='new';
    const payload = {title:form.title.trim(),year:Number(form.year),genres:form.genres.trim(),synopsis:form.synopsis.trim(),poster_url:form.poster_url.trim(),runtime:form.runtime?Number(form.runtime):null,language:form.language.trim(),country:form.country.trim()};
    try {
      await request(isNew?'/movies':`/movies/${editing}`,{method:isNew?'POST':'PUT',body:JSON.stringify(payload)});
      setEditing(null);setNotice(isNew?'Film created successfully':'Film updated successfully');setPage(1);setQ('');refresh(true);
    } catch(e) {setError(messageOf(e));} finally {setSaving(false);}
  };
  const remove = async (m: Movie) => {
    if (!window.confirm(`Delete "${m.title}"? Its ratings, reviews, and watchlist entries will be removed too. This cannot be undone.`)) return;
    setError('');setBusyId('movie-'+m.id);
    try {await request(`/movies/${m.id}`,{method:'DELETE'});setNotice(`Deleted ${m.title}`);setEditing(null);refresh(true);}catch(e){setError(messageOf(e));}finally{setBusyId('');}
  };
  const decide = async (kind: 'suggestions'|'reports', id: number, decision: string) => {
    setBusyId(kind+id);setError('');
    try {await request(`/admin/${kind}/${id}/${decision}`,{method:'POST'});setNotice(`${kind==='suggestions'?'Suggestion':'Report'} ${decision}`);refresh(kind==='suggestions'&&decision==='approved');}
    catch(e){setError(messageOf(e));}finally{setBusyId('');}
  };
  const changeRole = async (person: UserEntry, role: 'member'|'editor') => {
    setBusyId('user'+person.id);setError('');
    try {await request(`/admin/users/${person.id}/role`,{method:'PATCH',body:JSON.stringify({role})});setNotice(`${person.username} is now a ${role}`);refresh();}
    catch(e){setError(messageOf(e));}finally{setBusyId('');}
  };
  return <section className="main-content subpage studio">
    <span className="overline">YOUR CONTROL ROOM</span>
    <div className="studio-heading"><div><h2>Admin studio<span className="accent">.</span></h2><p className="muted">Curate your catalog, review edits, and manage your community.</p></div><span className="studio-role"><ShieldCheck size={16}/> Admin only</span></div>
    <div className="stat-grid">{Object.entries(stats).map(([key,value])=><div className="stat" key={key}><strong>{value}</strong><span>{key}</span></div>)}</div>
    <div className="studio-tabs" role="tablist" aria-label="Admin sections">
      <button className={tab==='movies'?'selected':''} onClick={()=>setTab('movies')}><Film size={16}/>Movies</button>
      <button className={tab==='suggestions'?'selected':''} onClick={()=>setTab('suggestions')}><ClipboardCheck size={16}/>Editor proposals {suggestions.filter(s=>s.status==='pending').length>0&&<b>{suggestions.filter(s=>s.status==='pending').length}</b>}</button>
      <button className={tab==='reports'?'selected':''} onClick={()=>setTab('reports')}><ShieldCheck size={16}/>Reports {reports.filter(r=>r.status==='pending').length>0&&<b>{reports.filter(r=>r.status==='pending').length}</b>}</button>
      <button className={tab==='users'?'selected':''} onClick={()=>setTab('users')}><Users size={16}/>Members</button>
    </div>
    {error&&<div role="alert" className="studio-error">{error}</div>}{notice&&<div role="status" className="studio-success"><Check size={16}/>{notice}</div>}
    {tab==='movies'&&<div className="studio-panel">
      <div className="studio-panel-header"><div><h3>Manage movies</h3><p className="muted">Create films or correct existing movie metadata.</p></div><button className="primary" onClick={startNew}><Plus size={17}/> New movie</button></div>
      {editing!==null&&<form className="studio-editor" onSubmit={save}>
        <div className="studio-panel-header"><h3>{editing==='new'?'Add a movie':'Edit movie'}</h3><button type="button" className="studio-text-button" onClick={()=>setEditing(null)}><X size={16}/> Cancel</button></div>
        <div className="studio-form-grid">
          <label>Title *<input required maxLength={240} value={form.title} onChange={e=>update('title',e.target.value)}/></label>
          <label>Release year *<input required type="number" min="1888" max="2200" value={form.year} onChange={e=>update('year',e.target.value)}/></label>
          <label>Genres (comma-separated)<input maxLength={4096} value={form.genres} onChange={e=>update('genres',e.target.value)} placeholder="Drama, Sci-Fi"/></label>
          <label>Runtime in minutes<input type="number" min="1" max="10000" value={form.runtime} onChange={e=>update('runtime',e.target.value)}/></label>
          <label>Language<input maxLength={100} value={form.language} onChange={e=>update('language',e.target.value)}/></label>
          <label>Country<input maxLength={100} value={form.country} onChange={e=>update('country',e.target.value)}/></label>
          <label className="studio-full">Poster image URL<input type="url" maxLength={600} value={form.poster_url} onChange={e=>update('poster_url',e.target.value)} placeholder="https://example.com/poster.jpg"/></label>
          <label className="studio-full">Synopsis<textarea maxLength={10000} rows={5} value={form.synopsis} onChange={e=>update('synopsis',e.target.value)}/></label>
        </div><div className="studio-form-actions"><button className="primary" disabled={saving}>{saving?'Saving…':editing==='new'?'Create movie':'Save changes'}</button></div>
      </form>}
      <label className="studio-search">Find a film to edit<input value={q} onChange={e=>{setQ(e.target.value);setPage(1);}} placeholder="Search catalog by title"/></label>
      <div className="studio-list">{items.map(m=><div key={m.id} className="studio-list-row"><div className="studio-list-main"><strong>{m.title}</strong><small>{m.year} · {m.genres.join(', ')||'No genre'}</small></div><button className="studio-secondary" onClick={()=>edit(m)}><Pencil size={15}/> Edit</button><button className="studio-danger" disabled={busyId==='movie-'+m.id} onClick={()=>remove(m)}><Trash2 size={15}/> Delete</button></div>)}{items.length===0&&<p className="muted">No matching movies.</p>}</div>
      <div className="studio-page"><span>{total} films · Page {page} of {Math.max(1,Math.ceil(total/20))}</span><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Previous</button><button disabled={page*20>=total} onClick={()=>setPage(p=>p+1)}>Next</button></div>
    </div>}
    {tab==='suggestions'&&<div className="studio-panel"><h3>Editor proposals</h3><p className="muted">Review proposed synopsis changes before applying them.</p>{suggestions.length===0&&<div className="studio-empty">No proposals yet.</div>}{suggestions.map(s=><article className="studio-review-card" key={s.id}><div className="studio-panel-header"><strong>{s.movie_title||`Movie #${s.movie_id}`} · Proposal #{s.id}</strong><span className={`studio-state ${s.status}`}>{s.status}</span></div><p><b>Submitted by:</b> {s.submitted_by||"Editor"} · <b>Reason:</b> {s.reason}</p>{s.current_synopsis!==undefined&&<><strong>Current description</strong><p className="studio-preview">{s.current_synopsis||"No description yet"}</p></>}<strong>Proposed description</strong><p className="studio-preview">{s.synopsis}</p>{s.status==='pending'&&<div className="studio-actions"><button className="studio-secondary" disabled={!!busyId} onClick={()=>decide('suggestions',s.id,'approved')}><Check size={15}/> Approve</button><button className="studio-danger" disabled={!!busyId} onClick={()=>decide('suggestions',s.id,'rejected')}><X size={15}/> Reject</button></div>}</article>)}</div>}
    {tab==='reports'&&<div className="studio-panel"><h3>Review reports</h3><p className="muted">Evaluate flagged reviews before hiding them. Hiding a review removes it from public view.</p>{reports.length===0&&<div className="studio-empty">No reports submitted.</div>}{reports.map(r=><article className="studio-review-card" key={r.id}><div className="studio-panel-header"><strong>{r.movie_title||`Review #${r.review_id}`} · Report #{r.id}</strong><span className={`studio-state ${r.status}`}>{r.status}</span></div><p><b>Reported by:</b> {r.reported_by||"Member"} · <b>Reason:</b> {r.reason}</p>{r.review_title&&<><strong>Flagged review: {r.review_title}</strong><p className="studio-preview">{r.review_body}</p></>}{r.status==='pending'&&<div className="studio-actions"><button className="studio-danger" disabled={!!busyId} onClick={()=>decide('reports',r.id,'hidden')}>Hide review</button><button className="studio-secondary" disabled={!!busyId} onClick={()=>decide('reports',r.id,'dismissed')}>Dismiss report</button></div>}</article>)}</div>}
    {tab==='users'&&<div className="studio-panel"><h3>Member roles</h3><p className="muted">Promote members to editors or return editors to regular membership. Admin accounts are managed locally.</p><div className="studio-list">{users.map(u=><div className="studio-list-row" key={u.id}><div className="studio-list-main"><strong>{u.username}</strong><small>{u.email} · {u.is_active?'Active':'Inactive'}</small></div><label className="studio-role-select">Role <select aria-label={`Role for ${u.username}`} value={u.role} disabled={u.role==='admin'||!u.is_active||busyId==='user'+u.id} onChange={e=>changeRole(u,e.target.value as 'member'|'editor')}><option value="member">Member</option><option value="editor">Editor</option>{u.role==='admin'&&<option value="admin">Admin</option>}</select></label></div>)}</div></div>}
  </section>;
}

export function EditorStudio({request}: {request: Api}) {
  const [q,setQ]=useState('');const [movies,setMovies]=useState<Movie[]>([]);const [chosen,setChosen]=useState<Movie|null>(null);
  const [synopsis,setSynopsis]=useState('');const [reason,setReason]=useState('');const [history,setHistory]=useState<Suggestion[]>([]);
  const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
  const refresh=()=>request('/me/suggestions').then(setHistory).catch(e=>setError(messageOf(e)));
  useEffect(()=>{let active=true;const t=window.setTimeout(()=>request('/movies?'+new URLSearchParams({q,size:'50'})).then(r=>{if(active)setMovies(r.items)}).catch(e=>{if(active)setError(messageOf(e))}),200);return()=>{active=false;window.clearTimeout(t)}},[q,request]);
  useEffect(()=>{refresh()},[request]);
  const submit=async(e:FormEvent<HTMLFormElement>)=>{e.preventDefault();if(!chosen)return;setBusy(true);setError('');setNotice('');try{await request(`/movies/${chosen.id}/suggestions`,{method:'POST',body:JSON.stringify({synopsis,reason})});setNotice('Proposal submitted for review');setReason('');refresh();}catch(e){setError(messageOf(e));}finally{setBusy(false)}};
  return <section className="main-content subpage studio"><span className="overline">HELP BUILD THE CATALOG</span><h2>Editor workspace<span className="accent">.</span></h2><p className="muted">Suggest improvements to movie descriptions. An admin reviews changes before publication.</p>{error&&<div className="studio-error" role="alert">{error}</div>}{notice&&<div className="studio-success" role="status"><Check size={16}/>{notice}</div>}
    <div className="studio-panel"><h3>Submit a synopsis correction</h3><label className="studio-search">Search for a movie<input value={q} onChange={e=>setQ(e.target.value)} placeholder="Type a movie title"/></label><div className="studio-movie-choices">{movies.map(m=><button key={m.id} className={chosen?.id===m.id?'chosen':''} onClick={()=>{setChosen(m);setSynopsis(m.synopsis);}}>{m.title} ({m.year})</button>)}</div>
    {chosen&&<form className="studio-editor" onSubmit={submit}><h3>Editing: {chosen.title}</h3><div className="studio-form-grid"><label className="studio-full">Proposed synopsis *<textarea required minLength={5} maxLength={10000} rows={5} value={synopsis} onChange={e=>setSynopsis(e.target.value)}/></label><label className="studio-full">Reason for this change *<textarea required minLength={5} maxLength={1000} rows={3} value={reason} onChange={e=>setReason(e.target.value)} placeholder="What information is incorrect or missing?"/></label></div><button className="primary" disabled={busy}>{busy?'Submitting…':'Submit for approval'}</button></form>}
    </div><div className="studio-panel"><h3>Your proposals</h3>{history.length===0&&<p className="muted">You haven't submitted any proposals yet.</p>}{history.map(s=><div className="studio-list-row" key={s.id}><div className="studio-list-main"><strong>{s.movie_title} · #{s.id}</strong><small>{s.reason}</small></div><span className={`studio-state ${s.status}`}>{s.status}</span></div>)}</div>
  </section>;
}
