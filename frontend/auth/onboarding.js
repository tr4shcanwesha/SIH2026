const onboardingForm = document.querySelector('#onboarding-form');
const onboardingStatus = document.querySelector('#onboarding-status');

onboardingForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(onboardingForm);
  const response = await fetch('/api/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.fromEntries(formData.entries())),
  });
  if (!response.ok) {
    onboardingStatus.textContent = 'Your profile could not be saved. Please try again.';
    return;
  }
  window.location.href = '/dashboard';
});
