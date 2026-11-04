/* Same menus as Vision Lib; same style.css tokens and keyboard behavior. */
(()=>{
const $=(s,el=document)=>el.querySelector(s);
const esc=s=>String(s??" ").replace(/[&<>"\']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","\'":"&#39;"}[c]));
const ICON={caret:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m8 10 4 4 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>',check:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m4.75 12.78 5.25 6.47 9.25-14.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'};
let activeMenu = null, menuSequence = 0;
function closeMenu(restoreFocus = false) {
  if (!activeMenu) return;
  const {trigger, menu} = activeMenu;
  activeMenu = null;
  trigger.setAttribute("aria-expanded", "false");
  menu.remove();
  if (restoreFocus && trigger.isConnected) trigger.focus({preventScroll: true});
}
function positionMenu() {
  if (!activeMenu) return;
  const {trigger, menu, align, matchWidth} = activeMenu;
  if (!trigger.isConnected) return closeMenu();
  const r = trigger.getBoundingClientRect(), edge = 8, gap = 6;
  const viewport = window.visualViewport, width = viewport?.width || innerWidth;
  const top = viewport?.offsetTop || 0, bottom = top + (viewport?.height || innerHeight);
  menu.style.maxWidth = `${width - edge * 2}px`;
  menu.style.minWidth = `${Math.min(Math.max(150, matchWidth ? r.width : 0), width - edge * 2)}px`;
  menu.style.maxHeight = `${bottom - top - edge * 2}px`;
  const height = menu.offsetHeight, below = bottom - r.bottom - gap - edge, above = r.top - top - gap - edge;
  const up = height > below && above > below;
  menu.dataset.side = up ? "top" : "bottom";
  menu.style.maxHeight = `${Math.max(0, up ? above : below)}px`;
  menu.style.left = `${Math.max(edge, Math.min(align === "start" ? r.left : r.right - menu.offsetWidth, width - menu.offsetWidth - edge))}px`;
  menu.style.top = `${Math.max(top + edge, up ? r.top - gap - menu.offsetHeight : r.bottom + gap)}px`;
}
function bindMenu(trigger, items, choose, {align = "end", matchWidth = false} = {}) {
  trigger.id ||= `menu-trigger-${++menuSequence}`;
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", `${trigger.id}-menu`);
  function open(focusLast = false) {
    closeMenu();
    const menu = document.createElement("div");
    menu.id = `${trigger.id}-menu`; menu.className = "menu";
    menu.setAttribute("role", "menu"); menu.setAttribute("aria-labelledby", trigger.id);
    menu.innerHTML = items().map(item => `${item.separator ? '<hr role="separator">' : ""}<button type="button" role="menuitemradio" aria-checked="${!!item.selected}" tabindex="-1" data-value="${esc(item.value)}" ${item.disabled ? "disabled" : ""}><span>${esc(item.label)}</span><span class="menu-check" aria-hidden="true">${item.selected ? ICON.check : ""}</span></button>`).join("");
    (document.querySelector("#cms dialog[open]") || document.querySelector("#cms")).appendChild(menu);
    activeMenu = {trigger, menu, align, matchWidth};
    trigger.setAttribute("aria-expanded", "true");
    positionMenu();
    menu.querySelectorAll("button").forEach(button => {
      button.addEventListener("pointermove", e => { if (e.pointerType === "mouse") button.focus({preventScroll: true}); });
      button.onclick = () => { const value = button.dataset.value; closeMenu(true); choose(value); };
    });
    const buttons = [...menu.querySelectorAll("button:not(:disabled)")];
    (focusLast ? buttons.at(-1) : buttons[0])?.focus({preventScroll: true});
  }
  trigger.onclick = () => activeMenu?.trigger === trigger ? closeMenu(true) : open();
  trigger.onkeydown = e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); open(e.key === "ArrowUp"); }
  };
}
function enhanceSelect(select, label, field = false) {
  const trigger = document.createElement("button");
  trigger.type = "button"; trigger.id = `${select.id || select.name}-trigger`;
  trigger.className = field ? "select-trigger field-trigger" : "pill-btn shadow select-trigger";
  trigger.setAttribute("aria-label", label);
  select.hidden = true;
  select.after(trigger);
  const update = () => { trigger.innerHTML = `<span>${esc(select.selectedOptions[0]?.textContent || "")}</span>${ICON.caret}`; };
  select.addEventListener("change", update); update();
  bindMenu(trigger, () => [...select.options].map(o => ({value: o.value, label: o.text, selected: o.selected, disabled: o.disabled})), value => {
    select.value = value; select.dispatchEvent(new Event("change", {bubbles: true}));
    document.getElementById(trigger.id)?.focus({preventScroll: true});
  }, {align: field ? "start" : "end", matchWidth: field});
}
document.addEventListener("pointerdown", e => {
  if (activeMenu && !activeMenu.menu.contains(e.target) && !activeMenu.trigger.contains(e.target)) closeMenu();
}, true);
document.addEventListener("focusin", e => {
  if (activeMenu && !activeMenu.menu.contains(e.target) && !activeMenu.trigger.contains(e.target)) closeMenu();
});
window.addEventListener("resize", positionMenu);
window.visualViewport?.addEventListener("resize", positionMenu);
window.addEventListener("scroll", e => {
  if (activeMenu && !activeMenu.menu.contains(e.target)) closeMenu();
}, true);
document.addEventListener("keydown", e => {
  if (!activeMenu) return;
  if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); return closeMenu(true); }
  if (e.key === "Tab") { closeMenu(true); return; }
  const buttons = [...activeMenu.menu.querySelectorAll("button:not(:disabled)")];
  const index = buttons.indexOf(document.activeElement);
  let next;
  if (e.key === "ArrowDown") next = (index + 1) % buttons.length;
  if (e.key === "ArrowUp") next = (index - 1 + buttons.length) % buttons.length;
  if (e.key === "Home") next = 0;
  if (e.key === "End") next = buttons.length - 1;
  if (next != null) { e.preventDefault(); e.stopImmediatePropagation(); buttons[next]?.focus(); }
}, true);


window.CMSSelect={enhance:enhanceSelect,close:closeMenu};
})();
