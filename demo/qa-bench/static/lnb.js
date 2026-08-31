
(function () {
  "use strict";

  var KEY = "tms.ui.lnb";
  var root = document.documentElement;

  function folded() {
    return root.getAttribute("data-lnb") === "fold";
  }

  
  function remember(v) {
    try { window.localStorage.setItem(KEY, v); } catch (e) {  }
  }

  function paint(btn) {
    var f = folded();
    btn.setAttribute("aria-pressed", f ? "true" : "false");
    
    btn.setAttribute("title", f ? "사이드바를 펼칩니다" : "사이드바를 접습니다");
  }

  function wire() {
    var btn = document.querySelector("[data-lnb-fold]");
    if (!btn) return;
    btn.hidden = false;
    paint(btn);
    btn.addEventListener("click", function () {
      if (folded()) root.removeAttribute("data-lnb");
      else root.setAttribute("data-lnb", "fold");
      remember(folded() ? "fold" : "open");
      paint(btn);
    });

    
    var mini = document.querySelector("[data-lnb-open]");
    if (!mini) return;
    mini.hidden = false;
    mini.addEventListener("click", function () {
      root.removeAttribute("data-lnb");
      remember("open");
      paint(btn);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
