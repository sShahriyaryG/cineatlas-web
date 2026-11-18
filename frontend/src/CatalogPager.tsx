import {ChevronLeft,ChevronRight} from 'lucide-react';
export function CatalogPager({page,total,size,onPage}:{page:number;total:number;size:number;onPage:(p:number)=>void}){
 const max=Math.max(1,Math.ceil(total/size));if(max<=1)return null;
 return <nav className="pagination" aria-label="Results pages"><button disabled={page<=1} onClick={e=>{onPage(page-1);e.currentTarget.closest('.global-group, .archive-page, .explore-page')?.scrollIntoView({block:'start'})}}><ChevronLeft size={16}/> Previous</button><span>Page {page} of {max}</span><button disabled={page>=max} onClick={e=>{onPage(page+1);e.currentTarget.closest('.global-group, .archive-page, .explore-page')?.scrollIntoView({block:'start'})}}>Next <ChevronRight size={16}/></button></nav>;
}
