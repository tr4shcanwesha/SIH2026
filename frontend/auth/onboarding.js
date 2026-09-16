const onboardingForm = document.querySelector('#onboarding-form');
const formState = document.querySelector('#form-state');
const successState = document.querySelector('#success-state');
const onboardingStatus = document.querySelector('#onboarding-status');
const onboardingMessage = document.querySelector('#onboarding-message');
const rejectionBanner = document.querySelector('#rejection-banner');
const editApplicationBtn = document.querySelector('#edit-application-btn');
const queryParams = new URLSearchParams(window.location.search);
const isEditMode = queryParams.get('edit') === '1';

const showSuccessState = () => {
  if (formState) formState.hidden = true;
  if (successState) successState.hidden = false;
  onboardingStatus.textContent = '';
  if (rejectionBanner) rejectionBanner.style.display = 'none';
};

const showFormState = () => {
  if (successState) successState.hidden = true;
  if (formState) formState.hidden = false;
};

const populateForm = (beekeeper) => {
  showFormState();
  onboardingForm.elements.name.value = beekeeper.name || '';
  onboardingForm.elements.phone.value = beekeeper.phone || '';
  onboardingForm.elements.location.value = beekeeper.location || '';
  onboardingForm.elements.identity_document_type.value = beekeeper.identity_document_type || '';
  onboardingForm.elements.address_document_type.value = beekeeper.address_document_type || '';
  onboardingForm.elements.certificate_type.value = beekeeper.certificate_type || '';

  if (beekeeper.kyc_status === 'pending' && beekeeper.profile_exists && !isEditMode) {
    showSuccessState();
    return;
  }

  if (beekeeper.kyc_status === 'rejected') {
    rejectionBanner.style.display = 'block';
    onboardingMessage.textContent = 'Your previous application was rejected. Please review the existing details and resubmit for manual review.';
    return;
  }

  onboardingMessage.textContent = 'We need these details to personalize your hive workspace and batch records.';
};

const loadProfile = async () => {
  const response = await fetch('/api/profile');
  if (!response.ok) return;
  const payload = await response.json();
  populateForm(payload.beekeeper);
};

editApplicationBtn?.addEventListener('click', () => {
  window.location.href = '/onboarding?edit=1';
});

onboardingForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(onboardingForm);
  formData.set('kyc_status', 'pending');

  const response = await fetch('/api/profile', {
    method: 'PATCH',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    onboardingStatus.textContent = errorText || 'Your profile could not be saved. Please try again.';
    return;
  }

  onboardingStatus.textContent = '';
  setTimeout(() => {
    window.location.href = '/onboarding?status=pending';
  }, 1000);
});

loadProfile().catch(() => undefined);
