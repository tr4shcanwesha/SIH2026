const profileButton = document.querySelector('.profile-button');
const profileMenu = document.querySelector('#profile-menu');
const notificationToggle = document.querySelector('#notification-toggle');
const notificationMenu = document.querySelector('#notification-menu');
let harvestBatches = [];
let harvestHives = new Map();
let harvestCarouselOffset = 0;
let harvestCarouselCurrent = 0;
let harvestCarouselDragging = false;
let harvestCarouselPointerStart = 0;
let harvestCarouselStartIndex = 0;
let harvestCarouselPointerMoved = false;
let harvestCarouselAnimating = false;
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
  const [batchResponse, hiveResponse] = await Promise.all([
    fetch('/api/honey-batches'),
    fetch('/api/hives'),
  ]);
  if (!batchResponse.ok || !hiveResponse.ok) {
    throw new Error('Unable to load harvest batches.');
  }
  const fetchedBatches = await batchResponse.json();
  const fetchedHives = await hiveResponse.json();
  harvestHives = new Map(fetchedHives.map((hive) => [hive.hive_id, hive]));
  const fetchedById = new Map(fetchedBatches.map((batch) => [batch.batch_id, batch]));
  const storedOrder = getHarvestOrder().filter((batchId) => fetchedById.has(batchId));
  const newBatchIds = fetchedBatches
    .map((batch) => batch.batch_id)
    .filter((batchId) => !storedOrder.includes(batchId));
  const order = [...newBatchIds, ...storedOrder];
  saveHarvestOrder(order);
  harvestBatches = order.map((batchId) => fetchedById.get(batchId));
  harvestCarouselOffset = Math.min(
    harvestCarouselOffset,
    Math.max(0, harvestBatches.length - 1)
  );
  harvestCarouselCurrent = harvestCarouselOffset;
};

const showHarvestToast = (message) => {
  const toast = document.querySelector('#harvest-toast');
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(window.harvestToastTimer);
  window.harvestToastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 3000);
};

