const API = '/api';

const state = {
  token: localStorage.getItem('ps_token') || null,
  user: JSON.parse(localStorage.getItem('ps_user') || 'null'),
  products: [],
  myProducts: [],
  cart: { items: [], total: 0 },
  activeFilter: 'All',
  editingProductId: null,
  manageTab: 'create',
  sellerOrders: [],
  sellerReceivedOrders: [],
  prefillTracking: null,
  trackLookup: null,
  view: 'home',
  expandedOrderId: null,
  trackedOrder: null,
  adminOrders: [],
  adminStatusFilter: 'all',
  productDetailId: null,
  prefillResetEmail: null,
  pendingResetCode: null
};

const BOUQUET_CATEGORIES = ['Roses', 'Mixed', 'Premium'];

function getBouquetCategoryOptions(editing) {
  const options = new Set(BOUQUET_CATEGORIES);
  state.products.forEach(p => {
    if (p.category) options.add(p.category);
  });
  if (editing?.category) options.add(editing.category);
  return [...options].sort((a, b) => a.localeCompare(b));
}

const app = document.getElementById('app');
let renderSeq = 0;

function staleRender(seq) {
  return seq !== renderSeq;
}

function formatCurrency(amount) {
  const value = Number(amount) || 0;
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function buildTrackingUrl(trackingNumber) {
  if (!trackingNumber) return '';
  return `${window.location.origin}${window.location.pathname}?track=${encodeURIComponent(trackingNumber)}`;
}

function productImageUrl(image) {
  const value = String(image || '').trim();
  if (!value) {
    return 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=600';
  }
  if (/^(https?:|data:|\/)/i.test(value)) return value;
  return `/uploads/${value.replace(/^uploads\//, '')}`;
}

function isCatalogProduct(p) {
  return p && !p.isUserCreated;
}

function productCardAction(p) {
  if (isCatalogProduct(p)) {
    return '';
  }
  if (p.isMine) {
    return `<span class="owner-product-badge">Your Product</span>`;
  }
  return `<button class="btn btn-primary" data-add="${p.id}">Add to cart</button>`;
}

function cartHasOwnProducts() {
  return state.cart.items.some(item => item.isMine);
}

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  });
  const text = await res.text().catch(() => '');
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    data = { error: text || res.statusText };
  }
  if (!res.ok) throw new Error(data.error || data.message || res.statusText || 'Something went wrong.');
  return data;
}

// ---------------------------------------------------------------------------
// Auth state
// ---------------------------------------------------------------------------
function setSession(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem('ps_token', token);
  localStorage.setItem('ps_user', JSON.stringify(user));
  applyAuthUi();
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('ps_token');
  localStorage.removeItem('ps_user');
  applyAuthUi();
}

function applyAuthUi() {
  if (state.user) {
    document.body.classList.add('logged-in');
    document.body.classList.remove('logged-out');
    document.body.classList.toggle('is-admin', Boolean(state.user.isAdmin));
    document.getElementById('hello-user').textContent = 'Hi, ' + state.user.name.split(' ')[0];
  } else {
    document.body.classList.add('logged-out');
    document.body.classList.remove('logged-in');
    document.body.classList.remove('is-admin');
  }
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
let toastTimer;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
}

// ---------------------------------------------------------------------------
// Cart helpers
// ---------------------------------------------------------------------------
async function refreshCart() {
  if (!state.token) {
    state.cart = { items: [], total: 0 };
    updateCartCount();
    return;
  }
  try {
    const data = await api('/cart');
    state.cart = data;
  } catch (e) {
    state.cart = { items: [], total: 0 };
  }
  updateCartCount();
}

function updateCartCount() {
  const count = state.cart.items.reduce((s, it) => s + it.qty, 0);
  document.getElementById('cart-count').textContent = count;
}

async function addToCart(productId) {
  if (!state.token) {
    toast('Please log in to add items to your cart.');
    navigate('login');
    return;
  }
  const product = state.products.find(p => p.id === productId);
  if (product?.isMine) {
    toast('You cannot order your own product.');
    return;
  }
  try {
    await api('/cart/add', { method: 'POST', body: { productId, qty: 1 } });
    await refreshCart();
    if (state.productDetailId === productId) {
      state.productDetailId = null;
    }
    toast('Added to your cart 🌸');
    if (state.view === 'home') render();
  } catch (e) {
    toast(e.message);
  }
}

