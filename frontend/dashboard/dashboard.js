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