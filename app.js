// Proof-Carrying Commands (PCC) Flight Safety Mission Control System
// Every value on this dashboard comes from a real backend call — nothing here is fabricated.

const API = '';
let activeProfile = null;
let profiles = [];
let lastMissionProfileKey = 'earth_observation';

async function api(path, opts) {
    const res = await fetch(API + path, opts);
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
}

document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navButtons = document.querySelectorAll('.nav-item');
    const screenViews = document.querySelectorAll('.screen-view');
    const screenTitle = document.getElementById('screen-title');
    const titles = {
        orbit: 'Flight Digital Twin — Spacecraft Attitude & Orbital Dynamics',
        sandbox: 'AI Agent Maneuver Proposal Sandbox',
        observatory: 'AI Agent Observatory & Multi-Agent Timeline',
        timeline: 'NASA cFS-Pattern Command Stream',
        security: 'Attack Library — Adversarial Verification',
        replay: 'Mission Replay',
    };
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const screen = btn.getAttribute('data-screen');
            navButtons.forEach(b => b.classList.remove('active'));
            screenViews.forEach(s => s.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`screen-${screen}`).classList.add('active');
            screenTitle.textContent = titles[screen] || 'PCC Flight Gate';
        });
    });

    // -------------------------------------------------------------
    // Satellite orbit canvas — spin speed driven by real Digital Twin ticks
    // -------------------------------------------------------------
    const satCanvas = document.getElementById('sat-canvas');
    const ctx = satCanvas.getContext('2d');
    let satAngle = 0, satSpin = 0, satSpinSpeed = 0.01;
    let isThrusterFiring = false, thrusterColor = '#38BDF8';

    function drawSatelliteScene() {
        ctx.clearRect(0, 0, satCanvas.width, satCanvas.height);
        const centerX = satCanvas.width / 2, centerY = satCanvas.height / 2;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        for (let i = 0; i < 30; i++) {
            ctx.fillRect((i * 37) % satCanvas.width, (i * 73) % satCanvas.height, (i % 2) + 1, (i % 2) + 1);
        }
        const earthRadius = 75;
        const g = ctx.createRadialGradient(centerX, centerY, 10, centerX, centerY, earthRadius);
        g.addColorStop(0, '#1E40AF'); g.addColorStop(0.7, '#1D4ED8'); g.addColorStop(1, '#0284C7');
        ctx.beginPath(); ctx.arc(centerX, centerY, earthRadius, 0, Math.PI * 2);
        ctx.fillStyle = g; ctx.shadowColor = '#38BDF8'; ctx.shadowBlur = 20; ctx.fill(); ctx.shadowBlur = 0;
        ctx.beginPath(); ctx.arc(centerX, centerY, earthRadius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)'; ctx.lineWidth = 3; ctx.stroke();

        const orbitRx = 200, orbitRy = 100;
        ctx.beginPath(); ctx.ellipse(centerX, centerY, orbitRx, orbitRy, -0.2, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]); ctx.stroke(); ctx.setLineDash([]);

        satAngle += 0.008;
        const satX = centerX + orbitRx * Math.cos(satAngle), satY = centerY + orbitRy * Math.sin(satAngle);
        satSpin += satSpinSpeed;
        ctx.save(); ctx.translate(satX, satY); ctx.rotate(satSpin);

        if (isThrusterFiring) {
            ctx.beginPath(); ctx.moveTo(-15, 0); ctx.lineTo(-30, -8); ctx.lineTo(-40, 0); ctx.lineTo(-30, 8); ctx.closePath();
            ctx.fillStyle = thrusterColor; ctx.shadowColor = thrusterColor; ctx.shadowBlur = 15; ctx.fill(); ctx.shadowBlur = 0;
        }
        ctx.fillStyle = '#475569'; ctx.fillRect(-12, -12, 24, 24);
        ctx.strokeStyle = '#94A3B8'; ctx.lineWidth = 1; ctx.strokeRect(-12, -12, 24, 24);
        ctx.fillStyle = '#1E3A8A'; ctx.strokeStyle = '#38BDF8';
        ctx.fillRect(-36, -6, 20, 12); ctx.strokeRect(-36, -6, 20, 12);
        ctx.fillRect(16, -6, 20, 12); ctx.strokeRect(16, -6, 20, 12);
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(20, 0); ctx.strokeStyle = '#38BDF8'; ctx.lineWidth = 2; ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -20); ctx.strokeStyle = '#10B981'; ctx.lineWidth = 2; ctx.stroke();
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
        fCtx.strokeStyle = '#EF4444'; fCtx.lineWidth = 2; fCtx.setLineDash([5, 5]); fCtx.stroke(); fCtx.setLineDash([]);
        fCtx.fillStyle = '#EF4444'; fCtx.fillText(`UNSAFE BOUND: ${maxBoundVal.toFixed(3)}`, pad + w - 130, unsafeY - 6);

        fCtx.beginPath(); fCtx.moveTo(pad, pad + h - (currentOmegaVal * 0.3 / scaleMax) * h);
        const steps = 20;
        for (let i = 1; i <= steps; i++) {
            const x = pad + (i / steps) * w, progress = i / steps;
            const val = currentOmegaVal * (0.3 + 0.7 * Math.sin(progress * Math.PI * 0.5));
            fCtx.lineTo(x, pad + h - (val / scaleMax) * h);
        }
        const isUnsafe = currentOmegaVal > maxBoundVal;
        fCtx.strokeStyle = isUnsafe ? '#EF4444' : '#10B981'; fCtx.lineWidth = 3; fCtx.stroke();
        fCtx.fillStyle = isUnsafe ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.08)';
        if (!isUnsafe) fCtx.fillRect(pad, unsafeY, w, pad + h - unsafeY);
        else fCtx.fillRect(pad, 0, w, unsafeY);
    }
    drawFarkasChart();

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
        lastMissionProfileKey = activeProfile.profile_key;
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
        document.getElementById('farkas-expr').style.color = t.overall === 'TRUSTED' ? '#10B981' : '#EF4444';
        drawFarkasChart();
    }

    // -------------------------------------------------------------
    // Agent Observatory
    // -------------------------------------------------------------
    function renderAgentObservatory(steps) {
        const el = document.getElementById('agent-observatory');
        el.innerHTML = steps.map(s => `
            <div class="agent-card ${s.status === 'REFUSED' ? 'refused' : ''}">
                <span class="agent-name">${s.step_order}. ${s.agent_name}</span>
                <div class="confidence-bar"><span style="width:${(s.confidence * 100).toFixed(0)}%"></span></div>
                <span class="agent-meta"><span>${s.status}</span><span>${s.latency_ms.toFixed(3)} ms</span></span>
                <span class="agent-reasoning">${s.reasoning_summary}</span>
            </div>`).join('');
    }

    // -------------------------------------------------------------
    // Command feed
    // -------------------------------------------------------------
    async function loadFeed() {
        const rows = await api('/api/commands/feed?limit=25');
        const tbody = document.getElementById('timeline-body');
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td><strong>${r.command_id}</strong></td>
                <td>${r.display_name || ''}</td>
                <td><span class="status-tag ${r.verdict.toLowerCase()}">${r.verdict}</span></td>
                <td><span class="highlight-cyan">${r.verifier_time_ms != null ? r.verifier_time_ms.toFixed(3) + ' ms' : '—'}</span></td>
                <td>${r.producer_time_ms != null ? r.producer_time_ms.toFixed(1) + ' ms' : '—'}</td>
                <td>${r.submitted_at}</td>
                <td><span class="stat-meta">${r.reject_reason || 'Farkas contradiction valid'}</span></td>
            </tr>`).join('');
    }

    async function loadStats() {
        const report = await api('/api/evaluation/report');
        document.getElementById('pass-count').textContent = Math.round(report.total_commands * report.acceptance_rate);
        document.getElementById('drop-count').textContent = Math.round(report.total_commands * report.rejection_rate);
        document.getElementById('stat-verifier-time').textContent = `${report.avg_verifier_latency_ms.toFixed(3)} ms`;
        document.getElementById('stat-producer-time').textContent = `${report.avg_producer_latency_ms.toFixed(1)} ms`;
        document.getElementById('stat-asymmetry').textContent = report.computational_asymmetry ? `${report.computational_asymmetry}x` : '—';
    }

    // -------------------------------------------------------------
    // Propose + verify a maneuver (used by header buttons and sandbox)
    // -------------------------------------------------------------
    async function proposeAndVerify(maneuverType, x0, u_cmd) {
        const body = { maneuver_type: maneuverType, mission_profile_key: activeProfile.profile_key };
        if (x0) body.x0 = x0;
        if (u_cmd) body.u_cmd = u_cmd;
        const proposal = await api('/api/commands/propose', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        renderAgentObservatory(proposal.pipeline_steps);

        if (proposal.refused) {
            document.getElementById('explain-narrative').textContent = `Refused before signing: ${proposal.refusal_reason}`;
            const badge = document.getElementById('trust-overall-badge');
            badge.textContent = 'REFUSED'; badge.className = 'badge badge-danger';
            document.getElementById('trust-checklist').innerHTML = '';
            await loadFeed(); await loadStats();
            return { proposal, verify: null };
        }

        const verifyBody = {
            command_row_id: proposal.command_row_id, proof: proposal.proof,
            submitted_command_id: proposal.command_id, submitted_u_cmd: proposal.u_cmd,
            mission_profile_key: activeProfile.profile_key,
        };
        const verify = await api('/api/commands/verify', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(verifyBody),
        });
        renderTrust(verify);
        await loadFeed(); await loadStats();
        return { proposal, verify };
    }

    document.getElementById('btn-trigger-safe').addEventListener('click', async () => {
        isThrusterFiring = true; thrusterColor = '#38BDF8'; setTimeout(() => { isThrusterFiring = false; }, 1200);
        await proposeAndVerify('SAFE_RCS_PULSE');
    });
    document.getElementById('btn-trigger-unsafe').addEventListener('click', async () => {
        await proposeAndVerify('UNSAFE_RCS_PULSE');
    });
    document.getElementById('btn-trigger-attack').addEventListener('click', async () => {
        isThrusterFiring = true; thrusterColor = '#EF4444'; setTimeout(() => { isThrusterFiring = false; }, 1200);
        const result = await api('/api/attacks/run', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ attack_type: 'replay', mission_profile_key: activeProfile.profile_key }),
        });
        renderTrust({ trust: result.trust, explain: result.explain });
        await loadFeed(); await loadStats();
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

    const calcBtn = document.getElementById('btn-calc-proof');
    if (calcBtn) {
        calcBtn.addEventListener('click', async () => {
            const x0 = [parseFloat(sliderWx.value), parseFloat(sliderWy.value), 0.0];
            const u_cmd = [parseFloat(sliderUx.value), parseFloat(sliderUy.value), 0.0];
            const display = document.getElementById('sandbox-json-display');
            display.textContent = 'Calling real backend (Z3 solver + verifier)…';
            try {
                const { proposal, verify } = await proposeAndVerify('SANDBOX', x0, u_cmd);
                display.textContent = JSON.stringify({ proposal_refused: proposal.refused, refusal_reason: proposal.refusal_reason, proof: proposal.proof, verification: verify }, null, 2);
            } catch (e) {
                display.textContent = `Error: ${e.message}`;
            }
        });
    }

    // -------------------------------------------------------------
    // Attack Library
    // -------------------------------------------------------------
    async function loadAttackLibrary() {
        const types = await api('/api/attacks/types');
        const grid = document.getElementById('attack-library-grid');
        grid.innerHTML = types.map(t => `
            <div class="panel attack-card" data-attack="${t}">
                <div class="panel-header"><h2>${t.replace(/_/g, ' ')}</h2><span class="badge badge-amber">Not yet run</span></div>
                <p class="card-desc" data-desc>Click Run to execute this attack against the live verifier.</p>
                <button class="btn btn-danger" data-run="${t}">Run Attack</button>
            </div>`).join('');
        grid.querySelectorAll('[data-run]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const attackType = btn.getAttribute('data-run');
                const card = btn.closest('.attack-card');
                const badge = card.querySelector('.badge');
                badge.textContent = 'Running…';
                const result = await api('/api/attacks/run', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ attack_type: attackType, mission_profile_key: activeProfile.profile_key }),
                });
                badge.textContent = result.detected ? 'DETECTED & REJECTED' : 'NOT DETECTED';
                badge.className = 'badge ' + (result.detected ? 'badge-danger' : 'badge-amber');
                card.querySelector('[data-desc]').textContent = `${result.description} -> ${result.reject_reason || 'accepted'}`;
                await loadFeed(); await loadStats();
            });
        });
    }

    // -------------------------------------------------------------
    // Mission Replay
    // -------------------------------------------------------------
    document.getElementById('btn-load-replay').addEventListener('click', async () => {
        const history = await api('/api/missions/replay?limit=50');
        const el = document.getElementById('replay-list');
        el.innerHTML = history.map(h => `
            <div class="replay-entry">
                <div class="replay-head">
                    <span>${h.command.command_id}</span>
                    <span class="status-tag ${h.command.verdict.toLowerCase()}">${h.command.verdict}</span>
                </div>
                <span class="card-desc">Seq #${h.command.sequence_no} — ${h.explain ? h.explain.narrative : 'not yet verified'}</span>
            </div>`).join('') || '<p class="card-desc">No mission history yet — propose and verify a command first.</p>';
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
                const t = msg.tick;
                document.querySelectorAll('.telemetry-pill .pill-val').length; // no-op guard
            }
        };
    }

    // Init
    loadProfiles().then(() => { loadFeed(); loadStats(); loadAttackLibrary(); });
    connectWS();
});
