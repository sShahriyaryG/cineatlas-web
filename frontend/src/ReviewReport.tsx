import {useEffect, useRef, useState} from 'react';
import {Flag, CheckCircle} from 'lucide-react';

type Props = {
  reviewId: number;
  signedIn: boolean;
  onSignIn: () => void;
  onReport: (reason: string) => Promise<unknown>;
};

/** Inline to avoid stacking another dialog on the movie-details dialog. */
export function ReviewReport({reviewId, signedIn, onSignIn, onReport}: Props) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const pending = useRef(false);
  const formId = `review-report-${reviewId}`;
  const trimmed = reason.trim();

  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  if (sent) return <div className="report-success" role="status"><CheckCircle size={15} aria-hidden="true"/> Report submitted for moderation.</div>;

  return <div className="review-report">
    <button ref={trigger} type="button" className="report-trigger" aria-expanded={open} aria-controls={open ? formId : undefined} onClick={() => {
      if (!signedIn) { onSignIn(); return; }
      if (!busy) {setOpen(!open); setError('');}
    }} disabled={busy}>
      <Flag size={14} aria-hidden="true"/> {signedIn ? 'Report review' : 'Sign in to report'}
    </button>
    {open && <form id={formId} className="report-form" onSubmit={async e => {
      e.preventDefault();
      if (pending.current) return;
      if (trimmed.length < 5 || trimmed.length > 1000) {setError('Enter a reason between 5 and 1,000 characters.'); return;}
      pending.current = true;
      setBusy(true); setError('');
      try { await onReport(trimmed); setSent(true); setOpen(false); }
      catch (err) {setError(err instanceof Error ? err.message : 'Unable to submit the report. Please try again.');}
      finally {pending.current = false; setBusy(false);}
    }}>
      <label htmlFor={`${formId}-reason`}>Why are you reporting this review?</label>
      <p id={`${formId}-help`}>For example, harassment, spam, or an unmarked spoiler. An administrator will review your report.</p>
      <textarea ref={input} id={`${formId}-reason`} value={reason} onChange={e=>{setReason(e.target.value);setError('');}} required minLength={5} maxLength={1000} rows={3} disabled={busy} aria-describedby={`${formId}-help ${formId}-count`} placeholder="Describe the issue…"/>
      <div className="report-count" id={`${formId}-count`}>{reason.length} / 1,000 characters · minimum 5</div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="report-actions">
        <button type="button" className="report-cancel" disabled={busy} onClick={()=>{setOpen(false);setReason('');setError('');trigger.current?.focus();}}>Cancel</button>
        <button type="submit" className="primary" disabled={busy || trimmed.length < 5 || trimmed.length > 1000}>{busy ? 'Submitting…' : 'Submit report'}</button>
      </div>
    </form>}
  </div>;
}
