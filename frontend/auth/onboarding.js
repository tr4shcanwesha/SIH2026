const onboardingForm = document.querySelector('#onboarding-form');
const formState = document.querySelector('#form-state');
const successState = document.querySelector('#success-state');
const onboardingStatus = document.querySelector('#onboarding-status');
const onboardingMessage = document.querySelector('#onboarding-message');
const rejectionBanner = document.querySelector('#rejection-banner');
const editApplicationBtn = document.querySelector('#edit-application-btn');
const registrationCredentials = document.querySelector('#registration-credentials');
const onboardingAuthSwitch = document.querySelector('#onboarding-auth-switch');
const onboardingSubmit = document.querySelector('#onboarding-submit');
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
  registrationCredentials.hidden = true;
  onboardingAuthSwitch.hidden = true;
  onboardingForm.elements.email.value = beekeeper.email || '';
  onboardingForm.elements.email.required = false;
  onboardingForm.elements.password.required = false;
  onboardingForm.elements.name.value = beekeeper.name || '';
  onboardingForm.elements.phone.value = beekeeper.phone || '';
  onboardingForm.elements.location.value = beekeeper.location || '';
  onboardingForm.elements.identity_document_type.value = beekeeper.identity_document_type || '';
  onboardingForm.elements.address_document_type.value = beekeeper.address_document_type || '';
  onboardingForm.elements.certificate_type.value = beekeeper.certificate_type || '';
  onboardingForm.elements.identity_document.required = !beekeeper.identity_document_path;
  onboardingForm.elements.certificate.required = !beekeeper.certificate_path;

  if (beekeeper.kyc_status === 'pending' && beekeeper.profile_exists && !isEditMode) {
    showSuccessState();
    return;
  }

  if (beekeeper.kyc_status === 'rejected') {
    rejectionBanner.style.display = 'block';
    onboardingMessage.textContent = 'Your application was rejected. Please review your submitted information and reapply with the required corrections.';
    onboardingSubmit.textContent = 'Reapply for approval';
    return;
  }

  onboardingMessage.textContent = isEditMode
    ? 'Review your details and resubmit your beekeeper application.'
    : 'We need these details to personalize your hive workspace and batch records.';
  onboardingSubmit.textContent = 'Update application';
};

const loadProfile = async () => {
  const response = await fetch('/api/profile');
  if (response.status === 401) return;
  if (!response.ok) throw new Error('Your application details could not be loaded.');
  const payload = await response.json();
  populateForm(payload.beekeeper);
};

editApplicationBtn?.addEventListener('click', () => {
  window.location.href = '/onboarding?edit=1';
});

onboardingForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  onboardingSubmit.disabled = true;
  onboardingStatus.textContent = '';
  const formData = new FormData(onboardingForm);
  formData.set('kyc_status', 'pending');
  const isRegistration = !registrationCredentials.hidden;
  const response = await fetch(isRegistration ? '/api/auth/register' : '/api/profile', {
    method: isRegistration ? 'POST' : 'PATCH',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    try {
      const errorPayload = JSON.parse(errorText);
      onboardingStatus.textContent = typeof errorPayload.detail === 'string'
        ? errorPayload.detail
        : 'Please check the submitted information and try again.';
    } catch {
      onboardingStatus.textContent = errorText || 'Your profile could not be saved. Please try again.';
    }
    onboardingSubmit.disabled = false;
    return;
  }

  onboardingStatus.textContent = '';
  window.location.assign('/onboarding?status=pending');
});

loadProfile().catch((error) => {
  onboardingStatus.textContent = error.message;
});
