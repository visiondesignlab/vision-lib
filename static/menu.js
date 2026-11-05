/* Shared selection menus for the public site and the content manager. */
(() => {
if (window.VisionMenu) return;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const {icon} = window.VisionSite;
const ICON = {check:icon("check"), caret:icon("caret")};
let activeMenu = null, menuSequence = 0;
function closeMenu(restoreFocus = false) {
  if (!activeMenu) return;
  const {trigger, menu} = activeMenu;
  activeMenu = null;
  trigger.setAttribute("aria-expanded", "false");
  menu.remove();
  trigger.removeAttribute("aria-controls");
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
  const heightLimit = Math.min(320, bottom - top - edge * 2);
  menu.style.maxHeight = heightLimit + "px";
  if (matchWidth) menu.style.width = Math.min(r.width, width - edge * 2) + "px";
  const height = menu.offsetHeight, below = bottom - r.bottom - gap - edge, above = r.top - top - gap - edge;
  const up = height > below && above > below;
  menu.dataset.side = up ? "top" : "bottom";
  menu.style.maxHeight = `${Math.max(0, Math.min(heightLimit, up ? above : below))}px`;
  menu.style.left = `${Math.max(edge, Math.min(align === "start" ? r.left : r.right - menu.offsetWidth, width - menu.offsetWidth - edge))}px`;
  menu.style.top = `${Math.max(top + edge, up ? r.top - gap - menu.offsetHeight : r.bottom + gap)}px`;
}
function focusOption(menu, button) {
  if (!button) return;
  button.focus({preventScroll:true});
  const top = button.offsetTop, bottom = top + button.offsetHeight;
  if (top < menu.scrollTop) menu.scrollTop = top;
  else if (bottom > menu.scrollTop + menu.clientHeight) menu.scrollTop = bottom - menu.clientHeight;
}

function bindMenu(trigger, items, choose, {align = "end", matchWidth = false} = {}) {
  trigger.id ||= `menu-trigger-${++menuSequence}`;
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");

  function open(focusLast = false) {
    closeMenu();
    const menu = document.createElement("div");
    menu.dataset.field = String(matchWidth);
    menu.id = `${trigger.id}-menu`; menu.className = "menu";
    menu.setAttribute("role", "menu"); menu.setAttribute("aria-labelledby", trigger.id);
    menu.innerHTML = items().map(item => `${item.separator ? '<hr role="separator">' : ""}<button type="button" role="menuitemradio" aria-checked="${!!item.selected}" tabindex="-1" data-value="${esc(item.value)}" ${item.disabled ? "disabled" : ""}><span>${esc(item.label)}</span><span class="menu-check" aria-hidden="true">${item.selected ? ICON.check : ""}</span></button>`).join("");
    (trigger.closest("dialog[open], .modal, #overlay, .cms-body") || document.body).appendChild(menu);
    activeMenu = {trigger, menu, align, matchWidth};
    trigger.setAttribute("aria-expanded", "true");
    trigger.setAttribute("aria-controls", menu.id);
    positionMenu();
    menu.querySelectorAll("button").forEach(button => {
      button.addEventListener("pointermove", e => { if (e.pointerType === "mouse") button.focus({preventScroll: true}); });
      button.onclick = () => { const value = button.dataset.value; closeMenu(true); choose(value); };
    });
    const buttons = [...menu.querySelectorAll("button:not(:disabled)")];
    const selected = buttons.find(button => button.getAttribute("aria-checked") === "true");
    const initial = selected || (focusLast ? buttons.at(-1) : buttons[0]);
    initial?.focus({preventScroll: true});
    if (initial) menu.scrollTop = initial.offsetTop - (menu.clientHeight - initial.offsetHeight) / 2;
  }
  trigger.onclick = () => activeMenu?.trigger === trigger ? closeMenu(true) : open();
  trigger.onkeydown = e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); open(e.key === "ArrowUp"); }
  };
}
function enhanceSelect(select, label, field = false) {
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.id = select.id ? select.id + "-trigger" : "field-menu-" + ++menuSequence;
  for (const caption of Array.from(select.labels || [])) {
    if (caption.htmlFor === select.id && select.id) caption.htmlFor = trigger.id;
  }
  trigger.className = field ? "select-trigger field-trigger" : "pill-btn shadow select-trigger";
  trigger.setAttribute("aria-label", label);
  select.hidden = true;
  select.after(trigger);
  const valueLabel = document.createElement("span");
  valueLabel.id = trigger.id + "-value";
  trigger.setAttribute("aria-describedby", valueLabel.id);
  trigger.appendChild(valueLabel);
  trigger.insertAdjacentHTML("beforeend", ICON.caret);
  const update = () => {
    trigger.disabled = select.disabled;
    valueLabel.textContent = select.selectedOptions[0]?.textContent || "";
  };
  select.addEventListener("change", update); update();
  bindMenu(trigger, () => [...select.options].map(o => ({value: o.value, label: o.text, selected: o.selected, disabled: o.disabled})), value => {
    select.value = value; select.dispatchEvent(new Event("change", {bubbles: true}));
    document.getElementById(trigger.id)?.focus({preventScroll: true});
  }, {align: field ? "start" : "end", matchWidth: field});
  return update;
}
document.addEventListener("pointerdown", e => {
  if (activeMenu && !activeMenu.menu.contains(e.target) && !activeMenu.trigger.contains(e.target)) closeMenu();
}, true);
document.addEventListener("focusin", e => {
  if (activeMenu && !activeMenu.menu.contains(e.target) && !activeMenu.trigger.contains(e.target)) closeMenu();
});
window.addEventListener("resize", positionMenu);
window.visualViewport?.addEventListener("resize", positionMenu);
window.visualViewport?.addEventListener("scroll", positionMenu);
window.addEventListener("scroll", e => {
  if (!activeMenu || activeMenu.menu.contains(e.target)) return;
  // Focusing a mobile control can finish scrolling after the menu opens.
  // Follow the trigger while it is on screen instead of discarding the user's choice.
  const r = activeMenu.trigger.getBoundingClientRect();
  if (r.bottom <= 0 || r.top >= innerHeight) closeMenu();
  else positionMenu();
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
  if (next != null) {
    e.preventDefault(); e.stopImmediatePropagation(); focusOption(activeMenu.menu, buttons[next]);
  } else if (e.key.length === 1 && e.key.trim() && !e.altKey && !e.ctrlKey && !e.metaKey && !e.isComposing) {
    const now = performance.now();
    activeMenu.prefix = (now - (activeMenu.typedAt || 0) < 650 ? activeMenu.prefix || "" : "") + e.key.toLowerCase();
    activeMenu.typedAt = now;
    const match = buttons.find(button => button.textContent.trim().toLowerCase().startsWith(activeMenu.prefix));
    if (match) { e.preventDefault(); focusOption(activeMenu.menu, match); }
  }
}, true);
window.VisionMenu = {bindMenu, enhanceSelect, closeMenu, get active() { return activeMenu !== null; }};
})();
