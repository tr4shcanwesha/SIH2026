const googleButton = document.querySelector('#google-sign-in');
const googleStatus = document.querySelector('#google-status');

async function startGoogleSignIn() {
  googleButton.disabled = true;
  googleStatus.textContent = '';

  try {
    const configResponse = await fetch('/api/auth/config');
    if (!configResponse.ok) throw new Error('Authentication is unavailable.');

    const config = await configResponse.json();
    const supabaseClient = window.supabase.createClient(
      config.supabase_url,
      config.supabase_anon_key
    );
    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: new URL('/auth', window.location.origin).href }
    });

    if (error) throw error;
  } catch (error) {
    googleStatus.textContent = error.message;
    googleButton.disabled = false;
  }
}

async function exchangeGoogleSession() {
  const query = new URLSearchParams(window.location.search);
  const isOAuthCallback = window.location.hash.includes('access_token') || query.has('code');
  if (!isOAuthCallback) return;

  const configResponse = await fetch('/api/auth/config');
  if (!configResponse.ok) return;

  const config = await configResponse.json();
  const supabaseClient = window.supabase.createClient(
    config.supabase_url,
    config.supabase_anon_key
  );
  const { data: { session } } = await supabaseClient.auth.getSession();

  if (!session?.access_token) return;

  const form = document.createElement('form');
  form.method = 'post';
  form.action = '/api/auth/google-session';

  const token = document.createElement('input');
  token.type = 'hidden';
  token.name = 'access_token';
  token.value = session.access_token;
  form.appendChild(token);

  document.body.appendChild(form);
  form.submit();
}

googleButton.addEventListener('click', startGoogleSignIn);
exchangeGoogleSession().catch((error) => {
  googleStatus.textContent = error.message;
});
