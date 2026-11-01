(function(){
  // API layer
  const api = {
    _authHeaders(){ return { 'X-Auth-User': 'ui-demo' }; },
    async health(){ return fetch(`${API_BASE}/health`).then(r=>r.json()) },
    async list(){ return fetch(`${API_BASE}/subscribers`, { headers: this._authHeaders() }).then(r=>r.json()) },
    async subscribe(email,name){
      const res = await fetch(`${API_BASE}/subscribe`,{
        method:'POST',headers:{'Content-Type':'application/json', ...this._authHeaders()},
        body:JSON.stringify({email,name:name||undefined})
      });
      if(res.status===201) return res.json();
      const err = await res.json().catch(()=>({detail:`HTTP ${res.status}`}));
      throw new Error(err.detail||'Subscribe failed');
    },
    async unsubscribe(email){
      const res = await fetch(`${API_BASE}/subscribers/${encodeURIComponent(email)}`,{method:'DELETE', headers: this._authHeaders()});
      if(res.status===204) return;
      const errText = await res.text().catch(()=>`HTTP ${res.status}`);
      throw new Error(errText||'Unsubscribe failed');
    },
    async searchUsers(q, page=1, pageSize=20){
      // server-backed search per spec; requests are abortable
      const params = new URLSearchParams({query: q, page: String(page), page_size: String(pageSize)});
      const url = `${API_BASE}/api/subscribers/search?${params.toString()}`;
      const res = await fetch(url, { signal: api._ctrl?.signal, headers: this._authHeaders() });
      if(!res.ok){ const txt = await res.text().catch(()=>`HTTP ${res.status}`); throw new Error(txt||'Search failed'); }
      return res.json();
    },
    _ctrl: null,
    abortPrev(){ if(api._ctrl){ api._ctrl.abort(); } api._ctrl = new AbortController(); return api._ctrl; }
  };

  // Elements
  const els = {
    form: document.getElementById('form-subscribe'),
    email: document.getElementById('email'),
    name: document.getElementById('name'),
    btn: document.getElementById('btn-subscribe'),
    tbody: document.getElementById('subs-body'),
    toast: document.getElementById('toast'),
    searchInput: document.getElementById('search-input'),
    searchClear: document.getElementById('search-clear'),
    counter: document.getElementById('results-counter'),
    empty: document.getElementById('empty-state'),
    pager: document.getElementById('pager'),
    pagePrev: document.getElementById('page-prev'),
    pageNext: document.getElementById('page-next'),
    pageInfo: document.getElementById('page-info')
  };

  // Helpers
  const normalizeQuery = (s)=> (s ?? '').trim();
  function debounce(fn, wait){ let t; return (...args)=>{ clearTimeout(t); t = setTimeout(()=>fn(...args), wait); }; }
  function setCounter(total, pageCount){
    if(!els.counter) return;
    if(total==null){ els.counter.textContent=''; return; }
    els.counter.textContent = `Всего: ${total}${pageCount!=null?` • На странице: ${pageCount}`:''}`;
  }
  function renderEmptyState(msg){ if(!els.empty) return; els.empty.style.display='block'; els.empty.textContent = msg; }
  function clearEmptyState(){ if(!els.empty) return; els.empty.style.display='none'; els.empty.textContent=''; }

  function toast(msg, ok=true){
    els.toast.style.display='block';
    els.toast.textContent = msg;
    els.toast.style.background = ok ? '#e5f6ff' : '#fee2e2';
    els.toast.style.color = ok ? '#0369a1' : '#991b1b';
    els.toast.style.borderColor = ok ? '#bae6fd' : '#fecaca';
    setTimeout(()=>{els.toast.style.display='none'}, 3000);
  }

  function renderList(items){
    if(!Array.isArray(items) || items.length===0){
      els.tbody.innerHTML = '<tr><td colspan="3">Список пуст</td></tr>';
      return;
    }
    els.tbody.innerHTML = '';
    // Adjust headers based on data type
    const col1Header = document.getElementById('col1-header');
    const col2Header = document.getElementById('col2-header');
    const col3Header = document.getElementById('col3-header');
    const first = items[0] || {};
    const isSearchMode = 'username' in first && !('email' in first);
    if(col1Header && col2Header){
      if(isSearchMode){
        col1Header.textContent = 'Ник';
        col2Header.textContent = '';
        if(col3Header) col3Header.textContent = '';
      }else{
        col1Header.textContent = 'Email';
        col2Header.textContent = 'Имя';
        if(col3Header) col3Header.textContent = '';
      }
    }
    items.forEach(item=>{
      const tr = document.createElement('tr');
      const tdCol1 = document.createElement('td');
      const tdCol2 = document.createElement('td');
      const tdActions = document.createElement('td');
      tdActions.className = 'row-actions';
      // Detect mode by presence of fields
      const isSearchItem = 'username' in item && !('email' in item);
      if(isSearchItem){
        tdCol1.textContent = item.username || '';
        tdCol2.textContent = '';
        tdActions.textContent = '';
      }else{
        tdCol1.textContent = item.email || '';
        tdCol2.textContent = item.name || '';
        const btnDel = document.createElement('button');
        btnDel.textContent = 'Удалить';
        btnDel.addEventListener('click', async ()=>{
          if(!confirm(`Удалить подписчика ${item.email}?`)) return;
          try{
            await api.unsubscribe(item.email);
            toast('Удалено');
            await refresh();
          }catch(e){ toast(e.message,false); }
        });
        tdActions.appendChild(btnDel);
      }
      tr.appendChild(tdCol1); tr.appendChild(tdCol2); tr.appendChild(tdActions);
      els.tbody.appendChild(tr);
    });
  }

  async function refresh(){
    els.tbody.innerHTML = '<tr><td colspan="3">Загрузка…</td></tr>';
    try{
      const items = await api.list();
      // Do not overwrite search results if a valid search query is active
      const activeQ = (els.searchInput && (els.searchInput.value||'').trim()) || '';
      if(activeQ.length >= 2){
        // skip applying full list while search is active
        return;
      }
      renderList(items);
    }catch(e){
      els.tbody.innerHTML = `<tr><td colspan="3">Ошибка загрузки: ${e.message}</td></tr>`;
    }
  }

  // Search flow (server-backed per spec)
  let currentPage = 1;
  let lastQuery = '';

  async function runSearch(q, page=1){
    const trimmed = normalizeQuery(q).slice(0, 100);
    if(trimmed.length < 2){
      // reset to full list when query too short or empty
      clearEmptyState();
      setCounter(null);
      if(els.pager) els.pager.style.display='none';
      lastQuery=''; currentPage=1;
      await refresh();
      return;
    }
    // cancel previous
    api.abortPrev();
    try{
      const data = await api.searchUsers(trimmed, page, 20);
      const items = data.items || [];
      clearEmptyState();
      renderList(items);
      setCounter(data.total, items.length);
      // pager
      const totalPages = Math.max(1, Math.ceil((data.total||0) / (data.page_size||items.length||20)));
      currentPage = data.page || page || 1;
      lastQuery = trimmed;
      if(els.pager){
        els.pager.style.display = totalPages>1 ? 'flex' : 'none';
        els.pagePrev.disabled = currentPage<=1;
        els.pageNext.disabled = currentPage>=totalPages;
        els.pageInfo.textContent = `Стр. ${currentPage} из ${totalPages}`;
      }
      if(items.length===0){ renderEmptyState('Совпадений не найдено. Измените запрос или очистите фильтр.'); }
    }catch(e){
      // On error, show message but keep list
      renderEmptyState(`Ошибка поиска: ${e.message}`);
    }
  }

  const debouncedSearch = debounce((q)=>{ runSearch(q, 1); }, 300);

  function clearSearch(){ if(!els.searchInput) return; els.searchInput.value=''; setCounter(null); clearEmptyState(); runSearch('',1); }

  // Subscribe form
  els.form.addEventListener('submit', async (ev)=>{
    ev.preventDefault();
    const email = els.email.value.trim();
    const name = els.name.value.trim();
    if(!email){ toast('Введите Email', false); return; }
    els.btn.disabled = true;
    try{
      await api.subscribe(email, name);
      toast('Подписка добавлена');
      els.email.value=''; els.name.value='';
      await refresh();
    }catch(e){ toast(e.message,false); }
    finally{ els.btn.disabled=false; }
  });

  // Initial load
  refresh();

  // Event wiring - search
  if(els.searchInput){
    els.searchInput.addEventListener('input', (e)=>{
      const val = e.target.value;
      debouncedSearch(val);
    });
    els.searchInput.addEventListener('keydown', (e)=>{
      if(e.key==='Escape'){ e.stopPropagation(); clearSearch(); els.searchInput.focus(); }
    });
  }
  if(els.searchClear){
    els.searchClear.addEventListener('click', ()=>{ clearSearch(); els.searchInput && els.searchInput.focus(); });
  }
  if(els.pagePrev){
    els.pagePrev.addEventListener('click', ()=>{ if(currentPage>1){ runSearch(lastQuery, currentPage-1); } });
  }
  if(els.pageNext){
    els.pageNext.addEventListener('click', ()=>{ runSearch(lastQuery, currentPage+1); });
  }
  // Global Esc fallback to clear when search has value
  document.addEventListener('keydown', (e)=>{
    if(e.key==='Escape' && els.searchInput && els.searchInput.value){ clearSearch(); }
  });
})();
