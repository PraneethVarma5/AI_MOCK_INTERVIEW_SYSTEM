// auth.js
// Pure Supabase Auth (frontend-driven)
// Requires: <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
// main.js should already define API_BASE

const SUPABASE_URL = 'https://ftxbbdmhuzgtbuwdsvkc.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ0eGJiZG1odXpndGJ1d2RzdmtjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMzUwOTcsImV4cCI6MjA5MDcxMTA5N30.p7O7MnQQ79drskPxFylQFWayK0-2Uc77OjmDPjnr0vw';

const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ── AUTH STATE ────────────────────────────────────────────────────────────────
const Auth = {
    user: null,
    accessToken: null,
    refreshToken: null,
    isGuest: false,
    guestId: null,

    init: async function () {
        const saved = localStorage.getItem('interviewai_auth');
        if (saved) {
            try {
                const data = JSON.parse(saved);
                this.user = data.user || null;
                this.accessToken = data.accessToken || null;
                this.refreshToken = data.refreshToken || null;
                this.isGuest = data.isGuest || false;
                this.guestId = data.guestId || null;
            } catch (_) {
                localStorage.removeItem('interviewai_auth');
            }
        }

        // Sync from Supabase session if available
        try {
            const { data } = await supabaseClient.auth.getSession();
            const session = data?.session;

            if (session) {
                this.accessToken = session.access_token;
                this.refreshToken = session.refresh_token;
                this.isGuest = false;

                const { data: userData } = await supabaseClient.auth.getUser();
                const user = userData?.user;

                if (user) {
                    this.user = {
                        id: user.id,
                        email: user.email,
                        full_name: (user.user_metadata || {}).full_name || ''
                    };
                    this.save();

                    // best-effort profile sync to backend
                    this.syncProfile().catch(() => {});
                }
            }
        } catch (e) {
            console.warn('Supabase session restore failed:', e);
        }

        // Listen for auth changes
        supabaseClient.auth.onAuthStateChange(async (event, session) => {
            if (session) {
    this.accessToken = session.access_token;
    this.refreshToken = session.refresh_token;
    this.isGuest = false;

    const user = session.user;
    this.user = {
        id: user.id,
        email: user.email,
        full_name: (user.user_metadata || {}).full_name || ''
    };
    this.save();
    this.updateHeaderUI();
    this.enforceAuthGate();

    // If we're in password recovery flow, force reset modal again
    if (sessionStorage.getItem('interviewai_recovery_mode') === 'true') {
        setTimeout(() => {
            const modal = document.getElementById('modal-auth');
            const tabs = document.getElementById('auth-tabs');

            document.querySelectorAll('.auth-form-section').forEach(el => el.classList.remove('active'));
            document.getElementById('auth-reset')?.classList.add('active');

            if (modal) {
                modal.style.zIndex = '9999';
                modal.classList.add('active');
            }

            if (tabs) tabs.style.display = 'none';
        }, 100);
    }
}
        });

        this.updateHeaderUI();
        this.enforceAuthGate();

        // Handle password recovery redirect
        await this.handleRecoveryFlow();
    },

    save() {
        localStorage.setItem('interviewai_auth', JSON.stringify({
            user: this.user,
            accessToken: this.accessToken,
            refreshToken: this.refreshToken,
            isGuest: this.isGuest,
            guestId: this.guestId,
        }));
    },

    clear() {
        this.user = null;
        this.accessToken = null;
        this.refreshToken = null;
        this.isGuest = false;
        this.guestId = null;
        localStorage.removeItem('interviewai_auth');
        this.updateHeaderUI();
        this.enforceAuthGate();
    },

    isLoggedIn() {
        return !!this.accessToken || this.isGuest;
    },

    getAuthHeaders() {
        if (this.accessToken) {
            return { 'Authorization': `Bearer ${this.accessToken}` };
        }
        return {};
    },

    async syncProfile() {
        if (!this.accessToken || !this.user) return;

        try {
            await fetch(`${API_BASE}/auth/sync-profile`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.getAuthHeaders()
                },
                body: JSON.stringify({
                    email: this.user.email,
                    full_name: this.user.full_name || ''
                })
            });
        } catch (e) {
            console.warn('Profile sync failed:', e);
        }
    },

