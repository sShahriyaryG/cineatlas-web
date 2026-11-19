export type Entity='movie'|'person';
export type Credit={related_id:number;role:string;character:string;position?:number|null};
export type Fields=Record<string,unknown>;
export type Changes={core:Fields;metadata:Fields;credits?:Credit[]};
export type Snapshot={core:Fields;metadata:Fields;credits:Credit[]};
export type Contribution={id:number;entity:Entity;target_id:number|null;result_id:number|null;status:string;version:number;baseline:Snapshot;changes:Changes;reason:string;source_url:string|null;review_note:string;author_name:string;reviewer_name:string|null;created_at:string;updated_at:string};
export const emptySnapshot=():Snapshot=>({core:{},metadata:{},credits:[]});
export function contributionTitle(c:Contribution){const key=c.entity==='movie'?'title':'name';return String(c.changes.core[key]||c.baseline.core[key]||`New ${c.entity}`)}
export function diffRows(b:Snapshot,c:Changes){return ['core','metadata'].flatMap(group=>Object.entries(c[group as 'core'|'metadata']).map(([key,value])=>({key,before:b[group as 'core'|'metadata'][key],after:value}))).concat(c.credits===undefined?[]:[{key:'credits',before:b.credits,after:c.credits}]);}
export function updateField(c:Changes,b:Snapshot,group:'core'|'metadata',key:string,value:unknown):Changes{const next={...c[group]};if(JSON.stringify(b[group][key])===JSON.stringify(value))delete next[key];else next[key]=value;return {...c,[group]:next}}

export function moveCredit(credits:Credit[],index:number,direction:-1|1){
 const role=credits[index]?.role;if(!role)return credits;
 const slots=credits.map((c,i)=>c.role===role?i:-1).filter(i=>i>=0);const from=slots.indexOf(index),to=from+direction;
 if(to<0||to>=slots.length)return credits;
 const group=slots.map(i=>credits[i]);[group[from],group[to]]=[group[to],group[from]];
 const next=[...credits];slots.forEach((slot,i)=>{next[slot]={...group[i],position:i}});return next;
}
export function reviseChanges(old:Contribution,current:Snapshot):Changes{
 // Preserve new relationships added since the old proposal; only replay its credit delta.
 const changes={...old.changes};
 if(old.changes.credits){
  const key=(c:Credit)=>JSON.stringify([c.related_id,c.role,c.character]);
  const before=new Map(old.baseline.credits.map(c=>[key(c),c]));
  const after=new Map(old.changes.credits.map(c=>[key(c),c]));
  const next=new Map(current.credits.map(c=>[key(c),c]));
  for(const [k] of before)if(!after.has(k))next.delete(k);
  for(const [k,c] of after)if(!before.has(k)||before.get(k)?.position!==c.position)next.set(k,c);
  changes.credits=[...next.values()];
 }
 return changes;
}

// Keep draft and submission feedback readable and consistent with server limits.
export function contributionValidation(entity:Entity,baseline:Snapshot,changes:Changes,reason:string,submit:boolean):string[]{
 const core={...baseline.core,...changes.core};const errors:string[]=[];
 if(entity==='movie'){
  const year=core.year,runtime=core.runtime;
  if(Object.prototype.hasOwnProperty.call(changes.core,'year')&&year!=null&&(typeof year!=='number'||!Number.isInteger(year)||year<1888||year>2200))errors.push('Enter a whole release year between 1888 and 2200.');
  if(Object.prototype.hasOwnProperty.call(changes.core,'runtime')&&runtime!=null&&(typeof runtime!=='number'||!Number.isInteger(runtime)||runtime<1||runtime>10000))errors.push('Enter a whole runtime between 1 and 10,000 minutes.');
  if(submit&&!String(core.title??'').trim())errors.push('Enter a film title.');
  if(submit&&year==null)errors.push('Enter a release year.');
 }else if(submit&&!String(core.name??'').trim())errors.push('Enter a person name.');
 if(submit&&reason.trim().length<5)errors.push('Enter a contribution reason of at least 5 characters.');
 return errors;
}
export function finderPath(entity:Entity,query:string,page:number,size:number):string|null{
 const q=query.trim();if(!q)return null;
 const params=new URLSearchParams({q,page:String(page),size:String(size)});
 return `${entity==='movie'?'/movies':'/directory/people'}?${params}`;
}

export type LegacyContribution={kind:'synopsis';id:number;movie_id:number;movie_title:string;synopsis:string;reason:string;status:string;author_name:string;created_at:string;current_synopsis?:string};
export type HistoryItem=({kind:'structured'}&Contribution)|LegacyContribution;
export function historyKey(c:HistoryItem){return `${c.kind}-${c.id}`;}
export function historyTitle(c:HistoryItem){return c.kind==='synopsis'?c.movie_title:contributionTitle(c);}
export function historyType(c:HistoryItem){return c.kind==='synopsis'?'Edit film · Synopsis':`${c.target_id===null?'New':'Edit'} ${c.entity==='movie'?'film':'person'}`;}
export function historyPath(admin:boolean,status:string,page:number,size:number){const params=new URLSearchParams({page:String(page),size:String(size)});if(status!=='all')params.set('status',status);return `/${admin?'admin':'me'}/contribution-history?${params}`;}
