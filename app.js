// Proof-Carrying Commands (PCC) Flight Safety Mission Control System

document.addEventListener('DOMContentLoaded', () => {
    // Navigation Setup
    const navButtons = document.querySelectorAll('.nav-item');
    const screenViews = document.querySelectorAll('.screen-view');
    const screenTitle = document.getElementById('screen-title');

    const titles = {
        orbit: 'Spacecraft Orbital & Attitude Dynamics',
        sandbox: 'AI Agent Maneuver Proposal Sandbox',
        timeline: 'NASA cFS Software Bus Message Stream',
        security: 'Adversarial Security Lab & Attack Simulation'
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
    // 1. CANVAS 1: 3D/2D Satellite Orbit & Attitude Visualizer
    // -------------------------------------------------------------
    const satCanvas = document.getElementById('sat-canvas');
    const ctx = satCanvas.getContext('2d');

    let satAngle = 0;
    let satSpin = 0;
    let satSpinSpeed = 0.014;
    let isThrusterFiring = false;
    let thrusterColor = '#38BDF8';

    function drawSatelliteScene() {
        ctx.clearRect(0, 0, satCanvas.width, satCanvas.height);

        const centerX = satCanvas.width / 2;
        const centerY = satCanvas.height / 2;

        // Draw Deep Space Background Stars
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        for (let i = 0; i < 30; i++) {
            const starX = (i * 37) % satCanvas.width;
            const starY = (i * 73) % satCanvas.height;
            ctx.fillRect(starX, starY, (i % 2) + 1, (i % 2) + 1);
        }

        // Draw Earth
        const earthRadius = 75;
        const earthGradient = ctx.createRadialGradient(centerX, centerY, 10, centerX, centerY, earthRadius);
        earthGradient.addColorStop(0, '#1E40AF');
        earthGradient.addColorStop(0.7, '#1D4ED8');
        earthGradient.addColorStop(1, '#0284C7');

        ctx.beginPath();
        ctx.arc(centerX, centerY, earthRadius, 0, Math.PI * 2);
        ctx.fillStyle = earthGradient;
        ctx.shadowColor = '#38BDF8';
        ctx.shadowBlur = 20;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Earth Atmosphere Glow Ring
        ctx.beginPath();
        ctx.arc(centerX, centerY, earthRadius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
        ctx.lineWidth = 3;
        ctx.stroke();

        // Draw Orbital Path
        const orbitRx = 200;
        const orbitRy = 100;
        ctx.beginPath();
        ctx.ellipse(centerX, centerY, orbitRx, orbitRy, -0.2, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Calculate Satellite Position along Orbit
        satAngle += 0.008;
        const satX = centerX + orbitRx * Math.cos(satAngle);
        const satY = centerY + orbitRy * Math.sin(satAngle);

        // Draw Satellite Body
        satSpin += satSpinSpeed;
        ctx.save();
        ctx.translate(satX, satY);
        ctx.rotate(satSpin);

        // Thruster Particle Pulse Effect
        if (isThrusterFiring) {
            ctx.beginPath();
            ctx.moveTo(-15, 0);
            ctx.lineTo(-30, -8);
            ctx.lineTo(-40, 0);
            ctx.lineTo(-30, 8);
            ctx.closePath();
            ctx.fillStyle = thrusterColor;
            ctx.shadowColor = thrusterColor;
            ctx.shadowBlur = 15;
            ctx.fill();
            ctx.shadowBlur = 0;
        }

        // CubeSat Body
        ctx.fillStyle = '#475569';
        ctx.fillRect(-12, -12, 24, 24);
        ctx.strokeStyle = '#94A3B8';
        ctx.lineWidth = 1;
        ctx.strokeRect(-12, -12, 24, 24);

        // Solar Array Wings
        ctx.fillStyle = '#1E3A8A';
        ctx.strokeStyle = '#38BDF8';
        ctx.fillRect(-36, -6, 20, 12);
        ctx.strokeRect(-36, -6, 20, 12);

        ctx.fillRect(16, -6, 20, 12);
        ctx.strokeRect(16, -6, 20, 12);

        // Attitude Coordinate Axes (X=Cyan, Y=Green)
        ctx.beginPath();
        ctx.moveTo(0, 0); ctx.lineTo(20, 0);
        ctx.strokeStyle = '#38BDF8'; ctx.lineWidth = 2; ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0); ctx.lineTo(0, -20);
        ctx.strokeStyle = '#10B981'; ctx.lineWidth = 2; ctx.stroke();

        ctx.restore();

        requestAnimationFrame(drawSatelliteScene);
    }

    drawSatelliteScene();

    // -------------------------------------------------------------
    // 2. CANVAS 2: Live Farkas Infeasibility Barrier Plot
    // -------------------------------------------------------------
    const farkasCanvas = document.getElementById('farkas-canvas');
    const fCtx = farkasCanvas.getContext('2d');

    let currentOmegaVal = 0.014;
    let maxBoundVal = 0.050;

    function drawFarkasChart() {
        fCtx.clearRect(0, 0, farkasCanvas.width, farkasCanvas.height);

        const pad = 40;
        const w = farkasCanvas.width - pad * 2;
        const h = farkasCanvas.height - pad * 2;

        // Axes
        fCtx.beginPath();
        fCtx.moveTo(pad, pad);
        fCtx.lineTo(pad, pad + h);
        fCtx.lineTo(pad + w, pad + h);
        fCtx.strokeStyle = '#334155';
        fCtx.lineWidth = 1.5;
        fCtx.stroke();

        // Axis Labels
        fCtx.fillStyle = '#64748B';
        fCtx.font = '10px "IBM Plex Mono"';
        fCtx.fillText('Time t (sec)', pad + w / 2 - 25, pad + h + 25);
        fCtx.fillText('||ω|| (rad/s)', 5, pad - 10);

        // Unsafe Threshold Line (0.050 rad/s)
        const unsafeY = pad + h - (maxBoundVal / 0.08) * h;
        fCtx.beginPath();
        fCtx.moveTo(pad, unsafeY);
        fCtx.lineTo(pad + w, unsafeY);
        fCtx.strokeStyle = '#EF4444';
        fCtx.lineWidth = 2;
        fCtx.setLineDash([5, 5]);
        fCtx.stroke();
        fCtx.setLineDash([]);

        fCtx.fillStyle = '#EF4444';
        fCtx.fillText('UNSAFE BOUND: 0.050', pad + w - 130, unsafeY - 6);

        // State Trajectory Curve
        fCtx.beginPath();
        fCtx.moveTo(pad, pad + h - (0.010 / 0.08) * h);

        const steps = 20;
        for (let i = 1; i <= steps; i++) {
            const x = pad + (i / steps) * w;
            const progress = i / steps;
            const val = 0.010 + (currentOmegaVal - 0.010) * Math.sin(progress * Math.PI * 0.5);
            const y = pad + h - (val / 0.08) * h;
            fCtx.lineTo(x, y);
        }

        const isUnsafe = currentOmegaVal > maxBoundVal;
        fCtx.strokeStyle = isUnsafe ? '#EF4444' : '#10B981';
        fCtx.lineWidth = 3;
        fCtx.stroke();

        // Farkas Hyperplane Separation Zone
        if (!isUnsafe) {
            fCtx.fillStyle = 'rgba(16, 185, 129, 0.08)';
            fCtx.fillRect(pad, unsafeY, w, pad + h - unsafeY);
        } else {
            fCtx.fillStyle = 'rgba(239, 68, 68, 0.15)';
            fCtx.fillRect(pad, 0, w, unsafeY);
        }
    }

    drawFarkasChart();

    // -------------------------------------------------------------
    // 3. Interactive Maneuver Sandbox Controls
    // -------------------------------------------------------------
    const sliderWx = document.getElementById('slider-wx');
    const sliderWy = document.getElementById('slider-wy');
    const sliderUx = document.getElementById('slider-ux');
    const sliderUy = document.getElementById('slider-uy');

    function updateSandbox() {
        const wx = parseFloat(sliderWx.value);
        const wy = parseFloat(sliderWy.value);
        const ux = parseFloat(sliderUx.value);
        const uy = parseFloat(sliderUy.value);

        document.getElementById('val-wx').textContent = wx.toFixed(3);
        document.getElementById('val-wy').textContent = wy.toFixed(3);
        document.getElementById('val-ux').textContent = ux.toFixed(3);
        document.getElementById('val-uy').textContent = uy.toFixed(3);

        const predictedOmega = Math.sqrt(Math.pow(wx + ux * 0.8, 2) + Math.pow(wy + uy * 0.8, 2));
        currentOmegaVal = predictedOmega;
        satSpinSpeed = predictedOmega;

        document.getElementById('disp-omega').textContent = `${predictedOmega.toFixed(3)} rad/s`;

        const isSafe = predictedOmega <= maxBoundVal;
        const stateBadge = document.getElementById('sat-state-badge');

        if (isSafe) {
            stateBadge.textContent = 'STABLE LEO ORBIT';
            stateBadge.className = 'badge badge-cyan';
            document.getElementById('farkas-expr').textContent = `λᵀ · (C·x_post - d) = ${(predictedOmega - maxBoundVal).toFixed(4)} < 0  (PROVED SAFE)`;
            document.getElementById('farkas-expr').style.color = '#10B981';
        } else {
            stateBadge.textContent = 'UNSAFE SPINOUT DETECTED';
            stateBadge.className = 'badge badge-danger';
            document.getElementById('farkas-expr').textContent = `λᵀ · (C·x_post - d) = +${(predictedOmega - maxBoundVal).toFixed(4)} ≥ 0  (REFUSED)`;
            document.getElementById('farkas-expr').style.color = '#EF4444';
        }

        drawFarkasChart();

        // Sample proof payload update
        const payload = {
            "command_id": "RCS_PULSE_01043",
            "command_hash": "sha256:d5ac120f6ad61aa12060b724f",
            "sequence_no": 1043,
            "predicted_omega": predictedOmega.toFixed(4),
            "max_bound": maxBoundVal,
            "model_id": "linear_rigid_body_v1",
            "certificate": {
                "type": "farkas_linear_infeasibility",
                "multipliers": isSafe ? [0.20, 0.0, 0.40] : [],
                "status": isSafe ? "PROVED_SAFE" : "PROOF_GENERATION_FAILED"
            },
            "verifier_verdict": isSafe ? "VERIFIED_PASS_2.1ms" : "REJECTED_DROP"
        };

        document.getElementById('sandbox-json-display').textContent = JSON.stringify(payload, null, 2);
    }

    [sliderWx, sliderWy, sliderUx, sliderUy].forEach(s => s.addEventListener('input', updateSandbox));
    updateSandbox();

    // -------------------------------------------------------------
    // 4. Command Feed Table Handling
    // -------------------------------------------------------------
    const commandsData = [
        { id: 'RCS_PULSE_01043', prop: 'Attitude Rate', status: 'VERIFIED', vTime: '2.1 ms', pTime: '4,180 ms', timestamp: '16:30:12', reason: 'Farkas Contradiction Valid' },
        { id: 'POWER_BOOST_0089', prop: 'Power Budget', status: 'VERIFIED', vTime: '1.9 ms', pTime: '3,950 ms', timestamp: '16:28:04', reason: 'Battery SoC >= 40%' },
        { id: 'HALLUCINATED_002', prop: 'Spinout Check', status: 'REFUSED', vTime: '0.0 ms', pTime: '4,520 ms', timestamp: '16:22:15', reason: 'Unsafe Rate > 0.05 rad/s' },
        { id: 'REPLAY_ATTACK_09', prop: 'Replay Shield', status: 'REJECTED', vTime: '0.3 ms', pTime: '0 ms', timestamp: '16:15:30', reason: 'Stale Sequence #1042' }
    ];

    function renderTable() {
        const tbody = document.getElementById('timeline-body');
        tbody.innerHTML = '';
        commandsData.forEach(cmd => {
            const tr = document.createElement('tr');
            const statusClass = cmd.status.toLowerCase();
            tr.innerHTML = `
                <td><strong>${cmd.id}</strong></td>
                <td>${cmd.prop}</td>
                <td><span class="status-tag ${statusClass}">${cmd.status}</span></td>
                <td><span class="highlight-cyan">${cmd.vTime}</span></td>
                <td>${cmd.pTime}</td>
                <td>${cmd.timestamp}</td>
                <td><span class="stat-meta">${cmd.reason}</span></td>
            `;
            tbody.appendChild(tr);
        });
    }

    renderTable();

    // -------------------------------------------------------------
    // 5. Button Actions & Scenario Triggers
    // -------------------------------------------------------------
    document.getElementById('btn-trigger-safe').addEventListener('click', () => {
        isThrusterFiring = true;
        thrusterColor = '#38BDF8';
        setTimeout(() => { isThrusterFiring = false; }, 1200);

        sliderUx.value = 0.001;
        sliderUy.value = -0.002;
        updateSandbox();

        const now = new Date().toTimeString().split(' ')[0];
        commandsData.unshift({
            id: `RCS_PULSE_0${Math.floor(1000 + Math.random() * 9000)}`,
            prop: 'Attitude Rate',
            status: 'VERIFIED',
            vTime: `${(1.8 + Math.random() * 0.5).toFixed(1)} ms`,
            pTime: `${Math.floor(3800 + Math.random() * 500)} ms`,
            timestamp: now,
            reason: 'Farkas Contradiction Valid'
        });
        renderTable();
        alert('✓ Safe RCS Thruster Pulse Authorized by NASA cFS Verifier in < 2.1 ms!');
    });

    document.getElementById('btn-trigger-unsafe').addEventListener('click', () => {
        sliderUx.value = 0.045;
        sliderUy.value = 0.045;
        updateSandbox();

        const now = new Date().toTimeString().split(' ')[0];
        commandsData.unshift({
            id: `UNSAFE_BURN_${Math.floor(100 + Math.random() * 900)}`,
            prop: 'Spinout Check',
            status: 'REFUSED',
            vTime: '0.0 ms',
            pTime: '4,350 ms',
            timestamp: now,
            reason: 'Unsafe Rate > 0.05 rad/s'
        });
        renderTable();
        alert('⚠ Unsafe AI Maneuver Refused! Z3 Solver failed to find Farkas certificate. No command sent.');
    });

    document.getElementById('btn-trigger-attack').addEventListener('click', () => {
        isThrusterFiring = true;
        thrusterColor = '#EF4444';
        setTimeout(() => { isThrusterFiring = false; }, 1200);

        const now = new Date().toTimeString().split(' ')[0];
        commandsData.unshift({
            id: `REPLAY_ATTACK_${Math.floor(100 + Math.random() * 900)}`,
            prop: 'Replay Shield',
            status: 'REJECTED',
            vTime: '0.3 ms',
            pTime: '0 ms',
            timestamp: now,
            reason: 'Stale Sequence Number Reused'
        });
        renderTable();
        alert('⚡ SECURITY ALERT: Replay Attack Intercepted & Dropped by NASA cFS Gate at Step 1!');
    });

    window.triggerHashMismatch = function() {
        const now = new Date().toTimeString().split(' ')[0];
        commandsData.unshift({
            id: `TAMPERED_CMD_${Math.floor(100 + Math.random() * 900)}`,
            prop: 'Hash Binding',
            status: 'REJECTED',
            vTime: '0.4 ms',
            pTime: '0 ms',
            timestamp: now,
            reason: 'SHA-256 Command Hash Mismatch'
        });
        renderTable();
        alert('⚡ SECURITY ALERT: Command Payload Tampering Intercepted by cFS Gate at Step 2!');
    };
});