async handleRecoveryFlow() {
    try {
        const hashParams = new URLSearchParams((window.location.hash || '').replace(/^#/, ''));
        const queryParams = new URLSearchParams(window.location.search || '');

        const type =
            hashParams.get('type') ||
            queryParams.get('type');

        const accessToken =
            hashParams.get('access_token') ||
            queryParams.get('access_token');

        const refreshToken =
            hashParams.get('refresh_token') ||
            queryParams.get('refresh_token');

        const code = queryParams.get('code');

        let recoveryDetected = false;

        // Case 1: direct recovery tokens in URL
        if (type === 'recovery' && accessToken && refreshToken) {
            const { error } = await supabaseClient.auth.setSession({
                access_token: accessToken,
                refresh_token: refreshToken
            });

            if (error) {
                console.error('Recovery session failed:', error.message);
                return;
            }

            recoveryDetected = true;
        }

        // Case 2: PKCE/code flow
        if (!recoveryDetected && (type === 'recovery' || code)) {
            await new Promise(resolve => setTimeout(resolve, 1200));

            const { data, error } = await supabaseClient.auth.getSession();
            if (!error && data?.session) {
                recoveryDetected = true;
            }
        }

        if (recoveryDetected) {
            sessionStorage.setItem('interviewai_recovery_mode', 'true');

            // Clear URL tokens so refresh doesn't look cursed
            if (window.history?.replaceState) {
                const cleanUrl = `${window.location.origin}${window.location.pathname}`;
                window.history.replaceState({}, document.title, cleanUrl);
            }

            setTimeout(() => {
                const modal = document.getElementById('modal-auth');
                const tabs = document.getElementById('auth-tabs');
                const resetSection = document.getElementById('auth-reset');

                document.querySelectorAll('.auth-form-section').forEach(el => el.classList.remove('active'));
                resetSection?.classList.add('active');

                if (tabs) tabs.style.display = 'none';

                if (modal) {
                    modal.style.zIndex = '9999';
                    modal.classList.add('active');
                }
            }, 150);
        }
    } catch (e) {
        console.error('Recovery flow error:', e);
    }
},

    // ── Auth Gate ──────────────────────────────────────────────────────────
    enforceAuthGate() {
        const gate = document.getElementById('auth-gate');
        if (!gate) return;

        if (!this.isLoggedIn()) {
            gate.classList.add('visible');
        } else {
            gate.classList.remove('visible');
        }

        this._updateModeCardLocking();

        const guestNotice = document.getElementById('guest-notice');
        if (guestNotice) {
            guestNotice.style.display = this.isGuest ? 'block' : 'none';
        }
    },

    _updateModeCardLocking() {
        const resumeCard = document.getElementById('resume-jd-card');
        if (!resumeCard) return;

        if (this.isGuest) {
            resumeCard.classList.add('locked');

            if (!resumeCard.querySelector('.mode-badge-lock')) {
                const lockBadge = document.createElement('span');
                lockBadge.className = 'mode-badge-lock';
                lockBadge.textContent = '🔒 Login Required';
                resumeCard.insertBefore(lockBadge, resumeCard.firstChild);
            }
        } else {
            resumeCard.classList.remove('locked');
            const lockBadge = resumeCard.querySelector('.mode-badge-lock');
            if (lockBadge) lockBadge.remove();
        }
    },

    // ── Header UI ──────────────────────────────────────────────────────────
    updateHeaderUI() {
        const area = document.getElementById('auth-header-area');
        if (!area) return;

        if (this.isGuest) {
            area.innerHTML = `
                <div class="user-avatar">
                    <div class="user-avatar-circle">G</div>
                    <span style="font-size:0.82rem;color:var(--text-secondary);">Guest</span>
                    <button class="auth-header-btn" onclick="Auth.clear();location.reload()">Sign In</button>
                </div>`;
        } else if (this.user) {
            const initials = (this.user.full_name || this.user.email || 'U')
                .split(' ')
                .map(w => w[0])
                .slice(0, 2)
                .join('')
                .toUpperCase();

            area.innerHTML = `
                <div class="user-avatar" style="gap:10px;">
                    <button style="background:none;border:none;color:var(--text-secondary);padding:0;font-size:0.82rem;cursor:pointer;font-weight:600;" onclick="openDashboard()">📊 Dashboard</button>
                    <div class="user-avatar-circle" title="${this.user.email}">${initials}</div>
                    <button class="auth-header-btn" onclick="handleLogout()">Sign Out</button>
                </div>`;
        } else {
            area.innerHTML = `<button class="auth-header-btn" onclick="openAuthModal('login')" id="signin-header-btn">Sign In</button>`;
        }
    }
};

// ── MODAL HELPERS ─────────────────────────────────────────────────────────────
function openAuthModal(tab) {
    const modal = document.getElementById('modal-auth');
    if (!modal) return;
    modal.style.zIndex = '300';
    modal.classList.add('active');
    if (tab) switchAuthTab(tab);
}

function closeAuthModal() {
    const modal = document.getElementById('modal-auth');
    if (modal) modal.classList.remove('active');
}

function handleResumeCardClick() {
    if (!Auth.isLoggedIn() || Auth.isGuest) {
        openAuthModal(Auth.isGuest ? 'register' : 'login');
        return;
    }
    if (typeof showSetupStep === 'function') showSetupStep();
}

// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function switchAuthTab(tab) {
    document.querySelectorAll('.auth-form-section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.auth-tab').forEach(el => el.classList.remove('active'));

    const guestArea = document.getElementById('guest-divider');
    const guestBtn  = document.getElementById('guest-btn');
    const tabs      = document.getElementById('auth-tabs');

    // OTP removed from logic
    const hideGuest = ['forgot', 'reset'].includes(tab);
    if (guestArea) guestArea.style.display = hideGuest ? 'none' : '';
    if (guestBtn)  guestBtn.style.display  = hideGuest ? 'none' : '';
    if (tabs)      tabs.style.display      = tab === 'reset' ? 'none' : '';

    const section = document.getElementById(`auth-${tab}`);
    if (section) section.classList.add('active');

    if (tab === 'login')    document.querySelectorAll('.auth-tab')[0]?.classList.add('active');
    if (tab === 'register') document.querySelectorAll('.auth-tab')[1]?.classList.add('active');

    clearAuthErrors();
}

function clearAuthErrors() {
    document.querySelectorAll('.auth-error, .auth-success').forEach(el => {
        el.classList.remove('visible');
        el.textContent = '';
    });
}

function showAuthError(id, msg) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = msg;
        el.classList.add('visible');
    }
}

function showAuthSuccess(id, msg) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = msg;
        el.classList.add('visible');
    }
}