const addHarvestBatch = (harvestButton) => new Promise((resolve) => {
  const modal = document.querySelector('#harvest-entry-modal');
  const form = document.querySelector('#harvest-entry-form');
  const quantityInput = document.querySelector('#harvest-quantity');
  const honeyTypeInput = document.querySelector('#harvest-honey-type');
  const error = document.querySelector('#harvest-entry-error');
  const submitButton = form?.querySelector('.harvest-entry-submit');
  if (!modal || !form || !quantityInput || !honeyTypeInput || !error || !submitButton) {
    resolve(false);
    return;
  }

  quantityInput.value = '';
  honeyTypeInput.value = '';
  error.textContent = '';
  modal.hidden = false;
  document.body.classList.add('harvest-entry-modal-open');
  quantityInput.focus();

  const finish = (result) => {
    form.removeEventListener('submit', submit);
    modal.querySelectorAll('[data-close-harvest-entry]').forEach((element) => {
      element.removeEventListener('click', close);
    });
    modal.hidden = true;
    document.body.classList.remove('harvest-entry-modal-open');
    resolve(result);
  };
  const close = () => finish(false);
  const submit = async (event) => {
    event.preventDefault();
    const quantity = Number(quantityInput.value);
    const honeyType = honeyTypeInput.value.trim();
    if (!Number.isFinite(quantity) || quantity <= 0) {
      error.textContent = 'Quantity must be a positive number.';
      quantityInput.focus();
      return;
    }
    if (!honeyType) {
      error.textContent = 'Honey type is required.';
      honeyTypeInput.focus();
      return;
    }
    submitButton.disabled = true;
    error.textContent = '';
    try {
      const response = await fetch('/api/honey-batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hive_id: harvestButton.dataset.harvestHive,
          honey_type: honeyType,
          quantity,
        }),
      });
      if (!response.ok) {
        throw new Error('Honey batch could not be created.');
      }
      await response.json();
      await loadHarvestBatches();
      finish(true);
      showHarvestToast('Harvest saved successfully.');
    } catch (requestError) {
      console.error('Failed to create honey batch:', requestError);
      error.textContent = requestError.message;
      submitButton.disabled = false;
    }
  };
  form.addEventListener('submit', submit);
  modal.querySelectorAll('[data-close-harvest-entry]').forEach((element) => {
    element.addEventListener('click', close);
  });
});

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
  const featuredList = document.querySelector('#harvest-featured');
  if (!harvestList) {
    return;
  }

  const progressByStatus = { HARVESTED: 25, PROCESSED: 70, DISTRIBUTED: 100 };
  const labelByStatus = { HARVESTED: 'HARVESTED', PROCESSED: 'PROCESSED', DISTRIBUTED: 'DISTRIBUTED' };
  const batches = harvestBatches;
  const statusClass = {
    HARVESTED: 'status-harvested',
    PROCESSED: 'status-processed',
    DISTRIBUTED: 'status-distributed',
  };
  const batchStatusMarkup = (batchStatus) => `
    <span class="harvest-status ${statusClass[batchStatus] || 'status-harvested'}">
      <span class="harvest-status-dot"></span>${labelByStatus[batchStatus] || batchStatus}
    </span>`;
  const actionMarkup = (batch, batchStatus) => batchStatus === 'HARVESTED'
    ? `<button class="harvest-reference-action action-amber" type="button" data-process-batch="${batch.batch_id}">Mark Processed <span>›</span></button>`
    : batchStatus === 'PROCESSED'
      ? `<button class="harvest-reference-action action-outline" type="button" data-distribute-batch="${batch.batch_id}">Mark Distributed <span>›</span></button>`
      : '<button class="harvest-reference-action action-done" type="button" disabled>Completed <span>✓</span></button>';
  const batchMarkup = (batch) => {
    const batchStatus = String(batch.status).toUpperCase();
    const progress = progressByStatus[batchStatus] || 25;
    const verificationUrl = batch.verification_url || `${window.location.origin}/verify/${batch.batch_id}`;
    return `
      <article class="harvest-reference-row harvest-card">
        <div class="harvest-reference-id">
          <div class="harvest-reference-hex"><img src="/assets/dashboard/hive.png" alt="Hive"></div>
          <div><strong>${batch.hive_id}</strong><small>Batch ${batch.batch_id} · created ${new Date(batch.harvest_date).toLocaleDateString()}</small></div>
        </div>
        <div class="batch-verification">
          <div class="batch-qr" data-qr-url="${verificationUrl}" aria-label="Verification QR code"></div>
          ${batchStatusMarkup(batchStatus)}
          <a class="batch-verify-button" href="${verificationUrl}">Verify this batch</a>
        </div>
        <div class="harvest-reference-progress">
          <div class="harvest-reference-track"><span class="progress-${batchStatus.toLowerCase()}" style="width:${progress}%"></span></div>
          <small>${progress}%</small>
        </div>
        ${actionMarkup(batch, batchStatus)}
        <button class="harvest-more-button" type="button" aria-label="More batch options">⋮</button>
      </article>
      `;
  };
  harvestList.innerHTML = batches.length
    ? batches.map(batchMarkup).join('')
    : '<p class="hive-empty">No harvest batches yet. Use Harvest on a hive to create one.</p>';
  if (featuredList) {
    const carouselCardMarkup = (batch, index) => {
      const batchStatus = String(batch.status).toUpperCase();
      const imageByStatus = {
        HARVESTED: 'harvest',
        PROCESSED: 'processed',
        DISTRIBUTED: 'distributed',
      };
      const statusImage = imageByStatus[batchStatus] || 'harvest';
      const hive = harvestHives.get(batch.hive_id) || {};
      return `<article class="harvest-featured-card" data-carousel-index="${index}" tabindex="0">
        <div class="harvest-card-icon"><img src="/assets/dashboard/hive.png" alt="Hive"></div>
        <div class="harvest-card-body">
          ${batchStatusMarkup(batchStatus)}
          <h3>${batch.hive_id}</h3>
          <small>Location <b>${hive.location || 'Not available'}</b></small>
          <small>Species <b>${hive.bee_species || 'Not available'}</b></small>
          <small>Hive type <b>${hive.hive_type || 'Not available'}</b></small>
          <small>Harvested <b>${new Date(batch.harvest_date).toLocaleDateString()}</b></small>
        </div>
        <div class="harvest-card-thumb"><img src="/assets/dashboard/${statusImage}.png" alt="${batchStatus}"></div>
      </article>`;
    };
    featuredList.innerHTML = batches.length ? `
      <div class="harvest-carousel">
        <button class="harvest-carousel-arrow" type="button" data-carousel-direction="-1" aria-label="Show previous batches" ${batches.length < 2 ? 'disabled' : ''}>‹</button>
        <div class="harvest-carousel-viewport">
          <div class="harvest-featured-cards">
            ${batches.map((batch, index) => carouselCardMarkup(batch, index)).join('')}
          </div>
        </div>
        <button class="harvest-carousel-arrow" type="button" data-carousel-direction="1" aria-label="Show next batches" ${batches.length < 2 ? 'disabled' : ''}>›</button>
      </div>` : '';
    featuredList.querySelectorAll('[data-carousel-direction]').forEach((arrow) => {
      arrow.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        moveHarvestCarousel(Number(arrow.dataset.carouselDirection));
      });
    });
  }
  renderHarvestCarousel();
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
  document.querySelectorAll('.batch-qr').forEach((element) => {
    element.setAttribute('role', 'button');
    element.setAttribute('tabindex', '0');
    element.addEventListener('click', () => openQrLightbox(element));
    element.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openQrLightbox(element);
      }
    });
  });
};

