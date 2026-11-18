import {useCallback,useLayoutEffect,useState} from 'react';
import {gridLayout,type GridKind} from './gridPaging';
export function useGridPaging(kind:GridKind){
 const [node,setNode]=useState<HTMLElement|null>(null);
 const ref=useCallback((el:HTMLElement|null)=>setNode(el),[]);
 const [width,setWidth]=useState(960);
 useLayoutEffect(()=>{
  if(!node)return;
  const read=()=>{const css=getComputedStyle(node);const next=node.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight);if(next>0)setWidth(next)};
  read();
  const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(read);
  observer?.observe(node);window.addEventListener('resize',read);
  return()=>{observer?.disconnect();window.removeEventListener('resize',read)};
 },[node]);
 const {columns,size}=gridLayout(width,kind);
 return {ref,size,style:{gridTemplateColumns:`repeat(${columns},minmax(0,1fr))`}};
}
