const TOKEN_KEY = 'vox-token';
const authScreen = document.querySelector('#auth-screen');
const appScreen = document.querySelector('#app-screen');
const authForm = document.querySelector('#auth-form');
const authError = document.querySelector('#auth-error');
const authSubmit = document.querySelector('#auth-submit');
const modePills = document.querySelector('#mode-pills');
const usernameRow = document.querySelector('#username-row');
const usernameInput = document.querySelector('#username');
const confirmRow = document.querySelector('#confirm-row');
const confirmInput = document.querySelector('#confirm');
const passwordInput = document.querySelector('#password');
const passwordLabel = document.querySelector('#password-label');
const emailInput = document.querySelector('#email');
const forgotRow = document.querySelector('#forgot-row');
const backSigninRow = document.querySelector('#back-signin-row');
const userEmail = document.querySelector('#user-email');
const jobs = document.querySelector('#jobs');
const empty = document.querySelector('#empty');
const template = document.querySelector('#job-template');
const voiceForm = document.querySelector('#voice-form');
const createError = document.querySelector('#create-error');
const pdfInput = document.querySelector('#pdf');

let mode = 'signin';

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
  return { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' };
}

function showError(node, message, isSuccess = false) {
  node.hidden = !message;
  node.textContent = message || '';
  node.classList.toggle('form-success', isSuccess && message);
  node.classList.toggle('form-error', !isSuccess || !message);
}

function setMode(next) {
  const switched = mode !== next;
  mode = next;
  const signin = next === 'signin';
  const register = next === 'register';
  const forgot = next === 'forgot';

  document.querySelectorAll('.mode-pill').forEach((button) => {
    button.classList.toggle('on', button.dataset.mode === next);
  });

  modePills.hidden = forgot;
  usernameRow.classList.toggle('is-visible', register);
  usernameInput.required = register;
  confirmRow.classList.toggle('is-visible', register || forgot);
  confirmInput.required = register || forgot;
  forgotRow.hidden = !signin;
  backSigninRow.hidden = !forgot;

  if (register || forgot) {
    passwordInput.minLength = 12;
    passwordInput.placeholder = 'At least 12 characters';
    passwordLabel.textContent = forgot ? 'New password' : 'Password';
    passwordInput.autocomplete = 'new-password';
  } else {
    passwordInput.removeAttribute('minlength');
    passwordInput.placeholder = 'Enter your password';
    passwordLabel.textContent = 'Password';
    passwordInput.autocomplete = 'current-password';
    confirmInput.value = '';
  }

  authSubmit.textContent = register ? 'Create account' : forgot ? 'Reset password' : 'Sign in';
  showError(authError, '');

  if (switched) {
    // Keep auth tabs isolated so values from one flow don't leak into another.
    emailInput.value = '';
    usernameInput.value = '';
    passwordInput.value = '';
    confirmInput.value = '';
    passwordInput.type = 'password';
  }
}

function showApp(profile) {
  authScreen.hidden = true;
  appScreen.hidden = false;
  userEmail.textContent = profile.username || profile.email;
  loadLibrary();
}

function showAuth() {
  localStorage.removeItem(TOKEN_KEY);
  appScreen.hidden = true;
  authScreen.hidden = false;
  setMode('signin');
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === 'string' ? detail : detail?.[0]?.msg;
    throw new Error(message || data.message || 'Request failed');
  }
  return data;
}

function renderJob(job) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.dataset.id = job.chunkId;
  node.querySelector('strong').textContent = job.title || job.text || 'Untitled';
  const ready = job.status === 'ready';
  node.querySelector('small').textContent = ready ? 'Ready · 1/1 parts' : 'Queued';
  node.querySelector('.mark').hidden = !ready;
  return node;
}

function drawLibrary(items) {
  jobs.innerHTML = '';
  empty.hidden = items.length > 0;
  items.forEach((item) => jobs.append(renderJob(item)));
}

async function loadLibrary() {
  const items = await api('/api/library', { headers: authHeaders() });
  drawLibrary(items);
}

async function poll(id) {
  for (let i = 0; i < 30; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const job = await api(`/api/chunks/${id}`, { headers: authHeaders() });
    const node = jobs.querySelector(`[data-id="${id}"]`);
    if (!node) return;
    if (job.status === 'ready') {
      node.querySelector('small').textContent = 'Ready · 1/1 parts';
      node.querySelector('.mark').hidden = false;
      return;
    }
  }
}

document.querySelectorAll('.mode-pill').forEach((button) => {
  button.addEventListener('click', () => setMode(button.dataset.mode));
});

document.querySelector('#forgot-link').addEventListener('click', () => setMode('forgot'));
document.querySelector('#back-signin').addEventListener('click', () => setMode('signin'));

document.querySelector('#toggle-password').addEventListener('click', () => {
  const hidden = passwordInput.type === 'password';
  passwordInput.type = hidden ? 'text' : 'password';
});

authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  showError(authError, '');
  const username = usernameInput.value.trim();
  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (mode === 'register' && !username) {
    showError(authError, 'Username is required.');
    return;
  }

  if ((mode === 'register' || mode === 'forgot') && password !== confirmInput.value) {
    showError(authError, 'Passwords do not match.');
    return;
  }

  authSubmit.disabled = true;
  try {
    if (mode === 'forgot') {
      const result = await api('/api/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      passwordInput.value = '';
      confirmInput.value = '';
      setMode('signin');
      showError(authError, result.message, true);
      return;
    }

    let result;
    if (mode === 'register') {
      try {
        result = await api('/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, email, password }),
        });
      } catch (error) {
        const message = `${error?.message || ''}`.toLowerCase();
        if (message.includes('already exists')) {
          // If the account already exists, continue with sign in.
          result = await api('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          });
        } else {
          throw error;
        }
      }
    } else {
      result = await api('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
    }

    localStorage.setItem(TOKEN_KEY, result.token);
    showApp(result);
  } catch (error) {
    showError(authError, error.message);
  } finally {
    authSubmit.disabled = false;
  }
});

document.querySelector('#sign-out').addEventListener('click', showAuth);
document.querySelector('#refresh').addEventListener('click', () => {
  loadLibrary().catch((error) => showError(createError, error.message));
});

voiceForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  showError(createError, '');
  const button = voiceForm.querySelector('button[type="submit"]');
  const text = document.querySelector('#text').value.trim();
  const title = document.querySelector('#title').value.trim();
  const voice = document.querySelector('#voice').value;
  if (!text) return;
  button.disabled = true;
  try {
    const job = await api('/api/chunks', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ text, title, voice }),
    });
    empty.hidden = true;
    jobs.prepend(renderJob({ ...job, title: title || text, text, status: 'queued' }));
    document.querySelector('#text').value = '';
    document.querySelector('#title').value = '';
    poll(job.chunkId);
  } catch (error) {
    showError(createError, error.message);
  } finally {
    button.disabled = false;
  }
});

pdfInput.addEventListener('change', async () => {
  const file = pdfInput.files[0];
  pdfInput.value = '';
  if (!file) return;
  if (file.name.toLowerCase().endsWith('.pdf')) {
    showError(createError, 'PDF text extraction is not enabled yet. Paste the text instead.');
    return;
  }
  document.querySelector('#title').value ||= file.name.replace(/\.[^.]+$/, '');
  document.querySelector('#text').value = await file.text();
});

async function boot() {
  if (!token()) return;
  try {
    const me = await api('/api/me', { headers: authHeaders() });
    showApp(me);
  } catch {
    showAuth();
  }
}

boot();
setMode('signin');
