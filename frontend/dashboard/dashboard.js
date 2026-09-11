const profileButton = document.querySelector('.profile-button');
const profileMenu = document.querySelector('#profile-menu');
const notificationToggle = document.querySelector('#notification-toggle');
const notificationMenu = document.querySelector('#notification-menu');

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