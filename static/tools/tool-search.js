const {icon} = window.VisionSite;
/* Shared, monochrome keyword field for the directory and model boards. */
export function toolSearch(label, placeholder, initial, onInput) {
  const field = document.createElement('div');
  field.className = 'ai-search';
  const input = document.createElement('input');
  input.type = 'text';
  input.setAttribute('role', 'searchbox');
  input.setAttribute('enterkeyhint', 'search');
  input.setAttribute('aria-label', label);
  input.placeholder = placeholder;
  input.value = initial || '';
  const clear = document.createElement('button');
  clear.type = 'button';
  clear.className = 'ai-search-clear';
  clear.title = '清除搜索';
  clear.setAttribute('aria-label', '清除搜索');
  clear.innerHTML = icon('close');
  const sync = () => { clear.hidden = !input.value; };
  function change() { sync(); onInput(input.value); }
  function reset() { input.value = ''; change(); input.focus({preventScroll:true}); }
  clear.onclick = reset;
  input.oninput = change;
  input.onkeydown = e => {
    if (e.key === 'Escape' && !e.isComposing && input.value) { e.preventDefault(); reset(); }
  };
  sync();
  field.append(input, clear);
  return {field, input, sync};
}
