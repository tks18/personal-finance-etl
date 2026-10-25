(function () {
  function progress() {
    let bar=document.getElementById("pf-reading-progress");
    if(!bar){bar=document.createElement("div");bar.id="pf-reading-progress";document.body.appendChild(bar);}
    const update=()=>{const d=document.documentElement,max=d.scrollHeight-d.clientHeight;bar.style.width=(max>0?Math.min(100,d.scrollTop/max*100):0)+"%";};
    document.addEventListener("scroll",update,{passive:true}); update();
  }
  function mermaidZoom() {
    let modal=document.querySelector(".pf-mermaid-modal");
    if(!modal){
      modal=document.createElement("div"); modal.className="pf-mermaid-modal";
      modal.innerHTML='<div class="pf-mermaid-modal__panel" role="dialog" aria-modal="true" aria-label="Expanded diagram"><button class="pf-mermaid-modal__close" aria-label="Close expanded diagram">×</button><div class="pf-mermaid-modal__content"></div></div>';
      document.body.appendChild(modal);
      modal.addEventListener("click",e=>{if(e.target===modal||e.target.closest(".pf-mermaid-modal__close"))modal.classList.remove("is-open");});
      document.addEventListener("keydown",e=>{if(e.key==="Escape")modal.classList.remove("is-open");});
    }
    document.querySelectorAll(".md-typeset .mermaid").forEach(el=>{
      if(el.dataset.pfZoom)return; el.dataset.pfZoom="1"; el.title="Click to expand diagram";
      el.addEventListener("click",()=>{const svg=el.querySelector("svg");if(!svg)return;modal.querySelector(".pf-mermaid-modal__content").innerHTML=svg.outerHTML;modal.classList.add("is-open");modal.querySelector(".pf-mermaid-modal__close").focus();});
    });
  }
  function boot(){progress();mermaidZoom();}
  if(typeof document$!=="undefined")document$.subscribe(boot);else document.addEventListener("DOMContentLoaded",boot);
})();
