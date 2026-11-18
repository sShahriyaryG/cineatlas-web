import {useEffect,useRef,useState,type FormEvent} from 'react';

type SessionEntry={id:string;device:string;transport:'cookie'|'bearer';created_at:string;expires_at:string;current:boolean};
type Props={username:string;request:(path:string,options?:RequestInit)=>Promise<any>;close:()=>void;onSignedOut:()=>void};
const date=(v:string)=>new Date(v).toLocaleString();
const message=(e:unknown)=>e instanceof Error?e.message:'Request failed';
export function SecurityPanel({username,request,close,onSignedOut}:Props){
  const dialog=useRef<HTMLDialogElement>(null);
  const [sessions,setSessions]=useState<SessionEntry[]>([]),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [passwordChanged,setPasswordChanged]=useState(false),[passwordError,setPasswordError]=useState('');
  const passwordResult=useRef<HTMLDivElement>(null);
  const changing=useRef(false);
  useEffect(()=>{if(passwordChanged)passwordResult.current?.focus()},[passwordChanged]);
  const [revision,setRevision]=useState(0);
  useEffect(()=>{const el=dialog.current;const prior=document.activeElement;if(el&&!el.open)el.showModal();return()=>{if(el?.open)el.close();if(prior instanceof HTMLElement&&prior.isConnected)prior.focus()}},[]);
  useEffect(()=>{let active=true;const controller=new AbortController();setLoading(true);request('/auth/sessions',{signal:controller.signal}).then(data=>{if(active)setSessions(data)}).catch(e=>{if(active)setError(message(e))}).finally(()=>{if(active)setLoading(false)});return()=>{active=false;controller.abort()}},[request,revision]);
  const terminate=async(s:SessionEntry)=>{if(!window.confirm(s.current?'Sign out of this session?':'Sign out of this device?'))return;setBusy(true);setError('');try{await request(`/auth/sessions/${encodeURIComponent(s.id)}`,{method:'DELETE'});if(s.current)onSignedOut();else{setNotice('Session ended');setRevision(v=>v+1)}}catch(e){setError(message(e))}finally{setBusy(false)}};
  const everywhere=async()=>{if(!window.confirm('Sign out of all devices, including this one?'))return;setBusy(true);setError('');try{await request('/auth/logout-all',{method:'POST'});onSignedOut()}catch(e){setError(message(e))}finally{setBusy(false)}};
  const change=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();
    if(busy||changing.current)return;
    setPasswordError('');
    // Read the actual form values, including values supplied by browser autofill.
    const data=new FormData(e.currentTarget);
    const current=String(data.get('current_password')??'');
    const password=String(data.get('new_password')??'');
    const confirm=String(data.get('confirm_password')??'');
    if(password!==confirm){setPasswordError('New passwords do not match');return}
    changing.current=true;setBusy(true);
    try{
      await request('/auth/password',{method:'POST',body:JSON.stringify({current_password:current,new_password:password})});
      // Unmount the submitted form only after the API confirms success. Do not
      // clear the fields first: browsers can use form removal to detect success.
      setPasswordChanged(true);setRevision(v=>v+1);
    }catch(e){setPasswordError(message(e))}finally{changing.current=false;setBusy(false)}
  };
  return <dialog ref={dialog} className="modal security-panel" aria-labelledby="security-title" onCancel={e=>{e.preventDefault();if(!busy)close()}}>
    <button className="close" type="button" disabled={busy} onClick={close} aria-label="Close account security">×</button>
    <h2 id="security-title">Account security</h2><p className="muted">Manage signed-in devices and your password.</p>
    {error&&<p className="error" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <h3>Active sessions</h3>{loading?<p role="status">Loading sessions…</p>:sessions.length===0?<p>No sessions to display. <button className="secondary-button" onClick={()=>setRevision(v=>v+1)}>Retry</button></p>:<ul className="session-list">{sessions.map(s=><li key={s.id}><div><strong>{s.current?'This session':s.transport==='cookie'?'Browser session':'API session'}</strong><small>{s.device||'Device not provided'}</small><small>Signed in: {date(s.created_at)}</small><small>Expires: {date(s.expires_at)}</small></div><button className="secondary-button" disabled={busy} onClick={()=>terminate(s)}>Sign out</button></li>)}</ul>}
    <button className="secondary-button" disabled={busy} onClick={everywhere}>Sign out everywhere</button>
    <h3 id="change-password-title">Change password</h3>
    {passwordChanged?<>
      <div className="studio-success" role="status" tabIndex={-1} ref={passwordResult}>
        <div><strong>Password changed successfully.</strong><p>Other sessions have been signed out. You are still signed in on this device.</p></div>
      </div>
      <button type="button" className="secondary-button" disabled={busy} onClick={()=>{setPasswordError('');setPasswordChanged(false)}}>Change password again</button>
    </>:<form id="change-password-form" method="post" aria-labelledby="change-password-title" onSubmit={change}>
      <label htmlFor="change-password-account">Account username<input id="change-password-account" name="username" autoComplete="username" value={username} readOnly/></label>
      <label htmlFor="change-current-password">Current password<input id="change-current-password" name="current_password" type="password" autoComplete="current-password" required maxLength={128} readOnly={busy}/></label>
      <label htmlFor="change-new-password">New password<input id="change-new-password" name="new_password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} readOnly={busy}/></label>
      <label htmlFor="change-confirm-password">Confirm new password<input id="change-confirm-password" name="confirm_password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} readOnly={busy}/></label>
      {passwordError&&<p className="error" role="alert">{passwordError}</p>}
      <button type="submit" className="primary" disabled={busy}>{changing.current?'Changing password…':'Change password'}</button>
    </form>}
  </dialog>;
}
