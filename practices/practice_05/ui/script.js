(function(){
  const api = {
    async health(){ return fetch(`${API_BASE}/health`).then(r=>r.json()) },
    async list(){ return fetch(`${API_BASE}/subscribers`).then(r=>r.json()) },
    async subscribe(email,name){
      const res = await fetch(`${API_BASE}/subscribe`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({email,name:name||undefined})
      });
      if(res.status===201) return res.json();
      const err = await res.json().catch(()=>({detail:`HTTP ${res.status}`}));
      throw new Error(err.detail||'Subscribe failed');
    },
    async unsubscribe(email){
      const res = await fetch(`${API_BASE}/subscribers/${encodeURIComponent(email)}`,{method:'DELETE'});
      if(res.status===204) return;
      const errText = await res.text().catch(()=>`HTTP ${res.status}`);
      throw new Error(errText||'Unsubscribe failed');
    }
  };

  const els = {
    form: document.getElementById('form-subscribe'),
    email: document.getElementById('email'),
    name: document.getElementById('name'),
    btn: document.getElementById('btn-subscribe'),
    tbody: document.getElementById('subs-body'),
    toast: document.getElementById('toast')
  };

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
    items.forEach(item=>{
      const tr = document.createElement('tr');
      const tdEmail = document.createElement('td');
      const tdName = document.createElement('td');
      const tdActions = document.createElement('td');
      tdEmail.textContent = item.email || '';
      tdName.textContent = item.name || '';
      tdActions.className = 'row-actions';
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
      tr.appendChild(tdEmail); tr.appendChild(tdName); tr.appendChild(tdActions);
      els.tbody.appendChild(tr);
    });
  }

  async function refresh(){
    els.tbody.innerHTML = '<tr><td colspan="3">Загрузка…</td></tr>';
    try{
      const items = await api.list();
      renderList(items);
    }catch(e){
      els.tbody.innerHTML = `<tr><td colspan="3">Ошибка загрузки: ${e.message}</td></tr>`;
    }
  }

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
})();
