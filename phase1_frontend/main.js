// ── CONFIG ────────────────────────────────────────────────────────────────────
const API_BASE =
    window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
        ? 'http://127.0.0.1:8000'
        : 'https://ai-mock-interview-api-9sj4.onrender.com';

// ── STATE ─────────────────────────────────────────────────────────────────────
let uploadInProgress = false;
let setupStepInitialized = false;
let uploadInitialized = false;
let startButtonInitialized = false;
let setupDifficultyInitialized = false;
let setupCountSyncInitialized = false;
let state = {
    step: 'mode',
    mode: null,           // 'hr' | 'resume' | 'role'
    resumeText: '',
    questions: [],
    currentIndex: 0,
    answers: {},          // { [index]: string }
    results: [],
    autoSelectCount: false,
    voiceMode: false,
    timerMode: false,
    timePerQuestion: 120,
    selectedRole: null,
    lockedQuestions: new Set() // only matters when timer mode is ON

};

// ── DOM HELPERS ───────────────────────────────────────────────────────────────
function $(id) { return document.getElementById(id); }

function showStep(stepName) {
    ['mode', 'setup', 'loading', 'interview', 'evaluating', 'results'].forEach(s => {
        const el = $(`step-${s}`);
        if (el) el.classList.add('hidden');
    });
    const target = $(`step-${stepName}`);
    if (target) target.classList.remove('hidden');
    state.step = stepName;
}

function showError(msg) {
    const el = $('error-toast');
    if (el) {
        el.textContent = '⚠️ ' + msg;
        el.classList.remove('hidden');
        setTimeout(() => el.classList.add('hidden'), 5000);
    } else {
        alert(msg);
    }
}

function showSuccess(msg) {
    const el = $('success-toast');
    if (el) {
        el.textContent = '✅ ' + msg;
        el.classList.remove('hidden');
        setTimeout(() => el.classList.add('hidden'), 4000);
    }
}

// ── MODAL HELPERS ─────────────────────────────────────────────────────────────
function openModal(id) {
    const el = $(id);
    if (el) el.classList.add('active');
}

function closeModal(id) {
    const el = $(id);
    if (el) el.classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// ── STEP NAVIGATION ───────────────────────────────────────────────────────────
function showModeStep() {
    clearInterval(timerInterval);

    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }

    showStep('mode');
}

function showSetupStep() {
    state.mode = 'resume';
    showStep('setup');
    restoreSetupState();

    // Initialize only once to avoid duplicate event listeners
    if (!setupStepInitialized) {
        initDifficultyPills();
        initQuestionCountSync();
        bindSetupPersistence();
        initUpload();
        initStartButton();
        setupStepInitialized = true;
    }
}

// ── DIFFICULTY PILLS ──────────────────────────────────────────────────────────
function initDifficultyPillsIn(containerId) {
    const pills = document.querySelectorAll(`#${containerId} .difficulty-pill`);
    pills.forEach(pill => {
        pill.addEventListener('click', () => {
            pills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
        });
    });
}

function getSelectedDifficultyFrom(containerId) {
    const active = document.querySelector(`#${containerId} .difficulty-pill.active`);
    return active ? active.dataset.value : 'mixed';
}

function initDifficultyPills() {
    if (setupDifficultyInitialized) return;

    const pills = document.querySelectorAll('#step-setup .difficulty-pill');
    pills.forEach(pill => {
        pill.addEventListener('click', () => {
            pills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
        });
    });

    setupDifficultyInitialized = true;
}

function getSelectedDifficulty() {
    const active = document.querySelector('#step-setup .difficulty-pill.active');
    return active ? active.dataset.value : 'mixed';
}

// ── COUNT SYNC ────────────────────────────────────────────────────────────────
function syncCount(numId, rangeId) {
    const num = $(numId), range = $(rangeId);
    if (!num || !range) return;
    num.addEventListener('input', () => { range.value = num.value; });
    range.addEventListener('input', () => { num.value = range.value; });
}

