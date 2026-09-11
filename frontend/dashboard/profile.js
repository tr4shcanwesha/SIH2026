const profileName = document.querySelector('#profile-name');
const profileFields = document.querySelector('#profile-fields');
const profileStats = document.querySelector('#profile-stats');
const editProfileButton = document.querySelector('#edit-profile');
const editForm = document.querySelector('#profile-edit-form');
const profileStatus = document.querySelector('#profile-status');
const deleteAccountButton = document.querySelector('#delete-account');

const renderProfile = (payload) => {
  const beekeeper = payload.beekeeper;
  const stats = payload.stats;
  profileName.textContent = beekeeper.name || 'Beekeeper profile';
  profileFields.innerHTML = [
    ['Email', beekeeper.email],
    ['Phone', beekeeper.phone],
    ['Location', beekeeper.location],
  ].map(([label, value]) => `<div><span>${label}</span><b>${value || 'Not provided'}</b></div>`).join('');
  profileStats.innerHTML = [
    ['Hives', stats.hives],
    ['Harvested', stats.harvested],
    ['Processed', stats.processed],
    ['Distributed', stats.distributed],
  ].map(([label, value]) => `<div><span>${label}</span><b>${value}</b></div>`).join('');
  editForm.elements.name.value = beekeeper.name || '';
  editForm.elements.phone.value = beekeeper.phone || '';
  editForm.elements.location.value = beekeeper.location || '';
};

const loadProfile = async () => {
  const response = await fetch('/api/profile');
  if (!response.ok) throw new Error('Unable to load profile.');
  renderProfile(await response.json());
};

editProfileButton.addEventListener('click', () => {
  editForm.hidden = !editForm.hidden;
  editProfileButton.textContent = editForm.hidden ? 'Edit profile' : 'Close editor';
});

editForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const response = await fetch('/api/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.fromEntries(new FormData(editForm).entries())),
  });
  if (!response.ok) {
    profileStatus.textContent = 'Profile could not be saved.';
    return;
  }
  profileStatus.textContent = 'Profile saved.';
  renderProfile(await response.json());
});

deleteAccountButton.addEventListener('click', async () => {
  const confirmed = window.confirm(
    'Delete your account, hives, and honey batches? Blockchain history will be preserved but detached.'
  );
  if (!confirmed) return;

  deleteAccountButton.disabled = true;
  deleteAccountButton.textContent = 'Deleting account...';
  const response = await fetch('/api/profile', { method: 'DELETE' });
  if (!response.ok) {
    deleteAccountButton.disabled = false;
    deleteAccountButton.textContent = 'Delete account';
    profileStatus.textContent = 'Account could not be deleted.';
    return;
  }
  if (window.clearHoneyChainClientSession) {
    await window.clearHoneyChainClientSession();
  }
  window.location.href = '/';
});

loadProfile().catch((error) => { profileName.textContent = error.message; });
