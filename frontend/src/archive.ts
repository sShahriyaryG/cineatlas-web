// Date-only values are calendar dates, not local timezone instants.
export function calendarDate(value:string){
  const parsed=new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime())?value:parsed.toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric',timeZone:'UTC'});
}
export function safeExternal(value:string|null|undefined):string|undefined{
  if(!value)return undefined;
  try{const url=new URL(value);if((url.protocol==='http:'||url.protocol==='https:')&&!url.username&&!url.password)return url.href}catch{/* invalid URL */}
  return undefined;
}

// A release date alone may be a future schedule. Keep one fact, never two.
export function releaseFact(date:string|null,status:string|null,today=new Date().toISOString().slice(0,10)){
 const labels:Record<string,string>={released:'Released',upcoming:'Upcoming',in_production:'In production',cancelled:'Cancelled'};
 if(date){
  const future=date>today;
  const qualifier=status==='cancelled'?' (cancelled)':status==='in_production'?' (in production)':status==='upcoming'&&!future?' (release unconfirmed)':'';
  return {label:future?'Scheduled release':'Release date',value:calendarDate(date)+qualifier};
 }
 return status?{label:'Release',value:labels[status]||status}:null;
}
