const profileButton = document.querySelector('.profile-button');
const profileMenu = document.querySelector('#profile-menu');
const notificationToggle = document.querySelector('#notification-toggle');
const notificationMenu = document.querySelector('#notification-menu');
let harvestBatches = [];
const harvestCooldownMs = 60 * 1000;
const harvestCooldownStorageKey = 'honeychain-harvest-cooldowns';
const harvestOrderStorageKey = 'honeychain-harvest-order';

const getHarvestCooldowns = () => {
  try {
    return JSON.parse(window.sessionStorage.getItem(harvestCooldownStorageKey) || '{}');
  } catch (error) {
    console.error('Unable to read harvest cooldowns:', error);
    return {};
  }
};

const saveHarvestCooldowns = (cooldowns) => {
  window.sessionStorage.setItem(harvestCooldownStorageKey, JSON.stringify(cooldowns));
};

const getHarvestOrder = () => {
  try {
    return JSON.parse(window.sessionStorage.getItem(harvestOrderStorageKey) || '[]');
  } catch (error) {
    console.error('Unable to read harvest order:', error);
    return [];
  }
};

const saveHarvestOrder = (order) => {
  window.sessionStorage.setItem(harvestOrderStorageKey, JSON.stringify(order));
};

const loadDashboardProfile = async () => {
  const response = await fetch('/api/profile');
  if (!response.ok) return;
  const payload = await response.json();
  const welcome = document.querySelector('#dashboard-welcome');
  if (welcome) welcome.textContent = `Welcome back ${payload.beekeeper.name}`;
};

const renderDynamicTimes = () => {
  document.querySelectorAll('[data-sync-now]').forEach((element) => {
    element.textContent = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' }).format(new Date());
  });
  document.querySelectorAll('[data-relative-minutes]').forEach((element) => {
    const minutes = Number(element.dataset.relativeMinutes);
    element.textContent = minutes < 60
      ? `${minutes} minutes ago`
      : minutes < 1440
        ? `${Math.floor(minutes / 60)} hours ago`
        : `${Math.floor(minutes / 1440)} days ago`;
  });
};

renderDynamicTimes();
loadDashboardProfile().catch(() => {});

const loadHarvestBatches = async () => {
  const response = await fetch('/api/honey-batches');
  if (!response.ok) {
    throw new Error('Unable to load harvest batches.');
  }
  const fetchedBatches = await response.json();
  const fetchedById = new Map(fetchedBatches.map((batch) => [batch.batch_id, batch]));
  const storedOrder = getHarvestOrder().filter((batchId) => fetchedById.has(batchId));
  const newBatchIds = fetchedBatches
    .map((batch) => batch.batch_id)
    .filter((batchId) => !storedOrder.includes(batchId));
  const order = [...newBatchIds, ...storedOrder];
  saveHarvestOrder(order);
  harvestBatches = order.map((batchId) => fetchedById.get(batchId));
};

const addHarvestBatch = async (harvestButton) => {
  const response = await fetch('/api/honey-batches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      hive_id: harvestButton.dataset.harvestHive,
      honey_type: harvestButton.dataset.honeyType || 'Wild Forest Honey',
      quantity: Number(harvestButton.dataset.quantity || 0),
    }),
  });
  if (!response.ok) {
    throw new Error('Honey batch could not be created.');
  }

  const batch = await response.json();
  await loadHarvestBatches();
};

const startHarvestCooldown = (harvestButton) => {
  const cooldownEndsAt = Date.now() + harvestCooldownMs;
  const cooldowns = getHarvestCooldowns();
  cooldowns[harvestButton.dataset.harvestHive] = cooldownEndsAt;
  saveHarvestCooldowns(cooldowns);
  harvestButton.disabled = true;
  harvestButton.textContent = 'Harvested';
};

const restoreHarvestCooldown = (harvestButton) => {
  const hiveId = harvestButton.dataset.harvestHive;
  const cooldowns = getHarvestCooldowns();
  const cooldownEndsAt = Number(cooldowns[hiveId] || 0);

  if (cooldownEndsAt <= Date.now()) {
    if (cooldowns[hiveId]) {
      delete cooldowns[hiveId];
      saveHarvestCooldowns(cooldowns);
    }
    return;
  }

  harvestButton.disabled = true;
  harvestButton.textContent = 'Harvested';
  window.setTimeout(() => {
    const currentCooldowns = getHarvestCooldowns();
    if (Number(currentCooldowns[hiveId] || 0) <= Date.now()) {
      delete currentCooldowns[hiveId];
      saveHarvestCooldowns(currentCooldowns);
      harvestButton.disabled = false;
      harvestButton.textContent = 'Harvest';
    }
  }, cooldownEndsAt - Date.now());
};

