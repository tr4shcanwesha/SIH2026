const signOutForms = document.querySelectorAll('.signout-form');

signOutForms.forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    try {
      const configResponse = await fetch('/api/auth/config');
      if (configResponse.ok && window.supabase) {
        const config = await configResponse.json();
        const supabaseClient = window.supabase.createClient(
          config.supabase_url,
          config.supabase_anon_key
        );
        await supabaseClient.auth.signOut();
      }
    } finally {
      form.submit();
    }
  });
});
