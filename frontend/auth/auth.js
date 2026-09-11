const API_BASE_URL = 'http://localhost:8000';
const signInButton = document.querySelector('#google-sign-in');
const signOutButton = document.querySelector('#sign-out');
const statusMessage = document.querySelector('#auth-status');
const signedInPanel = document.querySelector('#signed-in');
const loginModeButton = document.querySelector('#login-mode');
const signupModeButton = document.querySelector('#signup-mode');
const authIntro = document.querySelector('#auth-intro');

let authMode = 'login';

let supabaseClient;

function showStatus(message = '') {
  statusMessage.textContent = message;
}

function showUser(user) {
  if (!user) {
    signedInPanel.hidden = true;
    signInButton.hidden = false;
    return;
  }

  signedInPanel.hidden = false;
  signInButton.hidden = true;
}

function setAuthMode(mode) {
  authMode = mode;
  const isSignup = mode === 'signup';
  loginModeButton.classList.toggle('active', !isSignup);
  signupModeButton.classList.toggle('active', isSignup);
  signInButton.lastChild.textContent = isSignup ? ' Sign up with Google' : ' Continue with Google';
  authIntro.textContent = isSignup
    ? 'Create your HoneyChain account with your Google account and keep every harvest record connected.'
    : 'Sign in with your Google account to manage your hives and follow batches.';
}

async function loadAuth() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/config`);
    if (!response.ok) throw new Error('The authentication service is unavailable.');
    const config = await response.json();
    supabaseClient = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);

    const { data: { session } } = await supabaseClient.auth.getSession();
    showUser(session?.user);

    if (session?.access_token) {
      await fetch(`${API_BASE_URL}/api/auth/session`, {
        headers: { Authorization: `Bearer ${session.access_token}` }
      });
    }
  } catch (error) {
    showStatus(error.message);
  }
}

signInButton.addEventListener('click', async () => {
  showStatus('');
  signInButton.disabled = true;
  const { error } = await supabaseClient.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.href }
  });
  if (error) {
    showStatus(error.message);
    signInButton.disabled = false;
  }
});

loginModeButton.addEventListener('click', () => setAuthMode('login'));
signupModeButton.addEventListener('click', () => setAuthMode('signup'));

signOutButton.addEventListener('click', async () => {
  await supabaseClient.auth.signOut();
  showUser(null);
});

loadAuth();