const renderHarvestBatches = () => {
  const harvestList = document.querySelector('#harvest-list');
  const harvestSummary = document.querySelector('#harvest-summary');
  if (!harvestList) {
    return;
  }

  const progressByStatus = { HARVESTED: 25, PROCESSED: 70, DISTRIBUTED: 100 };
  const labelByStatus = { HARVESTED: 'HARVESTED', PROCESSED: 'PROCESSED', DISTRIBUTED: 'DISTRIBUTED' };
  const batches = harvestBatches;
  harvestList.innerHTML = batches.length ? batches.map((batch) => {
    const batchStatus = String(batch.status).toUpperCase();
    const progress = progressByStatus[batchStatus] || 25;
    const nextAction = batchStatus === 'HARVESTED'
      ? `<button class="harvest-action-button" type="button" data-process-batch="${batch.batch_id}">Process</button>`
      : batchStatus === 'PROCESSED'
        ? `<button class="harvest-action-button" type="button" data-distribute-batch="${batch.batch_id}">Distribute</button>`
        : '<span class="status-pill pill-good">Complete</span>';
    return `
      <article class="harvest-card">
        <div class="harvest-card-head">
          <div><h3>${batch.hive_id}</h3><p>Batch ${batch.batch_id} · created ${new Date(batch.harvest_date).toLocaleDateString()}</p></div>
          <span class="status-pill ${batchStatus === 'DISTRIBUTED' ? 'pill-good' : 'pill-warn'}">${labelByStatus[batchStatus]}</span>
        </div>
        <div class="harvest-progress-meta"><span>Progress</span><b>${progress}%</b></div>
        <div class="harvest-progress"><span style="width:${progress}%"></span></div>
        <div class="batch-qr-row">
          <div class="batch-qr" data-qr-url="${batch.verification_url || `/verify/${batch.batch_id}`}"></div>
          <a class="batch-qr-link" href="${batch.verification_url || `/verify/${batch.batch_id}`}" target="_blank" rel="noreferrer">Verify this batch</a>
        </div>
        <div class="harvest-card-action">${nextAction}</div>
      </article>`;
  }).join('') : '<p class="hive-empty">No harvest batches yet. Use Harvest on a hive to create one.</p>';
  if (harvestSummary) {
    harvestSummary.textContent = `${batches.length} batch${batches.length === 1 ? '' : 'es'}`;
  }
  document.querySelectorAll('.batch-qr').forEach((element) => {
    if (window.QRCode && !element.hasChildNodes()) {
      new window.QRCode(element, {
        text: element.dataset.qrUrl,
        width: 88,
        height: 88,
        colorDark: '#2A1B0F',
        colorLight: '#FFFBF3',
        correctLevel: window.QRCode.CorrectLevel.M,
      });
    }
  });
};