function initQuestionCountSync() {
    if (setupCountSyncInitialized) return;

    syncCount('count-input', 'count-range');

    const toggle = $('ai-optimized-toggle');
    const manual = $('manual-count-controls');

    if (toggle && manual) {
        toggle.addEventListener('change', () => {
            manual.style.display = toggle.checked ? 'none' : 'block';
            state.autoSelectCount = toggle.checked;
        });
    }

    setupCountSyncInitialized = true;
}
function normalizeResults(results) {
    return (results || []).map((r, index) => ({
        question: r.question || r.question_text || r.text || state.questions?.[index]?.text || `Question ${index + 1}`,
        answer: r.answer || r.user_answer || state.answers?.[index] || "No answer provided.",
        score: typeof r.score === 'number'
            ? r.score
            : (typeof r.hybrid_score === 'number' ? r.hybrid_score : 0),
        feedback: r.feedback || "No feedback available.",
        improvements: r.improvements || r.key_improvements || "Improve structure and relevance.",
        ideal_answer: r.ideal_answer || r.sample_answer || "No ideal answer available.",
        missing_keywords: Array.isArray(r.missing_keywords) ? r.missing_keywords : [],
        ml_relevance_score: typeof r.ml_relevance_score === 'number'
            ? r.ml_relevance_score
            : (typeof r.relevance_score === 'number' ? r.relevance_score : 0),
        type: r.type || state.questions?.[index]?.type || "technical",
        difficulty: r.difficulty || state.questions?.[index]?.difficulty || "medium"
    }));
}

// ── SETUP STATE PERSISTENCE ───────────────────────────────────────────────────
function saveSetupState() {
    const payload = {
        jd: $('jd-input')?.value || '',
        count: $('count-input')?.value || '5',
        difficulty: getSelectedDifficulty(),
        aiOptimized: $('ai-optimized-toggle')?.checked || false,
        voiceMode: $('voice-toggle')?.checked || false,
        timerMode: $('timer-toggle')?.checked || false
    };

    sessionStorage.setItem('interviewSetupState', JSON.stringify(payload));
    sessionStorage.setItem('jobDescription', payload.jd);
    sessionStorage.setItem('questionCount', payload.count);
    sessionStorage.setItem('difficulty', payload.difficulty);
}

function restoreSetupState() {
    const raw = sessionStorage.getItem('interviewSetupState');
    if (!raw) return;
    try {
        const data = JSON.parse(raw);
        if ($('jd-input')) $('jd-input').value = data.jd || '';
        if ($('count-input')) $('count-input').value = data.count || '5';
        if ($('count-range')) $('count-range').value = data.count || '5';
        if ($('ai-optimized-toggle')) $('ai-optimized-toggle').checked = !!data.aiOptimized;
        if ($('voice-toggle')) $('voice-toggle').checked = !!data.voiceMode;
        if ($('timer-toggle')) $('timer-toggle').checked = !!data.timerMode;
        const pills = document.querySelectorAll('#step-setup .difficulty-pill');
        pills.forEach(p => p.classList.remove('active'));
        const target = document.querySelector(`#step-setup .difficulty-pill[data-value="${data.difficulty || 'mixed'}"]`);
        if (target) target.classList.add('active');
        const manualControls = $('manual-count-controls');
        if (manualControls) manualControls.style.display = data.aiOptimized ? 'none' : 'block';
        state.autoSelectCount = !!data.aiOptimized;
    } catch (err) {
        console.warn('Failed to restore setup state:', err);
    }
}

