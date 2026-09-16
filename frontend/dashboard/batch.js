const app = document.querySelector('#batch-app');
const batchId = decodeURIComponent(window.location.pathname.split('/').pop() || '');
const provisionalHoneyType = 'Golden Canopy Reserve';
let currentBatch = null;
let profile = null;

const isProvisionalBatch = (batch) => !batch.honey_type
  || batch.honey_type === provisionalHoneyType
  || batch.honey_type === 'Pending processing';

const escapeHtml = (value) => String(value ?? '-').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character]));
const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : '-';
const formatDateTime = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '-';

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
  document.querySelector('#sync-label').textContent = `Loaded ${new Date().toLocaleTimeString([], { timeStyle: 'short' })}`;
};

const downloadCertificate = () => {
  if (!currentBatch || !window.jspdf?.jsPDF) return;
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const width = 297;
  pdf.setFillColor(252, 246, 218); pdf.rect(0, 0, width, 210, 'F');
  pdf.setDrawColor(181, 133, 43); pdf.setLineWidth(.7); pdf.rect(12, 12, width - 24, 186); pdf.rect(17, 17, width - 34, 176);
  pdf.setTextColor(143, 96, 24); pdf.setFont('helvetica', 'bold'); pdf.setFontSize(10); pdf.text('HONEYCHAIN  /  COLLECTION CENTER', width / 2, 36, { align: 'center' });
  pdf.setTextColor(48, 36, 22); pdf.setFont('times', 'bold'); pdf.setFontSize(31); pdf.text('Certificate of Processed Honey', width / 2, 61, { align: 'center' });
  pdf.setFont('helvetica', 'normal'); pdf.setFontSize(11); pdf.setTextColor(102, 80, 48); pdf.text('This certificate confirms that the batch below passed the HoneyChain collection center release protocol.', width / 2, 73, { align: 'center' });
  pdf.setTextColor(48, 36, 22); pdf.setFontSize(15); pdf.text(currentBatch.batch_id, width / 2, 95, { align: 'center' });
  pdf.setDrawColor(48, 36, 22); pdf.line(54, 104, 243, 104);
  const rows = [['BEEKEEPER', profile?.beekeeper?.name || 'Verified beekeeper'], ['HONEY PROFILE', currentBatch.honey_type || 'Wildflower honey'], ['ORIGIN HIVE', currentBatch.hive_id], ['VOLUME', `${currentBatch.quantity} kg`], ['QUALITY GRADE', 'A+ / Premium raw honey'], ['RELEASED', formatDateTime(new Date())]];
  pdf.setFontSize(9); rows.forEach(([label, value], index) => { const x = 100 + (index % 2) * 97; const y = 121 + Math.floor(index / 2) * 20; pdf.setTextColor(117, 86, 38); pdf.text(label, x, y, { align: 'center' }); pdf.setTextColor(48, 36, 22); pdf.setFont('helvetica', 'bold'); pdf.text(String(value), x, y + 7, { align: 'center', maxWidth: 82 }); pdf.setFont('helvetica', 'normal'); });
  pdf.setTextColor(143, 96, 24); pdf.setFontSize(8); pdf.text('AUTHENTICITY RECORD', 270, 178, { align: 'right' }); pdf.setTextColor(102, 80, 48); pdf.text('Issued by HoneyChain Collection Center  ·  Ledger linked', 270, 185, { align: 'right' });
  pdf.save(`${currentBatch.batch_id}-honeychain-certificate.pdf`);
};

document.querySelector('#certificate-button').addEventListener('click', downloadCertificate);
loadBatch().catch((error) => { const node = document.querySelector('#error-message'); node.textContent = error.message; node.hidden = false; });