const initializeHarvestPage = () => {
  const harvestList = document.querySelector('#harvest-list');
  if (!harvestList || harvestList.dataset.initialized === 'true') {
    renderHarvestBatches();
    return;
  }
  harvestList.dataset.initialized = 'true';
  harvestList.addEventListener('click', async (event) => {
    const processButton = event.target.closest('[data-process-batch]');
    const distributeButton = event.target.closest('[data-distribute-batch]');
    const batchId = processButton?.dataset.processBatch || distributeButton?.dataset.distributeBatch;
    if (!batchId) {
      return;
    }
    const nextStatus = processButton ? 'PROCESSED' : 'DISTRIBUTED';
    const actionButton = processButton || distributeButton;
    actionButton.disabled = true;
    try {
      const response = await fetch(`/api/honey-batches/${encodeURIComponent(batchId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!response.ok) {
        throw new Error('Honey batch status could not be updated.');
      }
      await loadHarvestBatches();
      renderHarvestBatches();
    } catch (error) {
      console.error('Failed to update honey batch status:', error);
      actionButton.disabled = false;
    }
  });
  loadHarvestBatches()
    .then(renderHarvestBatches)
    .catch((error) => {
      harvestList.innerHTML = `<p class="hive-empty">${error.message}</p>`;
    });
};

document.addEventListener('click', async (event) => {
  const harvestButton = event.target.closest('[data-harvest-hive]');
  if (!harvestButton) {
    return;
  }
  harvestButton.disabled = true;
  harvestButton.textContent = 'Saving...';
  try {
    await addHarvestBatch(harvestButton);
    startHarvestCooldown(harvestButton);
  } catch (error) {
    console.error('Failed to create honey batch:', error);
    harvestButton.disabled = false;
    harvestButton.textContent = 'Harvest';
  }
});


const setPopoverOpen = (button, popover, isOpen) => {
  if (!button || !popover) {
    return;
  }
  popover.hidden = !isOpen;
  button.setAttribute('aria-expanded', String(isOpen));
};

if (notificationToggle && notificationMenu) {
  notificationToggle.addEventListener('click', () => {
    const isOpen = !notificationMenu.hidden;
    setPopoverOpen(notificationToggle, notificationMenu, !isOpen);
  });

  document.addEventListener('click', (event) => {
    if (!notificationToggle.contains(event.target) && !notificationMenu.contains(event.target)) {
      setPopoverOpen(notificationToggle, notificationMenu, false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setPopoverOpen(notificationToggle, notificationMenu, false);
    }
  });
}

if (profileButton && profileMenu) {
  const closeProfileMenu = () => {
    profileMenu.hidden = true;
    profileButton.setAttribute('aria-expanded', 'false');
  };

  profileButton.addEventListener('click', () => {
    const isOpen = !profileMenu.hidden;
    profileMenu.hidden = isOpen;
    profileButton.setAttribute('aria-expanded', String(!isOpen));
  });

  document.addEventListener('click', (event) => {
    if (!profileButton.contains(event.target) && !profileMenu.contains(event.target)) {
      closeProfileMenu();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeProfileMenu();
      profileButton.focus();
    }
  });
}

const dashboardSections = document.querySelectorAll('.dash-side > .side-link');
const dashboardContent = document.querySelector('#dashboard-content');
const currentPath = window.location.pathname.replace(/\/+$/, '');
const currentView = currentPath === '/dashboard'
  ? 'overview'
  : currentPath.split('/').pop() || 'overview';

dashboardSections.forEach((item) =>
  item.classList.toggle('active', item.dataset.view === currentView)
);

const loadDashboardView = async (viewName, updateHistory = false) => {
  if (!dashboardContent) {
    return;
  }

  const section = [...dashboardSections].find(
    (item) => item.dataset.view === viewName
  );

  const route = viewName === 'overview'
    ? '/dashboard'
    : `/dashboard/${viewName}`;

  if (!section) {
    window.location.href = '/dashboard';
    return;
  }

  dashboardSections.forEach((item) =>
    item.classList.toggle('active', item === section)
  );

  try {
    const response = await fetch(route);

    if (!response.ok) {
      window.location.href = route;
      return;
    }

    const html = await response.text();

    // Parse the fetched HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // Extract ONLY the dashboard content
    const newContent = doc.querySelector('#dashboard-content');

    if (!newContent) {
      window.location.href = route;
      return;
    }

    dashboardContent.innerHTML = newContent.innerHTML;
    renderDynamicTimes();
    loadDashboardProfile().catch(() => {});
    initializeHivePage();
    initializeHarvestPage();
    if (updateHistory) {
      window.history.pushState({ viewName }, '', route);
    }

  } catch (error) {
    console.error('Failed to load dashboard view:', error);
    window.location.href = route;
  }
};

dashboardSections.forEach((section) => {
  section.addEventListener('click', (event) => {
    event.preventDefault();
    loadDashboardView(section.dataset.view, true);
  });
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    setPopoverOpen(notificationToggle, notificationMenu, false);
  }
});

window.addEventListener('popstate', () => {
  const viewName = window.location.pathname.split('/').pop() || 'overview';
  loadDashboardView(viewName);
});

const initializeHivePage = () => {
  const hiveList = document.querySelector('#hive-list');
  const searchInput = document.querySelector('#hive-search-input');
  const summary = document.querySelector('#hive-summary');
  const addForm = document.querySelector('#add-hive-form');
  const openButton = document.querySelector('#open-add-hive');
  const cancelButton = document.querySelector('#cancel-add-hive');
  const formStatus = document.querySelector('#hive-form-status');

  if (!hiveList || !searchInput || !addForm) return;
  let hives = [];

  const renderHives = () => {
    const query = searchInput.value.trim().toLowerCase();
    const visibleHives = hives.filter((hive) =>
      [hive.hive_id, hive.location, hive.bee_species, hive.hive_type, hive.status]
        .some((value) => String(value || '').toLowerCase().includes(query))
    );
    hiveList.innerHTML = visibleHives.length ? visibleHives.map((hive) => {
      const statusClass = hive.status === 'Healthy' ? 'pill-good' : hive.status === 'Inactive' ? 'pill-inactive' : 'pill-warn';
      const metric = (label, value) => `<div class="hive-metric"><span>${label}</span><b>${value || 'No data'}</b></div>`;
      return `
      <article class="hive-list-item">
        <div class="hive-list-main">
          <div class="hive-mark" aria-hidden="true">H</div>
          <div><h3>${hive.hive_id}</h3><span class="hive-location">At ${hive.location}</span><p>${hive.notes || 'Live hive monitoring is active for this hive.'}</p></div>
        </div>
        <div class="hive-metrics">
          ${metric('Temperature', hive.temperature ? `${hive.temperature}°C` : null)}
          ${metric('Humidity', hive.humidity ? `${hive.humidity}%` : null)}
          ${metric('Weight', hive.weight ? `${hive.weight} kg` : null)}
          ${metric('Acoustic index', hive.acoustic_index || 'No data')}
        </div>
        <div class="hive-list-meta"><span>Installed</span><b>${hive.installation_date}</b><span>Species</span><b>${hive.bee_species}</b></div>
        <span class="status-pill ${statusClass}">${hive.status}</span>
        <div class="hive-actions">
          <button class="harvest-button" type="button" data-harvest-hive="${hive.hive_id}" data-honey-type="Wild Forest Honey" data-quantity="${hive.weight || 1}">Harvest</button>
          <button class="remove-hive-button" type="button" data-hive-id="${hive.hive_id}">Remove</button>
        </div>
      </article>`;
    }).join('') : '<p class="hive-empty">No hives match your search.</p>';
    summary.textContent = `${hives.length} registered hive${hives.length === 1 ? '' : 's'} · Updates every 10 seconds`;
    hiveList.querySelectorAll('[data-harvest-hive]').forEach(restoreHarvestCooldown);
  };

  const loadHives = async () => {
    const response = await fetch('/api/hives');
    if (!response.ok) throw new Error('Unable to load hives.');
    hives = await response.json();
    renderHives();
  };

  searchInput.addEventListener('input', renderHives);
  hiveList.addEventListener('click', async (event) => {
    const removeButton = event.target.closest('.remove-hive-button');
    if (!removeButton) return;

    const hiveId = removeButton.dataset.hiveId;
    if (!window.confirm(`Remove hive ${hiveId}?`)) return;

    removeButton.disabled = true;
    removeButton.textContent = 'Removing...';
    const response = await fetch(`/api/hives/${encodeURIComponent(hiveId)}`, { method: 'DELETE' });
    if (!response.ok) {
      removeButton.disabled = false;
      removeButton.textContent = 'Remove';
      return;
    }
    await loadHives();
  });
  openButton?.addEventListener('click', () => { addForm.hidden = false; openButton.hidden = true; });
  cancelButton?.addEventListener('click', () => { addForm.reset(); addForm.hidden = true; openButton.hidden = false; });
  addForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    formStatus.textContent = 'Saving hive...';
    const payload = Object.fromEntries(new FormData(addForm));
    const response = await fetch('/api/hives', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
    if (!response.ok) { formStatus.textContent = 'Hive could not be saved.'; return; }
    addForm.reset(); addForm.hidden = true; openButton.hidden = false; formStatus.textContent = '';
    await loadHives();
  });
  loadHives().catch((error) => { summary.textContent = error.message; });
  window.clearInterval(window.hiveRefreshTimer);
  window.hiveRefreshTimer = window.setInterval(() => loadHives().catch(() => {}), 10000);
};

initializeHivePage();
initializeHarvestPage();