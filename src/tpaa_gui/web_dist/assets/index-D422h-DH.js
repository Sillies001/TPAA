(function(){const o=document.createElement("link").relList;if(o&&o.supports&&o.supports("modulepreload"))return;for(const e of document.querySelectorAll('link[rel="modulepreload"]'))n(e);new MutationObserver(e=>{for(const t of e)if(t.type==="childList")for(const r of t.addedNodes)r.tagName==="LINK"&&r.rel==="modulepreload"&&n(r)}).observe(document,{childList:!0,subtree:!0});function s(e){const t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin==="use-credentials"?t.credentials="include":e.crossOrigin==="anonymous"?t.credentials="omit":t.credentials="same-origin",t}function n(e){if(e.ep)return;e.ep=!0;const t=s(e);fetch(e.href,t)}})();const i=document.querySelector("#app");if(!i)throw new Error("TPAA_GUI_ROOT_MISSING");i.innerHTML=`
  <main class="shell" aria-labelledby="product-title">
    <header class="titlebar">
      <h1 id="product-title">空中作战训练辅助评估系统</h1>
      <span>v33 产品壳工程脚手架</span>
    </header>
    <nav class="ribbon" aria-label="主模块">
      <button type="button" aria-current="page">总览</button>
      <button type="button" disabled>训练评估</button>
      <button type="button" disabled>回放</button>
      <button type="button" disabled>装备性能</button>
      <button type="button" disabled>数据与系统</button>
    </nav>
    <section class="state" aria-live="polite">
      <h2>产品视图尚未加载</h2>
      <p>G1 安全壳已启动；V01～V26 将在后续阶段按机器权威逐页接入。</p>
      <code>NO_SYNTHETIC_BUSINESS_DATA · FAIL_CLOSED</code>
    </section>
    <footer>GUI-DEMO-V33-2026-11-05 · Graphite · 本地受控会话</footer>
  </main>
`;