// ---------------------------------------------------------------------------
// Navigation / Router
// ---------------------------------------------------------------------------
function navigate(view) {
  if ((view === 'cart' || view === 'orders' || view === 'manage' || view === 'admin-orders') && !state.token) {
    view = 'login';
    toast('Please log in first.');
  }
  if (view === 'admin-orders' && state.user && !state.user.isAdmin) {
    view = 'home';
    toast('Admin access required.');
  }
  if (view === 'manage' && state.view !== 'manage') {
    state.manageTab = 'create';
    state.editingProductId = null;
  }
  state.view = view;
  void render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.addEventListener('click', (e) => {
  const target = e.target.closest('[data-nav]');
  if (target) {
    e.preventDefault();
    navigate(target.getAttribute('data-nav'));
  }
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  try { await api('/logout', { method: 'POST' }); } catch (e) {}
  clearSession();
  await refreshCart();
  toast('Logged out. See you soon!');
  navigate('home');
});

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------
function viewHome() {
  const categories = ['All', ...new Set(state.products.map(p => p.category))];
  const filtered = state.activeFilter === 'All'
    ? state.products
    : state.products.filter(p => p.category === state.activeFilter);

  return `
    <section class="hero">
      <div>
        <div class="hero-eyebrow">Fresh cut · Same-day delivery</div>
        <h1>Bouquets that say it <em>better</em> than words.</h1>
        <p>Hand-tied arrangements sourced from local growers, delivered to your door the same day you order.</p>
        <button class="btn btn-primary" onclick="document.querySelector('.product-grid').scrollIntoView({behavior:'smooth'})">Browse bouquets</button>
      </div>
      <div class="hero-art">
        <img src="https://images.unsplash.com/photo-1462530260150-162092dbf011?w=900" alt="A hand-tied bouquet of fresh flowers" />
        <div class="hero-badge"><strong>${state.products.length}+</strong>fresh arrangements</div>
      </div>
    </section>

    <div class="section-head">
      <h2>Our Bouquets</h2>
      <span>${filtered.length} arrangement${filtered.length === 1 ? '' : 's'}</span>
    </div>
    <div class="filters">
      ${categories.map(c => `<button type="button" class="chip ${c === state.activeFilter ? 'active' : ''}" data-filter="${c}">${escapeHtml(c)}</button>`).join('')}
    </div>
    <div class="product-grid">
      ${filtered.map(productCard).join('')}
    </div>
    ${renderProductDetailModal()}
  `;
}

function renderProductDetailModal() {
  if (!state.productDetailId) return '';
  const p = state.products.find(item => item.id === state.productDetailId);
  if (!p) return '';
  const actionHtml = p.isMine
    ? `<span class="owner-product-badge">Your Product</span>`
    : `<button class="btn btn-primary" type="button" data-add="${p.id}">Add to cart</button>`;
  return `
    <div class="product-modal-backdrop" aria-hidden="false">
      <div class="product-modal" role="dialog" aria-labelledby="product-modal-title">
        <button type="button" class="product-modal-close" aria-label="Close">&times;</button>
        <div class="product-modal-image">
          <img src="${escapeHtml(productImageUrl(p.image))}" alt="${escapeHtml(p.name)}" />
        </div>
        <div class="product-modal-body">
          <span class="product-cat">${escapeHtml(p.category)}</span>
          <h2 id="product-modal-title" class="product-name">${escapeHtml(p.name)}</h2>
          <p class="product-desc">${escapeHtml(p.description)}</p>
          ${p.isUserCreated && !p.isMine
            ? `<p class="product-modal-creator">Created by ${escapeHtml(p.creatorName || 'Community seller')}</p>`
            : ''}
          <div class="product-modal-footer">
            <span class="product-price">${formatCurrency(p.price)}</span>
            ${actionHtml}
          </div>
        </div>
      </div>
    </div>
  `;
}

function productCard(p) {
  const creatorTag = p.isMine
    ? `<span class="creator-badge creator-badge-top owner-product-badge">Your Product</span>`
    : p.isUserCreated
      ? `<span class="creator-badge creator-badge-top">Created by ${escapeHtml(p.creatorName || 'Community seller')}</span>`
      : '';
  const priceHtml = isCatalogProduct(p)
    ? ''
    : `<span class="product-price">${formatCurrency(p.price)}</span>`;
  const actionHtml = productCardAction(p);
  const footerHtml = priceHtml || actionHtml
    ? `<div class="product-footer">${priceHtml}${actionHtml}</div>`
    : (isCatalogProduct(p) ? `<div class="product-footer"><span class="product-view-hint">Tap to view details</span></div>` : '');
  return `
    <div class="product-card ${isCatalogProduct(p) ? 'product-card--browse' : ''}" data-product-detail="${p.id}" role="button" tabindex="0" aria-label="View ${escapeHtml(p.name)}">
      ${creatorTag}
      <div class="product-img"><img src="${escapeHtml(productImageUrl(p.image))}" alt="${escapeHtml(p.name)}" loading="lazy" /></div>
      <div class="product-body">
        <span class="product-cat">${p.category}</span>
        <h3 class="product-name">${p.name}</h3>
        <p class="product-desc">${p.description}</p>
        ${footerHtml}
      </div>
    </div>
  `;
}

function viewLogin() {
  return `
    <div class="view narrow">
      <div class="card-panel">
        <h2>Welcome back</h2>
        <p class="sub">Log in to order your next bouquet.</p>
        <div class="form-error" id="auth-error"></div>
        <form id="login-form">
          <div class="field">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="email" />
          </div>
          <div class="field">
            <label>Password</label>
            <div class="password-input">
              <input type="password" name="password" required autocomplete="current-password" />
              <button type="button" class="password-toggle" data-password-toggle
                aria-label="Show password" aria-pressed="false">
                <svg class="eye-open" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg class="eye-closed" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 6.2A11 11 0 0 1 12 6c6.5 0 10 6 10 6a18 18 0 0 1-2.1 2.8M6.6 6.6C3.6 8.4 2 12 2 12s3.5 6 10 6a10 10 0 0 0 4.1-.8M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
              </button>
            </div>
          </div>
          <div class="auth-link-row">
            <button type="button" data-nav="forgot-password">Forgot password?</button>
          </div>
          <button class="btn btn-primary btn-block" type="submit">Log in</button>
        </form>
        <div class="switch-line">New here? <button data-nav="register">Create an account</button></div>
      </div>
    </div>
  `;
}

function viewForgotPassword() {
  return `
    <div class="view narrow">
      <div class="card-panel">
        <h2>Forgot password</h2>
        <p class="sub">Enter your email and we will send you a reset code.</p>
        <div class="form-error" id="auth-error"></div>
        <div class="form-success" id="auth-success"></div>
        <form id="forgot-password-form">
          <div class="field">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="email"
              value="${escapeHtml(state.prefillResetEmail || '')}" />
          </div>
          <button class="btn btn-primary btn-block" type="submit">Send reset code</button>
        </form>
        <div class="switch-line">Remember your password? <button data-nav="login">Back to log in</button></div>
      </div>
    </div>
  `;
}

function viewResetPassword() {
  return `
    <div class="view narrow">
      <div class="card-panel">
        <h2>Reset password</h2>
        <p class="sub">Enter the reset code and choose a new password.</p>
        <div class="form-error" id="auth-error"></div>
        <div class="form-success" id="auth-success"></div>
        <form id="reset-password-form">
          <div class="field">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="email"
              value="${escapeHtml(state.prefillResetEmail || '')}" />
          </div>
          <div class="field">
            <label>Reset code</label>
            <input type="text" name="code" required inputmode="numeric" pattern="[0-9]{6}"
              maxlength="6" autocomplete="one-time-code" placeholder="6-digit code" />
          </div>
          <div class="field">
            <label>New password</label>
            <div class="password-input">
              <input type="password" name="password" required minlength="6" autocomplete="new-password" />
              <button type="button" class="password-toggle" data-password-toggle
                aria-label="Show password" aria-pressed="false">
                <svg class="eye-open" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg class="eye-closed" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 6.2A11 11 0 0 1 12 6c6.5 0 10 6 10 6a18 18 0 0 1-2.1 2.8M6.6 6.6C3.6 8.4 2 12 2 12s3.5 6 10 6a10 10 0 0 0 4.1-.8M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
              </button>
            </div>
          </div>
          <button class="btn btn-primary btn-block" type="submit">Update password</button>
        </form>
        <div class="switch-line">Need a code? <button data-nav="forgot-password">Request reset code</button></div>
      </div>
    </div>
  `;
}

function viewRegister() {
  return `
    <div class="view narrow">
      <div class="card-panel">
        <h2>Create your account</h2>
        <p class="sub">Join to save your delivery details and track orders.</p>
        <div class="form-error" id="auth-error"></div>
        <form id="register-form">
          <div class="field">
            <label>Full name</label>
            <input type="text" name="name" required autocomplete="name" />
          </div>
          <div class="field">
            <label>Email</label>
            <input type="email" name="email" required autocomplete="email" />
          </div>
          <div class="field">
            <label>Password</label>
            <div class="password-input">
              <input type="password" name="password" required minlength="6" autocomplete="new-password" />
              <button type="button" class="password-toggle" data-password-toggle
                aria-label="Show password" aria-pressed="false">
                <svg class="eye-open" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg class="eye-closed" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 6.2A11 11 0 0 1 12 6c6.5 0 10 6 10 6s-.8 1.4-2.1 2.8M6.6 6.6C3.6 8.4 2 12 2 12s3.5 6 10 6a10 10 0 0 0 4.1-.8M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
              </button>
            </div>
          </div>
          <button class="btn btn-primary btn-block" type="submit">Sign up</button>
        </form>
        <div class="switch-line">Already have an account? <button data-nav="login">Log in</button></div>
      </div>
    </div>
  `;
}

function viewCart() {
  if (state.cart.items.length === 0) {
    return `
      <div class="view">
        <div class="empty-state">
          <div class="big">🛒</div>
          <h3>Your cart is empty</h3>
          <p>Browse our bouquets and add something beautiful.</p>
          <button class="btn btn-primary" data-nav="home">Shop bouquets</button>
        </div>
      </div>
    `;
  }
  const ownProductsInCart = cartHasOwnProducts();
  return `
    <div class="view" style="display:grid;grid-template-columns:1.6fr 1fr;gap:32px;align-items:start;">
      <div>
        <div class="section-head" style="padding:0 0 16px;"><h2>Your Cart</h2></div>
        <div class="cart-list">
          ${state.cart.items.map(cartRow).join('')}
        </div>
      </div>
      <div class="cart-summary">
        <h3 style="margin-top:0;">Order Summary</h3>
        <div class="summary-row"><span>Subtotal</span><span>${formatCurrency(state.cart.total)}</span></div>
        <div class="summary-row"><span>Delivery</span><span>Free</span></div>
        <div class="summary-total"><span>Total</span><span>${formatCurrency(state.cart.total)}</span></div>
        ${ownProductsInCart ? `
          <div class="cart-warning">Remove your own products from the cart before placing an order.</div>
        ` : `
          <div class="checkout-address">
            <div class="field">
              <label for="delivery-address">Delivery address</label>
              <textarea id="delivery-address" rows="4" required placeholder="House / flat no, street, area, city, state, postal code, phone"></textarea>
              <p class="field-hint">Enter the full delivery address including contact details.</p>
            </div>
          </div>
          <div class="field">
            <span class="field-label">Payment method</span>
            <div class="payment-options">
              <label class="payment-option">
                <input type="radio" name="payment-method" value="online" checked />
                Online payment
              </label>
              <label class="payment-option">
                <input type="radio" name="payment-method" value="cash" />
                Cash in hand
              </label>
            </div>
            <p class="field-hint">Payment stays Pending until it is completed.</p>
          </div>
          <button class="btn btn-primary btn-block" id="checkout-btn">Place order</button>
        `}
      </div>
    </div>
  `;
}

function cartRow(it) {
  return `
    <div class="cart-row ${it.isMine ? 'is-own-product' : ''}">
      <img src="${escapeHtml(productImageUrl(it.image))}" alt="${escapeHtml(it.name)}" />
      <div class="info">
        <h4>${it.name}</h4>
        ${it.isMine ? '<div class="cart-own-label">Your Product — cannot be ordered</div>' : ''}
        <div class="meta">${formatCurrency(it.price)} each</div>
        <div class="qty-control">
          <button data-qty="${it.id}" data-delta="-1">−</button>
          <span>${it.qty}</span>
          <button data-qty="${it.id}" data-delta="1">+</button>
        </div>
        <button class="remove-link" data-remove="${it.id}">Remove</button>
      </div>
      <div class="product-price">${formatCurrency(it.price * it.qty)}</div>
    </div>
  `;
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  } catch {
    return value;
  }
}

function formatDateTime(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
  } catch {
    return value;
  }
}

function orderStatusClass(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'delivered') return 'is-delivered';
  if (normalized === 'cancelled' || normalized === 'refunded') return 'is-cancelled';
  if (normalized === 'out_for_delivery') return 'is-shipping';
  return 'is-active';
}

