const googleButton = document.querySelector('#google-sign-in');
const googleStatus = document.querySelector('#google-status');
const loginForm = document.querySelector('#login-form');
const loginStatus = document.querySelector('#login-status');
const loginButton = document.querySelector('#login-submit');
const registerForm = document.querySelector('#register-form');
const registerStatus = document.querySelector('#register-status');
const registerButton = document.querySelector('#register-submit');
const applicationStatus = document.querySelector('#application-status');
const applicationStatusMessage = document.querySelector('#application-status-message');
const applicationResubmit = document.querySelector('#application-resubmit');

function showApplicationStatus() {
  const status = new URLSearchParams(window.location.search).get('status');
  if (!applicationStatus || !applicationStatusMessage) return;

  if (status === 'rejected') {
    applicationStatus.classList.add('rejected');
    applicationStatusMessage.textContent =
      'Your previous application was rejected. Please review your details and resubmit it for approval.';
    if (applicationResubmit) applicationResubmit.hidden = false;
    applicationStatus.hidden = false;
  } else if (status === 'pending') {
    applicationStatusMessage.textContent =
      'Your application has been submitted and is pending review.';
    applicationStatus.hidden = false;
  }
}

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

async function signInWithPassword(event) {
  event.preventDefault();
  loginButton.disabled = true;
  loginStatus.textContent = '';

  try {
    const formData = new FormData(loginForm);
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: formData.get('email'),
        password: formData.get('password'),
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Sign in failed. Please try again.');
    }
    window.location.assign(result.redirect);
  } catch (error) {
    loginStatus.textContent = error.message;
    loginButton.disabled = false;
  }
}

async function registerWithEmail(event) {
  event.preventDefault();
  registerButton.disabled = true;
  registerStatus.textContent = '';

  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      body: new FormData(registerForm),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail || 'Registration failed. Please try again.');
    }
    window.location.assign(result.redirect);
  } catch (error) {
    registerStatus.textContent = error.message || 'Registration failed. Please try again.';
    registerButton.disabled = false;
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

googleButton?.addEventListener('click', startGoogleSignIn);
loginForm?.addEventListener('submit', signInWithPassword);
registerForm?.addEventListener('submit', registerWithEmail);
showApplicationStatus();
exchangeGoogleSession().catch((error) => {
  document.documentElement.classList.remove('oauth-callback-pending');
  googleStatus.textContent = error.message;
});
