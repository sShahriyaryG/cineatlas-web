// Keep the number of requested records and rendered columns in agreement.
export type GridKind='films'|'people'|'classifications';
export function gridLayout(width:number,kind:GridKind){
 const min=kind==='films'?145:kind==='people'?155:225;
 const gap=kind==='films'?18:kind==='people'?16:12;
 const rows=kind==='films'?2:4;
 const minimum=kind==='classifications'||width<240?1:2;
 const columns=Math.min(Math.floor(50/rows),Math.max(minimum,Math.floor((width+gap)/(min+gap))));
 return {columns,size:columns*rows};
}
export const pageForOffset=(offset:number,size:number)=>Math.floor(Math.max(0,offset)/size)+1;
