const googleButton = document.querySelector('#google-sign-in');
const googleStatus = document.querySelector('#google-status');

function createSupabaseClient() {
  return window.supabase.createClient(
    window.__HONEYCHAIN_SUPABASE_URL,
    window.__HONEYCHAIN_SUPABASE_ANON_KEY,
    {
      auth: {
        persistSession: true,
        storage: window.localStorage,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    }
  );
}

async function startGoogleSignIn() {
  googleButton.disabled = true;
  googleStatus.textContent = '';

  try {
    const configResponse = await fetch('/api/auth/config');
    if (!configResponse.ok) throw new Error('Authentication is unavailable.');

    const config = await configResponse.json();
    window.__HONEYCHAIN_SUPABASE_URL = config.supabase_url;
    window.__HONEYCHAIN_SUPABASE_ANON_KEY = config.supabase_anon_key;
    const supabaseClient = createSupabaseClient();
    await supabaseClient.auth.signOut({ scope: 'local' });
    const { data, error } = await supabaseClient.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: new URL('/auth', window.location.origin).href,
        queryParams: { prompt: 'select_account' },
        skipBrowserRedirect: true,
      }
    });

    if (error) throw error;
    if (!data?.url) throw new Error('Google sign-in could not be started.');
    const oauthUrl = new URL(data.url);
    oauthUrl.searchParams.set('prompt', 'select_account');
    window.location.assign(oauthUrl.href);
  } catch (error) {
    googleStatus.textContent = error.message;
    googleButton.disabled = false;
  }
}

async function exchangeGoogleSession() {
  const query = new URLSearchParams(window.location.search);
  const isOAuthCallback = window.location.hash.includes('access_token') || query.has('code');
  if (!isOAuthCallback) return;
  document.documentElement.classList.add('oauth-callback-pending');

  const configResponse = await fetch('/api/auth/config');
  if (!configResponse.ok) throw new Error('Authentication is unavailable.');

  const config = await configResponse.json();
  window.__HONEYCHAIN_SUPABASE_URL = config.supabase_url;
  window.__HONEYCHAIN_SUPABASE_ANON_KEY = config.supabase_anon_key;
  const supabaseClient = createSupabaseClient();
  const { data: { session } } = await supabaseClient.auth.getSession();

  if (!session?.access_token) throw new Error('Google did not return a valid session.');

  const form = document.createElement('form');
  form.method = 'post';
  form.action = '/api/auth/google-session';

  const token = document.createElement('input');
  token.type = 'hidden';
  token.name = 'access_token';
  token.value = session.access_token;
  form.appendChild(token);

  const refreshToken = document.createElement('input');
  refreshToken.type = 'hidden';
  refreshToken.name = 'refresh_token';
  refreshToken.value = session.refresh_token || '';
  form.appendChild(refreshToken);

  document.body.appendChild(form);
  form.submit();
}

googleButton.addEventListener('click', startGoogleSignIn);
exchangeGoogleSession().catch((error) => {
  document.documentElement.classList.remove('oauth-callback-pending');
  googleStatus.textContent = error.message;
});
