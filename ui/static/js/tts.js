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
            if (d.active) _activeVoice = d.active;
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
        if (label) label.textContent = state ? 'Voz ON' : 'Voz OFF';
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
        ef_dora: 'ef_dora — Español (mujer)', em_alex: 'em_alex — Español (hombre)',
        em_santa: 'em_santa — Español (hombre 2)',
        af_heart: 'af_heart — English (mujer)', af_bella: 'af_bella — English (mujer)',
        af_nicole: 'af_nicole — English (mujer)', af_sarah: 'af_sarah — English (mujer)',
        af_sky: 'af_sky — English (mujer)', am_adam: 'am_adam — English (hombre)',
        am_michael: 'am_michael — English (hombre)', bf_emma: 'bf_emma — British (mujer)',
        bf_isabella: 'bf_isabella — British (mujer)', bm_george: 'bm_george — British (hombre)',
        bm_lewis: 'bm_lewis — British (hombre)',
    };

    function _populateVoiceSelector(status) {
        const sel = document.getElementById('tts-voice-select');
        if (!sel) return;
        sel.innerHTML = '';
        const builtin = status.builtin || [];
        const custom = status.custom || [];
        if (builtin.length) {
            const esVoices = builtin.filter(v => v.startsWith('e'));
            const enVoices = builtin.filter(v => !v.startsWith('e'));
            const addGroup = (label, voices) => {
                if (!voices.length) return;
                const og = document.createElement('optgroup');
                og.label = label;
                voices.forEach(v => {
                    const o = document.createElement('option');
                    o.value = v;
                    o.textContent = _VOICE_LABELS[v] || v;
                    if (v === status.active) o.selected = true;
                    og.appendChild(o);
                });
                sel.appendChild(og);
            };
            addGroup('Español', esVoices);
            addGroup('English / British', enVoices);
        }
        if (custom.length) {
            const og = document.createElement('optgroup');
            og.label = 'Voces clonadas';
            custom.forEach(v => {
                const o = document.createElement('option');
                o.value = v; o.textContent = v;
                if (v === status.active) o.selected = true;
                og.appendChild(o);
            });
            sel.appendChild(og);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }

    window._sodaTTS = { speak, stop, toggle, setVoice, setSpeed, get enabled() { return _enabled; } };
})();