function paymentStatusClass(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'paid') return 'is-delivered';
  if (normalized === 'failed') return 'is-cancelled';
  if (normalized === 'refunded') return 'is-cancelled';
  return 'is-active';
}

function renderBuyerOrderItem(item) {
  return `
    <div class="buyer-order-item">
      ${item.image ? `<img src="${escapeHtml(productImageUrl(item.image))}" alt="${escapeHtml(item.name)}" />` : ''}
      <div class="buyer-order-item-body">
        <strong>${escapeHtml(item.name)}</strong>
        <div class="order-meta">Seller: ${escapeHtml(item.sellerName || 'Petal & Stem')}</div>
        <div class="order-meta">Qty: ${item.qty} · Price: ${formatCurrency(item.price)} · Total: ${formatCurrency(item.lineTotal || item.price * item.qty)}</div>
      </div>
    </div>
  `;
}

function renderBuyerOrderDetails(order) {
  return `
    <div class="buyer-order-details">
      <div class="order-detail-grid">
        <div><span class="tracking-meta-label">Order ID</span><strong>${escapeHtml(order.id)}</strong></div>
        <div><span class="tracking-meta-label">Order date</span><strong>${formatDateTime(order.createdAt)}</strong></div>
        <div><span class="tracking-meta-label">Order status</span><strong>${escapeHtml(order.statusLabel || order.status)}</strong></div>
        <div><span class="tracking-meta-label">Payment status</span><strong>${escapeHtml(order.paymentStatusLabel || order.paymentStatus || 'Pending')}</strong></div>
        <div><span class="tracking-meta-label">Payment method</span><strong>${escapeHtml(order.paymentMethodLabel || order.paymentMethod || 'Online payment')}</strong></div>
        <div><span class="tracking-meta-label">Total amount</span><strong>${formatCurrency(order.total)}</strong></div>
        <div><span class="tracking-meta-label">Tracking</span><strong>${escapeHtml(order.trackingNumber || 'Pending')}</strong></div>
      </div>
      <div class="buyer-order-items">
        ${(order.items || []).map(renderBuyerOrderItem).join('')}
      </div>
      ${renderOrderAddress(order)}
      ${renderOrderTrackingDetails(order, { showActions: true, allowNotes: true, noteRole: 'buyer' })}
    </div>
  `;
}

function renderOrderProgress(progress) {
  if (!progress || !progress.length) return '';
  return `
    <ol class="tracking-progress">
      ${progress.map(step => `
        <li class="tracking-step ${step.complete ? 'complete' : ''} ${step.current ? 'current' : ''}">
          <span class="tracking-dot" aria-hidden="true"></span>
          <span class="tracking-label">${escapeHtml(step.label)}</span>
        </li>
      `).join('')}
    </ol>
  `;
}

