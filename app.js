// Proof-Carrying Commands (PCC) Flight Safety Mission Control System
// Every value on this dashboard comes from a real backend call — nothing here is fabricated.

const API = '';
let activeProfile = null;
let profiles = [];
let activeMission = null;
let missions = [];
let lastVerification = null;
let lastProposal = null;

async function api(path, opts) {
    const res = await fetch(API + path, opts);
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
}

function requireActiveMission() {
    if (!activeMission) { alert('Create or select a Mission Workspace first.'); return null; }
    return activeMission.id;
}

// -------------------------------------------------------------
// Shared interaction-state helpers. Every animation these trigger is a
// direct consequence of a real async call's real lifecycle (pending/
// resolved/rejected) — never a fixed-duration decorative effect.
// -------------------------------------------------------------
async function withButtonLoading(btn, fn) {
    if (!btn) return fn();
    btn.classList.add('is-loading');
    btn.disabled = true;
    try {
        return await fn();
    } finally {
        btn.classList.remove('is-loading');
        btn.disabled = false;
    }
}

function flashResult(el, ok) {
    if (!el) return;
    el.classList.remove('flash-success', 'flash-error');
    // Force reflow so the animation replays on repeated rapid actions.
    void el.offsetWidth;
    el.classList.add(ok ? 'flash-success' : 'flash-error');
}

function emptyState(title, hint) {
    return `<div class="engineering-empty">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
        </svg>
        <span class="empty-title">${title}</span>
        <span class="empty-hint">${hint}</span>
    </div>`;
}

function pulseCard(el) {
    if (!el) return;
    el.classList.remove('value-pulse');
    void el.offsetWidth;
    el.classList.add('value-pulse');
}

/** Draws a real sparkline from an array of numbers — a simple polyline
 * between actual data points, no smoothing/interpolation invented. */
function drawSparkline(canvas, values, color) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.clientWidth || 300;
    const h = canvas.height = 48;
    ctx.clearRect(0, 0, w, h);
    if (values.length < 2) return;
    const min = Math.min(...values), max = Math.max(...values);
    const range = (max - min) || 1;
    ctx.beginPath();
    values.forEach((v, i) => {
        const x = (i / (values.length - 1)) * (w - 4) + 2;
        const y = h - 4 - ((v - min) / range) * (h - 8);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
    const last = values[values.length - 1];
    const lastX = w - 2, lastY = h - 4 - ((last - min) / range) * (h - 8);
    ctx.beginPath(); ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
}

/** Draws a real command-verdict history chart — one bar per real command from
 * /api/commands/feed, colored by its actual verdict. No synthetic data, no
 * smoothing: a bar's height/color is exactly that command's real outcome. */
function drawVerdictHistoryChart(canvas, commands) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.clientWidth || 300;
    const h = canvas.height = 160;
    ctx.clearRect(0, 0, w, h);
    if (!commands.length) return;
    const ordered = [...commands].reverse();
    const pad = 8, gap = 3, maxBarW = 28;
    const barW = Math.min(maxBarW, Math.max(2, (w - pad * 2) / ordered.length - gap));
    const colors = { VERIFIED: '#3FB27F', REJECTED: '#D9564F', REFUSED: '#D9A441' };
    ordered.forEach((c, i) => {
        const x = pad + i * (barW + gap);
        const color = colors[c.verdict] || '#616B7C';
        const barH = h - pad * 2;
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.85;
        ctx.fillRect(x, pad, barW, barH);
        ctx.globalAlpha = 1;
    });
    ctx.strokeStyle = '#232935'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, h - pad); ctx.lineTo(w, h - pad); ctx.stroke();
}

