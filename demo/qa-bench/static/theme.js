
(function () {
  "use strict";

  var KEY = "tms.ui.theme";
  var root = document.documentElement;

  function current() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  
  function remember(v) {
    try { window.localStorage.setItem(KEY, v); } catch (e) {  }
  }

  function paint(btn) {
    var dark = current() === "dark";
    
    btn.setAttribute("aria-checked", dark ? "true" : "false");
    
    btn.setAttribute("title", dark ? "밝은 화면으로 바꿉니다" : "어두운 화면으로 바꿉니다");
    var sun = btn.querySelector("[data-theme-sun]");
    var moon = btn.querySelector("[data-theme-moon]");
    if (moon) moon.hidden = !dark; 
    if (sun) sun.hidden = dark;    
  }

  function wire() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    btn.hidden = false;
    paint(btn);
    btn.addEventListener("click", function () {
      var next = current() === "light" ? "dark" : "light";
      if (next === "light") root.setAttribute("data-theme", "light");
      else root.removeAttribute("data-theme");
      remember(next);
      paint(btn);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