function bindSetupPersistence() {
    ['jd-input', 'count-input', 'count-range', 'ai-optimized-toggle', 'voice-toggle', 'timer-toggle'].forEach(id => {        const el = $(id);
        if (!el || el.dataset.persistBound === 'true') return;
        const eventType = el.type === 'checkbox' || el.type === 'range' ? 'change' : 'input';
        el.addEventListener(eventType, saveSetupState);
        el.dataset.persistBound = 'true';
    });
    document.querySelectorAll('#step-setup .difficulty-pill').forEach(pill => {
        if (pill.dataset.persistBound === 'true') return;
        pill.addEventListener('click', () => setTimeout(saveSetupState, 0));
        pill.dataset.persistBound = 'true';
    });
}

// ── HR INTERVIEW ──────────────────────────────────────────────────────────────
async function startHRInterview() {
    const numQ = parseInt($('hr-count')?.value || '5');
    const difficulty = getSelectedDifficultyFrom('hr-difficulty-pills');
    state.mode = 'hr';
    state.voiceMode = $('hr-voice')?.checked || false;
    state.timerMode = $('hr-timer')?.checked || false;

    closeModal('modal-hr');
    showStep('loading');
    $('loading-text').textContent = 'Loading HR questions from database…';

    try {
        const res = await fetch(`${API_BASE}/db/hr_questions?num_questions=${numQ}&difficulty=${difficulty}`);
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const data = await res.json();
        state.questions = data.questions;
        state.answers = {};
        state.currentIndex = 0;
        startInterview();
    } catch (e) {
        showStep('mode');
        showError('Failed to load HR questions: ' + e.message);
    }
}

// ── ROLE INTERVIEW ────────────────────────────────────────────────────────────
async function loadRoles() {
    const sel = $('role-select');
    if (!sel) return;

    try {
        const res = await fetch(`${API_BASE}/db/roles`);
        if (!res.ok) throw new Error(`Server error ${res.status}`);

        const data = await res.json();

        if (!data.roles || data.roles.length === 0) {
            sel.innerHTML = `<option value="">No roles found</option>`;
            sel.disabled = true;
            showError('No role questions found in database. Run db_init.py first.');
            return;
        }

        sel.innerHTML = `<option value="">Select a role</option>` +
            data.roles.map(r => `<option value="${r}">${r}</option>`).join('');
        sel.disabled = false;

    } catch (e) {
        console.warn('Could not load roles:', e);
        sel.innerHTML = `<option value="">Failed to load roles</option>`;
        sel.disabled = true;
        showError('Could not load roles. Make sure backend is running and database is initialized.');
    }
}
async function startRoleInterview() {
    const role = $('role-select')?.value;
    if (!role) { showError('Please select a role.'); return; }
    const numQ = parseInt($('role-count')?.value || '5');
    const difficulty = getSelectedDifficultyFrom('role-difficulty-pills');
    state.mode = 'role';
    state.selectedRole = role;
    state.voiceMode = $('role-voice')?.checked || false;
    state.timerMode = $('role-timer')?.checked || false;

    closeModal('modal-role');
    showStep('loading');
    $('loading-text').textContent = `Loading ${role} questions from database…`;

    try {
        const res = await fetch(`${API_BASE}/db/role_questions?role=${encodeURIComponent(role)}&num_questions=${numQ}&difficulty=${difficulty}`);
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const data = await res.json();
        state.questions = data.questions;
        state.answers = {};
        state.currentIndex = 0;
        startInterview();
    } catch (e) {
        showStep('mode');
        showError('Failed to load role questions: ' + e.message);
    }
}

