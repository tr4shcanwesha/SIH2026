const signOutForms = document.querySelectorAll('.signout-form, .profile-signout');

signOutForms.forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    try {
      if (window.clearHoneyChainClientSession) {
        await window.clearHoneyChainClientSession();
      }
    } finally {
      form.submit();
    }
  });
});
