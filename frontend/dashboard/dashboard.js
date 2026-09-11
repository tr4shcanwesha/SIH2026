const profileButton = document.querySelector('.profile-button');
const profileMenu = document.querySelector('#profile-menu');

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
const currentView = window.location.pathname.split('/').pop() || 'overview';

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

window.addEventListener('popstate', () => {
  const viewName = window.location.pathname.split('/').pop() || 'overview';
  loadDashboardView(viewName);
});