function renderOrderTimeline(timeline) {
  if (!timeline || !timeline.length) {
    return '<p class="tracking-empty">No tracking updates yet.</p>';
  }
  return `
    <div class="tracking-timeline">
      ${timeline.slice().reverse().map(event => `
        <div class="tracking-event">
          <div class="tracking-event-head">
            <strong>${escapeHtml(event.actorLabel ? `${event.actorLabel} · ${event.label || event.status}` : (event.label || event.status))}</strong>
            <span>${formatDateTime(event.createdAt)}</span>
          </div>
          ${event.note ? `<p>${escapeHtml(event.note)}</p>` : ''}
          ${event.location ? `<p class="tracking-location">${escapeHtml(event.location)}</p>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

function renderTrackingNoteForm(order, noteRole) {
  if (!order.canPostNote) return '';
  const isSeller = noteRole === 'seller';
  return `
    <form class="tracking-note-form" data-tracking-note-form="${escapeHtml(order.id)}" data-note-role="${escapeHtml(noteRole)}">
      <div class="field">
        <label for="tracking-note-${escapeHtml(order.id)}">${isSeller ? 'Update for the buyer' : 'Message the seller'}</label>
        <input id="tracking-note-${escapeHtml(order.id)}" name="note" data-tracking-note="${escapeHtml(order.id)}" maxlength="400" placeholder="${isSeller ? 'Optional note for the buyer' : 'Optional note for the seller'}" />
      </div>
      <button class="btn btn-primary" type="submit">Send update</button>
    </form>
  `;
}

function renderOrderTrackingDetails(order, { showActions = false, allowNotes = false, noteRole = 'buyer' } = {}) {
  return `
    <div class="tracking-panel">
      <div class="tracking-meta">
        <div>
          <span class="tracking-meta-label">Tracking number</span>
          <strong>${escapeHtml(order.trackingNumber || 'Pending')}</strong>
        </div>
        <div>
          <span class="tracking-meta-label">Last updated</span>
          <strong>${formatDateTime(order.updatedAt || order.createdAt)}</strong>
        </div>
        ${order.deliveryDate ? `
          <div>
            <span class="tracking-meta-label">Scheduled delivery</span>
            <strong>${formatDateTime(order.deliveryDate)}</strong>
          </div>
        ` : ''}
      </div>
      ${renderOrderProgress(order.progress)}
      ${renderOrderTimeline(order.timeline)}
      ${allowNotes ? renderTrackingNoteForm(order, noteRole) : ''}
      ${showActions && order.canCancel ? `
        <button class="btn btn-ghost" type="button" data-cancel-order="${order.id}">Cancel order</button>
      ` : ''}
    </div>
  `;
}

function renderOrderAddress(order) {
  return `
    <div class="order-info">
      <span>Delivery address</span>
      <p>${escapeHtml(order.deliveryAddress || 'No address provided')}</p>
    </div>
  `;
}

function viewOrders(orders) {
  if (!orders || orders.length === 0) {
    return `
      <div class="view">
        <div class="empty-state">
          <div class="big">📦</div>
          <h3>No orders yet</h3>
          <p>Once you place an order, it will appear here with live tracking updates.</p>
          <button class="btn btn-primary" data-nav="home">Shop bouquets</button>
        </div>
      </div>
    `;
  }
  return `
    <div class="view">
      <div class="section-head orders-head">
        <div>
          <h2>My Orders</h2>
          <p class="sub">Track delivery progress and view your order history.</p>
        </div>
        <button class="btn btn-ghost" data-nav="track">Track by number</button>
      </div>
      <div class="orders-list">
        ${orders.map(o => `
          <div class="order-card buyer-order-card">
            <div class="order-head">
              <div>
                <h4>Order ${escapeHtml(o.id)}</h4>
                <div class="order-meta">
                  ${formatDateTime(o.createdAt)} · ${o.items.length} item${o.items.length === 1 ? '' : 's'}
                  · Tracking ${escapeHtml(o.trackingNumber || 'pending')}
                </div>
              </div>
              <div class="order-head-badges">
                <span class="order-status ${orderStatusClass(o.status)}">${escapeHtml(o.statusLabel || o.status)}</span>
                <span class="order-status ${paymentStatusClass(o.paymentStatus)}">${escapeHtml(o.paymentStatusLabel || o.paymentStatus || 'Pending')}</span>
              </div>
            </div>
            <div class="order-items">
              ${o.items.map(it => `<div><span>${it.qty} × ${escapeHtml(it.name)}</span><span>${formatCurrency(it.lineTotal || it.price * it.qty)}</span></div>`).join('')}
            </div>
            <div class="order-total">Total: ${formatCurrency(o.total)}</div>
            <div class="order-actions">
              <button class="btn btn-ghost" type="button" data-toggle-tracking="${o.id}">
                ${state.expandedOrderId === o.id ? 'Hide details' : 'View details'}
              </button>
            </div>
            ${state.expandedOrderId === o.id ? renderBuyerOrderDetails(o) : ''}
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function viewTrackOrder() {
  const order = state.trackedOrder;
  return `
    <div class="view track-view">
      <div class="section-head">
        <div>
          <h2>Track your order</h2>
          <p class="sub">Enter your tracking number and account email to view delivery status.</p>
        </div>
      </div>
      <div class="track-card">
        <form id="track-order-form" class="track-form">
          <div class="field">
            <label for="track-number">Tracking number</label>
            <input id="track-number" name="trackingNumber" required placeholder="PS-20260805-AB12CD34" value="${escapeHtml(state.prefillTracking || order?.trackingNumber || '')}" />
          </div>
          <div class="field">
            <label for="track-email">Email address</label>
            <input id="track-email" name="email" type="email" required placeholder="you@example.com" value="${escapeHtml(state.user?.email || '')}" />
          </div>
          <button class="btn btn-primary" type="submit">Track order</button>
        </form>
        <div class="form-error" id="track-error"></div>
        ${order ? `
          <div class="track-result">
            <div class="order-head">
              <div>
                <h3>${escapeHtml(order.statusLabel || order.status)}</h3>
                <div class="order-meta">Tracking ${escapeHtml(order.trackingNumber)}</div>
              </div>
              <span class="order-status ${orderStatusClass(order.status)}">${escapeHtml(order.statusLabel || order.status)}</span>
            </div>
            ${renderOrderTrackingDetails(order, {
              allowNotes: Boolean(state.user?.email && order.customerEmail && state.user.email.toLowerCase() === String(order.customerEmail).toLowerCase()),
              noteRole: 'buyer',
              showActions: Boolean(state.user?.email && order.customerEmail && state.user.email.toLowerCase() === String(order.customerEmail).toLowerCase())
            })}
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function viewAdminOrders(orders) {
  const statuses = ['all', 'pending', 'confirmed', 'preparing', 'out_for_delivery', 'delivered', 'cancelled', 'refunded'];
  return `
    <div class="view">
      <div class="section-head orders-head">
        <div>
          <h2>Manage Orders</h2>
          <p class="sub">Update order status and keep customers informed with a full audit trail.</p>
        </div>
      </div>
      <div class="admin-filters">
        ${statuses.map(status => `
          <button class="chip ${state.adminStatusFilter === status ? 'active' : ''}" type="button" data-admin-status="${status}">
            ${status === 'all' ? 'All' : status.replaceAll('_', ' ')}
          </button>
        `).join('')}
      </div>
      <div class="orders-list">
        ${orders.length ? orders.map(o => `
          <div class="order-card admin-order-card">
            <div class="order-head">
              <div>
                <h4>${escapeHtml(o.customerName || 'Customer')} · ${escapeHtml(o.trackingNumber || o.id)}</h4>
                <div class="order-meta">${formatDateTime(o.createdAt)} · ${escapeHtml(o.customerEmail || '')}</div>
              </div>
              <span class="order-status ${orderStatusClass(o.status)}">${escapeHtml(o.statusLabel || o.status)}</span>
            </div>
            <div class="order-items">
              ${o.items.map(it => `<div><span>${it.qty} × ${escapeHtml(it.name)}</span><span>${formatCurrency(it.price * it.qty)}</span></div>`).join('')}
            </div>
            ${renderOrderAddress(o)}
            <form class="admin-status-form" data-admin-order="${o.id}">
              <div class="field-row">
                <div class="field">
                  <label>Next status</label>
                  <select name="status">
                    <option value="confirmed">Confirmed</option>
                    <option value="preparing">Preparing bouquet</option>
                    <option value="out_for_delivery">Out for delivery</option>
                    <option value="delivered">Delivered</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="refunded">Refunded</option>
                  </select>
                </div>
                <div class="field">
                  <label>Customer note</label>
                  <input type="text" name="note" placeholder="Optional update for the customer" />
                </div>
              </div>
              <button class="btn btn-primary" type="submit">Update status</button>
            </form>
            ${renderOrderTrackingDetails(o)}
          </div>
        `).join('') : `
          <div class="empty-state">
            <div class="big">📦</div>
            <h3>No orders in this filter</h3>
          </div>
        `}
      </div>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function refreshMyProducts() {
  if (!state.token) {
    state.myProducts = [];
    return;
  }
  try {
    const data = await api('/products/mine');
    state.myProducts = data.products;
  } catch (e) {
    state.myProducts = [];
  }
}

async function refreshSellerOrders() {
  if (!state.token) {
    state.sellerOrders = [];
    state.sellerReceivedOrders = [];
    return;
  }
  try {
    const [completed, received] = await Promise.all([
      api('/products/mine/orders?status=delivered'),
      api('/products/mine/orders?status=received')
    ]);
    state.sellerOrders = completed.orders || [];
    state.sellerReceivedOrders = received.orders || [];
  } catch (e) {
    state.sellerOrders = [];
    state.sellerReceivedOrders = [];
    toast(e.message || 'Could not load seller orders.');
  }
}

function renderSellerOrderCard(o, { showSellerActions = false, showPaymentOnCompleted = false } = {}) {
  const items = o.sellerItems || o.items || [];
  const showOrderSteps = showSellerActions && (o.canAccept || o.canAdvance);
  const showPayment = o.canAcceptPayment && (showSellerActions || showPaymentOnCompleted);
  const showAnyAction = showOrderSteps || showPayment;
  return `
    <article class="seller-order-card">
      <div class="order-head">
        <div>
          <h4>Order ${escapeHtml(o.id)}</h4>
          <div class="order-meta">
            Buyer: ${escapeHtml(o.buyerName || 'Customer')}
            ${o.buyerEmail ? ` · ${escapeHtml(o.buyerEmail)}` : ''}
          </div>
          <div class="order-meta">${formatDateTime(o.createdAt)} · Tracking ${escapeHtml(o.trackingNumber || 'pending')}</div>
        </div>
        <div class="order-head-badges">
          <span class="order-status ${orderStatusClass(o.status)}">${escapeHtml(o.statusLabel || o.status)}</span>
          <span class="order-status ${paymentStatusClass(o.paymentStatus)}">${escapeHtml(o.paymentStatusLabel || o.paymentStatus || 'Pending')}</span>
        </div>
      </div>
      <div class="order-detail-grid seller-order-meta">
        <div><span class="tracking-meta-label">Order ID</span><strong>${escapeHtml(o.id)}</strong></div>
        <div><span class="tracking-meta-label">Buyer name</span><strong>${escapeHtml(o.buyerName || 'Customer')}</strong></div>
        <div><span class="tracking-meta-label">Quantity</span><strong>${items.reduce((sum, it) => sum + it.qty, 0)}</strong></div>
        <div><span class="tracking-meta-label">Payment</span><strong>${escapeHtml(o.paymentMethodLabel || o.paymentMethod || 'Online payment')}</strong></div>
        <div><span class="tracking-meta-label">Payment status</span><strong>${escapeHtml(o.paymentStatusLabel || o.paymentStatus || 'Pending')}</strong></div>
      </div>
      <div class="seller-order-items">
        ${items.map(it => `
          <div class="seller-order-item-row">
            ${it.image ? `<img src="${escapeHtml(productImageUrl(it.image))}" alt="${escapeHtml(it.name)}" />` : ''}
            <span>${it.qty} × ${escapeHtml(it.name)}</span>
            <span>${formatCurrency(it.lineTotal || it.price * it.qty)}</span>
          </div>
        `).join('')}
      </div>
      ${showAnyAction ? `
        <div class="seller-order-actions">
          ${showOrderSteps ? `
            <div class="seller-order-actions-group">
              <span class="field-label">Delivery steps (no payment needed)</span>
              <div class="seller-order-actions-row">
                ${o.canAccept ? `
                  <button class="btn btn-primary" type="button" data-confirm-order="${escapeHtml(o.id)}">Confirm</button>
                ` : ''}
                ${o.canAdvance ? `
                  <button class="btn btn-primary" type="button" data-advance-order="${escapeHtml(o.id)}">${escapeHtml(o.nextStatusAction || o.nextStatusLabel || 'Next step')}</button>
                ` : ''}
              </div>
            </div>
          ` : ''}
          ${showPayment ? `
            <div class="seller-order-actions-group">
              <span class="field-label">Payment (mark when received)</span>
              <div class="seller-order-actions-row">
                <button class="btn btn-ghost" type="button" data-payment-accepted="${escapeHtml(o.id)}">Payment accepted</button>
              </div>
            </div>
          ` : ''}
        </div>
      ` : showSellerActions ? `
        <p class="field-hint seller-order-note">No actions needed right now for this order.</p>
      ` : ''}
      <div class="order-actions">
        <button class="btn btn-ghost" type="button" data-toggle-tracking="${escapeHtml(o.id)}">
          ${state.expandedOrderId === o.id ? 'Hide details' : 'View details'}
        </button>
      </div>
      ${state.expandedOrderId === o.id ? renderOrderTrackingDetails(o, { allowNotes: true, noteRole: 'seller' }) : ''}
    </article>
  `;
}

function viewReceivedOrders(orders) {
  const noBouquets = !state.myProducts.length;
  return `
    <section class="card-panel">
      <h2>Orders Received</h2>
      <p class="sub">You can complete delivery even while payment is still Pending. Mark payment only when you receive the money.</p>
      ${orders.length ? `
        <div class="seller-orders-list">
          ${orders.map(o => renderSellerOrderCard(o, { showSellerActions: true })).join('')}
        </div>
      ` : `
        <div class="empty-state manage-empty">
          <div class="big">📦</div>
          <h3>No orders received yet</h3>
          ${noBouquets ? `
            <p>You have not created any bouquets yet. Create one under the <strong>Create</strong> tab first.</p>
            <p class="field-hint">If you are the buyer (for example Kavya), log out and sign in with the seller account (for example sireesha) to manage received orders.</p>
          ` : `
            <p>When someone orders your bouquet, it will appear here with <strong>Confirm</strong> and <strong>Payment accepted</strong> buttons.</p>
          `}
        </div>
      `}
    </section>
  `;
}

function viewCompletedOrders(orders) {
  return `
    <section class="card-panel">
      <h2>Completed Orders</h2>
      <p class="sub">Delivered orders appear here. You can still mark payment as accepted if it was pending at delivery.</p>
      ${orders.length ? `
        <div class="seller-orders-list">
          ${orders.map(o => renderSellerOrderCard(o, { showPaymentOnCompleted: true })).join('')}
        </div>
      ` : `
        <div class="empty-state manage-empty">
          <div class="big">📦</div>
          <h3>No completed orders yet</h3>
          <p>When a customer order with your bouquet is delivered, it will appear here.</p>
        </div>
      `}
    </section>
  `;
}

function bouquetForm(editing) {
  const currentImage = editing?.image || '';
  return `
    <div class="form-error" id="product-error"></div>
    <form id="product-form">
      <div class="field">
        <label>Bouquet name</label>
        <input type="text" name="name" required value="${escapeHtml(editing?.name || '')}" />
      </div>
      <div class="field-row">
        <div class="field">
          <label>Price (₹)</label>
          <input type="number" name="price" required min="0.01" step="0.01" value="${editing?.price ?? ''}" />
        </div>
        <div class="field">
          <label for="bouquet-category">Category</label>
          <select id="bouquet-category" name="category" required>
            ${!editing?.category ? '<option value="" disabled selected>Select category</option>' : ''}
            ${getBouquetCategoryOptions(editing).map(c => `
              <option value="${escapeHtml(c)}" ${editing?.category === c ? 'selected' : ''}>${escapeHtml(c)}</option>
            `).join('')}
          </select>
        </div>
      </div>
      <div class="field">
        <label>Upload image from computer</label>
        <input type="file" id="image-file" accept="image/jpeg,image/png,image/webp,image/gif" />
        <p class="field-hint">JPG, PNG, WEBP, or GIF up to 5 MB. Drag to move, zoom, then apply crop.</p>
      </div>
      <div class="field">
        <label>Or image URL</label>
        <input type="text" name="image" id="image-url" placeholder="https://... or leave blank if uploading"
          value="${escapeHtml(currentImage)}" />
      </div>
      <div class="image-cropper is-hidden" id="image-cropper">
        <div class="crop-stage" id="crop-stage" title="Drag to reposition">
          <img id="crop-image" alt="Crop source" draggable="false" />
          <div class="crop-frame" id="crop-frame" aria-hidden="true"></div>
        </div>
        <div class="crop-controls">
          <label class="crop-zoom-label">
            Zoom
            <input type="range" id="crop-zoom" min="1" max="3" step="0.01" value="1" />
          </label>
          <button class="btn btn-ghost" type="button" id="crop-reset">Reset</button>
          <button class="btn btn-primary" type="button" id="crop-apply">Apply crop</button>
        </div>
        <p class="field-hint">Drag the image inside the square, then click Apply crop.</p>
      </div>
      <div class="image-preview ${currentImage ? '' : 'is-empty'}" id="image-preview">
        ${currentImage ? `<img src="${escapeHtml(productImageUrl(currentImage))}" alt="Bouquet preview" />` : '<span>Image preview</span>'}
      </div>
      <div class="field">
        <label>Description</label>
        <textarea name="description" rows="4" required>${escapeHtml(editing?.description || '')}</textarea>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit">${editing ? 'Update bouquet' : 'Create bouquet'}</button>
        ${editing ? '<button class="btn btn-ghost" type="button" data-cancel-edit>Cancel</button>' : ''}
      </div>
    </form>
  `;
}

function bouquetCardActions(productId) {
  return `
    <div class="my-bouquet-actions">
      <button type="button" class="icon-action-btn" data-edit-product="${productId}" aria-label="Edit bouquet" title="Edit">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
        </svg>
      </button>
      <button type="button" class="icon-action-btn icon-action-btn-danger" data-delete-product="${productId}" aria-label="Delete bouquet" title="Delete">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="M3 6h18M8 6V4h8v2m-11 0 1 14h10L19 6"/>
        </svg>
      </button>
    </div>
  `;
}

function myBouquetCard(p) {
  const creator = p.creatorName || state.user?.name?.split(' ')[0] || 'You';
  return `
    <article class="my-bouquet-card">
      <img src="${escapeHtml(productImageUrl(p.image))}" alt="${escapeHtml(p.name)}" />
      <div class="my-bouquet-body">
        <div class="my-bouquet-header">
          <span class="product-cat">${escapeHtml(p.category)}</span>
          <div class="my-bouquet-header-right">
            <span class="creator-badge creator-badge-inline">Created by ${escapeHtml(creator)}</span>
            ${bouquetCardActions(p.id)}
          </div>
        </div>
        <h3>${escapeHtml(p.name)}</h3>
        <p>${escapeHtml(p.description)}</p>
        <div class="my-bouquet-footer">
          <strong>${formatCurrency(p.price)}</strong>
        </div>
      </div>
    </article>
  `;
}

function emptyMineState(message) {
  return `
    <div class="empty-state manage-empty">
      <div class="big">✿</div>
      <h3>No bouquets yet</h3>
      <p>${message}</p>
      <button class="btn btn-primary" type="button" data-manage-tab="create">Create bouquet</button>
    </div>
  `;
}

function viewManageProducts() {
  const tabs = [
    { id: 'create', label: 'Create' },
    { id: 'mine', label: 'My Bouquets' },
    { id: 'received', label: 'Orders Received' },
    { id: 'completed', label: 'Completed' }
  ];
  let panel = '';

  if (state.manageTab === 'completed') {
    panel = viewCompletedOrders(state.sellerOrders);
  } else if (state.manageTab === 'received') {
    panel = viewReceivedOrders(state.sellerReceivedOrders);
  } else if (state.manageTab === 'mine') {
    panel = `
      <section class="card-panel">
        <h2>My Bouquets</h2>
        <p class="sub">Everything you created is listed here.</p>
        ${state.myProducts.length
          ? `<div class="my-bouquet-grid">
              ${state.myProducts.map(p => myBouquetCard(p)).join('')}
            </div>`
          : emptyMineState('Create your first bouquet to see it here.')}
      </section>
    `;
  } else {
    const editing = state.myProducts.find(p => p.id === state.editingProductId);
    panel = `
      <section class="card-panel product-editor">
        <h2>${editing ? 'Update bouquet' : 'Create bouquet'}</h2>
        <p class="sub">${editing ? 'Edit your bouquet details below.' : 'Add a new flower bouquet. It will appear in Shop and My Bouquets.'}</p>
        ${bouquetForm(editing || null)}
      </section>
    `;
  }

  return `
    <div class="view manage-page">
      <div class="section-head manage-heading">
        <h2>Flower Bouquets</h2>
        <span>Create listings and track completed orders</span>
      </div>
      <div class="manage-tabs" role="tablist">
        ${tabs.map(tab => `
          <button type="button" class="manage-tab ${state.manageTab === tab.id ? 'active' : ''}"
            data-manage-tab="${tab.id}" role="tab"
            aria-selected="${state.manageTab === tab.id}">${tab.label}</button>
        `).join('')}
      </div>
      <div class="manage-panel">
        ${panel}
      </div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
function readSellerScanNote(orderId) {
  const field = document.querySelector(`[data-seller-scan-note="${orderId}"]`);
  return field ? field.value.trim() : '';
}

function shouldPauseTrackingPoll() {
  const active = document.activeElement;
  return Boolean(active && active.closest && (
    active.closest('[data-tracking-note]') ||
    active.closest('[data-seller-scan-note]') ||
    active.closest('#track-order-form')
  ));
}

let trackingPollId = null;

function stopTrackingPoll() {
  if (trackingPollId) {
    clearInterval(trackingPollId);
    trackingPollId = null;
  }
}

function startTrackingPoll() {
  stopTrackingPoll();
  const watching =
    state.view === 'orders' ||
    state.view === 'track' ||
    (state.view === 'manage' && (state.manageTab === 'received' || state.manageTab === 'completed'));
  if (!watching) return;
  trackingPollId = setInterval(() => {
    if (document.hidden || shouldPauseTrackingPoll()) return;
    render();
  }, 12000);
}

async function postTrackingNote(orderId, noteRole, note) {
  const path = noteRole === 'seller'
    ? `/products/mine/orders/${orderId}/notes`
    : `/orders/${orderId}/notes`;
  const data = await api(path, { method: 'POST', body: { note } });
  if (noteRole === 'seller') {
    await refreshSellerOrders();
  }
  if (state.trackedOrder?.id === orderId) {
    state.trackedOrder = data.order;
  }
  return data.order;
}

async function render() {
  const seq = ++renderSeq;

  if (state.view === 'home') {
    if (staleRender(seq)) return;
    app.innerHTML = viewHome();
  } else if (state.view === 'login') {
    if (staleRender(seq)) return;
    app.innerHTML = viewLogin();
    bindAuthForm('login');
  } else if (state.view === 'forgot-password') {
    if (staleRender(seq)) return;
    app.innerHTML = viewForgotPassword();
    bindForgotPasswordForm();
  } else if (state.view === 'reset-password') {
    if (staleRender(seq)) return;
    app.innerHTML = viewResetPassword();
    bindResetPasswordForm();
  } else if (state.view === 'register') {
    if (staleRender(seq)) return;
    app.innerHTML = viewRegister();
    bindAuthForm('register');
  } else if (state.view === 'cart') {
    await refreshCart();
    if (staleRender(seq)) return;
    app.innerHTML = viewCart();
  } else if (state.view === 'orders') {
    let orders = [];
    try {
      const data = await api('/orders');
      orders = data.orders;
    } catch (e) {}
    if (staleRender(seq)) return;
    app.innerHTML = viewOrders(orders);
  } else if (state.view === 'track') {
    if (state.trackLookup) {
      try {
        const data = await api('/orders/track', {
          method: 'POST',
          body: state.trackLookup
        });
        state.trackedOrder = data.order;
      } catch (e) {}
    }
    if (staleRender(seq)) return;
    app.innerHTML = viewTrackOrder();
    bindTrackOrderForm();
  } else if (state.view === 'admin-orders') {
    let orders = [];
    try {
      const query = state.adminStatusFilter !== 'all'
        ? `?status=${encodeURIComponent(state.adminStatusFilter)}`
        : '';
      const data = await api('/admin/orders' + query);
      orders = data.orders;
      state.adminOrders = orders;
    } catch (e) {
      toast(e.message || 'Could not load admin orders.');
    }
    if (staleRender(seq)) return;
    app.innerHTML = viewAdminOrders(orders);
    bindAdminOrderForms();
  } else if (state.view === 'manage') {
    await refreshMyProducts();
    if (staleRender(seq)) return;
    if (state.manageTab === 'completed' || state.manageTab === 'received') {
      await refreshSellerOrders();
    }
    if (staleRender(seq)) return;
    app.innerHTML = viewManageProducts();
    if (document.getElementById('product-form')) bindProductForm();
  }
  startTrackingPoll();
}

function bindAuthForm(type) {
  const form = document.getElementById(type + '-form');
  const errBox = document.getElementById('auth-error');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.remove('show');
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    try {
      const data = await api('/' + type, { method: 'POST', body: payload });
      setSession(data.token, data.user);
      await refreshCart();
      toast(type === 'login' ? `Welcome back, ${data.user.name.split(' ')[0]}!` : `Welcome, ${data.user.name.split(' ')[0]}! Account created.`);
      navigate('home');
    } catch (e) {
      errBox.textContent = e.message;
      errBox.classList.add('show');
    }
  });
}

function bindForgotPasswordForm() {
  const form = document.getElementById('forgot-password-form');
  const errBox = document.getElementById('auth-error');
  const successBox = document.getElementById('auth-success');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.remove('show');
    successBox.classList.remove('show');
    const fd = new FormData(form);
    const email = String(fd.get('email') || '').trim().toLowerCase();
    state.prefillResetEmail = email;
    try {
      const data = await api('/forgot-password', { method: 'POST', body: { email } });
      let message = data.message || 'If an account exists, check your email for a reset code.';
      if (data.resetCode) {
        state.pendingResetCode = data.resetCode;
        message += ` Your reset code: <strong class="reset-code">${escapeHtml(data.resetCode)}</strong>`;
        successBox.innerHTML = `${message} <button type="button" class="btn btn-ghost btn-sm" data-nav="reset-password">Enter code</button>`;
      } else {
        successBox.textContent = message;
      }
      successBox.classList.add('show');
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.add('show');
    }
  });
}

function bindResetPasswordForm() {
  const form = document.getElementById('reset-password-form');
  const errBox = document.getElementById('auth-error');
  const successBox = document.getElementById('auth-success');
  const codeInput = form.querySelector('input[name="code"]');
  if (state.pendingResetCode && !codeInput.value) {
    codeInput.value = state.pendingResetCode;
  }
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.remove('show');
    successBox.classList.remove('show');
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    state.prefillResetEmail = String(payload.email || '').trim().toLowerCase();
    try {
      const data = await api('/reset-password', { method: 'POST', body: payload });
      state.pendingResetCode = null;
      successBox.textContent = data.message || 'Password updated. You can log in now.';
      successBox.classList.add('show');
      toast('Password updated.');
      setTimeout(() => navigate('login'), 1200);
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.add('show');
    }
  });
}

function bindProductForm() {
  const form = document.getElementById('product-form');
  const errBox = document.getElementById('product-error');
  const fileInput = document.getElementById('image-file');
  const urlInput = document.getElementById('image-url');
  const preview = document.getElementById('image-preview');
  const cropperEl = document.getElementById('image-cropper');
  const stage = document.getElementById('crop-stage');
  const cropImage = document.getElementById('crop-image');
  const cropFrame = document.getElementById('crop-frame');
  const zoomInput = document.getElementById('crop-zoom');
  const applyBtn = document.getElementById('crop-apply');
  const resetBtn = document.getElementById('crop-reset');

  const crop = {
    baseScale: 1,
    zoom: 1,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
    ready: false
  };
  let croppedBlob = null;
  let objectUrl = null;

  function showPreview(src) {
    if (!src) {
      preview.classList.add('is-empty');
      preview.innerHTML = '<span>Image preview</span>';
      return;
    }
    preview.classList.remove('is-empty');
    preview.innerHTML = `<img src="${escapeHtml(productImageUrl(src))}" alt="Bouquet preview" />`;
  }

  function frameRect() {
    const size = Math.min(stage.clientWidth * 0.82, stage.clientHeight * 0.82, 260);
    return {
      left: (stage.clientWidth - size) / 2,
      top: (stage.clientHeight - size) / 2,
      size
    };
  }

  function clampOffsets() {
    const frame = frameRect();
    const scale = crop.baseScale * crop.zoom;
    const w = cropImage.naturalWidth * scale;
    const h = cropImage.naturalHeight * scale;
    const minX = frame.left + frame.size - w;
    const maxX = frame.left;
    const minY = frame.top + frame.size - h;
    const maxY = frame.top;
    const centerX = stage.clientWidth / 2 - w / 2;
    const centerY = stage.clientHeight / 2 - h / 2;
    crop.offsetX = Math.min(maxX - centerX, Math.max(minX - centerX, crop.offsetX));
    crop.offsetY = Math.min(maxY - centerY, Math.max(minY - centerY, crop.offsetY));
  }

  function renderCrop() {
    if (!crop.ready) return;
    const scale = crop.baseScale * crop.zoom;
    const w = cropImage.naturalWidth * scale;
    const h = cropImage.naturalHeight * scale;
    clampOffsets();
    cropImage.style.width = `${w}px`;
    cropImage.style.height = `${h}px`;
    cropImage.style.left = `${stage.clientWidth / 2 - w / 2 + crop.offsetX}px`;
    cropImage.style.top = `${stage.clientHeight / 2 - h / 2 + crop.offsetY}px`;
    const frame = frameRect();
    cropFrame.style.width = `${frame.size}px`;
    cropFrame.style.height = `${frame.size}px`;
  }

  function openCropper(src, { crossOrigin = false } = {}) {
    cropperEl.classList.remove('is-hidden');
    crop.ready = false;
    crop.zoom = 1;
    crop.offsetX = 0;
    crop.offsetY = 0;
    zoomInput.value = '1';
    croppedBlob = null;
    cropImage.onload = () => {
      const frame = frameRect();
      crop.baseScale = Math.max(
        frame.size / cropImage.naturalWidth,
        frame.size / cropImage.naturalHeight
      );
      crop.ready = true;
      renderCrop();
    };
    cropImage.onerror = () => {
      errBox.textContent = 'Could not load that image for cropping.';
      errBox.classList.add('show');
      cropperEl.classList.add('is-hidden');
    };
    if (crossOrigin) cropImage.crossOrigin = 'anonymous';
    else cropImage.removeAttribute('crossorigin');
    cropImage.src = src;
  }

  function applyCrop() {
    if (!crop.ready) return Promise.reject(new Error('Load an image before cropping.'));
    return new Promise((resolve, reject) => {
      const frame = frameRect();
      const scale = crop.baseScale * crop.zoom;
      const imgLeft = parseFloat(cropImage.style.left);
      const imgTop = parseFloat(cropImage.style.top);
      const sx = (frame.left - imgLeft) / scale;
      const sy = (frame.top - imgTop) / scale;
      const sw = frame.size / scale;
      const sh = frame.size / scale;
      const canvas = document.createElement('canvas');
      const output = 900;
      canvas.width = output;
      canvas.height = output;
      const ctx = canvas.getContext('2d');
      try {
        ctx.drawImage(cropImage, sx, sy, sw, sh, 0, 0, output, output);
      } catch (err) {
        reject(new Error('This image URL blocks cropping. Upload from your computer instead.'));
        return;
      }
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('Could not create cropped image.'));
          return;
        }
        croppedBlob = blob;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = URL.createObjectURL(blob);
        showPreview(objectUrl);
        urlInput.value = '';
        resolve(blob);
      }, 'image/jpeg', 0.92);
    });
  }

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    errBox.classList.remove('show');
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    openCropper(objectUrl);
    showPreview(objectUrl);
  });

  let urlTimer;
  urlInput.addEventListener('input', () => {
    clearTimeout(urlTimer);
    const value = urlInput.value.trim();
    if (!value || fileInput.files?.length) {
      if (!value && !fileInput.files?.length && !croppedBlob) showPreview('');
      return;
    }
    urlTimer = setTimeout(() => {
      croppedBlob = null;
      openCropper(value, { crossOrigin: true });
      showPreview(value);
    }, 400);
  });

  zoomInput.addEventListener('input', () => {
    crop.zoom = Number(zoomInput.value) || 1;
    renderCrop();
  });

  resetBtn.addEventListener('click', () => {
    crop.zoom = 1;
    crop.offsetX = 0;
    crop.offsetY = 0;
    zoomInput.value = '1';
    renderCrop();
  });

  applyBtn.addEventListener('click', async () => {
    try {
      errBox.classList.remove('show');
      await applyCrop();
      toast('Crop applied.');
    } catch (e) {
      errBox.textContent = e.message;
      errBox.classList.add('show');
    }
  });

  stage.addEventListener('pointerdown', (e) => {
    if (!crop.ready) return;
    crop.dragging = true;
    crop.startX = e.clientX;
    crop.startY = e.clientY;
    crop.originX = crop.offsetX;
    crop.originY = crop.offsetY;
    stage.setPointerCapture(e.pointerId);
    stage.classList.add('is-dragging');
  });

  stage.addEventListener('pointermove', (e) => {
    if (!crop.dragging) return;
    crop.offsetX = crop.originX + (e.clientX - crop.startX);
    crop.offsetY = crop.originY + (e.clientY - crop.startY);
    renderCrop();
  });

  function endDrag(e) {
    if (!crop.dragging) return;
    crop.dragging = false;
    stage.classList.remove('is-dragging');
    if (e?.pointerId != null) {
      try { stage.releasePointerCapture(e.pointerId); } catch (_) {}
    }
  }

  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.remove('show');
    const payload = Object.fromEntries(new FormData(form).entries());
    payload.price = Number(payload.price);
    const editingId = state.editingProductId;

    try {
      if (!croppedBlob && !cropperEl.classList.contains('is-hidden') && crop.ready) {
        await applyCrop();
      }

      if (croppedBlob) {
        const body = new FormData();
        body.append('image', croppedBlob, 'bouquet-crop.jpg');
        const headers = {};
        if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
        const uploadRes = await fetch(API + '/upload', { method: 'POST', headers, body });
        const uploadData = await uploadRes.json().catch(() => ({}));
        if (!uploadRes.ok) throw new Error(uploadData.error || 'Image upload failed.');
        payload.image = uploadData.url;
      } else if (fileInput.files?.[0]) {
        const body = new FormData();
        body.append('image', fileInput.files[0]);
        const headers = {};
        if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
        const uploadRes = await fetch(API + '/upload', { method: 'POST', headers, body });
        const uploadData = await uploadRes.json().catch(() => ({}));
        if (!uploadRes.ok) throw new Error(uploadData.error || 'Image upload failed.');
        payload.image = uploadData.url;
      }

      payload.image = String(payload.image || '').trim();
      if (!payload.image) {
        throw new Error('Upload an image from your computer or paste an image URL.');
      }

      await api(editingId ? `/products/${editingId}` : '/products', {
        method: editingId ? 'PUT' : 'POST',
        body: payload
      });
      const data = await api('/products');
      state.products = data.products;
      await refreshMyProducts();
      state.editingProductId = null;
      state.manageTab = 'mine';
      toast(editingId ? 'Bouquet updated.' : 'Bouquet created.');
      render();
    } catch (e) {
      errBox.textContent = e.message;
      errBox.classList.add('show');
    }
  });
}

// ---------------------------------------------------------------------------
// Delegated events for dynamic content (filters, add to cart, cart qty/remove, checkout)
// ---------------------------------------------------------------------------
app.addEventListener('click', async (e) => {
  const passwordToggle = e.target.closest('[data-password-toggle]');
  if (passwordToggle) {
    const input = passwordToggle.closest('.password-input').querySelector('input');
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    passwordToggle.setAttribute('aria-pressed', String(!showing));
    passwordToggle.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    return;
  }

  const manageTab = e.target.closest('[data-manage-tab]');
  if (manageTab) {
    state.manageTab = manageTab.getAttribute('data-manage-tab');
    if (state.manageTab !== 'create') state.editingProductId = null;
    await render();
    return;
  }

  const editProduct = e.target.closest('[data-edit-product]');
  if (editProduct) {
    state.editingProductId = editProduct.getAttribute('data-edit-product');
    state.manageTab = 'create';
    state.view = 'manage';
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  if (e.target.closest('[data-cancel-edit]')) {
    state.editingProductId = null;
    state.manageTab = 'mine';
    render();
    return;
  }

  const deleteProduct = e.target.closest('[data-delete-product]');
  if (deleteProduct) {
    const productId = deleteProduct.getAttribute('data-delete-product');
    const product = state.myProducts.find(p => p.id === productId)
      || state.products.find(p => p.id === productId);
    if (!confirm(`Delete "${product?.name || 'this bouquet'}"?`)) return;
    try {
      await api(`/products/${productId}`, { method: 'DELETE' });
      state.products = state.products.filter(p => p.id !== productId);
      state.myProducts = state.myProducts.filter(p => p.id !== productId);
      if (state.editingProductId === productId) state.editingProductId = null;
      toast('Bouquet deleted.');
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  const filterBtn = e.target.closest('[data-filter]');
  if (filterBtn) {
    state.activeFilter = filterBtn.getAttribute('data-filter');
    render();
    return;
  }

  const closeProductModal = e.target.closest('.product-modal-close')
    || e.target.classList.contains('product-modal-backdrop');
  if (closeProductModal) {
    state.productDetailId = null;
    render();
    return;
  }

  const productCard = e.target.closest('[data-product-detail]');
  if (productCard && !e.target.closest('[data-add]')) {
    state.productDetailId = productCard.getAttribute('data-product-detail');
    render();
    return;
  }

  const confirmOrderBtn = e.target.closest('[data-confirm-order]');
  if (confirmOrderBtn) {
    const orderId = confirmOrderBtn.getAttribute('data-confirm-order');
    try {
      await api(`/products/mine/orders/${orderId}/accept`, {
        method: 'POST',
        body: { note: readSellerScanNote(orderId) }
      });
      toast('Seller scan posted: order confirmed.');
      state.expandedOrderId = orderId;
      await refreshSellerOrders();
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  const paymentAcceptedBtn = e.target.closest('[data-payment-accepted]');
  if (paymentAcceptedBtn) {
    const orderId = paymentAcceptedBtn.getAttribute('data-payment-accepted');
    try {
      await api(`/products/mine/orders/${orderId}/payment-accepted`, { method: 'POST' });
      toast('Seller scan posted: payment accepted.');
      state.expandedOrderId = orderId;
      await refreshSellerOrders();
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  const advanceOrderBtn = e.target.closest('[data-advance-order]');
  if (advanceOrderBtn) {
    const orderId = advanceOrderBtn.getAttribute('data-advance-order');
    try {
      const data = await api(`/products/mine/orders/${orderId}/advance`, {
        method: 'POST',
        body: { note: readSellerScanNote(orderId) }
      });
      toast(`Seller scan posted: ${data.order?.statusLabel || 'Done'}.`);
      state.expandedOrderId = orderId;
      await refreshSellerOrders();
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  const copyTracking = e.target.closest('[data-copy-tracking]');
  if (copyTracking) {
    const trackingNumber = copyTracking.getAttribute('data-copy-tracking');
    try {
      await navigator.clipboard.writeText(trackingNumber);
      toast('Tracking number copied.');
    } catch (err) {
      toast(trackingNumber);
    }
    return;
  }

  const addBtn = e.target.closest('[data-add]');
  if (addBtn) {
    await addToCart(addBtn.getAttribute('data-add'));
    return;
  }

  const qtyBtn = e.target.closest('[data-qty]');
  if (qtyBtn) {
    const id = qtyBtn.getAttribute('data-qty');
    const delta = parseInt(qtyBtn.getAttribute('data-delta'), 10);
    const item = state.cart.items.find(it => it.id === id);
    const newQty = item.qty + delta;
    if (newQty <= 0) {
      await api('/cart/remove', { method: 'POST', body: { productId: id } });
    } else {
      await api('/cart/update', { method: 'POST', body: { productId: id, qty: newQty } });
    }
    await refreshCart();
    app.innerHTML = viewCart();
    return;
  }

  const removeBtn = e.target.closest('[data-remove]');
  if (removeBtn) {
    await api('/cart/remove', { method: 'POST', body: { productId: removeBtn.getAttribute('data-remove') } });
    await refreshCart();
    app.innerHTML = viewCart();
    return;
  }

  if (e.target.id === 'checkout-btn') {
    if (cartHasOwnProducts()) {
      toast('You cannot order your own product.');
      return;
    }
    const address = document.getElementById('delivery-address')?.value.trim() || '';
    if (!address) {
      toast('Enter a complete delivery address.');
      return;
    }
    if (address.length < 10) {
      toast('Enter a complete delivery address with street, city, and contact details.');
      return;
    }
    try {
      const paymentMethod = document.querySelector('input[name="payment-method"]:checked')?.value || 'online';
      const data = await api('/checkout', {
        method: 'POST',
        body: { address, paymentMethod }
      });
      const tracking = data.order?.trackingNumber ? ` Tracking: ${data.order.trackingNumber}` : '';
      toast(`Order placed! 🌷 Thank you.${tracking}`);
      await refreshCart();
      navigate('orders');
    } catch (err) {
      toast(err.message);
    }
  }

  const toggleTracking = e.target.closest('[data-toggle-tracking]');
  if (toggleTracking) {
    const orderId = toggleTracking.getAttribute('data-toggle-tracking');
    state.expandedOrderId = state.expandedOrderId === orderId ? null : orderId;
    render();
    return;
  }

  const cancelOrderBtn = e.target.closest('[data-cancel-order]');
  if (cancelOrderBtn) {
    const orderId = cancelOrderBtn.getAttribute('data-cancel-order');
    if (!confirm('Cancel this order?')) return;
    try {
      await api(`/orders/${orderId}/cancel`, { method: 'POST' });
      toast('Order cancelled.');
      render();
    } catch (err) {
      toast(err.message);
    }
    return;
  }

  const adminStatusChip = e.target.closest('[data-admin-status]');
  if (adminStatusChip) {
    state.adminStatusFilter = adminStatusChip.getAttribute('data-admin-status');
    render();
    return;
  }
});

function bindTrackOrderForm() {
  const form = document.getElementById('track-order-form');
  const errBox = document.getElementById('track-error');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errBox.classList.remove('show');
    const fd = new FormData(form);
    try {
      const data = await api('/orders/track', {
        method: 'POST',
        body: {
          trackingNumber: fd.get('trackingNumber'),
          email: fd.get('email')
        }
      });
      state.trackedOrder = data.order;
      state.trackLookup = {
        trackingNumber: String(fd.get('trackingNumber') || '').trim(),
        email: String(fd.get('email') || '').trim()
      };
      render();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.add('show');
    }
  });
}

document.addEventListener('submit', async (e) => {
  const form = e.target.closest('[data-tracking-note-form]');
  if (!form) return;
  e.preventDefault();
  const orderId = form.getAttribute('data-tracking-note-form');
  const noteRole = form.getAttribute('data-note-role') || 'buyer';
  const note = (new FormData(form).get('note') || '').trim();
  if (!note) {
    toast(noteRole === 'seller' ? 'Enter an update for the buyer.' : 'Enter a message for the seller.');
    return;
  }
  try {
    await postTrackingNote(orderId, noteRole, note);
    state.expandedOrderId = orderId;
    toast(noteRole === 'seller' ? 'Seller said update posted.' : 'Buyer said update posted.');
    render();
  } catch (err) {
    toast(err.message);
  }
});

function bindAdminOrderForms() {
  document.querySelectorAll('.admin-status-form').forEach(form => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const orderId = form.getAttribute('data-admin-order');
      const formData = new FormData(form);
      try {
        await api(`/admin/orders/${orderId}/status`, {
          method: 'PATCH',
          body: {
            status: formData.get('status'),
            note: formData.get('note')
          }
        });
        toast('Order status updated.');
        render();
      } catch (err) {
        toast(err.message);
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function chatMessage(content, role) {
  return `<div class="chat-message ${role}">${escapeHtml(content)}</div>`;
}

const CHAT_WELCOME_MESSAGE = 'Hi there! Tell me what flowers you need, and I’ll help you shop.';
let chatHistory = [{ role: 'assistant', content: CHAT_WELCOME_MESSAGE }];
function viewChatWidget() {
  return `
    <div class="chat-widget" id="chat-widget">
      <div class="chat-header">
        <h3>Petal & Stem Assistant</h3>
        <div class="chat-header-actions">
          <button type="button" id="chat-clear-btn" class="chat-header-text-btn">Clear</button>
          <button type="button" id="close-chat-btn" aria-label="Close chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>
      <div class="chat-body" id="chat-body">
        <div class="chat-message ai">${escapeHtml(CHAT_WELCOME_MESSAGE)}</div>
      </div>
      <div class="chat-input-row">
        <textarea id="chat-input" placeholder="Ask the flower assistant..." rows="1"></textarea>
        <button class="btn btn-ghost" id="chat-cancel-btn" type="button">Cancel</button>
        <button class="btn btn-primary" id="chat-send-btn" type="button">Send</button>
      </div>
    </div>
  `;
}

async function sendChatMessage() {
  try {
    return await api('/ai/chat', {
      method: 'POST',
      body: { messages: chatHistory },
    });
  } catch (err) {
    const errorText = err.message || 'AI request failed.';
    return { content: `Error: ${errorText}` };
  }
}

function appendChatMessage(content, role) {
  const body = document.getElementById('chat-body');
  if (!body) return;
  body.insertAdjacentHTML('beforeend', chatMessage(content, role));
  body.scrollTop = body.scrollHeight;
}

function openChatWidget() {
  const widget = document.getElementById('chat-widget');
  if (widget) widget.classList.add('open');
}

function closeChatWidget() {
  const widget = document.getElementById('chat-widget');
  if (widget) widget.classList.remove('open');
  const input = document.getElementById('chat-input');
  if (input) input.value = '';
}

function clearChatHistory() {
  const body = document.getElementById('chat-body');
  const input = document.getElementById('chat-input');
  chatHistory = [{ role: 'assistant', content: CHAT_WELCOME_MESSAGE }];
  if (body) {
    body.innerHTML = chatMessage(CHAT_WELCOME_MESSAGE, 'ai');
  }
  if (input) input.value = '';
}

async function handleChatSend() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  if (!input || !sendBtn) return;
  const message = input.value.trim();
  if (!message) return;
  appendChatMessage(message, 'user');
  chatHistory.push({ role: 'user', content: message });
  input.value = '';
  sendBtn.disabled = true;
  sendBtn.textContent = 'Thinking...';
  try {
    const ai = await sendChatMessage();
    const reply = ai.content || 'Sorry, I could not prepare a reply. Please try again.';
    chatHistory.push({ role: 'assistant', content: reply });
    appendChatMessage(reply, 'ai');
    if (ai.cartUpdated) {
      await refreshCart();
    }
  } catch (err) {
    appendChatMessage(err.message, 'ai');
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
  }
}

function bindChatWidget() {
  document.getElementById('open-chat-btn')?.addEventListener('click', openChatWidget);
  document.getElementById('close-chat-btn')?.addEventListener('click', closeChatWidget);
  document.getElementById('chat-cancel-btn')?.addEventListener('click', closeChatWidget);
  document.getElementById('chat-clear-btn')?.addEventListener('click', clearChatHistory);
  document.getElementById('chat-send-btn')?.addEventListener('click', handleChatSend);
  document.getElementById('chat-input')?.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSend();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('chat-widget')?.classList.contains('open')) {
      closeChatWidget();
    }
  });
}

async function init() {
  applyAuthUi();
  const params = new URLSearchParams(window.location.search);
  const trackNum = params.get('track');
  if (trackNum) {
    state.view = 'track';
    state.prefillTracking = trackNum;
  }
  if (state.token) {
    try {
      const session = await api('/me');
      setSession(state.token, session.user);
    } catch (e) {
      clearSession();
    }
  }
  try {
    const data = await api('/products');
    state.products = data.products;
  } catch (e) {
    toast('Could not load products. Is the server running?');
  }
  await refreshCart();
  await render();
  document.body.insertAdjacentHTML('beforeend', viewChatWidget());
  bindChatWidget();
}

init();
