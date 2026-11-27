"use strict";

// Readable source used directly by _includes/scripts.html; no minification step.
document.documentElement.classList.add("js");

const navigation = document.getElementById("site-nav");
const toggle = navigation.querySelector(".nav-toggle");
const menu = document.getElementById("main-navigation");
const links = [...menu.querySelectorAll("a")];
const sections = links.map(link => document.getElementById(link.hash.slice(1))).filter(Boolean);
const mobile = window.matchMedia("(max-width: 640px)");
let explicitSection = sections.find(section => location.hash === `#${section.id}`) || null;
let framePending = false;

function closeMenu(restoreFocus = false) {
  menu.classList.remove("is-open");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open navigation");
  if (restoreFocus) toggle.focus();
}

toggle.hidden = false;
toggle.addEventListener("click", () => {
  const open = menu.classList.toggle("is-open");
  toggle.setAttribute("aria-expanded", String(open));
  toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
});

links.forEach(link => link.addEventListener("click", () => {
  explicitSection = document.getElementById(link.hash.slice(1));
  closeMenu();
  scheduleUpdate();
}));
mobile.addEventListener("change", () => closeMenu());
document.addEventListener("click", event => {
  if (!event.target.closest("#site-nav")) closeMenu();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && menu.classList.contains("is-open")) closeMenu(true);
});

function updateNavigation() {
  framePending = false;
  if (!sections.length) return;
  const headerBottom = document.querySelector(".masthead").getBoundingClientRect().bottom;
  let current = sections[0];
  sections.forEach(section => {
    if (section.getBoundingClientRect().top <= headerBottom + 36) current = section;
  });
  if (explicitSection) {
    current = explicitSection;
  } else if (window.scrollY > 0 && Math.ceil(window.innerHeight + window.scrollY) >= document.documentElement.scrollHeight - 2) {
    current = sections[sections.length - 1];
  }
  links.forEach(link => {
    if (link.hash === `#${current.id}`) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}

function scheduleUpdate() {
  if (!framePending) {
    framePending = true;
    window.requestAnimationFrame(updateNavigation);
  }
}

function resumeScrollTracking() {
  explicitSection = null;
  scheduleUpdate();
}

window.addEventListener("scroll", scheduleUpdate, { passive: true });
window.addEventListener("resize", scheduleUpdate);
window.addEventListener("load", scheduleUpdate);
window.addEventListener("hashchange", () => {
  explicitSection = sections.find(section => location.hash === `#${section.id}`) || null;
  if (location.hash === "#top") explicitSection = sections[0];
  scheduleUpdate();
});
window.addEventListener("wheel", resumeScrollTracking, { passive: true });
window.addEventListener("touchmove", resumeScrollTracking, { passive: true });
document.addEventListener("keydown", event => {
  if (!["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " ", "Spacebar"].includes(event.key)) return;
  if (event.target.closest("input, textarea, select, [contenteditable]")) return;
  if (event.target.closest("button") && [" ", "Spacebar"].includes(event.key)) return;
  resumeScrollTracking();
});
document.querySelectorAll('a[href$="#top"]').forEach(link => link.addEventListener("click", () => {
  explicitSection = sections[0];
  scheduleUpdate();
}));
updateNavigation();
