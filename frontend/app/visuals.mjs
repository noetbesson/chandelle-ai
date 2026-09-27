// Motion's free browser distribution is local; content stays visible without JS animations.
let cleanup=()=>{};
export function stopVisuals(){cleanup();cleanup=()=>{};}
export function enhanceVisuals(){
  stopVisuals();
  const root=document,media=globalThis.matchMedia?.('(prefers-reduced-motion: reduce)');
  const controls=new Set(),targets=new Set(),observer=globalThis.IntersectionObserver;
  let visibleObserver,abort;
  const stop=()=>{visibleObserver?.disconnect();abort?.abort();for(const c of controls)c.stop();controls.clear();for(const el of targets){for(const name of ['opacity','transform','scale'])el.style.removeProperty(name);}targets.clear();};
  const start=()=>{
    stop();
    if(media?.matches||!globalThis.Motion?.animate)return;
    const run=(el,frames,options)=>{const c=Motion.animate(el,frames,options);controls.add(c);targets.add(el);if(options.repeat!==Infinity)c.then(()=>controls.delete(c));return c;};
    root.querySelectorAll('.header-logo .candle-flame path').forEach((el,i)=>run(el,{transform:['skewX(-2deg) scaleY(.98)','skewX(2deg) scaleY(1.03)']},{duration:3.6+i*.12,repeat:Infinity,repeatType:'mirror',ease:'easeInOut'}));
    if(observer){
      visibleObserver=new observer(entries=>{
        let index=0;
        for(const entry of entries)if(entry.isIntersecting){visibleObserver.unobserve(entry.target);run(entry.target,{opacity:[0,1],transform:['translateY(12px)','translateY(0)']},{duration:.48,delay:Math.min(index++*.055,.22),ease:'easeOut'});}
      },{threshold:.08});
      root.querySelectorAll('[data-reveal], [data-discover-row]').forEach(el=>visibleObserver.observe(el));
    }
    abort=new AbortController();let pressed;
    root.addEventListener('pointerdown',e=>{if(e.button!==0)return;const action=e.target.closest?.('.activity-actions a, .activity-actions button');pressed=action?.closest('[data-discover-row]');if(pressed)run(pressed,{scale:.98},{duration:.12});},{signal:abort.signal});
    const release=()=>{if(pressed){run(pressed,{scale:1},{duration:.18});pressed=null;}};
    root.addEventListener('pointerup',release,{signal:abort.signal});root.addEventListener('pointercancel',release,{signal:abort.signal});
  };
  media?.addEventListener?.('change',start);
  cleanup=()=>{stop();media?.removeEventListener?.('change',start);};
  start();
}
// Capture image failures (which do not bubble); the illustrated fallback is underneath.
globalThis.document?.addEventListener('error',e=>{if(e.target?.hasAttribute?.('data-activity-image'))e.target.remove();},true);
