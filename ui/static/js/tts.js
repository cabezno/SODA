/**
 * SODA TTS — browser-side audio playback.
 * Exposes window._sodaTTS with speak(), stop(), toggle(), setVoice(), setSpeed().
 * All audio is generated server-side (Kokoro) and streamed as WAV.
 */
(function () {
    'use strict';

    let _enabled = false;
    let _currentAudio = null;
    let _activeVoice = null;
    let _activeSpeed = 1.0;

    async function _fetchStatus() {
        try {
            const r = await fetch('/api/tts/status');
            const d = await r.json();
            _enabled = d.available && d.enabled;
            if (d.active || d.current_voice) _activeVoice = d.active || d.current_voice;
            if (d.speed) _activeSpeed = d.speed;
            return d;
        } catch (_) {
            return { available: false, enabled: false };
        }
    }

    async function speak(text) {
        if (!_enabled) return;
        if (!text || !text.trim()) return;
        stop();
        try {
            const body = { text };
            if (_activeVoice) body.voice = _activeVoice;
            body.speed = _activeSpeed;
            const r = await fetch('/api/tts/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!r.ok) return;
            const blob = await r.blob();
            const url = URL.createObjectURL(blob);
            _currentAudio = new Audio(url);
            _currentAudio.onended = () => { URL.revokeObjectURL(url); _currentAudio = null; };
            _currentAudio.play();
        } catch (e) {
            console.warn('[TTS] speak error:', e);
        }
    }

    function stop() {
        if (_currentAudio) {
            _currentAudio.pause();
            _currentAudio = null;
        }
    }

    async function toggle(forceState) {
        const enabled = typeof forceState === 'boolean' ? forceState : !_enabled;
        try {
            const r = await fetch('/api/tts/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled }),
            });
            const d = await r.json();
            _enabled = d.tts_enabled;
            _updateSwitchUI(_enabled);
            if (!_enabled) stop();
        } catch (e) {
            console.warn('[TTS] toggle error:', e);
        }
        return _enabled;
    }

    async function setVoice(voice) {
        try {
            const r = await fetch('/api/tts/set_voice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ voice }),
            });
            if (r.ok) _activeVoice = voice;
        } catch (e) {
            console.warn('[TTS] setVoice error:', e);
        }
    }

    async function setSpeed(speed) {
        try {
            const r = await fetch('/api/tts/set_speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed }),
            });
            if (r.ok) _activeSpeed = speed;
        } catch (e) {
            console.warn('[TTS] setSpeed error:', e);
        }
    }

    function _updateSwitchUI(state) {
        const sw = document.getElementById('tts-toggle-switch');
        if (!sw) return;
        sw.checked = state;
        const label = document.getElementById('tts-toggle-label');
        if (label) label.textContent = state ? 'Talk ON' : 'Talk OFF';
    }

    // Initialise on load
    async function _init() {
        const status = await _fetchStatus();
        _updateSwitchUI(_enabled);
        // Populate voice selector if TTS card is visible
        _populateVoiceSelector(status);
        // Update speed slider
        const slider = document.getElementById('tts-speed-slider');
        if (slider) {
            slider.value = _activeSpeed;
            const label = document.getElementById('tts-speed-val');
            if (label) label.textContent = _activeSpeed.toFixed(1) + '×';
        }
    }

    const _VOICE_LABELS = {
        'es-AR-ElenaNeural': 'Elena — Argentina (femenina)',
        'es-AR-TomasNeural': 'Tomás — Argentina (masculino)',
        'es-ES-AlvaroNeural': 'Álvaro — España (masculino)',
        'es-ES-ElviraNeural': 'Elvira — España (femenina)',
        'es-MX-DaliaNeural': 'Dalia — México (femenina)',
        'es-MX-JorgeNeural': 'Jorge — México (masculino)',
    };

    function _populateVoiceSelector(status) {
        const sel = document.getElementById('tts-voice-select');
        if (!sel) return;
        sel.innerHTML = '';
        const active = status.active || status.current_voice || '';
        const builtin = status.builtin || [];
        const custom = status.custom || [];

        const addGroup = (label, voices) => {
            if (!voices.length) return;
            const og = document.createElement('optgroup');
            og.label = label;
            voices.forEach(v => {
                const o = document.createElement('option');
                o.value = v;
                o.textContent = _VOICE_LABELS[v] || v;
                if (v === active) o.selected = true;
                og.appendChild(o);
            });
            sel.appendChild(og);
        };

        if (builtin.length) {
            const arVoices = builtin.filter(v => v.includes('-AR-'));
            const esVoices = builtin.filter(v => v.includes('-ES-'));
            const mxVoices = builtin.filter(v => v.includes('-MX-'));
            const otherVoices = builtin.filter(v => !v.includes('-AR-') && !v.includes('-ES-') && !v.includes('-MX-'));
            addGroup('Argentina', arVoices);
            addGroup('España', esVoices);
            addGroup('México', mxVoices);
            addGroup('Otros', otherVoices);
        }
        if (custom.length) {
            addGroup('Voces clonadas', custom);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }

    window._sodaTTS = { speak, stop, toggle, setVoice, setSpeed, get enabled() { return _enabled; } };
})();
