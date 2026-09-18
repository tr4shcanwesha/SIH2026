const app = document.querySelector('#batch-app');
const batchId = decodeURIComponent(window.location.pathname.split('/').pop() || '');
const provisionalHoneyType = 'Golden Canopy Reserve';
let currentBatch = null;
let profile = null;

const isProvisionalBatch = (batch) => !batch.honey_type
  || batch.honey_type === provisionalHoneyType
  || batch.honey_type === 'Pending processing';

const escapeHtml = (value) => String(value ?? '-').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character]));
const formatDate = (value) => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '-';
const formatDateTime = (value) => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', hour12: true, timeZone: 'Asia/Kolkata' }).format(new Date(value)) : '-';
const batchLoading = document.querySelector('#batch-loading');
const batchError = document.querySelector('#error-message');

const setBatchLoading = (isLoading) => {
  if (batchLoading) batchLoading.hidden = !isLoading;
};

const renderJourney = (status) => {
  const stages = [
    ['HARVESTED', 'Harvested', 'Hive collection'],
    ['PROCESSED', 'Processed', 'Lab release'],
    ['DISTRIBUTED', 'Distributed', 'Final mile'],
  ];
  const currentIndex = stages.findIndex(([key]) => key === status);
  document.querySelector('#journey-rail').innerHTML = stages.map(([key, label, detail], index) => `
    <div class="journey-stage ${index <= currentIndex ? 'done' : ''} ${index === currentIndex ? 'current' : ''}">
      <span class="stage-dot"></span><strong>${label}</strong><small>${index <= currentIndex && index === currentIndex ? 'Current status' : detail}</small>
    </div>`).join('');
};

const renderBatch = (batch) => {
  currentBatch = batch;
  const status = String(batch.status || 'HARVESTED').toUpperCase();
  const hive = batch.hive || {};
  const statusLabel = status.charAt(0) + status.slice(1).toLowerCase();
  document.title = `${batch.batch_id} - HoneyChain`;
  const displayHoneyType = isProvisionalBatch(batch) ? provisionalHoneyType : batch.honey_type;
  document.querySelector('#batch-title').innerHTML = `${escapeHtml(displayHoneyType)}<span>.</span>`;
  document.querySelector('#batch-id').textContent = batch.batch_id;
  document.querySelector('#status-chip').textContent = statusLabel;
  document.querySelector('#honey-type').textContent = displayHoneyType;
  document.querySelector('#harvest-date').textContent = formatDate(batch.harvest_date);
  document.querySelector('#quantity').textContent = isProvisionalBatch(batch)
    ? 'Pending lab measurement'
    : `${batch.quantity} kg`;
  document.querySelector('#hive-id').textContent = batch.hive_id;
  document.querySelector('#origin-location').textContent = hive.location || 'Registered apiary';
  document.querySelector('#origin-species').textContent = `${hive.bee_species || 'Native honey bees'} · ${hive.hive_type || 'Traditional hive'}`;
  document.querySelector('#beekeeper-name').textContent = profile?.beekeeper?.name || 'Verified beekeeper';
  document.querySelector('#status-chip').className = `status-chip status-${status.toLowerCase()}`;
  document.querySelector('#report-reference').textContent = `HC-LAB-${batch.batch_id.replace(/^HB-/, '')}`;
  document.querySelector('#processed-date').textContent = formatDateTime(new Date());
  document.querySelector('#distributed-date').textContent = formatDateTime(new Date());
  document.querySelector('#lab-section').hidden = !['PROCESSED', 'DISTRIBUTED'].includes(status);
  document.querySelector('#distribution-section').hidden = status !== 'DISTRIBUTED';
  renderJourney(status);
};

const loadBatch = async () => {
  setBatchLoading(true);
  const [batchResponse, profileResponse, hivesResponse] = await Promise.all([
    fetch('/api/honey-batches'),
    fetch('/api/profile'),
    fetch('/api/hives'),
  ]);
  if (!batchResponse.ok) throw new Error('This batch could not be loaded.');
  const batches = await batchResponse.json();
  const batch = batches.find((item) => item.batch_id.toUpperCase() === batchId.toUpperCase());
  if (!batch) throw new Error(`Batch ${batchId} was not found in your collection.`);
  if (profileResponse.ok) profile = await profileResponse.json();
  if (hivesResponse.ok) {
    const hives = await hivesResponse.json();
    batch.hive = hives.find((hive) => hive.hive_id === batch.hive_id) || {};
  }
  renderBatch(batch);
  setBatchLoading(false);
  document.querySelector('#sync-label').textContent = `Loaded ${new Date().toLocaleTimeString([], { timeStyle: 'short' })}`;
};

const openCertificate = () => {
  if (!currentBatch) return;
  window.open(`/api/public/batches/${encodeURIComponent(currentBatch.batch_id)}/certificate`, '_blank', 'noopener');
};

document.querySelector('#certificate-button').addEventListener('click', () => {
  openCertificate();
});
loadBatch().catch((error) => {
  setBatchLoading(false);
  batchError.textContent = error.message;
  batchError.hidden = false;
});