// ── REGISTER ─────────────────────────────────────────────────────────────────
async function handleRegister() {
    const name     = document.getElementById('register-name')?.value.trim() || '';
    const email    = document.getElementById('register-email')?.value.trim() || '';
    const password = document.getElementById('register-password')?.value || '';

    clearAuthErrors();

    if (!email || !password) return showAuthError('register-error', 'Email and password are required.');
    if (password.length < 8) return showAuthError('register-error', 'Password must be at least 8 characters.');
    if (!email.includes('@')) return showAuthError('register-error', 'Please enter a valid email address.');

    const btn = document.querySelector('#auth-register .btn');
    if (btn) {
        btn.textContent = 'Creating account…';
        btn.disabled = true;
    }

    try {
        const redirectTo = `${window.location.origin}${window.location.pathname}`;
        const { data, error } = await supabaseClient.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: redirectTo,
                data: {
                    full_name: name
                }
            }
        });

        if (error) throw error;

        // If email confirmation is enabled, session may be null until verified
        showAuthSuccess(
            'register-success',
            '✅ Account created! Check your email and click the verification link, then sign in.'
        );

        // best-effort profile sync if session already exists
        if (data?.session && data?.user) {
            Auth.user = {
                id: data.user.id,
                email: data.user.email,
                full_name: (data.user.user_metadata || {}).full_name || name || ''
            };
            Auth.accessToken = data.session.access_token;
            Auth.refreshToken = data.session.refresh_token;
            Auth.isGuest = false;
            Auth.save();
            await Auth.syncProfile();
        }

        setTimeout(() => switchAuthTab('login'), 1800);
    } catch (e) {
        showAuthError('register-error', e.message || 'Registration failed.');
    } finally {
        if (btn) {
            btn.textContent = 'Create Account →';
            btn.disabled = false;
        }
    }
}

// ── LOGIN ─────────────────────────────────────────────────────────────────────
async function handleLogin() {
    const email    = document.getElementById('login-email')?.value.trim() || '';
    const password = document.getElementById('login-password')?.value || '';

    clearAuthErrors();

    if (!email || !password) {
        return showAuthError('login-error', 'Email and password are required.');
    }

    const btn = document.querySelector('#auth-login .btn');
    if (btn) {
        btn.textContent = 'Signing in…';
        btn.disabled = true;
    }

    try {
        const { data, error } = await supabaseClient.auth.signInWithPassword({
            email,
            password
        });

        if (error) throw error;

        Auth.user = {
            id: data.user.id,
            email: data.user.email,
            full_name: (data.user.user_metadata || {}).full_name || ''
        };
        Auth.accessToken = data.session.access_token;
        Auth.refreshToken = data.session.refresh_token;
        Auth.isGuest = false;

        Auth.save();
        Auth.updateHeaderUI();
        Auth.enforceAuthGate();
        closeAuthModal();

        const gate = document.getElementById('auth-gate');
        if (gate) gate.classList.remove('visible');

        await Auth.syncProfile();

        if (typeof showSuccess === 'function') {
            showSuccess(`Welcome back, ${Auth.user.full_name || Auth.user.email}! 👋`);
        }
    } catch (e) {
        const msg = (e.message || '').toLowerCase();

        if (msg.includes('email not confirmed') || msg.includes('not confirmed')) {
            showAuthError('login-error', 'Please verify your email first. Check your inbox.');
        } else if (msg.includes('invalid login credentials')) {
            showAuthError('login-error', 'Invalid email or password.');
        } else {
            showAuthError('login-error', e.message || 'Login failed.');
        }
    } finally {
        if (btn) {
            btn.textContent = 'Sign In →';
            btn.disabled = false;
        }
    }
}

// ── FORGOT PASSWORD ───────────────────────────────────────────────────────────
async function handleForgotPassword() {
    const email = document.getElementById('forgot-email')?.value.trim() || '';
    clearAuthErrors();

    if (!email) return showAuthError('forgot-error', 'Please enter your email.');

    const btn = document.querySelector('#auth-forgot .btn');
    if (btn) {
        btn.textContent = 'Sending…';
        btn.disabled = true;
    }

    try {
        const { error } = await supabaseClient.auth.resetPasswordForEmail(email, {
            redirectTo: `${window.location.origin}${window.location.pathname}?mode=recovery`
        });

        if (error) {
            // nicer message for Supabase rate limit
            if ((error.message || '').toLowerCase().includes('rate limit')) {
                throw new Error('Too many reset emails sent. Wait a few minutes and try again.');
            }
            throw error;
        }

        showAuthSuccess('forgot-success', 'If that email exists, a reset link has been sent. Check your inbox.');
    } catch (e) {
        showAuthError('forgot-error', e.message || 'Failed to send reset email.');
    } finally {
        if (btn) {
            btn.textContent = 'Send Reset Link →';
            btn.disabled = false;
        }
    }
}
// ── RESET PASSWORD ────────────────────────────────────────────────────────────
// Used ONLY after Supabase recovery redirect
async function handleResetPassword() {
    const newPw = document.getElementById('new-password')?.value || '';
    const confirmPw = document.getElementById('confirm-password')?.value || '';

    clearAuthErrors();

    if (!newPw || !confirmPw) {
        return showAuthError('reset-error', 'Please enter both password fields.');
    }

    if (newPw !== confirmPw) {
        return showAuthError('reset-error', 'Passwords do not match.');
    }

    if (newPw.length < 8) {
        return showAuthError('reset-error', 'Password must be at least 8 characters.');
    }

    const btn = document.querySelector('#auth-reset .btn');
    if (btn) {
        btn.textContent = 'Updating Password…';
        btn.disabled = true;
    }

    try {
        const { error } = await supabaseClient.auth.updateUser({
            password: newPw
        });

        if (error) throw error;

        showAuthSuccess('reset-success', '✅ Password updated successfully! Redirecting to login...');

        // Exit recovery mode
        sessionStorage.removeItem('interviewai_recovery_mode');

        // Clear input fields
        const np = document.getElementById('new-password');
        const cp = document.getElementById('confirm-password');
        if (np) np.value = '';
        if (cp) cp.value = '';

        // Sign out recovery session so user must login fresh
        await supabaseClient.auth.signOut();
        Auth.clear();

        setTimeout(() => {
            const tabs = document.getElementById('auth-tabs');
            if (tabs) tabs.style.display = '';

            switchAuthTab('login');
            openAuthModal('login');
        }, 1200);

    } catch (e) {
        showAuthError('reset-error', e.message || 'Reset failed.');
    } finally {
        if (btn) {
            btn.textContent = 'Reset Password →';
            btn.disabled = false;
        }
    }
}
// ── LOGOUT ────────────────────────────────────────────────────────────────────
async function handleLogout() {
    try {
        await supabaseClient.auth.signOut();
    } catch (_) {}

    try {
        await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...Auth.getAuthHeaders() }
        });
    } catch (_) {}

    Auth.clear();

    if (typeof showSuccess === 'function') {
        showSuccess('Signed out successfully.');
    }
}