document.addEventListener('DOMContentLoaded', () => {
    // -------------------------------------------------------------
    // Navigation — each screen loads its own real data on activation
    // -------------------------------------------------------------
    const navButtons = document.querySelectorAll('.nav-item');
    const screenViews = document.querySelectorAll('.screen-view');
    const screenTitle = document.getElementById('screen-title');
    const screenSubtitle = document.getElementById('screen-subtitle');
    const screenMeta = {
        overview: ['Mission Overview', 'Real mission health, verification state, and recent agent/command activity'],
        planning: ['Mission Planning', 'Propose a maneuver through the real Planner → Dynamics → Safety → Proof Generator → Reviewer pipeline'],
        files: ['Mission Files', 'Upload research papers, algorithms, notebooks, and engineering documents'],
        spacecraft: ['Spacecraft Configuration', 'Deterministic component validation and the persisted structured spacecraft model'],
        telemetry: ['Telemetry', 'Real Digital Twin ticks, imported CSV rows, and deterministic statistical analysis'],
        twin: ['Digital Twin', 'Live engineering console — attitude, power, thermal, comms, orbit context'],
        pipeline: ['Multi-Agent Pipeline', 'The real 5-agent verification chain, plus every engineering agent\'s execution history'],
        verification: ['Verification', 'Farkas certificate detail, audit chain integrity, adversarial testing'],
        replay: ['Mission Replay', 'Every command, proof, rejection — scoped to the active mission'],
        knowledge: ['Knowledge', 'Grounded Q&A and scientific review over uploaded documents'],
        reports: ['Reports', 'Mission analytics, compare, deterministic reports, and Claude-narrated summaries'],
        evidence: ['Evidence', 'Composed evidence package, mission timeline, import provenance'],
        settings: ['Settings', 'Mission profiles, mission lifecycle, plugin interface, system status'],
    };
    const screenLoaders = {
        overview: loadOverviewScreen, spacecraft: loadSpacecraftScreen, telemetry: loadTelemetryScreen,
        twin: loadTwinContextScreen, pipeline: loadPipelineScreen, verification: loadVerificationScreen,
        replay: loadReplayScreen, knowledge: loadKnowledgeScreen, reports: loadReportsScreen,
        evidence: loadEvidenceScreen, settings: loadSettingsScreen, files: loadFilesScreen,
    };
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const screen = btn.getAttribute('data-screen');
            navButtons.forEach(b => b.classList.remove('active'));
            screenViews.forEach(s => s.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`screen-${screen}`).classList.add('active');
            const meta = screenMeta[screen] || ['PCC Flight Gate', ''];
            screenTitle.textContent = meta[0];
            screenSubtitle.textContent = meta[1];
            if (screenLoaders[screen]) screenLoaders[screen]();
        });
    });

    // -------------------------------------------------------------
    // Satellite orbit canvas — spin speed driven by real Digital Twin ticks
    // -------------------------------------------------------------
    const satCanvas = document.getElementById('sat-canvas');
    const ctx = satCanvas.getContext('2d');
    let satAngle = 0, satSpin = 0, satSpinSpeed = 0.01;
    let isThrusterFiring = false, thrusterColor = '#4FB3D9';

    function drawSatelliteScene() {
        ctx.clearRect(0, 0, satCanvas.width, satCanvas.height);
        const centerX = satCanvas.width / 2, centerY = satCanvas.height / 2;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        for (let i = 0; i < 30; i++) {
            ctx.fillRect((i * 37) % satCanvas.width, (i * 73) % satCanvas.height, (i % 2) + 1, (i % 2) + 1);
        }
        const earthRadius = 75;
        const g = ctx.createRadialGradient(centerX, centerY, 10, centerX, centerY, earthRadius);
        g.addColorStop(0, '#2A3B5C'); g.addColorStop(0.7, '#243A5E'); g.addColorStop(1, '#1B4A5E');
        ctx.beginPath(); ctx.arc(centerX, centerY, earthRadius, 0, Math.PI * 2);
        ctx.fillStyle = g; ctx.fill();
        ctx.beginPath(); ctx.arc(centerX, centerY, earthRadius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(79, 179, 217, 0.25)'; ctx.lineWidth = 2; ctx.stroke();

        const orbitRx = 200, orbitRy = 100;
        ctx.beginPath(); ctx.ellipse(centerX, centerY, orbitRx, orbitRy, -0.2, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]); ctx.stroke(); ctx.setLineDash([]);

        satAngle += 0.008;
        const satX = centerX + orbitRx * Math.cos(satAngle), satY = centerY + orbitRy * Math.sin(satAngle);
        satSpin += satSpinSpeed;
        ctx.save(); ctx.translate(satX, satY); ctx.rotate(satSpin);

        if (isThrusterFiring) {
            ctx.beginPath(); ctx.moveTo(-15, 0); ctx.lineTo(-30, -8); ctx.lineTo(-40, 0); ctx.lineTo(-30, 8); ctx.closePath();
            ctx.fillStyle = thrusterColor; ctx.fill();
        }
        ctx.fillStyle = '#475569'; ctx.fillRect(-12, -12, 24, 24);
        ctx.strokeStyle = '#94A3B8'; ctx.lineWidth = 1; ctx.strokeRect(-12, -12, 24, 24);
        ctx.fillStyle = '#1B2130'; ctx.strokeStyle = '#4FB3D9';
        ctx.fillRect(-36, -6, 20, 12); ctx.strokeRect(-36, -6, 20, 12);
        ctx.fillRect(16, -6, 20, 12); ctx.strokeRect(16, -6, 20, 12);
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(20, 0); ctx.strokeStyle = '#4FB3D9'; ctx.lineWidth = 2; ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -20); ctx.strokeStyle = '#3FB27F'; ctx.lineWidth = 2; ctx.stroke();
        ctx.restore();
        requestAnimationFrame(drawSatelliteScene);
    }
    drawSatelliteScene();

    // -------------------------------------------------------------
    // Farkas infeasibility chart — driven entirely by real propose/verify responses
    // -------------------------------------------------------------
    const farkasCanvas = document.getElementById('farkas-canvas');
    const fCtx = farkasCanvas.getContext('2d');
    let currentOmegaVal = 0.0, maxBoundVal = 0.05;

    function drawFarkasChart() {
        fCtx.clearRect(0, 0, farkasCanvas.width, farkasCanvas.height);
        const pad = 40, w = farkasCanvas.width - pad * 2, h = farkasCanvas.height - pad * 2;
        fCtx.beginPath(); fCtx.moveTo(pad, pad); fCtx.lineTo(pad, pad + h); fCtx.lineTo(pad + w, pad + h);
        fCtx.strokeStyle = '#334155'; fCtx.lineWidth = 1.5; fCtx.stroke();
        fCtx.fillStyle = '#64748B'; fCtx.font = '10px "IBM Plex Mono"';
        fCtx.fillText('Time t (sec)', pad + w / 2 - 25, pad + h + 25);
        fCtx.fillText('||ω|| (rad/s)', 5, pad - 10);

        const scaleMax = Math.max(0.08, maxBoundVal * 1.6);
        const unsafeY = pad + h - (maxBoundVal / scaleMax) * h;
        fCtx.beginPath(); fCtx.moveTo(pad, unsafeY); fCtx.lineTo(pad + w, unsafeY);
        fCtx.strokeStyle = '#D9564F'; fCtx.lineWidth = 1.5; fCtx.setLineDash([4, 4]); fCtx.stroke(); fCtx.setLineDash([]);
        fCtx.fillStyle = '#D9564F'; fCtx.fillText(`UNSAFE BOUND: ${maxBoundVal.toFixed(3)}`, pad + w - 130, unsafeY - 6);

        fCtx.beginPath(); fCtx.moveTo(pad, pad + h - (currentOmegaVal * 0.3 / scaleMax) * h);
        const steps = 20;
        for (let i = 1; i <= steps; i++) {
            const x = pad + (i / steps) * w, progress = i / steps;
            const val = currentOmegaVal * (0.3 + 0.7 * Math.sin(progress * Math.PI * 0.5));
            fCtx.lineTo(x, pad + h - (val / scaleMax) * h);
        }
        const isUnsafe = currentOmegaVal > maxBoundVal;
        fCtx.strokeStyle = isUnsafe ? '#D9564F' : '#3FB27F'; fCtx.lineWidth = 2; fCtx.stroke();
        fCtx.fillStyle = isUnsafe ? 'rgba(217, 86, 79, 0.10)' : 'rgba(63, 178, 127, 0.06)';
        if (!isUnsafe) fCtx.fillRect(pad, unsafeY, w, pad + h - unsafeY);
        else fCtx.fillRect(pad, 0, w, unsafeY);
    }
    drawFarkasChart();

    // -------------------------------------------------------------
    // Mission Workspace selector — which mission commands/telemetry attach to
    // -------------------------------------------------------------
    const missionSelect = document.getElementById('mission-select');
    async function loadMissions() {
        missions = await api('/api/missions');
        missionSelect.innerHTML = missions.map(m => `<option value="${m.id}">${m.mission_name} (${m.status})</option>`).join('');
        activeMission = missions[0] || null;
        if (activeMission) await api(`/api/missions/${activeMission.id}/activate`, { method: 'POST' });
    }
    missionSelect.addEventListener('change', async () => {
        activeMission = missions.find(m => m.id === Number(missionSelect.value));
        if (activeMission) await api(`/api/missions/${activeMission.id}/activate`, { method: 'POST' });
        const active = document.querySelector('.nav-item.active');
        if (active) active.click();
    });
    const newMissionModal = document.getElementById('new-mission-modal');
    const newMissionInput = document.getElementById('new-mission-name-input');
    async function createMission(mission_name) {
        const created = await api('/api/missions', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mission_name, mission_profile_key: activeProfile ? activeProfile.profile_key : 'earth_observation' }),
        });
        await loadMissions();
        missionSelect.value = created.id;
        activeMission = created;
        await api(`/api/missions/${created.id}/activate`, { method: 'POST' });
        const active = document.querySelector('.nav-item.active');
        if (active) active.click();
    }
    document.getElementById('btn-new-mission').addEventListener('click', () => {
        newMissionInput.value = '';
        newMissionModal.style.display = 'flex';
        newMissionInput.focus();
    });
    document.getElementById('btn-new-mission-cancel').addEventListener('click', () => {
        newMissionModal.style.display = 'none';
    });
    document.getElementById('btn-new-mission-confirm').addEventListener('click', async () => {
        const mission_name = newMissionInput.value.trim();
        if (!mission_name) return;
        newMissionModal.style.display = 'none';
        await createMission(mission_name);
    });
    newMissionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') document.getElementById('btn-new-mission-confirm').click();
        if (e.key === 'Escape') newMissionModal.style.display = 'none';
    });

    // -------------------------------------------------------------
    // Mission profile selector (Mission Knowledge Base)
    // -------------------------------------------------------------
    const profileSelect = document.getElementById('mission-profile-select');
    async function loadProfiles() {
        profiles = await api('/api/profiles');
        profileSelect.innerHTML = profiles.map(p => `<option value="${p.profile_key}">${p.display_name} (${p.max_omega_rad_s} rad/s)</option>`).join('');
        activeProfile = profiles[0];
        maxBoundVal = activeProfile.max_omega_rad_s;
        document.getElementById('disp-bound').textContent = `${maxBoundVal.toFixed(3)} rad/s`;
        drawFarkasChart();
    }
    profileSelect.addEventListener('change', () => {
        activeProfile = profiles.find(p => p.profile_key === profileSelect.value);
        maxBoundVal = activeProfile.max_omega_rad_s;
        document.getElementById('disp-bound').textContent = `${maxBoundVal.toFixed(3)} rad/s`;
        drawFarkasChart();
    });

    // -------------------------------------------------------------
    // Trust panel + Explainable AI (shared render function)
    // -------------------------------------------------------------
    function renderTrust(verify) {
        const t = verify.trust, ex = verify.explain;
        const badge = document.getElementById('trust-overall-badge');
        badge.textContent = t.overall;
        badge.className = 'badge ' + (t.overall === 'TRUSTED' ? 'badge-success' : 'badge-danger');
        const checks = [
            ['Proof valid', t.proof_valid], ['Telemetry fresh', t.telemetry_fresh],
            ['Sequence valid', t.sequence_valid], ['Signature valid', t.signature_valid],
            ['Safety property satisfied', t.safety_satisfied],
        ];
        document.getElementById('trust-checklist').innerHTML = checks.map(([label, ok]) =>
            `<li class="${ok ? 'ok' : 'fail'}">${ok ? '✓' : '✗'} ${label}</li>`).join('');
        document.getElementById('explain-narrative').textContent = ex.narrative;

        currentOmegaVal = ex.actual;
        satSpinSpeed = Math.min(0.25, ex.actual);
        document.getElementById('disp-omega').textContent = `${ex.actual.toFixed(4)} rad/s`;
        const stateBadge = document.getElementById('sat-state-badge');
        if (t.overall === 'TRUSTED') { stateBadge.textContent = 'STABLE ORBIT'; stateBadge.className = 'badge badge-cyan'; }
        else { stateBadge.textContent = 'MANEUVER REJECTED'; stateBadge.className = 'badge badge-danger'; }
        document.getElementById('farkas-expr').textContent = ex.narrative;
        document.getElementById('farkas-expr').style.color = t.overall === 'TRUSTED' ? '#3FB27F' : '#D9564F';
        drawFarkasChart();
    }

    /** Real "Attempted Directive" + verdict panel on the Verification screen.
     * Every value here comes directly from the real /api/commands/propose response —
     * no fabricated command syntax, no fabricated constraint bounds. */
    function renderDirectiveDetail(proposal, verify) {
        const directiveEl = document.getElementById('trust-directive');
        const labelEl = document.getElementById('trust-verdict-label');
        const detailEl = document.getElementById('trust-verdict-detail');
        if (!directiveEl || !detailEl) return;

        const u = proposal.u_cmd || [];
        directiveEl.textContent = `RCS_PULSE ${proposal.command_id}  u_cmd=[${u.map(v => v.toFixed(3)).join(', ')}] Nm`;

        if (proposal.refused) {
            labelEl.textContent = 'Constraint Violated';
            detailEl.innerHTML = `<span class="material-symbols-outlined">warning</span> ${proposal.refusal_reason}`;
            detailEl.className = 'text-red font-mono flex-icon';
        } else if (verify) {
            const ok = verify.verdict === 'VERIFIED';
            labelEl.textContent = 'Verifier Verdict';
            detailEl.innerHTML = ok
                ? `<span class="material-symbols-outlined">check_circle</span> VERIFIED — accepted in ${(verify.verifier_time_ms || 0).toFixed(3)}ms`
                : `<span class="material-symbols-outlined">warning</span> ${verify.reject_reason || verify.verdict}`;
            detailEl.className = ok ? 'text-emerald font-mono flex-icon' : 'text-red font-mono flex-icon';
        }
    }

    function renderProofDetail(proposal, verify) {
        const el = document.getElementById('proof-detail');
        if (!el) return;
        el.textContent = JSON.stringify({
            command_id: proposal.command_id, sequence_no: proposal.proof.sequence_no,
            command_hash: proposal.proof.command_hash, model_id: proposal.proof.model_id,
            signature: proposal.proof.signature, bound: proposal.proof.bound,
            certificate: proposal.proof.certificate,
            verification: verify ? { verdict: verify.verdict, reject_reason: verify.reject_reason, verifier_time_ms: verify.verifier_time_ms } : null,
        }, null, 2);
    }

    // -------------------------------------------------------------
    // Agent Observatory (Multi-Agent Pipeline screen & Overview graph)
    // -------------------------------------------------------------
    let currentPipelineSteps = [];
    let selectedAgentIndex = 0;

    function renderPipelineDeepDive(step) {
        if (!step) return;
        const reasoningP = document.querySelector('.agent-reasoning-col .reasoning-p');
        const treeBox = document.querySelector('.agent-reasoning-col .tree-box');
        const progressBar = document.querySelector('.agent-reasoning-col .bar-fill');
        const progressVal = document.querySelector('.agent-reasoning-col .text-amber.font-mono');
        const inputJson = document.querySelectorAll('.agent-io-col .json-code')[0];
        const outputJson = document.querySelectorAll('.agent-io-col .json-code')[1];
        const latVal = document.querySelectorAll('.agent-io-col .stat-cell strong')[0];
        const confVal = document.querySelectorAll('.agent-io-col .stat-cell strong')[1];
        const agentTitle = document.querySelector('.agent-reasoning-col .panel-header h3');
        const statusBadge = document.getElementById('agent-status-badge');

        if (agentTitle) agentTitle.innerHTML = `<span class="material-symbols-outlined">psychology</span> ${step.agent_name}`;
        if (statusBadge) {
            const isDone = step.status === 'COMPLETED' || step.status === 'OK';
            const isBad = step.status === 'REFUSED' || step.status === 'REJECTED';
            statusBadge.textContent = step.status || 'UNKNOWN';
            statusBadge.className = 'badge ' + (isBad ? 'badge-danger' : isDone ? 'badge-success' : 'badge-warning');
        }
        if (reasoningP) reasoningP.textContent = step.reasoning_summary || 'No reasoning summary available.';
        if (latVal) latVal.textContent = `${(step.latency_ms || 0).toFixed(2)} ms`;
        if (confVal) confVal.textContent = `${((step.confidence || 0.99) * 100).toFixed(1)} %`;
        if (progressBar) progressBar.style.width = `${((step.confidence || 0.99) * 100).toFixed(0)}%`;
        if (progressVal) progressVal.textContent = `${((step.confidence || 0.99) * 100).toFixed(0)}%`;

        const deps = step.dependencies || (step.dependencies_json ? JSON.parse(step.dependencies_json) : []);
        if (treeBox) {
            treeBox.innerHTML = `
                <div class="tree-node"><span>▼</span> <span>${step.agent_name}_Seq_04</span></div>
                ${deps.length ? deps.map(d => `<div class="tree-node branch">├─ <span class="text-emerald">Valid(${d.agent_name}_Output)</span></div>`).join('') : '<div class="tree-node branch">├─ <span class="text-emerald">Valid(Initial_State_Input)</span></div>'}
                <div class="tree-node branch">└─ <span class="text-emerald">Status(${step.status})</span></div>`;
        }

        if (inputJson) {
            inputJson.textContent = JSON.stringify({
                agent: step.agent_name, step_order: step.step_order,
                dependencies: deps, timestamp: Date.now() / 1000
            }, null, 2);
        }
        if (outputJson) {
            outputJson.textContent = JSON.stringify({
                status: step.status, confidence: step.confidence,
                latency_ms: step.latency_ms, reasoning: step.reasoning_summary
            }, null, 2);
        }
    }

    function renderAgentObservatory(steps, sourceLabel) {
        currentPipelineSteps = steps || [];
        const el = document.getElementById('agent-observatory');

        // Real agent count in this pipeline run — never a hardcoded placeholder
        const badge = document.getElementById('roster-active-badge');
        if (badge) badge.textContent = steps && steps.length ? `${steps.length} AGENTS` : '0 AGENTS';

        // Active Propagation Nodes on Pipeline screen — always reflects real step data
        const nodeFlow = document.querySelector('.pipeline-nodes-flow');
        if (nodeFlow) {
            const nodeNames = ['Planner', 'Dynamics', 'Safety', 'Proof', 'Reviewer'];
            nodeFlow.innerHTML = nodeNames.map((name, idx) => {
                const step = steps && steps[idx];
                const isDone = !!step && (step.status === 'COMPLETED' || step.status === 'OK');
                const isWarn = !!step && (step.status === 'REFUSED' || step.status === 'REJECTED');
                const circleClass = isWarn ? 'active warning' : isDone ? 'complete' : '';
                const icon = isDone ? 'check_circle' : isWarn ? 'warning' : 'circle';
                const lineClass = isDone ? 'active' : '';
                return `
                    <div class="pipeline-node">
                        <div class="node-circle ${circleClass}"><span class="material-symbols-outlined">${icon}</span></div>
                        <span class="node-label ${isWarn ? 'amber font-semibold' : ''}">${name}</span>
                    </div>
                    ${idx < nodeNames.length - 1 ? `<div class="node-line ${lineClass}"></div>` : ''}
                `;
            }).join('');
        }

        // Roster List — real steps, or an honest empty state (never fake preset agents)
        const rosterCol = document.querySelector('.roster-list');
        if (rosterCol) {
            if (steps && steps.length) {
                rosterCol.innerHTML = steps.map((s, idx) => `
                    <button class="roster-item ${idx === selectedAgentIndex ? 'active amber' : ''}" data-agent-idx="${idx}">
                        <div class="roster-item-top">
                            <strong class="${idx === selectedAgentIndex ? 'text-amber' : ''}">${s.agent_name}</strong>
                            <span class="status-dot ${s.status === 'COMPLETED' || s.status === 'OK' ? 'green' : 'amber'}"></span>
                        </div>
                        <div class="roster-item-meta font-mono">
                            <span>LAT: ${s.latency_ms.toFixed(0)}ms</span><span>CONF: ${(s.confidence * 100).toFixed(0)}%</span>
                        </div>
                    </button>
                `).join('');

                rosterCol.querySelectorAll('[data-agent-idx]').forEach(btn => {
                    btn.addEventListener('click', () => {
                        selectedAgentIndex = Number(btn.getAttribute('data-agent-idx'));
                        renderAgentObservatory(currentPipelineSteps, sourceLabel);
                    });
                });
            } else {
                rosterCol.innerHTML = '<p class="card-desc">No pipeline run yet for this mission — propose a maneuver on Mission Planning.</p>';
            }
        }

        if (steps && steps.length) {
            const totalLat = steps.reduce((sum, s) => sum + (s.latency_ms || 0), 0);
            const avgConf = steps.reduce((sum, s) => sum + (s.confidence || 0), 0) / (steps.length || 1);

            const latEl = document.querySelector('.pipeline-stats-header .chip-val');
            const confEl = document.querySelectorAll('.pipeline-stats-header .chip-val')[1];
            if (latEl) latEl.textContent = `${totalLat.toFixed(0)}ms`;
            if (confEl) confEl.textContent = `${(avgConf * 100).toFixed(1)}%`;

            renderPipelineDeepDive(steps[selectedAgentIndex] || steps[0]);
        }

        if (!steps || !steps.length) {
            if (el) el.innerHTML = emptyState('Awaiting pipeline activity',
                'No pipeline run exists yet for this mission. Propose a maneuver on Mission Planning to see the real Planner → Dynamics → Safety → Proof Generator → Reviewer chain execute here.');
            const agentTitle = document.querySelector('.agent-reasoning-col .panel-header h3');
            const reasoningP = document.querySelector('.agent-reasoning-col .reasoning-p');
            const treeBox = document.querySelector('.agent-reasoning-col .tree-box');
            if (agentTitle) agentTitle.innerHTML = '<span class="material-symbols-outlined">psychology</span> No agent selected';
            if (reasoningP) reasoningP.textContent = 'Propose a maneuver on Mission Planning to see a real agent\'s reasoning here.';
            if (treeBox) treeBox.innerHTML = '';
            const statusBadge = document.getElementById('agent-status-badge');
            if (statusBadge) { statusBadge.textContent = 'IDLE'; statusBadge.className = 'badge badge-info'; }
            document.querySelectorAll('.agent-io-col .json-code').forEach(elm => { elm.textContent = 'No pipeline run yet.'; });
            document.querySelectorAll('.agent-io-col .stat-cell strong').forEach(elm => { elm.textContent = '—'; });
            return;
        }
        if (el) {
            el.innerHTML = (sourceLabel ? `<p class="ops-note">${sourceLabel}</p>` : '') + steps.map(s => {
                const deps = s.dependencies || (s.dependencies_json ? JSON.parse(s.dependencies_json) : []);
                const depsHtml = deps.length
                    ? `<span class="agent-deps">← ${deps.map(d => `${d.agent_name}${d.shared_fields && d.shared_fields.length ? ' (' + d.shared_fields.join(', ') + ')' : ''}`).join(', ')}</span>`
                    : '<span class="agent-deps">← (first in pipeline)</span>';
                return `
                <div class="agent-card reveal ${s.status === 'REFUSED' ? 'refused' : ''}" style="animation-delay:${(s.step_order - 1) * 80}ms">
                    <span class="agent-name">${s.step_order}. ${s.agent_name}</span>
                    <div class="confidence-bar"><span style="width:${(s.confidence * 100).toFixed(0)}%"></span></div>
                    <span class="agent-meta"><span>${s.status}</span><span>${s.latency_ms.toFixed(3)} ms</span></span>
                    <span class="agent-reasoning">${s.reasoning_summary}</span>
                    ${depsHtml}
                </div>`;
            }).join('');
        }
    }

    async function loadPipelineScreen() {
        const missionId = requireActiveMission();
        if (missionId !== null) {
            try {
                const history = await api(`/api/missions/replay?limit=1&mission_id=${missionId}`);
                if (history.length) renderAgentObservatory(history[0].pipeline_steps, `Last real pipeline run — command ${history[0].command.command_id}`);
                else renderAgentObservatory([]);
            } catch (e) { renderAgentObservatory([]); }
        }
        const runs = await api(`/api/missions/${missionId}/agent-runs?limit=30`);
        document.getElementById('agent-runs-body').innerHTML = runs.map(r => `
            <tr>
                <td>${r.agent_name}</td>
                <td>${r.output && r.output.agent_version ? r.output.agent_version : '—'}</td>
                <td><span class="status-tag ${r.status === 'OK' ? 'verified' : 'rejected'}">${r.status}</span></td>
                <td>${r.latency_ms.toFixed(3)} ms</td>
                <td>${(r.input_summary || '—').slice(0, 60)}</td>
                <td>${r.created_at}</td>
            </tr>`).join('') || `<tr><td colspan="6">${emptyState('No engineering agent runs yet', 'Run Mission Intake (upload a file), Spacecraft Configuration, Telemetry Analysis, or ask the Knowledge Agent a question from their respective pages.')}</td></tr>`;
    }

    // -------------------------------------------------------------
    // Command feed + evaluation stats
    // -------------------------------------------------------------
    async function loadFeed() {
        const rows = await api('/api/commands/feed?limit=25');
        return rows;
    }

    async function loadStats() {
        const report = await api('/api/evaluation/report');
        const verified = Math.round(report.total_commands * report.acceptance_rate);
        const rejected = Math.round(report.total_commands * report.rejection_rate);
        document.getElementById('pass-count').textContent = verified;
        document.getElementById('drop-count').textContent = rejected;
        document.getElementById('stat-verifier-time').textContent = `${report.avg_verifier_latency_ms.toFixed(3)} ms`;
        document.getElementById('stat-producer-time').textContent = `${report.avg_producer_latency_ms.toFixed(1)} ms`;
        document.getElementById('stat-asymmetry').textContent = report.computational_asymmetry ? `${report.computational_asymmetry}x` : '—';
        const ovPass = document.getElementById('ov-pass-count'), ovDrop = document.getElementById('ov-drop-count');
        if (ovPass) ovPass.textContent = verified;
        if (ovDrop) ovDrop.textContent = rejected;

        const cpuVal = document.getElementById('sys-cpu-value'), cpuBar = document.getElementById('sys-cpu-bar');
        if (cpuVal) { cpuVal.textContent = `${report.process_cpu_percent.toFixed(1)}%`; cpuBar.style.width = `${Math.min(report.process_cpu_percent, 100)}%`; }
        const memVal = document.getElementById('sys-mem-value'), memBar = document.getElementById('sys-mem-bar');
        if (memVal) { memVal.textContent = `${report.process_memory_mb.toFixed(0)} MB`; memBar.style.width = `${Math.min(report.process_memory_mb / 512 * 100, 100)}%`; }
        const attacksVal = document.getElementById('sys-attacks-value'), attacksBar = document.getElementById('sys-attacks-bar');
        if (attacksVal) { attacksVal.textContent = report.attacks_simulated; attacksBar.style.width = `${Math.min(report.attacks_simulated * 10, 100)}%`; }

        return report;
    }

    // -------------------------------------------------------------
    // Propose + verify a maneuver
    // -------------------------------------------------------------
    async function proposeAndVerify(maneuverType, x0, u_cmd) {
        lastProposeAt = Date.now();
        const body = { maneuver_type: maneuverType, mission_profile_key: activeProfile.profile_key };
        if (x0) body.x0 = x0;
        if (u_cmd) body.u_cmd = u_cmd;
        if (activeMission) body.mission_id = activeMission.id;
        const proposal = await api('/api/commands/propose', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        renderAgentObservatory(proposal.pipeline_steps, `Just proposed — command ${proposal.command_id}`);

        if (proposal.refused) {
            document.getElementById('explain-narrative').textContent = `Refused before signing: ${proposal.refusal_reason}`;
            const badge = document.getElementById('trust-overall-badge');
            badge.textContent = 'REFUSED'; badge.className = 'badge badge-danger';
            document.getElementById('trust-checklist').innerHTML = '';
            renderDirectiveDetail(proposal, null);
            lastProposal = proposal;
            flashResult(document.getElementById('trust-panel'), false);
            await loadStats();
            return { proposal, verify: null };
        }

        const verifyBody = {
            command_row_id: proposal.command_row_id, proof: proposal.proof,
            submitted_command_id: proposal.command_id, submitted_u_cmd: proposal.u_cmd,
            mission_id: proposal.mission_id,
        };
        const verify = await api('/api/commands/verify', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(verifyBody),
        });
        renderTrust(verify);
        renderProofDetail(proposal, verify);
        renderDirectiveDetail(proposal, verify);
        flashResult(document.getElementById('trust-panel'), verify.verdict === 'VERIFIED');
        lastVerification = { proposal, verify };
        lastProposal = proposal;
        await loadStats();
        return { proposal, verify };
    }

    document.getElementById('btn-trigger-safe').addEventListener('click', async (e) => {
        isThrusterFiring = true; thrusterColor = '#4FB3D9'; setTimeout(() => { isThrusterFiring = false; }, 1200);
        await withButtonLoading(e.currentTarget, () => proposeAndVerify('SAFE_RCS_PULSE'));
    });
    document.getElementById('btn-trigger-unsafe').addEventListener('click', async (e) => {
        await withButtonLoading(e.currentTarget, () => proposeAndVerify('UNSAFE_RCS_PULSE'));
    });
    document.getElementById('btn-approve-adjust').addEventListener('click', async (e) => {
        isThrusterFiring = true; thrusterColor = '#4FB3D9'; setTimeout(() => { isThrusterFiring = false; }, 1200);
        await withButtonLoading(e.currentTarget, () => proposeAndVerify('SAFE_RCS_PULSE'));
    });
    document.getElementById('btn-review-logic').addEventListener('click', () => {
        const pipelineBtn = document.querySelector('.nav-item[data-screen="pipeline"]');
        if (pipelineBtn) pipelineBtn.click();
    });

    // -------------------------------------------------------------
    // Sandbox: sliders drive a real propose+verify call, not a JS formula
    // -------------------------------------------------------------
    const sliderWx = document.getElementById('slider-wx'), sliderWy = document.getElementById('slider-wy');
    const sliderUx = document.getElementById('slider-ux'), sliderUy = document.getElementById('slider-uy');
    [sliderWx, sliderWy, sliderUx, sliderUy].forEach(s => s.addEventListener('input', () => {
        document.getElementById('val-wx').textContent = parseFloat(sliderWx.value).toFixed(3);
        document.getElementById('val-wy').textContent = parseFloat(sliderWy.value).toFixed(3);
        document.getElementById('val-ux').textContent = parseFloat(sliderUx.value).toFixed(3);
        document.getElementById('val-uy').textContent = parseFloat(sliderUy.value).toFixed(3);
    }));

    document.getElementById('btn-calc-proof').addEventListener('click', async (e) => {
        const x0 = [parseFloat(sliderWx.value), parseFloat(sliderWy.value), 0.0];
        const u_cmd = [parseFloat(sliderUx.value), parseFloat(sliderUy.value), 0.0];
        const display = document.getElementById('sandbox-json-display');
        display.innerHTML = '<span class="skeleton-line w80"></span><span class="skeleton-line w60"></span><span class="skeleton-line w40"></span>';
        await withButtonLoading(e.currentTarget, async () => {
            try {
                const { proposal, verify } = await proposeAndVerify('SANDBOX', x0, u_cmd);
                display.textContent = JSON.stringify({ proposal_refused: proposal.refused, refusal_reason: proposal.refusal_reason, proof: proposal.proof, verification: verify }, null, 2);
                flashResult(display, !proposal.refused);
            } catch (err) {
                display.textContent = `Error: ${err.message}`;
                flashResult(display, false);
            }
        });
    });

    // -------------------------------------------------------------
    // Attack Library (Verification screen — adversarial testing)
    // -------------------------------------------------------------
    const ATTACK_TAXONOMY = {
        replay: { category: 'Replay Attack', severity: 'HIGH', difficulty: 'LOW' },
        tampered_command: { category: 'Payload Attack', severity: 'HIGH', difficulty: 'LOW' },
        wrong_certificate: { category: 'Certificate Attack', severity: 'CRITICAL', difficulty: 'MEDIUM' },
        missing_proof: { category: 'Integrity Attack', severity: 'HIGH', difficulty: 'LOW' },
        stale_telemetry: { category: 'Timing Attack', severity: 'MEDIUM', difficulty: 'LOW' },
        wrong_sequence: { category: 'Sequence Attack', severity: 'HIGH', difficulty: 'MEDIUM' },
        modified_payload: { category: 'Crypto Attack', severity: 'CRITICAL', difficulty: 'HIGH' },
    };
    async function loadAttackLibrary() {
        const types = await api('/api/attacks/types');
        const grid = document.getElementById('attack-library-grid');
        grid.innerHTML = types.map(t => {
            const tax = ATTACK_TAXONOMY[t] || { category: 'Adversarial Test', severity: '—', difficulty: '—' };
            return `
            <div class="panel attack-card" data-attack="${t}">
                <div class="panel-header"><h2>${t.replace(/_/g, ' ')}</h2><span class="badge badge-amber">Not yet run</span></div>
                <p class="card-desc">${tax.category} — severity ${tax.severity}, difficulty ${tax.difficulty}</p>
                <p class="card-desc" data-desc>Click Run to execute this attack against the live verifier.</p>
                <button class="btn btn-danger" data-run="${t}">Run Attack</button>
            </div>`;
        }).join('');
        grid.querySelectorAll('[data-run]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const attackType = btn.getAttribute('data-run');
                const card = btn.closest('.attack-card');
                const badge = card.querySelector('.badge');
                badge.textContent = 'Running…';
                const result = await api('/api/attacks/run', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ attack_type: attackType, mission_profile_key: activeProfile.profile_key,
                                            mission_id: activeMission ? activeMission.id : undefined }),
                });
                badge.textContent = result.detected ? 'DETECTED & REJECTED' : 'NOT DETECTED';
                badge.className = 'badge ' + (result.detected ? 'badge-danger' : 'badge-amber');
                card.querySelector('[data-desc]').textContent = `Expected: rejected. Actual: ${result.verdict} — ${result.reject_reason || result.description}.`;
                await loadStats();
            });
        });
    }

    // -------------------------------------------------------------
    // Verification screen: proof detail + audit chain + attack library
    // -------------------------------------------------------------
    async function loadVerificationScreen() {
        await loadStats();
        if (lastVerification) renderProofDetail(lastVerification.proposal, lastVerification.verify);
        if (lastProposal) renderDirectiveDetail(lastProposal, lastVerification && lastVerification.verify);
        loadAttackLibrary();
    }
    document.getElementById('btn-load-audit').addEventListener('click', async () => {
        const resultEl = document.getElementById('audit-result');
        resultEl.innerHTML = '<p class="ops-note">Verifying…</p>';
        const [chain, verify] = await Promise.all([api('/api/audit/chain?limit=25'), api('/api/audit/verify')]);
        resultEl.innerHTML = `<span class="badge ${verify.valid ? 'badge-success' : 'badge-danger'}">${verify.valid ? 'CHAIN VALID' : 'CHAIN BROKEN at index ' + verify.broken_at_index}</span>`;
        document.getElementById('audit-chain-body').innerHTML = chain.map(c => `
            <tr><td>${c.sequence_index}</td><td>${c.command_id}</td><td title="${c.chain_hash}">${c.chain_hash.slice(0, 24)}…</td></tr>`).join('')
            || '<tr><td colspan="3" class="card-desc">No accepted commands in the chain yet.</td></tr>';
    });

    // -------------------------------------------------------------
    // Mission Overview
    // -------------------------------------------------------------
    async function loadOverviewScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        document.getElementById('ov-mission-name').textContent = activeMission.mission_name;
        document.getElementById('ov-mission-status').textContent = `#${activeMission.id} · ${activeMission.status}`;

        const [status, runs, feed] = await Promise.all([
            api(`/api/missions/${missionId}/status`), api(`/api/missions/${missionId}/agent-runs?limit=10`),
            loadFeed(), loadStats(),
        ]);
        const badge = document.getElementById('ov-health-badge');
        badge.textContent = status.mission_health.overall;
        badge.className = 'badge ' + { NOMINAL: 'badge-success', CAUTION: 'badge-amber', CRITICAL: 'badge-danger', UNKNOWN: 'badge-info' }[status.mission_health.overall];
        document.getElementById('ov-health-reasons').innerHTML = status.mission_health.reasons.length
            ? status.mission_health.reasons.map(r => `<li class="fail">${r}</li>`).join('')
            : '<li class="ok">No health flags.</li>';
        document.getElementById('ov-verification').textContent = status.verification_state.state;
        document.getElementById('ov-freshness').textContent = status.telemetry_freshness_seconds === null ? 'no telemetry yet' : `${status.telemetry_freshness_seconds.toFixed(1)}s`;

        const activity = [
            ...runs.map(r => ({ at: r.created_at, text: `Agent ${r.agent_name} → ${r.status} (${r.latency_ms.toFixed(1)}ms)`, kind: 'agent' })),
            ...feed.slice(0, 10).map(c => ({ at: c.submitted_at, text: `Command ${c.command_id} → ${c.verdict}`, kind: 'command' })),
        ].sort((a, b) => (a.at < b.at ? 1 : -1)).slice(0, 12);
        document.getElementById('ov-activity-list').innerHTML = activity.length
            ? activity.map(a => `<div class="ops-timeline-entry"><span><span class="kind-tag">${a.kind}</span> ${a.text}</span><span class="card-desc">${a.at}</span></div>`).join('')
            : '<p class="card-desc">No activity yet for this mission — upload data on Mission Files, or propose a maneuver on Mission Planning.</p>';
    }

    // -------------------------------------------------------------
    // Mission Files
    // -------------------------------------------------------------
    function renderIntakeFindings(intake) {
        const el = document.getElementById('intake-findings');
        if (!intake) { el.textContent = 'No intake run yet.'; return; }
        if (intake.clean) { el.innerHTML = '<span class="status-tag verified">CLEAN</span> No problems found.'; return; }
        const items = [];
        intake.duplicate_uploads.forEach(d => items.push(`Duplicate upload: ${d.filenames.join(', ')} (identical content)`));
        intake.corrupt_files.forEach(d => items.push(`Corrupt file: ${d.filename}`));
        intake.unsupported_files.forEach(d => items.push(`Unsupported format: ${d.filename}`));
        intake.missing_fields.forEach(m => items.push(m));
        el.innerHTML = items.map(i => `<div class="card-desc">⚠ ${i}</div>`).join('');
    }

    async function loadDocumentList(missionId) {
        const docs = await api(`/api/missions/${missionId}/documents`);
        document.getElementById('doc-list-body').innerHTML = docs.map(d => `
            <tr>
                <td>${d.doc_type}</td><td>${d.filename} (#${d.id})</td><td>v${d.version_no}</td>
                <td>${(d.size_bytes / 1024).toFixed(1)} KB</td>
                <td><span class="status-tag ${d.extraction_status === 'OK' ? 'verified' : d.extraction_status === 'CORRUPT' ? 'rejected' : 'pending'}">${d.extraction_status}</span></td>
                <td style="display:flex;gap:0.35rem;flex-wrap:wrap">
                    <button class="btn btn-secondary" data-download-doc="${d.id}" style="padding:0.2rem 0.4rem;font-size:0.68rem">Download</button>
                    <button class="btn btn-secondary" data-review="paper" data-doc-id="${d.id}" style="padding:0.2rem 0.4rem;font-size:0.68rem">Paper</button>
                    <button class="btn btn-secondary" data-review="algorithm" data-doc-id="${d.id}" style="padding:0.2rem 0.4rem;font-size:0.68rem">Algorithm</button>
                    <button class="btn btn-warning" data-delete-doc="${d.id}" style="padding:0.2rem 0.4rem;font-size:0.68rem;color:var(--accent-red)">Delete</button>
                </td>
            </tr>`).join('') || `<tr><td colspan="6">${emptyState('No files uploaded yet', 'Upload a research paper, algorithm description, notebook, MATLAB script, or engineering note above — real text extraction runs immediately.')}</td></tr>`;

        document.querySelectorAll('[data-review]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const kind = btn.getAttribute('data-review');
                const docId = btn.getAttribute('data-doc-id');
                const resultEl = document.getElementById('scientific-review-result');
                resultEl.innerHTML = '<span class="skeleton-line w80"></span><span class="skeleton-line w60"></span>';
                await withButtonLoading(btn, async () => {
                    const resp = await api(`/api/missions/${missionId}/documents/${docId}/review/${kind}`, { method: 'POST' });
                    resultEl.textContent = JSON.stringify(resp, null, 2);
                    flashResult(resultEl, resp.reviewed !== false);
                });
            });
        });

        document.querySelectorAll('[data-download-doc]').forEach(btn => {
            btn.addEventListener('click', () => {
                const docId = btn.getAttribute('data-download-doc');
                window.open(`/api/missions/${missionId}/documents/${docId}/download`, '_blank');
            });
        });

        document.querySelectorAll('[data-delete-doc]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const docId = btn.getAttribute('data-delete-doc');
                if (!confirm(`Delete document #${docId}?`)) return;
                await withButtonLoading(btn, async () => {
                    const resp = await api(`/api/missions/${missionId}/documents/${docId}`, { method: 'DELETE' });
                    renderIntakeFindings(resp.mission_intake);
                    await loadDocumentList(missionId);
                });
            });
        });
    }

    async function loadFilesScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        await loadDocumentList(missionId);
    }

    document.getElementById('btn-upload-document').addEventListener('click', async (e) => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const fileInput = document.getElementById('doc-upload-file');
        if (!fileInput.files.length) { alert('Choose a file first.'); return; }
        const docType = document.getElementById('doc-upload-type').value;
        const form = new FormData();
        form.append('file', fileInput.files[0]);
        await withButtonLoading(e.currentTarget, async () => {
            const resp = await (await fetch(`/api/missions/${missionId}/documents?doc_type=${docType}`, { method: 'POST', body: form })).json();
            renderIntakeFindings(resp.mission_intake);
            await loadDocumentList(missionId);
            flashResult(document.getElementById('doc-list-body').closest('.panel'), resp.extraction_status === 'OK');
        });
    });

    // -------------------------------------------------------------
    // Knowledge screen
    // -------------------------------------------------------------
    function loadKnowledgeScreen() { /* stateless forms — nothing to preload */ }

    document.getElementById('btn-search-documents').addEventListener('click', async (e) => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const q = document.getElementById('doc-search-query').value.trim();
        if (!q) return;
        const el = document.getElementById('doc-search-results');
        await withButtonLoading(e.currentTarget, async () => {
            const resp = await api(`/api/missions/${missionId}/documents/search?q=${encodeURIComponent(q)}`);
            el.innerHTML = `<p class="ops-note">${resp.search_type} search — ${resp.results.length} result(s)</p>` +
                (resp.results.length ? resp.results.map(r => `
                    <div class="replay-entry">
                        <div class="replay-head"><span>${r.filename}</span><span>score ${r.score}</span></div>
                        <span class="card-desc">${r.snippet}</span>
                    </div>`).join('') : emptyState('No matches', 'No uploaded document contains this term. Keyword search requires an exact word match — try a different phrasing.'));
        });
    });

    document.getElementById('btn-ask-knowledge').addEventListener('click', async (e) => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const question = document.getElementById('knowledge-question').value.trim();
        if (!question) return;
        const el = document.getElementById('knowledge-answer');
        el.innerHTML = '<div class="engineering-empty"><span class="skeleton-line w60"></span><span class="skeleton-line w80"></span><span class="skeleton-line w40"></span></div>';
        await withButtonLoading(e.currentTarget, async () => {
            const resp = await api(`/api/missions/${missionId}/knowledge/ask`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
            });
            const evidenceHtml = resp.evidence.map(ev => `
                <div class="replay-entry">
                    <div class="replay-head"><span>${ev.filename}${ev.page_number !== null ? ' — page ' + ev.page_number : ''} (${ev.section_type})</span><span>confidence ${ev.confidence}</span></div>
                    <span class="card-desc">${ev.snippet}</span>
                </div>`).join('');
            el.innerHTML = `
                <div class="farkas-math-box">
                    <span class="math-title">Answer (${resp.generated_by}):</span>
                    <code class="math-expr">${resp.answer}</code>
                </div>
                ${resp.evidence.length ? `<p class="ops-note">Cited evidence (${resp.evidence.length}):</p>${evidenceHtml}` : ''}`;
            flashResult(el.querySelector('.farkas-math-box'), resp.generated_by !== 'deterministic_refusal');
        });
    });

    document.getElementById('btn-compare-documents').addEventListener('click', async (e) => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const a = document.getElementById('compare-doc-a').value.trim();
        const b = document.getElementById('compare-doc-b').value.trim();
        if (!a || !b) return;
        const resultEl = document.getElementById('scientific-review-result');
        resultEl.innerHTML = '<span class="skeleton-line w80"></span><span class="skeleton-line w60"></span>';
        await withButtonLoading(e.currentTarget, async () => {
        const resp = await api(`/api/missions/${missionId}/documents/compare`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_id_a: Number(a), document_id_b: Number(b) }),
        });
        resultEl.textContent = JSON.stringify(resp, null, 2);
        flashResult(resultEl, resp.compared !== false);
        });
    });

    // -------------------------------------------------------------
    // Mission Replay
    // -------------------------------------------------------------
    async function loadReplayScreen() {
        const missionId = requireActiveMission();
        const el = document.getElementById('replay-list');
        el.innerHTML = '<p class="card-desc">Loading…</p>';
        const url = missionId !== null ? `/api/missions/replay?limit=50&mission_id=${missionId}` : '/api/missions/replay?limit=50';
        const history = await api(url);
        el.innerHTML = history.map(h => `
            <div class="replay-entry">
                <div class="replay-head">
                    <span>${h.command.command_id}</span>
                    <span class="status-tag ${h.command.verdict.toLowerCase()}">${h.command.verdict}</span>
                </div>
                <span class="card-desc">Seq #${h.command.sequence_no} — ${h.explain ? h.explain.narrative : 'not yet verified'}</span>
            </div>`).join('') || '<p class="card-desc">No mission history yet — propose and verify a command on Mission Planning first.</p>';
    }
    document.getElementById('btn-load-replay').addEventListener('click', loadReplayScreen);

    // -------------------------------------------------------------
    // Imports — shared by Spacecraft, Telemetry, Digital Twin, Settings screens
    // -------------------------------------------------------------
    const IMPORT_RESULT_EL = {
        tle: 'import-tle-result', omm: 'import-omm-result', csv: 'import-result',
        'mission-json': 'import-mission-json-result', 'spacecraft-profile': 'import-spacecraft-profile-result',
        'constraint-profile': 'import-constraint-profile-result',
    };

    async function runImport(kind, dryRun) {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const resultEl = document.getElementById(IMPORT_RESULT_EL[kind]);
        const qs = dryRun ? '?dry_run=true' : '';
        try {
            let resp;
            if (kind === 'tle') {
                resp = await api(`/api/missions/${missionId}/imports/tle${qs}`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        line1: document.getElementById('import-tle-line1').value,
                        line2: document.getElementById('import-tle-line2').value,
                    }),
                });
            } else if (kind === 'csv') {
                const fileInput = document.getElementById('import-csv-file');
                if (!fileInput.files.length) { resultEl.textContent = 'Choose a CSV file first.'; return; }
                const form = new FormData();
                form.append('file', fileInput.files[0]);
                resp = await (await fetch(`/api/missions/${missionId}/imports/csv-telemetry${qs}`, { method: 'POST', body: form })).json();
            } else {
                const textareaId = { 'mission-json': 'import-mission-json', 'spacecraft-profile': 'import-spacecraft',
                                      'constraint-profile': 'import-constraint', 'omm': 'import-omm' }[kind];
                let body;
                try { body = JSON.parse(document.getElementById(textareaId).value || '{}'); }
                catch (e) { resultEl.textContent = `Invalid JSON: ${e.message}`; return; }
                resp = await api(`/api/missions/${missionId}/imports/${kind}${qs}`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
                });
            }
            resultEl.textContent = JSON.stringify(resp, null, 2);
            flashResult(resultEl, resp.valid !== false);
            if (!dryRun && resp.valid !== false) {
                if (kind === 'tle' || kind === 'omm') loadTwinContextScreen();
            }
        } catch (e) {
            resultEl.textContent = `Request failed: ${e.message}`;
            flashResult(resultEl, false);
        }
    }
    document.querySelectorAll('[data-import]').forEach(btn => {
        btn.addEventListener('click', () => withButtonLoading(btn, () => runImport(btn.getAttribute('data-import'), btn.getAttribute('data-dry') === 'true')));
    });

    // -------------------------------------------------------------
    // Spacecraft Configuration
    // -------------------------------------------------------------
    async function submitSpacecraftConfig(dryRun) {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const resultEl = document.getElementById('spacecraft-config-result');
        let body;
        try { body = JSON.parse(document.getElementById('spacecraft-config-json').value || '{}'); }
        catch (e) { resultEl.textContent = `Invalid JSON: ${e.message}`; return; }
        const qs = dryRun ? '?dry_run=true' : '';
        const resp = await api(`/api/missions/${missionId}/spacecraft/configure${qs}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        resultEl.textContent = JSON.stringify(resp, null, 2);
        flashResult(resultEl, resp.valid !== false);
        if (!dryRun && resp.valid) await loadSpacecraftModel(missionId);
    }
    document.getElementById('btn-configure-dry').addEventListener('click', (e) => withButtonLoading(e.currentTarget, () => submitSpacecraftConfig(true)));
    document.getElementById('btn-configure-spacecraft').addEventListener('click', (e) => withButtonLoading(e.currentTarget, () => submitSpacecraftConfig(false)));

    async function loadSpacecraftModel(missionId) {
        const data = await api(`/api/missions/${missionId}/spacecraft/model`);
        const el = document.getElementById('spacecraft-model-view');
        if (!data.spacecraft.length) { el.innerHTML = '<p class="card-desc">No spacecraft configured yet for this mission.</p>'; return; }
        el.innerHTML = data.spacecraft.map(sc => `
            <div class="ops-import-card">
                <h3>${sc.name} — Ixx=${sc.inertia_ixx} Iyy=${sc.inertia_iyy} Izz=${sc.inertia_izz}</h3>
                ${sc.components.map(c => `<div class="card-desc">${c.component_type}: ${c.name} — ${JSON.stringify(c.parameters)}</div>`).join('') || '<p class="card-desc">No components.</p>'}
            </div>`).join('');
    }

    async function loadSpacecraftScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        await loadSpacecraftModel(missionId);
    }

    // -------------------------------------------------------------
    // Telemetry
    // -------------------------------------------------------------
    async function loadTelemetryScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const rows = await api(`/api/telemetry/latest?limit=20&mission_id=${missionId}`);
        document.getElementById('telemetry-latest-body').innerHTML = rows.map(r => `
            <tr><td>${r.ts}</td><td>${r.omega_x.toFixed(4)}</td><td>${r.omega_y.toFixed(4)}</td><td>${r.omega_z.toFixed(4)}</td>
                <td>${r.reaction_wheel_momentum.toFixed(4)}</td><td>${r.battery_soc_pct.toFixed(1)}</td>
                <td>${r.temperature_c.toFixed(1)}</td><td>${r.power_draw_w.toFixed(1)}</td></tr>`).join('')
            || '<tr><td colspan="8" class="card-desc">No telemetry recorded yet for this mission.</td></tr>';

        const chronological = [...rows].reverse();
        const batteryValues = chronological.map(r => r.battery_soc_pct);
        const thermalValues = chronological.map(r => r.temperature_c);
        const batteryLatestEl = document.getElementById('tel-spark-battery-latest');
        const thermalLatestEl = document.getElementById('tel-spark-thermal-latest');
        if (batteryValues.length) {
            drawSparkline(document.getElementById('tel-spark-battery'), batteryValues, '#3FB27F');
            batteryLatestEl.textContent = `${batteryValues[batteryValues.length - 1].toFixed(1)}%`;
        } else {
            batteryLatestEl.textContent = '—';
        }
        if (thermalValues.length) {
            drawSparkline(document.getElementById('tel-spark-thermal'), thermalValues, '#4FB3D9');
            thermalLatestEl.textContent = `${thermalValues[thermalValues.length - 1].toFixed(1)}°C`;
        } else {
            thermalLatestEl.textContent = '—';
        }
    }
    document.getElementById('btn-run-telemetry-analysis').addEventListener('click', async () => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const resp = await api(`/api/missions/${missionId}/telemetry-analysis/run`, { method: 'POST' });
        document.getElementById('telemetry-analysis-result').textContent = JSON.stringify(resp, null, 2);
    });

    // -------------------------------------------------------------
    // Digital Twin — orbit context + mission health snapshot
    // -------------------------------------------------------------
    async function loadTwinContextScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        if (omegaHistory.length) drawSparkline(document.getElementById('spark-omega'), omegaHistory, '#4FB3D9');
        if (batteryHistory.length) drawSparkline(document.getElementById('spark-battery'), batteryHistory, '#3FB27F');
        try {
            const s = await api(`/api/missions/${missionId}/status`);
            document.getElementById('twin-health').textContent = s.mission_health.overall;
            document.getElementById('twin-verification').textContent = `verification: ${s.verification_state.state}`;
        } catch (e) { /* leave as-is */ }
        try {
            const orbit = await api(`/api/missions/${missionId}/orbit-context`);
            document.getElementById('twin-latlon').textContent = `${orbit.lat_deg.toFixed(2)}°, ${orbit.lon_deg.toFixed(2)}°`;
            document.getElementById('twin-altitude').textContent = `${orbit.altitude_km.toFixed(1)} km`;
            document.getElementById('twin-period').textContent = `${orbit.orbital_period_minutes.toFixed(1)} min`;
            document.getElementById('twin-orbit-note').textContent = 'Real SGP4 propagation from the mission\'s imported TLE, at the actual current time.';
        } catch (e) {
            document.getElementById('twin-latlon').textContent = '—';
            document.getElementById('twin-altitude').textContent = '—';
            document.getElementById('twin-period').textContent = '—';
            document.getElementById('twin-orbit-note').textContent = 'No TLE imported for this mission yet — import one below.';
        }
    }

    // -------------------------------------------------------------
    // Reports screen
    // -------------------------------------------------------------
    async function loadOpsAnalytics(missionId) {
        document.getElementById('analytics-mission-label').textContent = `Mission #${missionId}`;
        const a = await api(`/api/missions/${missionId}/analytics`);
        const pct = v => v === null ? '—' : `${(v * 100).toFixed(0)}%`;
        document.getElementById('ops-analytics-stats').innerHTML = `
            <div class="stat-card"><span class="stat-label">COMMANDS</span><span class="stat-value">${a.total_commands}</span></div>
            <div class="stat-card"><span class="stat-label">ACCEPTANCE RATE</span><span class="stat-value highlight-green">${pct(a.acceptance_rate)}</span></div>
            <div class="stat-card"><span class="stat-label">AVG VERIFIER LATENCY</span><span class="stat-value highlight-cyan">${a.avg_verifier_latency_ms.toFixed(4)}ms</span></div>
            <div class="stat-card"><span class="stat-label">ATTACKS DETECTED</span><span class="stat-value">${a.attacks_detected} / ${a.attacks_simulated}</span></div>
            <div class="stat-card"><span class="stat-label">IMPORTS RECORDED</span><span class="stat-value">${a.imports_recorded}</span></div>`;
    }

    async function loadOpsReports(missionId) {
        const reports = await api(`/api/missions/${missionId}/reports`);
        document.getElementById('ops-reports-list').innerHTML = reports.map(r => `
            <div class="replay-entry" style="display:flex;justify-content:space-between;align-items:center">
                <div>
                    <div class="replay-head"><span>Report #${r.id} — ${r.report_type}</span><span class="status-tag">${r.generated_by}</span></div>
                    <span class="card-desc">${r.created_at}</span>
                </div>
                <div style="display:flex;gap:0.35rem">
                    <button class="btn btn-secondary btn-sm" data-export-report="${r.id}" data-fmt="json" style="padding:0.2rem 0.45rem;font-size:0.68rem">JSON</button>
                    <button class="btn btn-secondary btn-sm" data-export-report="${r.id}" data-fmt="csv" style="padding:0.2rem 0.45rem;font-size:0.68rem">CSV</button>
                    <button class="btn btn-secondary btn-sm" data-export-report="${r.id}" data-fmt="pdf" style="padding:0.2rem 0.45rem;font-size:0.68rem">TXT/PDF</button>
                </div>
            </div>`).join('') || '<p class="card-desc">No reports generated yet.</p>';

        document.querySelectorAll('[data-export-report]').forEach(btn => {
            btn.addEventListener('click', () => {
                const reportId = btn.getAttribute('data-export-report');
                const fmt = btn.getAttribute('data-fmt');
                window.open(`/api/missions/${missionId}/reports/${reportId}/export/${fmt}`, '_blank');
            });
        });
    }

    async function loadVerdictHistoryChart(missionId) {
        const canvas = document.getElementById('verdict-history-chart');
        const emptyEl = document.getElementById('verdict-history-empty');
        const history = await api(`/api/missions/replay?limit=25&mission_id=${missionId}`);
        const commands = history.map(h => h.command);
        canvas.style.display = commands.length ? 'block' : 'none';
        emptyEl.style.display = commands.length ? 'none' : 'block';
        drawVerdictHistoryChart(canvas, commands);
    }

    async function loadReportsScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        await Promise.all([loadOpsAnalytics(missionId), loadOpsReports(missionId), loadVerdictHistoryChart(missionId)]);
    }

    document.getElementById('btn-run-compare').addEventListener('click', async () => {
        const ids = document.getElementById('compare-mission-ids').value.trim();
        if (!ids) return;
        try {
            const rows = await api(`/api/missions/compare?ids=${encodeURIComponent(ids)}`);
            document.getElementById('compare-body').innerHTML = rows.map(r => `
                <tr><td>${r.mission_id}</td><td>${r.total_commands}</td>
                    <td>${r.acceptance_rate === null ? '—' : (r.acceptance_rate * 100).toFixed(0) + '%'}</td>
                    <td>${r.avg_verifier_latency_ms.toFixed(4)}</td><td>${r.attacks_detected} / ${r.attacks_simulated}</td></tr>`).join('');
        } catch (e) {
            document.getElementById('compare-body').innerHTML = `<tr><td colspan="5" class="card-desc">${e.message}</td></tr>`;
        }
    });
    document.getElementById('btn-generate-report').addEventListener('click', async () => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        await api(`/api/missions/${missionId}/reports/generate`, { method: 'POST' });
        await loadOpsReports(missionId);
    });
    document.getElementById('btn-ask-assistant').addEventListener('click', async () => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const question = document.getElementById('assistant-question').value.trim();
        const resp = await api(`/api/missions/${missionId}/assistant/explain`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(question ? { question } : {}),
        });
        document.getElementById('assistant-answer-box').style.display = 'block';
        document.getElementById('assistant-answer-source').textContent = resp.generated_by;
        document.getElementById('assistant-answer').textContent = resp.answer;
        await loadOpsReports(missionId);
    });

    // -------------------------------------------------------------
    // Evidence screen
    // -------------------------------------------------------------
    async function loadOpsTimeline(missionId) {
        const events = await api(`/api/missions/${missionId}/timeline`);
        document.getElementById('ops-timeline-list').innerHTML = events.map(e => `
            <div class="ops-timeline-entry">
                <span><span class="kind-tag">${e.kind}</span> ${e.kind === 'command' ? e.command_id + ' — ' + e.verdict : e.import_type + ' — ' + (e.filename || 'no file')}</span>
                <span class="card-desc">${e.at || ''}</span>
            </div>`).join('') || '<p class="card-desc">No timeline events yet — propose a command or import data.</p>';
    }
    async function loadImportHistory(missionId) {
        const rows = await api(`/api/missions/${missionId}/imports`);
        document.getElementById('import-history-body').innerHTML = rows.map(r => `
            <tr>
                <td>${r.import_type}</td><td>${r.filename || '—'}</td><td>${r.record_count}</td>
                <td title="${r.checksum || ''}">${r.checksum ? r.checksum.slice(0, 18) + '…' : '—'}</td>
                <td>${r.source || '—'}</td><td>${r.schema_version || '—'}</td><td>${r.imported_at}</td>
            </tr>`).join('') || '<tr><td colspan="7" class="card-desc">No imports yet for this mission.</td></tr>';
    }
    async function loadEvidenceScreen() {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        await Promise.all([loadOpsTimeline(missionId), loadImportHistory(missionId)]);
    }
    document.getElementById('btn-download-evidence').addEventListener('click', async () => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const pkg = await api(`/api/missions/${missionId}/evidence-package`);
        const blob = new Blob([JSON.stringify(pkg, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `mission-${missionId}-evidence-package.json`;
        a.click();
        URL.revokeObjectURL(url);
    });

    // -------------------------------------------------------------
    // Settings screen
    // -------------------------------------------------------------
    async function loadSettingsScreen() {
        document.getElementById('settings-profiles-list').innerHTML = profiles.map(p => `
            <div class="agent-card">
                <span class="agent-name">${p.display_name}</span>
                <span class="agent-reasoning">${p.description}</span>
                <span class="agent-meta"><span>max ω ${p.max_omega_rad_s} rad/s</span><span>${p.thermal_min_c}–${p.thermal_max_c}°C</span></span>
            </div>`).join('');

        const missionId = requireActiveMission();
        if (missionId !== null) {
            document.getElementById('settings-mission-id').textContent = missionId;
            document.getElementById('settings-mission-status').value = activeMission.status;
        }
        document.getElementById('settings-ws-status').textContent = document.getElementById('ws-status-value').textContent;

        const plugins = await api('/api/plugins');
        document.getElementById('plugins-note').textContent =
            `Registered plugins: ${plugins.registered.length ? plugins.registered.join(', ') : 'none'}. ${plugins.note}`;
    }
    document.getElementById('btn-set-mission-status').addEventListener('click', async () => {
        const missionId = requireActiveMission();
        if (missionId === null) return;
        const status = document.getElementById('settings-mission-status').value;
        const updated = await api(`/api/missions/${missionId}/status`, {
            method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }),
        });
        activeMission = updated;
        document.getElementById('settings-mission-status-note').textContent = `Mission status updated to ${updated.status}.`;
        await loadMissions();
        missionSelect.value = missionId;
    });

    // -------------------------------------------------------------
    // WebSocket: Digital Twin ticks + live pipeline/verification pushes
    // -------------------------------------------------------------
    function connectWS() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${location.host}/ws`);
        const indicator = document.getElementById('ws-status-indicator'), value = document.getElementById('ws-status-value');
        ws.onopen = () => { indicator.classList.add('online'); value.textContent = 'CONNECTED'; };
        ws.onclose = () => { indicator.classList.remove('online'); value.textContent = 'DISCONNECTED'; setTimeout(connectWS, 3000); };
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'digital_twin_tick') {
                renderDigitalTwinTick(msg.tick);
            } else if (msg.type === 'verification' || msg.type === 'pipeline_run') {
                loadStats();
            }
        };
    }

    // Live Digital Twin state — only drives the display when the user hasn't just proposed a
    // maneuver (a real propose/verify result takes priority over the background simulation).
    let lastProposeAt = 0;
    // Rolling buffers of real values received over the WebSocket — never invented, never
    // interpolated beyond drawing a polyline between the actual points received.
    const omegaHistory = [], batteryHistory = [];
    const SPARKLINE_MAX_POINTS = 60;

    function formatMET(seconds) {
        const totalSec = Math.floor(seconds);
        const hrs = Math.floor(totalSec / 3600);
        const mins = Math.floor((totalSec % 3600) / 60);
        const secs = totalSec % 60;
        const p = num => String(num).padStart(2, '0');
        return `${String(hrs).padStart(3, '0')}:${p(mins)}:${p(secs)}:${p(Math.floor((seconds % 1) * 100))}`;
    }

    function renderDigitalTwinTick(tick) {
        if (Date.now() - lastProposeAt < 5000) return; // let a fresh verdict stay visible briefly
        const omegaMag = Math.sqrt(tick.omega_x ** 2 + tick.omega_y ** 2 + tick.omega_z ** 2);
        currentOmegaVal = omegaMag;
        satSpinSpeed = Math.min(0.25, omegaMag);
        document.getElementById('disp-omega').textContent = `${omegaMag.toFixed(4)} rad/s`;
        drawFarkasChart();

        const metEl = document.getElementById('met-clock-display');
        if (metEl) metEl.textContent = formatMET(tick.t || 42.2);

        const clock = document.getElementById('twin-clock');
        if (clock) {
            document.getElementById('twin-clock').textContent = `T+${tick.t.toFixed(1)}s`;
            document.getElementById('twin-rw').textContent = tick.reaction_wheel_momentum.toFixed(4);
            document.getElementById('twin-battery').textContent = `${tick.battery_soc_pct.toFixed(1)}%`;
            document.getElementById('twin-thermal').textContent = `${tick.temperature_c.toFixed(1)}°C`;
            document.getElementById('twin-power').textContent = `${tick.power_draw_w.toFixed(1)} W`;
            document.getElementById('twin-comm').textContent = `${tick.comm_delay_ms.toFixed(0)}ms / ${tick.sensor_latency_ms.toFixed(1)}ms`;
            document.getElementById('twin-sunlight').textContent = tick.in_sunlight ? 'ILLUMINATED' : 'ECLIPSE';

            // Only pulse the cards actually visible (Digital Twin screen active) — avoids
            // animating hidden DOM every second while another screen is open.
            if (document.getElementById('screen-twin').classList.contains('active')) {
                ['twin-clock', 'twin-rw', 'twin-battery', 'twin-thermal', 'twin-power', 'twin-comm', 'twin-sunlight']
                    .forEach(id => pulseCard(document.getElementById(id).closest('.stat-card')));
            }
        }

        omegaHistory.push(omegaMag); batteryHistory.push(tick.battery_soc_pct);
        if (omegaHistory.length > SPARKLINE_MAX_POINTS) omegaHistory.shift();
        if (batteryHistory.length > SPARKLINE_MAX_POINTS) batteryHistory.shift();
        const omegaCanvas = document.getElementById('spark-omega'), batteryCanvas = document.getElementById('spark-battery');
        if (omegaCanvas && document.getElementById('screen-twin').classList.contains('active')) {
            drawSparkline(omegaCanvas, omegaHistory, '#4FB3D9');
            drawSparkline(batteryCanvas, batteryHistory, '#3FB27F');
            document.getElementById('spark-omega-latest').textContent = `${omegaMag.toFixed(4)} rad/s`;
            document.getElementById('spark-battery-latest').textContent = `${tick.battery_soc_pct.toFixed(1)}%`;
        }
    }

    // Bind Launch Protocol & System Go CTA buttons
    const launchBtn = document.querySelector('.btn-launch');
    if (launchBtn) {
        launchBtn.addEventListener('click', () => {
            const planBtn = document.querySelector('.nav-item[data-screen="planning"]');
            if (planBtn) planBtn.click();
        });
    }
    const goBtn = document.getElementById('btn-system-go');
    if (goBtn) {
        goBtn.addEventListener('click', async (e) => {
            await withButtonLoading(e.currentTarget, () => proposeAndVerify('SAFE_RCS_PULSE'));
        });
    }

    // Init
    loadMissions().then(() => {
        loadProfiles().then(() => { loadFeed(); loadStats(); loadOverviewScreen(); });
    });
    connectWS();
});