const openQrLightbox = (qrElement) => {
  const qrLightbox = document.querySelector('#qr-lightbox');
  const qrImage = document.querySelector('#qr-lightbox-image');
  const qrCanvas = qrElement.querySelector('canvas');
  const qrSource = qrCanvas?.toDataURL('image/png') || qrElement.querySelector('img')?.src;
  if (!qrLightbox || !qrImage || !qrSource) {
    return;
  }
  qrImage.src = qrSource;
  qrLightbox.hidden = false;
  document.body.classList.add('qr-lightbox-open');
};

const closeQrLightbox = () => {
  const qrLightbox = document.querySelector('#qr-lightbox');
  if (!qrLightbox) {
    return;
  }
  qrLightbox.hidden = true;
  document.body.classList.remove('qr-lightbox-open');
};

const renderHarvestCarousel = () => {
  const viewport = document.querySelector('.harvest-carousel-viewport');
  const track = document.querySelector('.harvest-featured-cards');
  if (!viewport || !track || !harvestBatches.length) {
    return;
  }

  const spacing = viewport.clientWidth < 560
    ? Math.max(190, viewport.clientWidth * 0.62)
    : 300;
  track.querySelectorAll('.harvest-featured-card').forEach((card, index) => {
    const difference = ((index - harvestCarouselCurrent) % harvestBatches.length + harvestBatches.length) % harvestBatches.length;
    const signedDifference = difference > harvestBatches.length / 2
      ? difference - harvestBatches.length
      : difference;
    const absoluteDifference = Math.abs(signedDifference);
    const scale = Math.max(.72, 1 - absoluteDifference * .16);
    const opacity = Math.max(0, 1 - absoluteDifference * .42);
    card.style.transform = `translate(${signedDifference * spacing}px, -50%) scale(${scale})`;
    card.style.opacity = opacity;
    card.style.zIndex = String(Math.round(100 - absoluteDifference * 10));
    card.classList.toggle('carousel-active', absoluteDifference < .5);
    card.classList.toggle('carousel-dragging', harvestCarouselDragging);
    card.style.pointerEvents = absoluteDifference < 1.5 ? 'auto' : 'none';
  });
};

