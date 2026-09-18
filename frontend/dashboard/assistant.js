const assistantState = { history: [], busy: false };
const assistantStorageKey = 'honeychain-assistant-history';

const readHistoryFromSession = () => {
  try {
    const rawHistory = window.sessionStorage.getItem(assistantStorageKey);
    if (!rawHistory) return [];
    const parsedHistory = JSON.parse(rawHistory);
    if (!Array.isArray(parsedHistory)) return [];
    return parsedHistory.filter((entry) => entry && typeof entry.role === 'string' && typeof entry.content === 'string');
  } catch (error) {
    console.warn('Unable to load assistant history from session storage:', error);
    return [];
  }
};

const persistHistoryToSession = () => {
  try {
    window.sessionStorage.setItem(assistantStorageKey, JSON.stringify(assistantState.history.slice(-12)));
  } catch (error) {
    console.warn('Unable to save assistant history to session storage:', error);
  }
};

const initializeAssistant = () => {
  const shell = document.querySelector('#assistant-shell');
  if (!shell || shell.dataset.ready === 'true') return;
  shell.dataset.ready = 'true';

  const thread = shell.querySelector('#assistant-thread');
  const form = shell.querySelector('#assistant-form');
  const input = shell.querySelector('#assistant-input');
  const send = shell.querySelector('#assistant-send');
  const status = shell.querySelector('#assistant-status');
  const clearButton = shell.querySelector('#assistant-clear');
  const suggestions = shell.querySelectorAll('[data-prompt]');

  assistantState.history = readHistoryFromSession();

  const scrollThread = () => { thread.scrollTop = thread.scrollHeight; };

  const renderHistory = () => {
    thread.innerHTML = '';

    if (!assistantState.history.length) {
      const welcomeMessage = document.createElement('article');
      welcomeMessage.className = 'assistant-message assistant';
      welcomeMessage.innerHTML = '<div class="assistant-avatar">HC</div><div class="assistant-bubble"><strong>Welcome to your field desk.</strong><br>What would you like to understand about your operation today?</div>';
      thread.appendChild(welcomeMessage);
      return;
    }

    assistantState.history.forEach((entry) => {
      const item = document.createElement('article');
      item.className = `assistant-message ${entry.role}`;
      const safeContent = String(entry.content).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character])).replace(/\n/g, '<br>');
      item.innerHTML = `<div class="assistant-avatar">${entry.role === 'assistant' ? '<img src="/src/images/logo.png?v=2" alt="HoneyChain logo" />' : 'YOU'}</div><div class="assistant-bubble">${safeContent}</div>`;
      thread.appendChild(item);
    });
    scrollThread();
  };

  const addMessage = (role, content, pending = false) => {
    const item = document.createElement('article');
    item.className = `assistant-message ${role}${pending ? ' pending' : ''}`;
    const safeContent = pending
      ? '<span class="typing-dots"><i></i><i></i><i></i></span>'
      : String(content).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character])).replace(/\n/g, '<br>');
    const avatarMarkup = role === 'assistant' ? '<img src="/src/images/logo.png?v=2" alt="HoneyChain logo" />' : 'YOU';
    item.innerHTML = `<div class="assistant-avatar">${avatarMarkup}</div><div class="assistant-bubble">${safeContent}</div>`;
    thread.appendChild(item);
    scrollThread();
    return item;
  };

  const submit = async (message) => {
    const cleanMessage = message.trim();
    if (!cleanMessage || assistantState.busy) return;

    assistantState.busy = true;
    input.value = '';
    suggestions.forEach((button) => { button.disabled = true; });
    send.disabled = true;
    status.textContent = 'HoneyChain AI is thinking...';
    addMessage('user', cleanMessage);
    const pending = addMessage('assistant', '', true);

    try {
      const response = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: cleanMessage, history: assistantState.history }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || 'The assistant could not respond.');

      pending.remove();
      const answer = payload.answer || 'I could not produce a useful answer for that request.';
      addMessage('assistant', answer);
      assistantState.history.push({ role: 'user', content: cleanMessage }, { role: 'assistant', content: answer });
      assistantState.history = assistantState.history.slice(-12);
      persistHistoryToSession();
      status.textContent = 'Live workspace context · Ready';
    } catch (error) {
      pending.remove();
      addMessage('assistant', `I could not complete that request. ${error.message}`);
      status.textContent = 'Connection issue · Try again';
    } finally {
      assistantState.busy = false;
      suggestions.forEach((button) => { button.disabled = false; });
      send.disabled = false;
      input.focus();
    }
  };

  renderHistory();
  clearButton?.addEventListener('click', () => {
    if (assistantState.busy || !assistantState.history.length) return;
    if (!window.confirm('Clear this conversation?')) return;
    assistantState.history = [];
    window.sessionStorage.removeItem(assistantStorageKey);
    renderHistory();
    status.textContent = 'Live workspace context · Ready';
    input.focus();
  });
  form.addEventListener('submit', (event) => { event.preventDefault(); submit(input.value); });
  suggestions.forEach((button) => button.addEventListener('click', () => submit(button.dataset.prompt)));
  const alertPrompt = window.sessionStorage.getItem('honeychain-alert-prompt');
  if (alertPrompt) {
    window.sessionStorage.removeItem('honeychain-alert-prompt');
    submit(alertPrompt);
  }
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  });
};

initializeAssistant();