// ── FILE UPLOAD ───────────────────────────────────────────────────────────────
function initUpload() {
    if (uploadInitialized) return;

    const dropZone = $('drop-zone');
    const fileInput = $('resume-upload');
    const startBtn = $('start-btn');

    if (!dropZone || !fileInput) return;

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleResumeFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files?.[0];
        if (file) handleResumeFile(file);
    });

    async function handleResumeFile(file) {
        if (uploadInProgress) return;

        uploadInProgress = true;
        if (startBtn) startBtn.disabled = true;

        try {
            // Stay on setup page during upload
            showStep('setup');
            updateFileInfo(file.name, false);

            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch(`${API_BASE}/upload_resume`, {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                let errText = `Upload failed (${res.status})`;
                try {
                    const errData = await res.json();
                    errText = errData.detail || errText;
                } catch (_) {}
                throw new Error(errText);
            }

            const data = await res.json();
const extractedText = (data.resume_text || data.extracted_text || '').trim();

if (!extractedText) {
    throw new Error('Resume text extraction returned empty content.');
}

state.resumeText = extractedText;
sessionStorage.setItem('resumeText', extractedText);
sessionStorage.setItem('uploadedResumeName', file.name);

            updateFileInfo(file.name, true);
            if (startBtn) startBtn.disabled = false;
            showSuccess('Resume uploaded successfully.');

            // Stay on setup screen. DO NOT auto-navigate.
            showStep('setup');

        } catch (err) {
            console.error('Resume upload failed:', err);
            state.resumeText = '';
            sessionStorage.removeItem('resumeText');
            sessionStorage.removeItem('uploadedResumeName');

            updateFileInfo('', false);
            if (startBtn) startBtn.disabled = true;

            // Keep user on setup instead of bouncing to landing page
            showStep('setup');
            showError('Resume upload failed: ' + err.message);
        } finally {
            uploadInProgress = false;
            fileInput.value = '';
        }
    }

    // Restore previously uploaded resume from session
    const savedFileName = sessionStorage.getItem('uploadedResumeName');
    const savedText = sessionStorage.getItem('resumeText');

    if (savedFileName && savedText) {
        state.resumeText = savedText;
        updateFileInfo(savedFileName, true);
        if (startBtn) startBtn.disabled = false;
    }

    uploadInitialized = true;
}

function updateFileInfo(filename, restored = false) {
    const fileInfo = $('file-info');
    if (fileInfo) {
        fileInfo.innerHTML = `
            <div style="color:var(--success);font-weight:600;">✓ ${filename}</div>
            <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px;">${restored ? 'Previously uploaded — Ready!' : 'Resume uploaded successfully!'}</div>
        `;
    }
}

// async function handleFile(file) {
//     const MAX_SIZE = 10 * 1024 * 1024;
//     const allowed = ['.pdf', '.docx', '.txt'];
//     const ext = '.' + file.name.split('.').pop().toLowerCase();
//     if (!allowed.includes(ext)) { showError('Unsupported file type. Please use PDF, DOCX, or TXT.'); return; }
//     if (file.size > MAX_SIZE) { showError('File too large. Max size is 10 MB.'); return; }
//     if (uploadInProgress) return;
//     uploadInProgress = true;

//     const fileInfo = $('file-info');
//     const startBtn = $('start-btn');

//     if (fileInfo) {
//         fileInfo.innerHTML = `<span class="loader" style="width:28px;height:28px;"></span><p style="margin-top:12px;">Parsing resume…</p>`;
//     }
//     if (startBtn) startBtn.disabled = true;

//     try {
//         const formData = new FormData();
//         formData.append('file', file);

//         const res = await fetch(`${API_BASE}/upload_resume`, { method: 'POST', body: formData });
//         if (!res.ok) {
//             const err = await res.json().catch(() => ({}));
//             throw new Error(err.detail || `Upload failed (${res.status})`);
//         }
//         const data = await res.json();
//         state.resumeText = data.extracted_text || '';
//         sessionStorage.setItem('resumeText', state.resumeText);
//         sessionStorage.setItem('uploadedResumeName', file.name);
//         if (data.skill_match) sessionStorage.setItem('skillMatch', JSON.stringify(data.skill_match));
//         updateFileInfo(file.name);
//         if (startBtn) startBtn.disabled = false;
//         showSuccess('Resume parsed successfully!');
//     } catch (e) {
//         if (fileInfo) {
//             fileInfo.innerHTML = `<p style="color:var(--error);">⚠️ ${e.message}</p>`;
//         }
//         showError(e.message);
//     } finally {
//         uploadInProgress = false;
//     }
// }