const moveHarvestCarousel = (direction) => {
  if (harvestBatches.length < 2 || harvestCarouselAnimating) {
    return;
  }
  const track = document.querySelector('.harvest-featured-cards');
  if (!track) {
    return;
  }
  harvestCarouselAnimating = true;
  harvestCarouselDragging = false;
  const startIndex = Math.round(harvestCarouselCurrent);
  const targetIndex = startIndex + direction;
  harvestCarouselCurrent = startIndex;
  renderHarvestCarousel();
  track.offsetWidth;
  window.requestAnimationFrame(() => {
    harvestCarouselCurrent = targetIndex;
    harvestCarouselOffset = ((targetIndex % harvestBatches.length) + harvestBatches.length) % harvestBatches.length;
    renderHarvestCarousel();
    window.setTimeout(() => {
      harvestCarouselAnimating = false;
    }, 500);
  });
};

const initializeHarvestPage = () => {
  const harvestList = document.querySelector('#harvest-list');
  const featuredList = document.querySelector('#harvest-featured');
  if (!harvestList || harvestList.dataset.initialized === 'true') {
    renderHarvestBatches();
    return;
  }
  harvestList.dataset.initialized = 'true';
  document.querySelectorAll('[data-close-qr]').forEach((element) => {
    element.addEventListener('click', closeQrLightbox);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeQrLightbox();
    }
  });
  featuredList?.addEventListener('click', (event) => {
    const card = event.target.closest('[data-carousel-index]');
    if (!card) {
      return;
    }
    if (harvestCarouselPointerMoved) {
      harvestCarouselPointerMoved = false;
      return;
    }
    const targetIndex = Number(card.dataset.carouselIndex);
    const count = harvestBatches.length;
    let difference = (targetIndex - harvestCarouselCurrent) % count;
    if (difference > count / 2) {
      difference -= count;
    }
    if (difference < -count / 2) {
      difference += count;
    }
    harvestCarouselCurrent += difference;
    harvestCarouselOffset = ((Math.round(harvestCarouselCurrent) % count) + count) % count;
    renderHarvestCarousel();
  });
  featuredList?.addEventListener('pointerdown', (event) => {
    if (event.target.closest('[data-carousel-direction]')) {
      return;
    }
    harvestCarouselDragging = true;
    harvestCarouselPointerMoved = false;
    harvestCarouselPointerStart = event.clientX;
    harvestCarouselStartIndex = harvestCarouselCurrent;
    featuredList.setPointerCapture?.(event.pointerId);
    renderHarvestCarousel();
  });
  featuredList?.addEventListener('pointermove', (event) => {
    if (!harvestCarouselDragging || harvestBatches.length < 2) {
      return;
    }
    const viewport = document.querySelector('.harvest-carousel-viewport');
    const spacing = viewport?.clientWidth < 560 ? Math.max(190, (viewport?.clientWidth || 0) * .62) : 300;
    const distance = event.clientX - harvestCarouselPointerStart;
    if (Math.abs(distance) > 4) {
      harvestCarouselPointerMoved = true;
    }
    harvestCarouselCurrent = harvestCarouselStartIndex - distance / spacing;
    renderHarvestCarousel();
  });
  const finishCarouselDrag = (event) => {
    if (!harvestCarouselDragging) {
      return;
    }
    harvestCarouselDragging = false;
    const viewport = document.querySelector('.harvest-carousel-viewport');
    const spacing = viewport?.clientWidth < 560 ? Math.max(190, (viewport?.clientWidth || 0) * .62) : 300;
    const distance = event.clientX - harvestCarouselPointerStart;
    harvestCarouselCurrent = Math.round(harvestCarouselStartIndex - distance / spacing);
    harvestCarouselOffset = ((harvestCarouselCurrent % harvestBatches.length) + harvestBatches.length) % harvestBatches.length;
    if (harvestCarouselPointerMoved) {
      renderHarvestBatches();
    } else {
      renderHarvestCarousel();
    }
  };
  featuredList?.addEventListener('pointerup', finishCarouselDrag);
  featuredList?.addEventListener('pointercancel', finishCarouselDrag);
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
    const created = await addHarvestBatch(harvestButton);
    if (created) {
      startHarvestCooldown(harvestButton);
    } else {
      harvestButton.disabled = false;
      harvestButton.textContent = 'Harvest';
    }
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