// ── GUEST ─────────────────────────────────────────────────────────────────────
async function continueAsGuest() {
    try {
        const res = await fetch(`${API_BASE}/auth/guest`, { method: 'POST' });
        const data = await res.json();

        Auth.isGuest = true;
        Auth.guestId = data.guest_id;
        Auth.user = null;
        Auth.accessToken = null;
        Auth.refreshToken = null;
        Auth.save();
    } catch (_) {
        Auth.isGuest = true;
        Auth.guestId = `guest_${Date.now()}`;
        Auth.save();
    }

    Auth.updateHeaderUI();
    Auth.enforceAuthGate();
    closeAuthModal();

    const gate = document.getElementById('auth-gate');
    if (gate) gate.classList.remove('visible');

    if (typeof showSuccess === 'function') {
        showSuccess("Continuing as Guest — Resume+JD mode requires a free account.");
    }
}

// ── EXPERIENCE LEVEL TOGGLE ───────────────────────────────────────────────────
let _experienceLevel = 'experienced';
let _experienceYears = '2';

function setExperienceLevel(level) {
    _experienceLevel = level;
    document.getElementById('exp-fresher-btn')?.classList.toggle('active', level === 'fresher');
    document.getElementById('exp-experienced-btn')?.classList.toggle('active', level === 'experienced');

    const yearsRow = document.getElementById('exp-years-row');
    const hint = document.getElementById('exp-hint');

    if (level === 'fresher') {
        yearsRow?.classList.remove('visible');
        if (hint) hint.textContent = 'Questions will be tailored for freshers — focused on academics, fundamentals, and projects.';
    } else {
        yearsRow?.classList.add('visible');
        const years = document.getElementById('exp-years-select')?.value || '2';
        if (hint) hint.textContent = `Questions will be tailored to experienced professionals (${years} yr${years !== '1' ? 's' : ''}) with production system knowledge.`;
    }
}

// ── DOM READY ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    const yearsSelect = document.getElementById('exp-years-select');
    if (yearsSelect) {
        yearsSelect.addEventListener('change', () => {
            _experienceYears = yearsSelect.value;
            if (_experienceLevel === 'experienced') {
                const hint = document.getElementById('exp-hint');
                if (hint) hint.textContent = `Questions will be tailored to experienced professionals (${_experienceYears} yr${_experienceYears !== '1' ? 's' : ''}) with production system knowledge.`;
            }
        });
    }

    if (typeof setupOTPInputs === 'function') {
        setupOTPInputs();
    }

    await Auth.init();
});

// ── DASHBOARD ─────────────────────────────────────────────────────────────────
// ── PASSWORD UTILITIES ─────────────────────────────────────────────────────────
function togglePwVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    btn.textContent = isHidden ? '🙈' : '👁';
}

function updatePwStrength(value, context) {
    // context = 'register' | 'reset'
    const segs = context === 'reset'
        ? [document.getElementById('pw-seg-r1'), document.getElementById('pw-seg-r2'),
           document.getElementById('pw-seg-r3'), document.getElementById('pw-seg-r4')]
        : [document.getElementById('pw-seg-1'), document.getElementById('pw-seg-2'),
           document.getElementById('pw-seg-3'), document.getElementById('pw-seg-4')];
    const label = document.getElementById(`pw-label-${context}`);

    if (!segs[0]) return;

    let score = 0;
    if (value.length >= 8) score++;
    if (/[A-Z]/.test(value)) score++;
    if (/[0-9]/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;

    const classes = ['', 'weak', 'fair', 'fair', 'strong'];
    const labels  = ['', 'Weak', 'Fair', 'Good', 'Strong ✓'];
    const colors  = { weak: '#ff5252', fair: '#ffc107', strong: '#69f0ae' };

    segs.forEach((s, i) => {
        s.className = 'pw-seg';
        if (i < score) s.classList.add(classes[score]);
    });

    if (label) {
        label.textContent = value.length > 0 ? labels[score] : '';
        label.style.color = colors[classes[score]] || 'var(--text-secondary)';
    }
}

// ── COMPLETE DASHBOARD RENDER ──────────────────────────────────────────────────
let _dbCharts = {};
let _dbRawData = null;
let _dbCurrentMode = 'all';

function _destroyCharts() {
    Object.values(_dbCharts).forEach(c => { try { c.destroy(); } catch(_) {} });
    _dbCharts = {};
}

function _scoreClass(s) {
    if (s >= 7) return 'db-score-hi';
    if (s >= 5) return 'db-score-mid';
    return 'db-score-lo';
}

function _modeChip(mode) {
    const m = (mode || '').toLowerCase();
    const map = {
        resume: ['db-chip-resume', 'Resume+JD'],
        hr:     ['db-chip-hr', 'HR'],
        role:   ['db-chip-role', 'Role']
    };
    const [cls, label] = map[m] || ['db-chip-hr', mode.toUpperCase()];
    return `<span class="db-mode-chip ${cls}">${label}</span>`;
}

function _chartDefaults() {
    return {
        color: 'rgba(255,255,255,0.7)',
        borderColor: 'rgba(255,255,255,0.15)',
        grid: { color: 'rgba(255,255,255,0.06)', drawBorder: false },
        ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } }
    };
}