// ── START BUTTON (Resume mode) ────────────────────────────────────────────────
function initStartButton() {
    if (startButtonInitialized) return;

    const startBtn = $('start-btn');
    if (!startBtn) return;

    startBtn.addEventListener('click', async () => {
        if (!state.resumeText) { showError('Please upload your resume first.'); return; }

        saveSetupState();

        const numQ = state.autoSelectCount ? 8 : parseInt($('count-input')?.value || '5');
        const difficulty = getSelectedDifficulty();
        const jd = $('jd-input')?.value || '';
        state.voiceMode = $('voice-toggle')?.checked || false;
        state.timerMode = $('timer-toggle')?.checked || false;
        state.mode = 'resume';

        showStep('loading');
        $('loading-text').textContent = 'Generating your personalized questions…';

        try {
            const res = await fetch(`${API_BASE}/generate_questions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                resume_text: state.resumeText,
                job_description: jd,
                difficulty,
                num_questions: numQ,
                auto_select_count: state.autoSelectCount,
                force_refresh: false
            })
            });
            if (!res.ok) throw new Error(`Question generation failed (${res.status})`);
            const data = await res.json();
            state.questions = data.questions;
            state.answers = {};
            state.currentIndex = 0;
            startInterview();
        } catch (e) {
            showStep('setup');
            showError('Failed to generate questions: ' + e.message);
        }
    });
    startButtonInitialized = true;
}

// ── INTERVIEW ENGINE ──────────────────────────────────────────────────────────
let timerInterval = null;
let timeLeft = 120;

function startInterview() {
    state.lockedQuestions = new Set();
    showStep('interview');
    renderQuestion();
    initVoiceControls();
}

function renderQuestion() {
    const q = state.questions[state.currentIndex];
    if (!q) return;
    const total = state.questions.length;
    const idx = state.currentIndex;

    $('q-counter').textContent = `Question ${idx + 1} of ${total}`;
    $('progress-fill').style.width = `${((idx + 1) / total) * 100}%`;

    const qTag = $('q-tag');
    const type = (q.type || 'technical').toLowerCase();
    qTag.textContent = type.charAt(0).toUpperCase() + type.slice(1);
    qTag.className = `question-tag tag-${type}`;

    const diffBadge = $('q-diff-badge');
    const diff = (q.difficulty || 'medium').toLowerCase();
    diffBadge.textContent = diff.charAt(0).toUpperCase() + diff.slice(1);
    diffBadge.className = `diff-badge diff-${diff}`;

    $('current-question').textContent = q.text;
    $('answer-input').value = state.answers[idx] || '';
    $('char-count').textContent = `${($('answer-input').value || '').length} characters`;

    const prevBtn = $('prev-btn');
    const nextBtn = $('submit-answer-btn');
    if (prevBtn) prevBtn.disabled = idx === 0;
    if (nextBtn) nextBtn.textContent = idx === total - 1 ? 'Finish Interview ✓' : 'Next Question →';

    const timerDisplay = $('timer-display');
if (state.timerMode) {
    startTimer();
} else {
    clearInterval(timerInterval);
    if (timerDisplay) timerDisplay.style.display = 'none';
}

if (state.voiceMode) readQuestion(q.text);
}

function startTimer() {
    clearInterval(timerInterval);
    timeLeft = state.timePerQuestion;
    const display = $('timer-display');
    if (display) display.style.display = 'block';
    updateTimerDisplay();
    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerDisplay();
        if (timeLeft <= 0) {
    clearInterval(timerInterval);
    showError("Time's up! Moving to next question.");
    advanceQuestion();
}
    }, 1000);
}

function updateTimerDisplay() {
    const display = $('timer-display');
    if (!display) return;
    const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
    const s = (timeLeft % 60).toString().padStart(2, '0');
    display.textContent = `${m}:${s}`;
    display.style.color = timeLeft <= 30 ? 'var(--error)' : 'var(--accent-color)';
}

function advanceQuestion() {
    const answerInput = document.getElementById('answer-input');
    if (answerInput) {
        state.answers[state.currentIndex] = answerInput.value || '';
    }

    // If timer mode is ON, lock the current question once user leaves it
    if (state.timerMode) {
        state.lockedQuestions.add(state.currentIndex);
    }

    if (state.currentIndex < state.questions.length - 1) {
        state.currentIndex++;
        renderQuestion();
    } else {
        finishInterview();
    }
}
function goToPreviousQuestion() {
    if (state.currentIndex <= 0) return;

    const targetIndex = state.currentIndex - 1;

    // Timer mode ON => block locked previous questions
    if (state.timerMode && state.lockedQuestions.has(targetIndex)) {
        showError("Can't go to previous question because time is done or you already submitted the answer.");
        return;
    }

    // Save current answer before moving
    const answerInput = document.getElementById('answer-input');
    if (answerInput) {
        state.answers[state.currentIndex] = answerInput.value || '';
    }

    state.currentIndex = targetIndex;
    renderQuestion();
}
function initVoiceControls() {
    const controls = $('voice-controls');
    if (!controls) return;

    if (state.voiceMode) {
        controls.style.display = 'flex';
        const readBtn = $('read-question-btn');
        const recordBtn = $('record-answer-btn');

        if (readBtn) {
            readBtn.onclick = () => {
                const q = state.questions[state.currentIndex];
                if (q) readQuestion(q.text);
            };
        }

        if (recordBtn && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            let recognition = null;

            recordBtn.onclick = () => {
                if (recognition) { recognition.stop(); recognition = null; recordBtn.textContent = '🎤 Start Recording'; return; }
                recognition = new SR();
                recognition.lang = 'en-US';
                recognition.interimResults = false;
                recordBtn.textContent = '🔴 Recording…';

                recognition.onresult = (e) => {
                    const transcript = e.results[0][0].transcript;
                    const input = $('answer-input');
                    input.value += (input.value ? ' ' : '') + transcript;
                    $('char-count').textContent = `${input.value.length} characters`;
                };
                recognition.onend = () => { recordBtn.textContent = '🎤 Start Recording'; recognition = null; };
                recognition.onerror = () => { recordBtn.textContent = '🎤 Start Recording'; recognition = null; showError('Speech recognition error.'); };
                recognition.start();
            };
        } else if (recordBtn) {
            recordBtn.disabled = true;
            recordBtn.textContent = '🎤 Not supported';
        }
    } else {
        controls.style.display = 'none';
    }
}

function readQuestion(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.lang = 'en-US';
        utter.rate = 0.95;
        window.speechSynthesis.speak(utter);
    }
}

// ── ANSWER INPUT LISTENERS ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const answerInput = $('answer-input');
    if (answerInput) {
        answerInput.addEventListener('input', () => {
            $('char-count').textContent = `${answerInput.value.length} characters`;
        });
    }

    const prevBtn = $('prev-btn');
if (prevBtn) {
    prevBtn.addEventListener('click', goToPreviousQuestion);
}

    const nextBtn = $('submit-answer-btn');
    if (nextBtn) {
        nextBtn.addEventListener('click', advanceQuestion);
    }

    // Load roles for modal
    loadRoles();

    // Sync count sliders in modals
    syncCount('hr-count', 'hr-range');
    syncCount('role-count', 'role-range');

    // Difficulty pills in modals
    initDifficultyPillsIn('hr-difficulty-pills');
    initDifficultyPillsIn('role-difficulty-pills');

    // Show mode selection on load
    showStep('mode');
});

// ── FINISH & BATCH EVALUATE ───────────────────────────────────────────────────
async function finishInterview() {
    clearInterval(timerInterval);
    state.answers[state.currentIndex] = $('answer-input')?.value || '';
    showStep('evaluating');

    const answersPayload = state.questions.map((q, i) => ({
    question: q.text,
    answer: state.answers[i] || '',
    type: q.type || 'technical',
    difficulty: q.difficulty || 'medium',
    keywords: Array.isArray(q.keywords) ? q.keywords : null,
    ideal_answer: q.ideal_answer || null
}));

    try {
        const res = await fetch(`${API_BASE}/batch_evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                answers: answersPayload,
                mode: state.mode || 'resume'
            })
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`Evaluation failed (${res.status}): ${errText}`);
        }

        const data = await res.json();
state.results = normalizeResults(data.results || []);

// Safety fallback if backend returns malformed data
if (!state.results.length) {
    throw new Error('No evaluation results returned from backend');
}

    } catch (e) {
        console.error('Batch evaluation error:', e);

        // Always preserve original question/answer metadata in fallback
        state.results = state.questions.map((q, i) => ({
            question: q.text,
            answer: state.answers[i] || '',
            type: q.type || 'technical',
            difficulty: q.difficulty || 'medium',
            score: 0,
            feedback: 'Evaluation service unavailable.',
            missing_keywords: [],
            improvements: 'Check your API configuration.',
            ideal_answer: 'N/A',
            ml_relevance_score: null,
            ml_relevance_grade: 'N/A',
            hybrid_score: 0
        }));
    }

    renderResults();
    showStep('results');
}
// ── RESULTS RENDERER ──────────────────────────────────────────────────────────
function renderResults() {
    const results = Array.isArray(state.results) ? state.results : [];

    // Merge backend results with original question/answer metadata safely
    const mergedResults = results.map((res, idx) => {
        const originalQ = state.questions[idx] || {};
        return {
            question: res.question ?? originalQ.text ?? 'Question unavailable',
            answer: res.answer ?? state.answers[idx] ?? '',
            type: res.type ?? originalQ.type ?? 'technical',
            difficulty: res.difficulty ?? originalQ.difficulty ?? 'medium',
            score: typeof res.score === 'number' ? res.score : 0,
            hybrid_score: typeof res.hybrid_score === 'number' ? res.hybrid_score : (typeof res.score === 'number' ? res.score : 0),
            feedback: res.feedback ?? 'No feedback.',
            missing_keywords: Array.isArray(res.missing_keywords) ? res.missing_keywords : [],
            improvements: res.improvements ?? '',
            ideal_answer: res.ideal_answer ?? 'N/A',
            ml_relevance_score: res.ml_relevance_score ?? null,
            ml_relevance_grade: res.ml_relevance_grade ?? 'N/A'
        };
    });

    state.results = mergedResults;

    const getDisplayScore = (r) => {
        if (typeof r.hybrid_score === 'number') return r.hybrid_score;
        if (typeof r.score === 'number') return r.score;
        return 0;
    };

    const totalScore = mergedResults.reduce((sum, r) => sum + getDisplayScore(r), 0);
    const avg = mergedResults.length ? (totalScore / mergedResults.length).toFixed(1) : '0';
    const strongCount = mergedResults.filter(r => getDisplayScore(r) >= 7).length;

    const avgScoreEl = $('avg-score');
    if (avgScoreEl) {
        avgScoreEl.innerText = avg;
        const avgNum = parseFloat(avg);
        const scoreColor = avgNum >= 7 ? 'var(--success)' : (avgNum >= 5 ? '#ffc107' : 'var(--error)');
        if (avgScoreEl.parentElement) {
            avgScoreEl.parentElement.style.borderColor = scoreColor;
        }
    }

    // Mode label
    const modeLabels = {
        hr: '🎯 HR Practice',
        resume: '📄 Resume + JD',
        role: `💼 ${state.selectedRole || 'Role'} Practice`
    };
    const modeLabel = $('results-mode-label');
    if (modeLabel) modeLabel.textContent = `Mode: ${modeLabels[state.mode] || 'Mock Interview'}`;

    const statsGrid = $('stats-grid');
    if (statsGrid) {
        statsGrid.innerHTML = `
            <div class="stat-card">
                <span class="stat-number">${mergedResults.length}</span>
                <span class="stat-label">Questions Answered</span>
            </div>
            <div class="stat-card">
                <span class="stat-number" style="color:var(--success)">${strongCount}</span>
                <span class="stat-label">Strong Answers (7+)</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">${mergedResults.length - strongCount}</span>
                <span class="stat-label">Needs Work</span>
            </div>
        `;
    }

    const feedbackList = $('feedback-list');
    if (!feedbackList) return;
    feedbackList.innerHTML = '';

    mergedResults.forEach((res, idx) => {
        const displayScore = getDisplayScore(res);
        const scoreColor = displayScore >= 7 ? 'var(--success)' : (displayScore >= 5 ? '#ffc107' : 'var(--error)');
        const typeClass = `tag-${(res.type || 'technical').toLowerCase()}`;
        const diffClass = `diff-${(res.difficulty || 'medium').toLowerCase()}`;

        let relevanceHtml = '';
        if (res.ml_relevance_grade && res.ml_relevance_grade !== 'N/A' && typeof res.ml_relevance_score === 'number') {
            const relColor = res.ml_relevance_score >= 75 ? 'var(--success)' : (res.ml_relevance_score >= 55 ? '#ffc107' : 'var(--error)');
            relevanceHtml = `<div style="font-size:0.85rem;margin-top:4px;color:var(--text-secondary);">Relevance: <span style="color:${relColor};font-weight:600;">${res.ml_relevance_grade} (${res.ml_relevance_score}%)</span></div>`;
        }

        const card = document.createElement('div');
        card.className = 'card result-card';
        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;gap:16px;">
                <div style="flex:1;">
                    <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
                        <span class="question-tag ${typeClass}">${String(res.type || 'technical').toUpperCase()}</span>
                        <span class="diff-badge ${diffClass}">${String(res.difficulty || 'medium')}</span>
                    </div>
                    <h3 style="line-height:1.4;font-size:1rem;">Q${idx + 1}: ${res.question}</h3>
                </div>
                <div style="text-align:right;">
                    <span class="result-score" style="color:${scoreColor};">${displayScore}/10</span>
                    ${relevanceHtml}
                </div>
            </div>
            <div class="feedback-section">
                <div class="answer-block">
                    <h4>Your Answer</h4>
                    <p style="color:var(--text-secondary);font-style:italic;margin-bottom:15px;">"${res.answer || 'No answer provided.'}"</p>
                </div>
                <div class="result-grid">
                    <div class="result-col feedback-col">
                        <h4>Feedback</h4>
                        <p>${res.feedback || 'No feedback.'}</p>
                    </div>
                    ${res.improvements ? `<div class="result-col improvements-col"><h4>Key Improvements</h4><p>${res.improvements}</p></div>` : ''}
                </div>
                ${res.ideal_answer && res.ideal_answer !== 'N/A' ? `
                <div class="ideal-answer-block">
                    <h4 style="color:var(--accent-color);">💡 Ideal Answer</h4>
                    <p>${res.ideal_answer}</p>
                </div>` : ''}
                ${res.missing_keywords?.length ? `
                <div style="margin-top:12px;">
                    <h4 style="margin-bottom:8px;">Missing Keywords</h4>
                    <div style="display:flex;flex-wrap:wrap;gap:6px;">
                        ${res.missing_keywords.map(k => `<span class="keyword-tag">${k}</span>`).join('')}
                    </div>
                </div>` : ''}
            </div>`;
        feedbackList.appendChild(card);
    });
}
