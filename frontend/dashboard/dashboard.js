const profileButton = document.querySelector('.profile-button');
const profileMenu = document.querySelector('#profile-menu');
const searchToggle = document.querySelector('#search-toggle');
const searchPopover = document.querySelector('#dashboard-search');
const searchInput = document.querySelector('#dashboard-search-input');
const searchResults = document.querySelector('#search-results');
const notificationToggle = document.querySelector('#notification-toggle');
const notificationMenu = document.querySelector('#notification-menu');

const setPopoverOpen = (button, popover, isOpen) => {
  if (!button || !popover) {
    return;
  }
  popover.hidden = !isOpen;
  button.setAttribute('aria-expanded', String(isOpen));
};

const searchableElements = () => [
  ...document.querySelectorAll('#dashboard-content h2, #dashboard-content h3, #dashboard-content h4, #dashboard-content .kpi-card, #dashboard-content .hive-card, #dashboard-content .panel')
];

const renderSearchResults = (query) => {
  if (!searchResults) {
    return;
  }
  searchResults.innerHTML = '';
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return;
  }

  const matches = searchableElements()
    .filter((element) => element.textContent.toLowerCase().includes(normalizedQuery))
    .slice(0, 8);

  if (!matches.length) {
    searchResults.innerHTML = '<span class="search-empty">No matching dashboard items.</span>';
    return;
  }

  matches.forEach((element) => {
    const result = document.createElement('button');
    result.className = 'search-result';
    result.type = 'button';
    result.textContent = element.textContent.trim().replace(/\s+/g, ' ').slice(0, 80);
    result.addEventListener('click', () => {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setPopoverOpen(searchToggle, searchPopover, false);
    });
    searchResults.appendChild(result);
  });
};

if (searchToggle && searchPopover && searchInput) {
  searchToggle.addEventListener('click', () => {
    const isOpen = !searchPopover.hidden;
    setPopoverOpen(searchToggle, searchPopover, !isOpen);
    setPopoverOpen(notificationToggle, notificationMenu, false);
    if (isOpen) {
      searchInput.value = '';
      renderSearchResults('');
    } else {
      searchInput.focus();
    }
  });
  searchInput.addEventListener('input', () => renderSearchResults(searchInput.value));
}

if (notificationToggle && notificationMenu) {
  notificationToggle.addEventListener('click', () => {
    const isOpen = !notificationMenu.hidden;
    setPopoverOpen(notificationToggle, notificationMenu, !isOpen);
    setPopoverOpen(searchToggle, searchPopover, false);
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
    initializeHivePage();
    if (searchInput) {
      renderSearchResults(searchInput.value);
    }
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
    setPopoverOpen(searchToggle, searchPopover, false);
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
        <button class="remove-hive-button" type="button" data-hive-id="${hive.hive_id}">Remove</button>
      </article>`;
    }).join('') : '<p class="hive-empty">No hives match your search.</p>';
    summary.textContent = `${hives.length} registered hive${hives.length === 1 ? '' : 's'} · Updates every 10 seconds`;
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