function _buildLineDataset(data, label, color) {
    return {
        label,
        data: data.map(x => x.score),
        borderColor: color,
        backgroundColor: color.replace('1)', '0.08)'),
        borderWidth: 2,
        pointBackgroundColor: color,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.35,
        fill: true
    };
}

function renderDashboard(data, modeFilter) {
    _dbRawData = data;
    _dbCurrentMode = modeFilter || 'all';
    _destroyCharts();

    const content = document.getElementById('dashboard-content');
    if (!content) return;

    const ov = data.overview || {};
    const byType = data.by_type || [];
    const byDiff = data.by_difficulty || [];
    const recent = data.recent_sessions || [];
    const weakAreas = data.weak_areas || [];
    const scoreOverTime = data.score_over_time || [];
    const modeDistribution = data.mode_distribution || [];
    const modeAvgScores = data.mode_avg_scores || [];
    const byModeTime = data.score_over_time_by_mode || {};

    const isFiltered = modeFilter && modeFilter !== 'all';

    // Build KPI delta indicator
    const imp = ov.improvement ?? 0;
    const impClass = imp >= 0 ? 'pos' : 'neg';
    const impSign = imp >= 0 ? '+' : '';

    content.innerHTML = `
        <!-- MODE FILTER BAR -->
        <div class="db-mode-bar">
            <button class="db-mode-btn ${_dbCurrentMode === 'all'    ? 'active' : ''}" onclick="filterDashboard('all')">🌐 All Modes</button>
            <button class="db-mode-btn ${_dbCurrentMode === 'resume' ? 'active' : ''}" onclick="filterDashboard('resume')">📄 Resume + JD</button>
            <button class="db-mode-btn ${_dbCurrentMode === 'hr'     ? 'active' : ''}" onclick="filterDashboard('hr')">🎯 HR / Behavioral</button>
            <button class="db-mode-btn ${_dbCurrentMode === 'role'   ? 'active' : ''}" onclick="filterDashboard('role')">💼 Role-Based</button>
        </div>

        <!-- KPI CARDS -->
        <div class="db-kpi-grid">
            <div class="db-kpi" style="--kpi-accent: linear-gradient(90deg, #7c4dff, #9c6bff);">
                <div class="db-kpi-icon">🏆</div>
                <div class="db-kpi-val">${ov.total_sessions ?? 0}</div>
                <div class="db-kpi-lbl">Sessions Done</div>
                <div class="db-kpi-delta">${ov.total_questions ?? 0} questions answered</div>
            </div>
            <div class="db-kpi" style="--kpi-accent: linear-gradient(90deg, #00e5ff, #0091ea);">
                <div class="db-kpi-icon">📈</div>
                <div class="db-kpi-val">${ov.avg_score ?? 0}</div>
                <div class="db-kpi-lbl">Avg Score</div>
                <div class="db-kpi-delta ${impClass}">${impSign}${imp} vs first 3 sessions</div>
            </div>
            <div class="db-kpi" style="--kpi-accent: linear-gradient(90deg, #69f0ae, #00c853);">
                <div class="db-kpi-icon">⭐</div>
                <div class="db-kpi-val">${ov.best_score ?? 0}</div>
                <div class="db-kpi-lbl">Best Score</div>
                <div class="db-kpi-delta">${ov.strong_answers ?? 0} strong answers (7+)</div>
            </div>
            <div class="db-kpi" style="--kpi-accent: linear-gradient(90deg, #ffa726, #ff6d00);">
                <div class="db-kpi-icon">💪</div>
                <div class="db-kpi-val">${ov.strong_rate ?? 0}%</div>
                <div class="db-kpi-lbl">Success Rate</div>
                <div class="db-kpi-delta">${ov.weak_answers ?? 0} answers below 5</div>
            </div>
        </div>

        <!-- SCORE TREND + DONUT -->
        <div class="db-chart-grid">
            <div class="db-card">
                <div class="db-card-title"><div class="db-dot"></div>Score Trend Over Time</div>
                <div class="db-canvas-wrap"><canvas id="db-line-chart"></canvas></div>
            </div>
            <div class="db-card">
                <div class="db-card-title"><div class="db-dot" style="background:#00e5ff;"></div>Sessions by Mode</div>
                <div class="db-canvas-wrap"><canvas id="db-donut-chart"></canvas></div>
            </div>
        </div>

        <!-- TYPE + DIFFICULTY + WEAK AREAS -->
        <div class="db-chart-grid-3">
            <div class="db-card">
                <div class="db-card-title"><div class="db-dot" style="background:#69f0ae;"></div>By Question Type</div>
                <div class="db-canvas-wrap"><canvas id="db-type-chart"></canvas></div>
            </div>
            <div class="db-card">
                <div class="db-card-title"><div class="db-dot" style="background:#ffa726;"></div>By Difficulty</div>
                <div class="db-canvas-wrap"><canvas id="db-diff-chart"></canvas></div>
            </div>
            <div class="db-card">
                <div class="db-card-title"><div class="db-dot" style="background:#ff5252;"></div>Weak Areas</div>
                ${weakAreas.length
                    ? weakAreas.map(w => `
                        <div class="db-weak-item">
                            <span class="db-weak-label">${w.type}</span>
                            <div class="db-weak-track"><div class="db-weak-fill" style="width:${Math.min((w.avg_score||0)*10,100)}%"></div></div>
                            <span class="db-weak-score">${w.avg_score}</span>
                        </div>`).join('')
                    : `<div class="db-empty" style="padding:20px;">
                        <div class="db-empty-icon">🎉</div>
                        <div class="db-empty-msg">No weak areas!</div>
                        <div class="db-empty-sub">All question types averaging ≥ 6</div>
                       </div>`
                }
            </div>
        </div>

        <!-- RECENT SESSIONS TABLE -->
        <div class="db-card">
            <div class="db-card-title" style="margin-bottom:14px;"><div class="db-dot" style="background:#9c6bff;"></div>Recent Sessions</div>
            ${recent.length
                ? `<div class="db-table-wrap">
                    <table class="db-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Mode</th>
                                <th>Role / Topic</th>
                                <th>Difficulty</th>
                                <th>Qs</th>
                                <th>Score</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${recent.map(r => {
                                const s = r.score ?? 0;
                                const sc = _scoreClass(s);
                                return `<tr>
                                    <td style="color:var(--text-secondary);">${r.date || '—'}</td>
                                    <td>${_modeChip(r.mode)}</td>
                                    <td style="font-size:0.8rem;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.role || '—'}</td>
                                    <td style="text-transform:capitalize;color:var(--text-secondary);font-size:0.8rem;">${r.difficulty || '—'}</td>
                                    <td style="text-align:center;color:var(--text-secondary);">${r.questions || 0}</td>
                                    <td><span class="db-score-badge ${sc}">${s}</span></td>
                                    <td><button class="db-view-btn" onclick="openSessionDetail('${r.id}')">View →</button></td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                   </div>`
                : `<div class="db-empty">
                    <div class="db-empty-icon">📭</div>
                    <div class="db-empty-msg">No sessions yet</div>
                    <div class="db-empty-sub">Complete an interview to see your history here.</div>
                   </div>`
            }
        </div>
    `;

    // ── CHART.JS CHARTS ──────────────────────────────────────────────────────
    const cd = _chartDefaults();
    const chartBase = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
    };

    // 1. Score Trend Line
    const lineCtx = document.getElementById('db-line-chart');
    if (lineCtx) {
        const allModeKeys = Object.keys(byModeTime);
        const modeColors = {
            resume: '#7c4dff',
            hr:     '#00e5ff',
            role:   '#69f0ae'
        };

        let datasets = [];
        let labels = [];

        if (isFiltered) {
            // Show only this mode's trend
            const trend = byModeTime[modeFilter] || scoreOverTime;
            labels = trend.map((x, i) => x.date || `S${i+1}`);
            datasets = [_buildLineDataset(trend, modeFilter, modeColors[modeFilter] || '#7c4dff')];
        } else {
            // Show all modes overlaid
            const allDates = new Set();
            allModeKeys.forEach(k => (byModeTime[k]||[]).forEach(x => allDates.add(x.date || '')));
            labels = scoreOverTime.map((x, i) => x.date || `S${i+1}`);
            if (allModeKeys.length > 1) {
                // Multiple mode datasets
                datasets = allModeKeys.map(k => _buildLineDataset(
                    byModeTime[k] || [],
                    k.charAt(0).toUpperCase() + k.slice(1),
                    modeColors[k] || '#9c6bff'
                ));
            } else {
                datasets = [_buildLineDataset(scoreOverTime, 'Score', '#7c4dff')];
            }
        }

        _dbCharts.line = new Chart(lineCtx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                ...chartBase,
                plugins: {
                    legend: { display: datasets.length > 1, labels: { color: 'rgba(255,255,255,0.6)', font: { size: 10 }, boxWidth: 12 } },
                    tooltip: { callbacks: { label: ctx => ` Score: ${ctx.raw}/10` } }
                },
                scales: {
                    x: { grid: cd.grid, ticks: cd.ticks },
                    y: { min: 0, max: 10, grid: cd.grid, ticks: { ...cd.ticks, stepSize: 2 } }
                }
            }
        });
    }

    // 2. Sessions Donut
    const donutCtx = document.getElementById('db-donut-chart');
    if (donutCtx && modeDistribution.length) {
        const donutColors = ['#7c4dff','#00e5ff','#69f0ae','#ffa726'];
        _dbCharts.donut = new Chart(donutCtx, {
            type: 'doughnut',
            data: {
                labels: modeDistribution.map(x => x.mode),
                datasets: [{
                    data: modeDistribution.map(x => x.count),
                    backgroundColor: donutColors,
                    borderColor: 'rgba(0,0,0,0)',
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                ...chartBase,
                cutout: '62%',
                plugins: {
                    legend: { display: true, position: 'bottom', labels: { color: 'rgba(255,255,255,0.6)', font: { size: 10 }, boxWidth: 10, padding: 12 } }
                }
            }
        });
    } else if (donutCtx) {
        donutCtx.parentElement.innerHTML = '<div class="db-empty" style="padding:20px;"><div class="db-empty-icon">📊</div><div class="db-empty-sub">No data yet</div></div>';
    }

    // 3. By Type Bar
    const typeCtx = document.getElementById('db-type-chart');
    if (typeCtx && byType.length) {
        _dbCharts.type = new Chart(typeCtx, {
            type: 'bar',
            data: {
                labels: byType.map(x => x.type),
                datasets: [{
                    label: 'Avg Score',
                    data: byType.map(x => x.avg_score),
                    backgroundColor: byType.map(x => x.avg_score >= 7 ? 'rgba(105,240,174,0.6)' : x.avg_score >= 5 ? 'rgba(255,167,38,0.6)' : 'rgba(255,82,82,0.6)'),
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...chartBase,
                scales: {
                    x: { grid: { display: false }, ticks: cd.ticks },
                    y: { min: 0, max: 10, grid: cd.grid, ticks: { ...cd.ticks, stepSize: 2 } }
                },
                plugins: { ...chartBase.plugins, tooltip: { callbacks: { label: ctx => ` Avg: ${ctx.raw}/10` } } }
            }
        });
    } else if (typeCtx) {
        typeCtx.parentElement.innerHTML = '<div class="db-empty" style="padding:20px;"><div class="db-empty-icon">📊</div><div class="db-empty-sub">No data yet</div></div>';
    }

    // 4. By Difficulty Bar
    const diffCtx = document.getElementById('db-diff-chart');
    if (diffCtx && byDiff.length) {
        const diffColors = { Easy: 'rgba(105,240,174,0.6)', Medium: 'rgba(255,167,38,0.6)', Hard: 'rgba(255,82,82,0.6)' };
        _dbCharts.diff = new Chart(diffCtx, {
            type: 'bar',
            data: {
                labels: byDiff.map(x => x.difficulty),
                datasets: [{
                    data: byDiff.map(x => x.avg_score),
                    backgroundColor: byDiff.map(x => diffColors[x.difficulty] || 'rgba(124,77,255,0.6)'),
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...chartBase,
                scales: {
                    x: { grid: { display: false }, ticks: cd.ticks },
                    y: { min: 0, max: 10, grid: cd.grid, ticks: { ...cd.ticks, stepSize: 2 } }
                },
                plugins: { ...chartBase.plugins, tooltip: { callbacks: { label: ctx => ` Avg: ${ctx.raw}/10` } } }
            }
        });
    } else if (diffCtx) {
        diffCtx.parentElement.innerHTML = '<div class="db-empty" style="padding:20px;"><div class="db-empty-icon">📊</div><div class="db-empty-sub">No data yet</div></div>';
    }
}

function filterDashboard(mode) {
    if (!_dbRawData) return;
    _dbCurrentMode = mode;
    _destroyCharts();

    const isFiltered = mode && mode !== 'all';

    // Filter recent sessions
    const filteredRecent = isFiltered
        ? (_dbRawData.recent_sessions || []).filter(x => (x.mode || '').toLowerCase() === mode)
        : (_dbRawData.recent_sessions || []);

    // Filter score over time
    const byModeTime = _dbRawData.score_over_time_by_mode || {};
    const filteredTrend = isFiltered
        ? (byModeTime[mode] || []).map((x, i) => ({ ...x, session_number: i+1 }))
        : (_dbRawData.score_over_time || []);

    // Filter mode avg for KPI
    const modeAvg = isFiltered
        ? (_dbRawData.mode_avg_scores || []).find(x => (x.mode || '').toLowerCase() === mode)
        : null;

    const filteredData = {
        ..._dbRawData,
        recent_sessions: filteredRecent,
        score_over_time: filteredTrend,
        overview: {
            ..._dbRawData.overview,
            avg_score: modeAvg ? modeAvg.avg_score : _dbRawData.overview?.avg_score ?? 0,
            total_sessions: isFiltered ? filteredRecent.length : _dbRawData.overview?.total_sessions ?? 0
        }
    };

    renderDashboard(filteredData, mode);
}

// ── OPEN SESSION DETAIL ────────────────────────────────────────────────────────
async function openSessionDetail(sessionId) {
    const content = document.getElementById('session-detail-content');
    if (!content) return;

    content.innerHTML = `
        <div style="text-align:center;padding:60px;color:var(--text-secondary);">
            <span class="loader" style="width:36px;height:36px;"></span>
            <p style="margin-top:16px;">Loading session...</p>
        </div>`;

    openModal('modal-session-detail');

    try {
        const res = await fetch(`${API_BASE}/analytics/session/${sessionId}`, {
            headers: { ...Auth.getAuthHeaders() }
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);

        const session = data.session || {};
        const answers = data.answers || [];
        const overall = session.overall_score ?? 0;
        const scoreClass = overall >= 7 ? 'db-score-hi' : overall >= 5 ? 'db-score-mid' : 'db-score-lo';

        const strong = answers.filter(a => (a.score ?? 0) >= 7).length;
        const weak   = answers.filter(a => (a.score ?? 0) < 5).length;

        // Format date
        let dateStr = '—';
        if (session.created_at) {
            try {
                const d = new Date(session.created_at);
                dateStr = d.toLocaleDateString('en-US', { year:'numeric', month:'short', day:'numeric' });
            } catch(_) {}
        }

        content.innerHTML = `
            <button class="sd-back-btn" onclick="closeModal('modal-session-detail'); openDashboard();">← Back to Dashboard</button>

            <!-- Session KPIs -->
            <div class="sd-header">
                <div class="sd-kpi">
                    <div class="sd-kpi-val" style="color:${overall>=7?'#69f0ae':overall>=5?'#ffc107':'#ff8a80'};">${overall}</div>
                    <div class="sd-kpi-lbl">Overall Score</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val">${_modeChip(session.mode || '')}</div>
                    <div class="sd-kpi-lbl">Mode</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val" style="font-size:1rem;">${session.role || '—'}</div>
                    <div class="sd-kpi-lbl">Role</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val">${answers.length}</div>
                    <div class="sd-kpi-lbl">Questions</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val" style="color:#69f0ae;">${strong}</div>
                    <div class="sd-kpi-lbl">Strong (7+)</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val" style="color:#ff8a80;">${weak}</div>
                    <div class="sd-kpi-lbl">Weak (&lt;5)</div>
                </div>
                <div class="sd-kpi">
                    <div class="sd-kpi-val" style="font-size:0.9rem;">${dateStr}</div>
                    <div class="sd-kpi-lbl">Date</div>
                </div>
            </div>

            <!-- Score mini-chart -->
            <div class="db-card" style="margin-bottom:16px;">
                <div class="db-card-title"><div class="db-dot"></div>Score Per Question</div>
                <div style="position:relative;height:110px;"><canvas id="sd-scores-chart"></canvas></div>
            </div>

            <!-- Q&A Accordion -->
            <div class="sd-qa-list">
                ${answers.map((a, idx) => {
                    const s = a.score ?? 0;
                    const sc = _scoreClass(s);
                    const kws = Array.isArray(a.missing_keywords) ? a.missing_keywords : [];
                    return `
                    <div class="sd-qa-card">
                        <div class="sd-qa-header" onclick="toggleQA(this)">
                            <div class="sd-qa-q">Q${idx+1}. ${a.question_text || 'Question'}</div>
                            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                                <span class="db-score-badge ${sc}" style="width:30px;height:30px;font-size:0.78rem;">${s}</span>
                                <span class="sd-qa-chevron">▼</span>
                            </div>
                        </div>
                        <div class="sd-qa-body">
                            <div class="sd-section-lbl">Your Answer</div>
                            <div class="sd-text-block">${a.user_answer || '<em style="opacity:0.5;">No answer recorded</em>'}</div>

                            <div class="sd-section-lbl">AI Feedback</div>
                            <div class="sd-text-block">${a.feedback || 'No feedback available.'}</div>

                            <div class="sd-section-lbl">Key Improvements</div>
                            <div class="sd-text-block">${a.improvements || 'No suggestions.'}</div>

                            <div class="sd-section-lbl">💡 Ideal Answer</div>
                            <div class="sd-text-block sd-ideal">${a.ideal_answer || 'N/A'}</div>

                            ${kws.length ? `
                            <div class="sd-section-lbl">Missing Keywords</div>
                            <div class="sd-kw-list">${kws.map(k => `<span class="sd-kw-tag">${k}</span>`).join('')}</div>
                            ` : ''}
                        </div>
                    </div>`;
                }).join('')}
            </div>
        `;

        // Mini bar chart for per-question scores
        const sdCtx = document.getElementById('sd-scores-chart');
        if (sdCtx && answers.length) {
            const cd = _chartDefaults();
            new Chart(sdCtx, {
                type: 'bar',
                data: {
                    labels: answers.map((_, i) => `Q${i+1}`),
                    datasets: [{
                        data: answers.map(a => a.score ?? 0),
                        backgroundColor: answers.map(a => {
                            const s = a.score ?? 0;
                            return s >= 7 ? 'rgba(105,240,174,0.7)' : s >= 5 ? 'rgba(255,167,38,0.7)' : 'rgba(255,82,82,0.7)';
                        }),
                        borderRadius: 5,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: cd.ticks },
                        y: { min: 0, max: 10, grid: cd.grid, ticks: { ...cd.ticks, stepSize: 2 } }
                    }
                }
            });
        }

    } catch(err) {
        content.innerHTML = `
            <div class="db-empty">
                <div class="db-empty-icon">⚠️</div>
                <div class="db-empty-msg">Could not load session</div>
                <div class="db-empty-sub">${err.message}</div>
            </div>`;
    }
}

function toggleQA(header) {
    const body = header.nextElementSibling;
    const chevron = header.querySelector('.sd-qa-chevron');
    if (!body) return;
    const isOpen = body.classList.contains('open');
    body.classList.toggle('open', !isOpen);
    if (chevron) chevron.classList.toggle('open', !isOpen);
}

// ── OPEN DASHBOARD ─────────────────────────────────────────────────────────────
async function openDashboard() {
    if (!Auth.isLoggedIn() || Auth.isGuest) {
        openAuthModal('login');
        return;
    }

    _dbCurrentMode = 'all';
    const modal = document.getElementById('modal-dashboard');
    const content = document.getElementById('dashboard-content');
    if (!modal || !content) return;

    content.innerHTML = `
        <div style="text-align:center;padding:60px;color:var(--text-secondary);">
            <span class="loader" style="width:36px;height:36px;"></span>
            <p style="margin-top:16px;">Loading your analytics...</p>
        </div>`;

    openModal('modal-dashboard');

    try {
        const res = await fetch(`${API_BASE}/analytics/dashboard`, {
            headers: { ...Auth.getAuthHeaders() }
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
        renderDashboard(data, 'all');
    } catch(err) {
        content.innerHTML = `
            <div class="db-empty" style="padding:60px;">
                <div class="db-empty-icon">📉</div>
                <div class="db-empty-msg">Dashboard unavailable</div>
                <div class="db-empty-sub">${err.message}</div>
            </div>`;
    }
}


async function saveSessionToSupabase(sessionMeta, questions, results, overallScore) {
    if (Auth.isGuest || !Auth.isLoggedIn()) return;

    try {
        const createRes = await fetch(`${API_BASE}/sessions/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...Auth.getAuthHeaders()
            },
            body: JSON.stringify(sessionMeta),
        });

        const createData = await createRes.json().catch(() => ({}));

        if (!createRes.ok) {
            console.error('Session create failed:', createData);
            showError?.(`Session save failed (create): ${createData.detail || createRes.status}`);
            return;
        }

        const sessionId = createData.session_id;
        if (!sessionId) {
            console.error('No session_id returned:', createData);
            showError?.('Session save failed: no session ID returned.');
            return;
        }

        const completeRes = await fetch(`${API_BASE}/sessions/${sessionId}/complete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...Auth.getAuthHeaders()
            },
            body: JSON.stringify({
                results,
                questions,
                overall_score: overallScore
            }),
        });

        const completeData = await completeRes.json().catch(() => ({}));

        if (!completeRes.ok) {
            console.error('Session complete failed:', completeData);
            showError?.(`Session save failed (complete): ${completeData.detail || completeRes.status}`);
            return;
        }

        console.log('Session saved successfully:', sessionId);
    } catch (e) {
        console.error('Session save error:', e);
        showError?.(`Session save error: ${e.message}`);
    }
}