
        let editor;          // alias → _codigoEditor (set on init)
        let files = {};
        let ramTotal = null;
        let activeFile = null;
        let currentProjectId = null;
        const phases = ['capabilities', 'requirements', 'architecture', 'planning', 'development', 'validation'];

        // --- Monaco loader config (editors init lazily per tab) ---
        require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' } });

        // ── Cytoscape Graph Visualization ────────────────────────────────────
        let _cy = null;
        let _cyMode = 'modules'; // 'modules' | 'files'
        let _cyLevels = null;    // stored for layout reference

        const _CY_STYLE = [
            { selector: 'node', style: {
                'background-color': '#111', 'border-color': '#2a2a2a', 'border-width': 1.5,
                'color': '#555', 'label': 'data(label)',
                'font-size': 11, 'font-family': 'monospace',
                'text-valign': 'center', 'text-halign': 'center',
                'width': 130, 'height': 38, 'shape': 'roundrectangle',
                'text-wrap': 'ellipsis', 'text-max-width': 118,
                'transition-property': 'background-color, border-color, color',
                'transition-duration': '0.4s',
            }},
            { selector: 'node.generating', style: {
                'background-color': '#011820', 'border-color': '#00e5ff',
                'border-width': 2, 'color': '#00e5ff',
            }},
            { selector: 'node.done', style: {
                'background-color': '#011208', 'border-color': '#00c853', 'color': '#00c853',
            }},
            { selector: 'node.error', style: {
                'background-color': '#180101', 'border-color': '#ff4444', 'color': '#ff4444',
            }},
            { selector: 'node[type="python"]', style: { 'shape': 'roundrectangle' }},
            { selector: 'node[type="javascript"],node[type="typescript"]', style: { 'shape': 'barrel' }},
            { selector: 'node[type="css"],node[type="html"]', style: { 'shape': 'diamond', 'height': 44 }},
            { selector: 'node[type="json"],node[type="yaml"]', style: { 'shape': 'ellipse', 'height': 32, 'width': 100 }},
            { selector: 'edge', style: {
                'width': 1.2, 'line-color': '#222',
                'target-arrow-color': '#333', 'target-arrow-shape': 'triangle',
                'curve-style': 'bezier', 'arrow-scale': 0.7, 'opacity': 0.7,
            }},
            { selector: 'node:selected', style: {
                'border-color': '#fff', 'border-width': 2.5, 'color': '#fff',
            }},
        ];

        function _cyInit() {
            const container = document.getElementById('dag-container');
            if (!container || !window.cytoscape) return;
            if (_cy) { _cy.destroy(); _cy = null; }
            _cy = cytoscape({
                container,
                style: _CY_STYLE,
                userZoomingEnabled: true,
                userPanningEnabled: true,
                boxSelectionEnabled: false,
                backgroundColor: '#080808',
            });

            // Click node → open file in Código tab
            _cy.on('tap', 'node', async (e) => {
                const path = e.target.data('path');
                if (!path || !currentProjectId) return;
                try {
                    const res = await fetch(`/api/projects/${encodeURIComponent(currentProjectId)}/files`);
                    const data = await res.json();
                    const content = (data.files || {})[path] || '';
                    codigoOpenTab(path, content);
                } catch {}
            });

            // Tooltip on hover
            const tooltip = document.getElementById('graph-tooltip');
            _cy.on('mouseover', 'node', (e) => {
                if (!tooltip) return;
                const d = e.target.data();
                const lines = [`<b>${d.label}</b>`];
                if (d.type && d.type !== 'module') lines.push(`Tipo: ${d.type}`);
                if (d.files) lines.push(`Archivos: ${d.files}`);
                if (d.size) lines.push(`Tamaño: ${Math.round(d.size / 1024 * 10) / 10} KB`);
                if (d.path) lines.push(`<span style="color:#444">${d.path}</span>`);
                tooltip.innerHTML = lines.join('<br>');
                tooltip.style.display = 'block';
            });
            _cy.on('mouseout', 'node', () => { if (tooltip) tooltip.style.display = 'none'; });
            _cy.on('mousemove', (e) => {
                if (!tooltip || tooltip.style.display === 'none') return;
                const rect = container.getBoundingClientRect();
                tooltip.style.left = (e.originalEvent.clientX - rect.left + 14) + 'px';
                tooltip.style.top  = (e.originalEvent.clientY - rect.top  + 14) + 'px';
            });
        }

        function _cyLoadElements(nodes, edges) {
            if (!_cy) _cyInit();
            if (!_cy) return;
            document.getElementById('dag-empty').style.display = 'none';
            _cy.elements().remove();
            const els = [
                ...nodes.map(n => ({ data: { id: n.id, label: n.label, type: n.type || 'module', path: n.path, files: n.files, size: n.size } })),
                ...edges.map(e => ({ data: { source: e.source, target: e.target, id: `${e.source}→${e.target}` } })).filter(e => {
                    const ids = new Set(_cy ? [] : []);
                    return true; // filter invalid edges after add
                }),
            ];
            try { _cy.add(els); } catch {}
            // Remove edges whose endpoints don't exist
            _cy.edges().forEach(e => { if (!e.source().length || !e.target().length) e.remove(); });
        }

        function _cyLayout(name = 'breadthfirst') {
            if (!_cy || !_cy.nodes().length) return;
            const opts = name === 'breadthfirst'
                ? { name: 'breadthfirst', directed: true, spacingFactor: 1.4, padding: 40, avoidOverlap: true }
                : { name: 'cose', idealEdgeLength: 120, nodeOverlap: 20, refresh: 20, fit: true, padding: 40, randomize: false, componentSpacing: 80, nodeRepulsion: 8000, edgeElasticity: 100 };
            _cy.layout(opts).run();
        }

        async function _cyRenderModules(levels, projectId) {
            _cyLevels = levels;
            if (!projectId) {
                // Fallback: render from levels only, no edges
                const nodes = levels.flatMap((level, li) =>
                    level.map(name => ({ id: name, label: name, type: 'module', path: null, files: 0 }))
                );
                _cyLoadElements(nodes, []);
                _cyLayout('breadthfirst');
                return;
            }
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/graph?mode=modules`);
                const data = await res.json();
                _cyLoadElements(data.nodes, data.edges);
                _cyLayout('breadthfirst');
            } catch {
                // Fallback to levels
                const nodes = levels.flatMap(level =>
                    level.map(name => ({ id: name, label: name, type: 'module', path: null }))
                );
                _cyLoadElements(nodes, []);
                _cyLayout('breadthfirst');
            }
        }

        async function _cyRenderFiles(projectId) {
            if (!projectId) return;
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/graph?mode=files`);
                const data = await res.json();
                if (!data.nodes.length) return; // no files yet
                _cyLoadElements(data.nodes, data.edges);
                _cyLayout('cose');
            } catch {}
        }

        function _dagSetStatus(name, status) {
            if (!_cy) return;
            const node = _cy.$(`[id="${name}"]`);
            if (node.length) {
                node.removeClass('generating done error');
                if (status !== 'pending') node.addClass(status);
            }
        }

        // Public: switch between module/file view
        function cySetMode(mode) {
            _cyMode = mode;
            document.getElementById('btn-mode-modules').classList.toggle('active', mode === 'modules');
            document.getElementById('btn-mode-files').classList.toggle('active', mode === 'files');
            if (mode === 'modules' && (_cyLevels || currentProjectId)) {
                _cyRenderModules(_cyLevels || [], currentProjectId);
            } else if (mode === 'files') {
                _cyRenderFiles(currentProjectId);
            }
        }

        function cyFitGraph() { if (_cy) _cy.fit(undefined, 40); }
        function cyResetLayout() { _cyLayout(_cyMode === 'files' ? 'cose' : 'breadthfirst'); }

        // Legacy stubs (SVG DAG replaced by Cytoscape)
        function _dagRender(levels) { _cyRenderModules(levels, currentProjectId); }
        function _dagClear() {
            if (_cy) { _cy.elements().remove(); }
            const empty = document.getElementById('dag-empty');
            if (empty) empty.style.display = 'flex';
        }

        // ── Código Tab ────────────────────────────────────────────────────────
        let _codigoEditor = null;
        let _codigoTabs = [];     // [{path, content, dirty}]
        let _codigoActive = null;

        function initCodigoTab() {
            if (_codigoEditor) { _codigoEditor.layout(); return; }
            const container = document.getElementById('codigo-editor-container');
            if (!container || !window.monaco) { require(['vs/editor/editor.main'], initCodigoTab); return; }
            _codigoEditor = monaco.editor.create(container, {
                value: '// Abrí un archivo del proyecto o pegá código aquí…',
                language: 'plaintext', theme: 'vs-dark', automaticLayout: true,
                readOnly: false, minimap: { enabled: false },
                fontSize: 13, lineNumbers: 'on', scrollBeyondLastLine: false,
            });
            editor = _codigoEditor; // alias for legacy refs
            _codigoEditor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, codigoSaveFile);
            _codigoEditor.onDidChangeModelContent(() => {
                if (!_codigoActive) return;
                const tab = _codigoTabs.find(t => t.path === _codigoActive);
                if (tab && !tab.dirty) { tab.dirty = true; _codigoRenderTabs(); }
            });
        }

        function codigoOpenTab(path, content) {
            let tab = _codigoTabs.find(t => t.path === path);
            if (!tab) { tab = { path, content, dirty: false }; _codigoTabs.push(tab); }
            else { tab.content = content; }
            _codigoActive = path;
            _codigoRenderTabs();
            // Switch to Código top-level tab
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('.tab[data-tab="codigo"]').classList.add('active');
            document.getElementById('codigo-tab').classList.add('active');
            codigoShowPanel('editor');
            initCodigoTab();
            // Load file into editor (may be async if monaco not ready)
            const tryLoad = () => {
                if (!_codigoEditor) { setTimeout(tryLoad, 150); return; }
                const model = monaco.editor.createModel(tab.content, langFromFilename(path));
                _codigoEditor.setModel(model);
            };
            tryLoad();
        }

        function _codigoRenderTabs() {
            const bar = document.getElementById('codigo-file-tabs');
            if (!bar) return;
            bar.innerHTML = '';
            _codigoTabs.forEach(t => {
                const div = document.createElement('div');
                div.className = 'codigo-ftab' + (t.path === _codigoActive ? ' active' : '');
                const nameSpan = document.createElement('span');
                nameSpan.textContent = t.path.split('/').pop() + (t.dirty ? ' •' : '');
                nameSpan.onclick = () => codigoSetActive(t.path);
                const closeSpan = document.createElement('span');
                closeSpan.className = 'codigo-close';
                closeSpan.textContent = '✕';
                closeSpan.onclick = (e) => { e.stopPropagation(); codigoCloseTab(t.path); };
                div.appendChild(nameSpan);
                div.appendChild(closeSpan);
                bar.appendChild(div);
            });
        }

        function codigoSetActive(path) {
            const tab = _codigoTabs.find(t => t.path === path);
            if (!tab || !_codigoEditor) return;
            _codigoActive = path;
            _codigoRenderTabs();
            const model = monaco.editor.createModel(tab.content, langFromFilename(path));
            _codigoEditor.setModel(model);
        }

        function codigoCloseTab(path) {
            _codigoTabs = _codigoTabs.filter(t => t.path !== path);
            if (_codigoActive === path) {
                _codigoActive = _codigoTabs.length ? _codigoTabs[_codigoTabs.length - 1].path : null;
                if (_codigoActive) codigoSetActive(_codigoActive);
                else if (_codigoEditor) _codigoEditor.setValue('// Abrí un archivo del proyecto o pegá código aquí…');
            }
            _codigoRenderTabs();
        }

        async function codigoSaveFile() {
            if (!_codigoActive || !_codigoEditor || !currentProjectId) {
                const st = document.getElementById('codigo-status');
                if (st) st.textContent = 'Sin proyecto activo';
                return;
            }
            const content = _codigoEditor.getValue();
            const tab = _codigoTabs.find(t => t.path === _codigoActive);
            if (tab) { tab.content = content; tab.dirty = false; _codigoRenderTabs(); }
            const st = document.getElementById('codigo-status');
            if (st) st.textContent = 'Guardando…';
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(currentProjectId)}/files`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: _codigoActive, content }),
                });
                const d = await res.json();
                if (st) { st.textContent = d.status === 'saved' ? '✓ Guardado' : '✗ Error'; setTimeout(() => { st.textContent = ''; }, 2500); }
            } catch { if (st) st.textContent = '✗ Error de red'; }
        }

        function codigoNewFile() {
            const name = prompt('Nombre del archivo:', 'nuevo.py');
            if (!name) return;
            codigoOpenTab(name, '');
        }

        async function codigoOpenFromProject() {
            if (!currentProjectId) { alert('No hay proyecto activo.'); return; }
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(currentProjectId)}/files`);
                const data = await res.json();
                const paths = Object.keys(data.files || {});
                if (!paths.length) { alert('Sin archivos en el proyecto.'); return; }
                const choice = prompt(`Archivos:\n${paths.map((p, i) => `${i + 1}. ${p}`).join('\n')}\n\nNúmero:`);
                if (!choice) return;
                const idx = parseInt(choice) - 1;
                if (idx >= 0 && idx < paths.length) codigoOpenTab(paths[idx], data.files[paths[idx]]);
            } catch { alert('Error al cargar archivos.'); }
        }

        function codigoShowPanel(panel) {
            const ep = document.getElementById('codigo-editor-panel');
            const ip = document.getElementById('codigo-import-panel');
            if (ep) ep.style.display = panel === 'editor' ? 'flex' : 'none';
            if (ip) ip.style.display = panel === 'importar' ? 'flex' : 'none';
            document.querySelectorAll('.csel').forEach(b => b.classList.toggle('active', b.dataset.panel === panel));
            if (panel === 'editor' && _codigoEditor) _codigoEditor.layout();
            if (panel === 'importar') initImportEditor();
        }

        function langFromFilename(name) {
            const ext = name.split('.').pop().toLowerCase();
            const map = { py:'python', js:'javascript', ts:'typescript', html:'html', css:'css', json:'json', md:'markdown', yml:'yaml', yaml:'yaml', sh:'shell', txt:'plaintext' };
            return map[ext] || 'plaintext';
        }

        function iconFromFilename(name) {
            const ext = name.split('.').pop().toLowerCase();
            const map = { py:'[py]', js:'[js]', ts:'[ts]', html:'[html]', css:'[css]', json:'[json]', md:'[md]' };
            return map[ext] || '[file]';
        }

        function openFile(filename) {
            document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
            const item = document.querySelector(`.file-item[data-file="${CSS.escape(filename)}"]`);
            if (item) item.classList.add('active');
            activeFile = filename;
            codigoOpenTab(filename, files[filename] || '');
        }

        // Load all project files from disk into the file list
        async function loadAllProjectFiles(projectId) {
            if (!projectId) return;
            const btn = document.getElementById('load-files-btn');
            if (btn) { btn.disabled = true; btn.textContent = 'Cargando…'; }
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/files`);
                if (!res.ok) return;
                const data = await res.json();
                const allFiles = data.files || {};
                const list = document.getElementById('file-list');
                Object.entries(allFiles).forEach(([path, content]) => {
                    if (files[path] !== undefined) return; // already in list
                    files[path] = content;
                    const item = document.createElement('div');
                    item.className = 'file-item';
                    item.dataset.file = path;
                    item.innerHTML = `<span class="file-icon">${iconFromFilename(path)}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(path)}</span>`;
                    item.onclick = () => openFile(path);
                    list.appendChild(item);
                });
                const newCount = Object.keys(allFiles).length;
                log(`${newCount} archivo(s) cargados del proyecto`, 'MODULE_DONE');
            } catch(e) {
                log('No se pudieron cargar los archivos', 'HEALTH_WARN');
            } finally {
                if (btn) { btn.disabled = false; btn.textContent = 'Actualizar'; }
            }
        }

        // Open a specific file in editor by sending to backend (adds to files dict if not present)
        async function openFileByPath(projectId, filepath) {
            if (!projectId || !filepath) return;
            if (files[filepath] !== undefined) { openFile(filepath); return; }
            try {
                const res = await fetch('/api/open_in_editor', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({project_id: projectId, filepath}),
                });
                if (!res.ok) log('Archivo no encontrado: ' + filepath, 'HEALTH_WARN');
                // OPEN_FILE WS event will trigger openFile()
            } catch(e) {
                log('Error al abrir archivo', 'HEALTH_WARN');
            }
        }

        // --- Tabs (legacy stub — editor now lives in Código tab) ---
        function switchTab(tabId) { if (tabId === 'editor') initCodigoTab(); }

        // --- Objective tree ---
        function buildTree(levels) {
            const wrap = document.getElementById('tree-wrap');
            wrap.innerHTML = '';
            levels.forEach((mods, i) => {
                const lvl = document.createElement('div');
                lvl.className = 'tree-level';
                const label = document.createElement('div');
                label.className = 'tree-level-label';
                label.textContent = `Level ${i}${mods.length > 1 ? ' — parallel' : ''}`;
                const chips = document.createElement('div');
                chips.className = 'tree-modules';
                mods.forEach(mod => {
                    const chip = document.createElement('span');
                    chip.className = 'mod-chip';
                    chip.id = `mod-${mod}`;
                    chip.textContent = mod;
                    chips.appendChild(chip);
                });
                lvl.appendChild(label);
                lvl.appendChild(chips);
                wrap.appendChild(lvl);
            });
            document.getElementById('tree-section').classList.remove('hidden');
        }

        function setModuleState(modName, state) {
            const chip = document.getElementById(`mod-${modName}`);
            if (!chip) return;
            chip.className = `mod-chip ${state}`;
        }

        // --- Goal Tree panel ---
        function toggleGoalTree() {
            const toggle = document.getElementById('goal-tree-toggle');
            const body = document.getElementById('goal-tree-body');
            toggle.classList.toggle('collapsed');
            body.classList.toggle('hidden');
        }

        async function loadGoalTree(projectId) {
            if (!projectId) return;
            try {
                const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/goal_tree`);
                if (!res.ok) return;
                const data = await res.json();
                renderGoalTree(data.nodes || []);
            } catch(e) {}
        }

        function renderGoalTree(nodes) {
            const body = document.getElementById('goal-tree-body');
            const section = document.getElementById('goal-tree-section');
            if (!nodes || nodes.length === 0) { section.classList.add('hidden'); return; }
            body.innerHTML = '';
            section.classList.remove('hidden');
            // Sort: implemented first, then in_progress, then planned
            const order = {implemented:0, in_progress:1, planned:2, deprecated:3};
            nodes.sort((a,b) => (order[a.status]||2) - (order[b.status]||2));
            nodes.forEach(node => {
                const row = document.createElement('div');
                row.className = 'gt-node';
                row.title = node.description || '';
                const dot = document.createElement('div');
                dot.className = `gt-node-dot ${node.status || 'planned'}`;
                const desc = document.createElement('div');
                desc.className = 'gt-node-desc';
                desc.textContent = node.description || node.id;
                const typeLabel = document.createElement('div');
                typeLabel.className = 'gt-node-type';
                typeLabel.textContent = node.type || '';
                row.appendChild(dot);
                row.appendChild(desc);
                row.appendChild(typeLabel);
                body.appendChild(row);
            });
        }

        function updateGoalNodeStatus(goalId, newStatus) {
            // Called from WS events to update a node in real time
            const body = document.getElementById('goal-tree-body');
            if (!body) return;
            const nodes = body.querySelectorAll('.gt-node');
            nodes.forEach(row => {
                if (row.dataset.goalId === goalId) {
                    const dot = row.querySelector('.gt-node-dot');
                    if (dot) dot.className = `gt-node-dot ${newStatus}`;
                }
            });
        }

        // --- Wisdom panel ---
        function renderWisdom(observations) {
            const panel = document.getElementById('wisdom-panel');
            panel.innerHTML = '';
            if (!observations || observations.length === 0) return;
            panel.classList.remove('hidden');
            observations.forEach(obs => {
                const item = document.createElement('div');
                item.className = 'wisdom-item';
                item.innerHTML = `
                    <span class="wisdom-tag ${obs.type}">${obs.type.replace('_', ' ')}</span>
                    <div class="wisdom-body">
                        <div class="wisdom-msg">${escapeHtml(obs.message)}</div>
                        ${obs.suggestion ? `<div class="wisdom-sug">${escapeHtml(obs.suggestion)}</div>` : ''}
                    </div>`;
                panel.appendChild(item);
            });
        }

        // --- Project Chat ---
        // Consultar: always available when there's a project (read-only)
        // Modificar / Refundar: only when pipeline is idle (would conflict with ongoing run)
        function _lockMutating() {
            document.getElementById('chat-btn').disabled = true;
            document.getElementById('refound-btn').disabled = true;
        }
        function _unlockMutating() {
            document.getElementById('chat-btn').disabled = false;
            document.getElementById('refound-btn').disabled = false;
        }
        function _lockChat(label) {
            document.getElementById('chat-input').disabled = true;
            document.getElementById('ask-btn').disabled = true;
            if (label) document.getElementById('ask-btn').textContent = label;
        }
        function _unlockChat() {
            document.getElementById('chat-input').disabled = false;
            document.getElementById('ask-btn').disabled = false;
            document.getElementById('ask-btn').textContent = 'Consultar';
        }

        async function sendQuestion() {
            if (!currentProjectId) return;
            const input = document.getElementById('chat-input');
            const question = input.value.trim();
            if (!question) { input.focus(); return; }

            _lockChat('Consultando…');
            log(`› ${question}`, 'CHAT_Q');

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({project_id: currentProjectId, message: question}),
                });
                const data = await res.json();
                if (!res.ok) {
                    log(data.message || 'Error al consultar', 'FAILED');
                } else {
                    input.value = '';
                    log(data.answer, 'CHAT_A');
                }
            } catch(e) {
                log('No se pudo conectar con el servidor', 'FAILED');
            } finally {
                _unlockChat();
                input.focus();
            }
        }

        async function sendModification() {
            if (!currentProjectId) return;
            const input = document.getElementById('chat-input');
            const request = input.value.trim();
            if (!request) { input.focus(); return; }

            _lockChat('Consultando…');
            document.getElementById('chat-btn').textContent = 'Analizando…';

            try {
                const res = await fetch('/api/modify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({project_id: currentProjectId, request}),
                });
                const data = await res.json();
                if (!res.ok) {
                    log(data.message || 'Error al modificar', 'FAILED');
                } else {
                    input.value = '';
                }
            } catch(e) {
                log('No se pudo conectar con el servidor', 'FAILED');
            } finally {
                _unlockChat();
                document.getElementById('chat-btn').textContent = 'Modificar';
                input.focus();
            }
        }

        // --- Telegram pairing ---
        async function pairTelegram() {
            try {
                const status = await fetch('/api/telegram/status').then(r => r.json());
                if (status.configured) {
                    alert(`Telegram ya está vinculado (chat_id: ${status.chat_id}).\nPara re-vincular, borrá soda_config.json.`);
                    return;
                }
                if (!status.has_token) {
                    alert('No hay TELEGRAM_BOT_TOKEN en .env.\nAgregalo en ⚙ Configuración y reiniciá SODA.');
                    return;
                }
                const res = await fetch('/api/telegram/pair').then(r => r.json());
                alert(`Código de vinculación: ${res.code}\n\nEnviá /pair ${res.code} a tu bot de Telegram.`);
                document.getElementById('tg-btn').style.color = '#cca700';
            } catch(e) {
                alert('No se pudo generar el código de vinculación.');
            }
        }

        // Check Telegram status on load
        fetch('/api/telegram/status').then(r => r.json()).then(s => {
            const btn = document.getElementById('tg-btn');
            if (s.configured) { btn.style.color = '#4ec9b0'; btn.title = 'Telegram vinculado'; }
            else if (!s.has_token) { btn.style.opacity = '0.3'; btn.title = 'Sin TELEGRAM_BOT_TOKEN'; }
        }).catch(() => {});

        async function sendRefound() {
            if (!currentProjectId) return;
            if (!confirm('¿Refundar este proyecto? SODA resumirá el estado actual y lanzará un nuevo pipeline con contexto condensado.')) return;
            document.getElementById('refound-btn').disabled = true;
            document.getElementById('chat-btn').disabled = true;
            try {
                const res = await fetch('/api/refound', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({project_id: currentProjectId}),
                });
                if (!res.ok) {
                    const err = await res.json();
                    log(err.message || 'Refoundation failed', 'FAILED');
                    document.getElementById('refound-btn').disabled = false;
                    document.getElementById('chat-btn').disabled = false;
                }
            } catch(e) {
                log('Could not reach server', 'FAILED');
                document.getElementById('refound-btn').disabled = false;
                document.getElementById('chat-btn').disabled = false;
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.addEventListener('keydown', e => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendQuestion();
                });
            }
        });

        // --- Project name validation ---
        const NAME_RE = /^[a-zA-Z0-9_\-]{1,60}$/;

        function sanitizeName(raw) {
            // replace spaces and dots with underscore, strip the rest
            return raw.replace(/[\s\.]+/g, '_').replace(/[^a-zA-Z0-9_\-]/g, '');
        }

        document.getElementById('project-name-input').addEventListener('input', function() {
            const clean = sanitizeName(this.value);
            if (clean !== this.value) this.value = clean;
            this.classList.toggle('name-error', clean.length > 0 && !NAME_RE.test(clean));
        });

        // --- Run ---
        async function startRun() {
            const input = document.getElementById('description-input');
            const nameInput = document.getElementById('project-name-input');
            const btn = document.getElementById('run-btn');
            const description = input.value.trim();
            const projectName = nameInput.value.trim();

            if (!projectName) {
                nameInput.classList.add('name-error');
                nameInput.focus();
                return;
            }
            if (!NAME_RE.test(projectName)) {
                nameInput.classList.add('name-error');
                nameInput.focus();
                return;
            }
            if (!description) { input.focus(); return; }
            if (document.getElementById('question-box').classList.contains('visible')) {
                log('Hay una pregunta pendiente — respondé primero antes de iniciar un nuevo proyecto.', 'HEALTH_WARN');
                document.getElementById('answer-input').focus();
                return;
            }

            input.disabled = true;
            nameInput.disabled = true;
            btn.disabled = true;
            btn.textContent = 'Running…';
            document.getElementById('launch-panel').classList.remove('visible');

            try {
                const res = await fetch('/api/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({description, project_name: projectName, copilot_temperature: document.getElementById('copilot-temp-select').value}),
                });
                if (!res.ok) {
                    const err = await res.json();
                    log(err.message || 'No se pudo iniciar el pipeline', 'FAILED');
                    unlockInput();
                }
            } catch(e) {
                log('No se pudo conectar con el servidor', 'FAILED');
                unlockInput();
            }
        }

        function unlockInput() {
            const input = document.getElementById('description-input');
            const nameInput = document.getElementById('project-name-input');
            const btn = document.getElementById('run-btn');
            input.disabled = false;
            nameInput.disabled = false;
            btn.disabled = false;
            btn.textContent = 'Ejecutar';
            // Also reset import-from-code button if it was the trigger
            const importBtn = document.getElementById('import-go-btn');
            if (importBtn) { importBtn.disabled = false; importBtn.textContent = '🚀 Crear proyecto desde este código'; }
        }

        document.getElementById('description-input').addEventListener('keydown', e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) startRun();
        });

        // --- Launch panel ---
        let _launchProjectId = null;
        let _launchCommand = null;
        let _installCommand = null;

        function showLaunchPanel(projectId, runCommand, workspace, installCommand) {
            _launchProjectId = projectId;
            _launchCommand = runCommand;
            _installCommand = installCommand || '';
            const cmdEl = document.getElementById('launch-cmd');
            cmdEl.readOnly = false;
            cmdEl.value = runCommand;
            cmdEl.placeholder = runCommand ? '' : 'Ej: python app.py  /  uvicorn main:app  /  dotnet run';
            cmdEl.oninput = () => { _launchCommand = cmdEl.value.trim(); };
            const pathEl = document.getElementById('launch-path');
            const parts = [];
            if (runCommand) parts.push('Ejecutar: ' + runCommand);
            if (workspace) parts.push('Carpeta: ' + workspace);
            pathEl.textContent = parts.join('   |   ');
            document.getElementById('launch-panel').classList.add('visible');
        }

        async function launchProject() {
            _launchCommand = (document.getElementById('launch-cmd').value || '').trim();
            if (!_launchProjectId || !_launchCommand) {
                document.getElementById('launch-cmd').focus();
                return;
            }
            const btn = document.getElementById('launch-btn');
            btn.disabled = true;
            btn.textContent = 'Abriendo terminal…';
            try {
                const res = await fetch('/api/launch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        project_id: _launchProjectId,
                        run_command: _launchCommand,
                        install_command: _installCommand,
                    }),
                });
                const d = await res.json();
                if (d.status === 'launched') {
                    log(`Proceso iniciado → ${d.command || _launchCommand}`, 'DONE');
                    if (d.url) loadTestUI(d.url);
                } else {
                    log(`No se pudo ejecutar: ${d.message}`, 'FAILED');
                }
            } catch(e) {
                log('Error al conectar con el servidor para ejecutar', 'FAILED');
            }
            btn.disabled = false;
            btn.textContent = '▶ Instalar y Ejecutar';
        }

        // --- Test UI tab ---
        // ── Screenshot polling (for non-web desktop apps) ──────────────────
        let _screenshotInterval = null;
        let _screenshotProjectId = null;

        function _startScreenshotPolling(projectId) {
            _stopScreenshotPolling();
            _screenshotProjectId = projectId;
            const img = document.getElementById('testui-screenshot');
            if (!img) return;
            const _refresh = () => {
                img.src = `/api/projects/${encodeURIComponent(projectId)}/screenshot?t=${Date.now()}`;
            };
            _refresh();
            _screenshotInterval = setInterval(_refresh, 2000);
        }

        function _stopScreenshotPolling() {
            if (_screenshotInterval) { clearInterval(_screenshotInterval); _screenshotInterval = null; }
            const img = document.getElementById('testui-screenshot');
            if (img) img.style.display = 'none';
        }

        function _switchToTestUITab() {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('.tab[data-tab="testui"]').classList.add('active');
            document.getElementById('testui-tab').classList.add('active');
        }

        function loadTestUI(url) {
            _stopScreenshotPolling();
            document.getElementById('testui-url').value = url;
            const frame = document.getElementById('testui-frame');
            const empty = document.getElementById('testui-empty');
            const blocked = document.getElementById('testui-blocked');
            frame.style.display = 'none';
            blocked.style.display = 'none';
            empty.style.display = 'none';
            frame.onload = null;
            frame.onload = function() {
                try {
                    void frame.contentWindow.location.href;
                    frame.style.display = 'block';
                    blocked.style.display = 'none';
                } catch(e) {
                    frame.style.display = 'none';
                    blocked.style.display = 'flex';
                }
            };
            frame.src = url;
            _switchToTestUITab();
        }

        function loadTestUIScreenshot(projectId) {
            const frame = document.getElementById('testui-frame');
            const empty = document.getElementById('testui-empty');
            const blocked = document.getElementById('testui-blocked');
            const screenshot = document.getElementById('testui-screenshot');
            frame.style.display = 'none';
            blocked.style.display = 'none';
            empty.style.display = 'none';
            if (screenshot) screenshot.style.display = 'block';
            document.getElementById('testui-url').value = '[ captura de pantalla ]';
            _startScreenshotPolling(projectId);
            _switchToTestUITab();
        }

        function testUINavigate(url) {
            if (!url) return;
            if (!/^https?:\/\//i.test(url)) url = 'http://' + url;
            loadTestUI(url);
        }

        function testUIReload() {
            const frame = document.getElementById('testui-frame');
            if (frame.src && frame.src !== 'about:blank') {
                frame.src = frame.src;
            }
        }

        function testUIBack() {
            try { document.getElementById('testui-frame').contentWindow.history.back(); } catch(e) {}
        }

        function testUIForward() {
            try { document.getElementById('testui-frame').contentWindow.history.forward(); } catch(e) {}
        }

        function testUIOpenExternal() {
            const url = document.getElementById('testui-url').value;
            if (url && url !== 'about:blank') window.open(url, '_blank');
        }

        // --- Cost panel ---
        let _costPanelOpen = false;
        let _costInterval = null;

        function openCostPanel() {
            _costPanelOpen = true;
            document.getElementById('cost-overlay').classList.add('open');
            refreshCostPanel();
            _costInterval = setInterval(refreshCostPanel, 30000);
        }
        function closeCostPanel() {
            _costPanelOpen = false;
            document.getElementById('cost-overlay').classList.remove('open');
            if (_costInterval) { clearInterval(_costInterval); _costInterval = null; }
        }

        async function refreshCostPanel() {
            try {
                const [usageData, alertData] = await Promise.all([
                    fetch('/api/usage/summary').then(r => r.json()),
                    fetch('/api/alerts').then(r => r.json()),
                ]);

                const s = usageData.summary || {};
                const fmtCost = v => v >= 0.01 ? '$' + v.toFixed(3) : v > 0 ? '<$0.01' : '$0.00';
                const fmtNum = v => v >= 1000 ? (v/1000).toFixed(1) + 'k' : String(v || 0);

                document.getElementById('cost-total').textContent = fmtCost(s.cost_usd || 0);
                document.getElementById('cost-calls').textContent = fmtNum(s.total_calls || 0);
                document.getElementById('cost-tokens-in').textContent = fmtNum(s.tokens_input || 0);
                document.getElementById('cost-tokens-out').textContent = fmtNum(s.tokens_output || 0);

                const rows = (usageData.by_provider_model || []);
                const tbody = document.getElementById('cost-rows');
                tbody.innerHTML = rows.length === 0
                    ? '<tr><td colspan="5" style="color:#444;text-align:center;padding:8px">Sin datos aún</td></tr>'
                    : rows.map(r => {
                        const errStyle = r.error_calls > 0 ? 'color:#f44747' : '';
                        return `<tr>
                            <td style="color:#ccc">${r.provider}/${r.model}</td>
                            <td>${r.total_calls}</td>
                            <td>${fmtNum((r.tokens_input||0)+(r.tokens_output||0))}</td>
                            <td style="color:#4ec9b0">${fmtCost(r.cost_usd||0)}</td>
                            <td style="${errStyle}">${r.error_calls||0}</td>
                        </tr>`;
                    }).join('');

                const alerts = alertData.items || [];
                const awrap = document.getElementById('cost-alerts-wrap');
                awrap.innerHTML = alerts.length === 0 ? '' : alerts.map(a =>
                    `<div class="cost-alert ${a.level}">${a.message}</div>`
                ).join('');

                document.getElementById('cost-refresh-time').textContent =
                    'Actualizado: ' + new Date().toLocaleTimeString();
            } catch(e) {
                document.getElementById('cost-rows').innerHTML =
                    '<tr><td colspan="5" style="color:#555;text-align:center">Error al cargar datos</td></tr>';
            }
        }

        // --- Hardware polling ---
        async function updateStats() {
            try {
                const data = await fetch('/api/stats').then(r => r.json());
                const vPct = data.vram.total > 0 ? (data.vram.total - data.vram.free) / data.vram.total * 100 : 0;
                document.getElementById('vram-bar').style.width = vPct + '%';
                document.getElementById('vram-text').textContent = Math.round(vPct) + '%';

                document.getElementById('cpu-bar').style.width = data.system.cpu_usage + '%';
                document.getElementById('cpu-text').textContent = Math.round(data.system.cpu_usage) + '%';

                if (!ramTotal) {
                    const t = await fetch('/api/ram_total').then(r => r.json()).catch(() => null);
                    ramTotal = t?.ram_total_gb || 64;
                }
                const rPct = Math.max(0, 100 - data.system.ram_free_gb / ramTotal * 100);
                document.getElementById('ram-bar').style.width = rPct + '%';
                document.getElementById('ram-text').textContent = Math.round(rPct) + '%';

                if (data.recommendation) {
                    const [model, mode] = data.recommendation;
                    document.getElementById('model-badge').textContent = `${model} [${mode}]`;
                }
            } catch(e) {}
        }
        updateStats();
        setInterval(updateStats, 2000);

        // --- Phase tracker ---
        function setPhase(phase, allDone = false) {
            phases.forEach(p => {
                const el = document.getElementById('ph-' + p);
                if (!el) return;
                el.className = 'phase-step';
                if (allDone) { el.classList.add('done'); return; }
                if (p === phase) el.classList.add('active');
                else if (phases.indexOf(p) < phases.indexOf(phase)) el.classList.add('done');
            });
        }

        function setStatus(state) {
            const dot = document.getElementById('status-dot');
            dot.className = state;
        }

        // --- Console ---
        function log(message, type = 'LOG', data = {}) {
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            const ts = new Date().toTimeString().slice(0, 8);
            let badge = '';
            if ((type === 'AI_WORKING' || type === 'AI_ERROR') && data.ai) {
                badge = `<span class="ai-badge ${escapeHtml(data.ai)}">${escapeHtml(data.ai)}</span>`;
            }
            entry.innerHTML = `<span class="log-time">${ts}</span><span class="log-msg">${badge}${escapeHtml(message)}</span>`;
            const el = document.getElementById('console');
            el.appendChild(entry);
            // Keep DOM lean — drop oldest entries beyond limit
            while (el.childElementCount > 400) el.removeChild(el.firstChild);
            el.scrollTop = el.scrollHeight;
        }

        function escapeHtml(s) {
            return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }

        // --- WebSocket ---
        function connectWS() {
            const ws = new WebSocket(`ws://${window.location.host}/ws`);

            // Event types that are handled visually — no plain log line needed
            const _SILENT_LOG = new Set(['AI_WORKING','AI_ERROR','FILE_GENERATED','MODULE_START',
                'MODULE_DONE','WISDOM','ENV_CHECK','COPILOT_SUGGESTION',
                'COPILOT_APPLIED','COPILOT_REJECTED','USER_QUESTION','QUESTION_ANSWERED','OPEN_FILE']);

            ws.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    const type = payload.event_type || 'LOG';
                    const msg  = payload.message || '';
                    const data = payload.data || {};

                    // console.log("WS Event:", type, payload); // Debug

                    // Default log — only for types without a dedicated visual handler
                    if (!_SILENT_LOG.has(type)) log(msg, type, data);

                    switch (type) {
                        case 'START':
                            setStatus('running');
                            currentProjectId = data.project_id || null;
                            recursosInit();
                            document.getElementById('file-list').innerHTML = '';
                            document.getElementById('tree-wrap').innerHTML = '';
                            const treeSection = document.getElementById('tree-section');
                            if (treeSection) treeSection.classList.add('hidden');
                            const wisdomPanel = document.getElementById('wisdom-panel');
                            if (wisdomPanel) {
                                wisdomPanel.innerHTML = '';
                                wisdomPanel.classList.add('hidden');
                            }
                            _lockMutating();
                            hideQuestion();
                            files = {};
                            phases.forEach(p => { const el = document.getElementById('ph-' + p); if(el) el.className = 'phase-step'; });
                            resetProgress();
                            startTimer();
                            log(`Pipeline iniciado${data.project_name ? ' — ' + data.project_name : ''}`, 'START');
                            break;

                        case 'ENV_CHECK': {
                            const icon = data.available ? '✓' : '✗';
                            const cls  = data.available ? 'DONE' : 'HEALTH_WARN';
                            const ver  = data.available && data.version ? ` (${data.version})` : '';
                            log(`${icon} ${data.required_for}${ver}`, cls);
                            break;
                        }

                        case 'USER_QUESTION':
                            showQuestion(data.question || msg);
                            if (window._sodaTTS && (data.question || msg)) {
                                window._sodaTTS.speak(data.question || msg);
                            }
                            log(`[?] ${data.question || msg}`, 'CHECKPOINT');
                            break;

                        case 'QUESTION_ANSWERED':
                            hideQuestion();
                            break;

                        case 'PHASE_START': {
                            const phase = data.phase;
                            if (phase && phase !== 'wisdom' && phase !== 'modification') setPhase(phase);
                            if (PHASE_PCT[phase]) startPhaseProgress(phase);
                            log(msg || `Fase: ${phase}`, 'PHASE_START');
                            break;
                        }

                    case 'CAPABILITIES':
                        if (data.profile) {
                            const skills = (data.skills || []).join(', ') || 'ninguno';
                            log(`Perfil: ${data.profile} | Skills: ${skills}`, 'CAPABILITIES');
                            setProgress(PHASE_PCT.capabilities[1], `Perfil: ${data.profile}`);
                        }
                        break;

                    case 'WISDOM': {
                        const wisdomBuf = window._wisdomBuf = window._wisdomBuf || [];
                        if (data.type !== 'ok') {
                            wisdomBuf.push(data);
                            renderWisdom(wisdomBuf);
                            if (msg) log(msg, 'WISDOM');
                        }
                        break;
                    }

                    case 'CHECKPOINT':
                        if (data.number === 1) {
                            setProgress(PHASE_PCT.requirements[1], 'Blueprint listo');
                            if (data.project_name) {
                                document.getElementById('project-name').textContent = data.project_name;
                                document.getElementById('project-name').title = data.project_name;
                            }
                        }
                        if (data.number === 2) setProgress(PHASE_PCT.architecture[1], 'Arquitectura lista');
                        if (data.number === 3) {
                            _totalModules = data.total_modules || (data.levels || []).reduce((s, l) => s + l.length, 0);
                            _totalFiles   = data.total_files || 0;
                            _doneFiles    = 0;
                            _doneModules  = 0;
                            const mStr = `${_totalModules} módulo${_totalModules !== 1 ? 's' : ''}`;
                            const fStr = _totalFiles > 0 ? `, ${_totalFiles} archivo${_totalFiles !== 1 ? 's' : ''}` : '';
                            setProgress(PHASE_PCT.planning[1], `Plan listo — ${mStr}${fStr}`);
                            if (data.levels) { buildTree(data.levels); _dagRender(data.levels); }
                        }
                        if (data.phase === 'validation' && data.success) {
                            const rounds = data.rounds || 1;
                            setProgress(PHASE_PCT.validation[1], `Código validado — ${rounds} ronda${rounds !== 1 ? 's' : ''}`);
                        }
                        break;

                    case 'MODULE_START':
                        if (data.module) { setModuleState(data.module, 'running'); _dagSetStatus(data.module, 'generating'); log(msg, 'MODULE_START'); }
                        break;

                    case 'MODULE_DONE':
                        if (data.module) { setModuleState(data.module, 'done'); _dagSetStatus(data.module, 'done'); log(msg, 'MODULE_DONE'); }
                        break;

                    case 'FILE_GENERATED': {
                        const { filename, code, validated } = data;
                        if (!filename || code === undefined) break;
                        advanceDevProgress(filename);
                        files[filename] = code;
                        const item = document.createElement('div');
                        item.className = 'file-item';
                        item.dataset.file = filename;
                        item.innerHTML = `<span class="file-icon">${iconFromFilename(filename)}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(filename)}</span><span class="file-validated ${validated?'ok':'fail'}">${validated?'OK':'ERR'}</span>`;
                        item.onclick = () => openFile(filename);
                        document.getElementById('file-list').appendChild(item);
                        openFile(filename);
                        log(`${validated ? '✓' : '✗'} ${filename}`, validated ? 'MODULE_DONE' : 'HEALTH_WARN');
                        break;
                    }

                    case 'OPEN_FILE': {
                        const { filename: ofName, code: ofCode } = data;
                        if (ofName && ofCode !== undefined) {
                            files[ofName] = ofCode;
                            // Add to file list if not already present
                            if (!document.querySelector(`.file-item[data-file="${CSS.escape(ofName)}"]`)) {
                                const item = document.createElement('div');
                                item.className = 'file-item';
                                item.dataset.file = ofName;
                                item.innerHTML = `<span class="file-icon">${iconFromFilename(ofName)}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(ofName)}</span>`;
                                item.onclick = () => openFile(ofName);
                                document.getElementById('file-list').appendChild(item);
                            }
                            openFile(ofName);
                            log(`Abriendo en editor: ${ofName}`, 'MODULE_DONE');
                        }
                        break;
                    }

                    case 'MODIFICATION_PLAN':
                        log(`[${data.change_type?.toUpperCase()}] ${data.impact_summary || data.description}`, 'MODIFICATION_PLAN');
                        break;

                    case 'IMPACT_REPORT': {
                        const affected = [...(data.directly_affected||[]), ...(data.transitively_affected||[])];
                        log(`Impact [${data.risk_level}] — affects: ${affected.join(', ') || 'none'}. ${data.risk_reason}`, 'IMPACT_REPORT');
                        affected.forEach(m => setModuleState(m, 'running'));
                        break;
                    }

                    case 'HEALTH_WARN':
                        if (data.module) _dagSetStatus(data.module, 'error');
                        log(msg || data.reason || data.message || JSON.stringify(data), 'HEALTH_WARN');
                        break;

                    case 'EVOLUTION':
                        log(`Profile '${data.profile}' updated — ${data.count} learnings captured`, 'EVOLUTION');
                        break;

                    case 'BRANCH_CREATED':
                        log(`Branch created: ${data.branch_name} (${data.branch_id})`, 'BRANCH_CREATED');
                        break;

                    case 'COPILOT_SUGGESTION':
                        showCopilotSuggestion(data.phase || '', data.message || msg, data.proposed_change || '');
                        log(`[Copilot/${data.phase || '?'}] ${data.message || msg}`, 'COPILOT_SUGGESTION');
                        break;

                    case 'COPILOT_APPLIED':
                        hideCopilotSuggestion();
                        log(`[Claude/eval] Copilot aceptado (${data.phase || '?'}) — ${data.reason || ''}`, 'COPILOT_APPLIED');
                        break;

                    case 'COPILOT_REJECTED':
                        hideCopilotSuggestion();
                        log(`[Claude/eval] Copilot descartado (${data.phase || '?'}) — ${data.reason || ''}`, 'COPILOT_REJECTED');
                        break;

                    case 'REFOUNDATION':
                        log(`Refoundation desde proyecto ${data.parent_id}`, 'REFOUNDATION');
                        break;

                    case 'AI_WORKING':
                        setAiActivity(data.ai, msg, data.file || '');
                        setAiPillWorking(data.ai);
                        log(msg, 'AI_WORKING', data);
                        break;

                    case 'AI_ERROR':
                        setAiPillError(data.ai);
                        setAiActivity(null);
                        setStatus('running');
                        log(msg, 'AI_ERROR', data);
                        break;

                    case 'DONE':
                        setPhase(null, true);
                        setStatus('done');
                        stopTimer();
                        setProgress(100, '¡Aplicación lista!', 'done');
                        _tickTimer();
                        unlockInput();
                        _unlockMutating();
                        setAiActivity(null);
                        clearAiWorking();
                        window._wisdomBuf = [];
                        hideQuestion();
                        if (data.project_id) loadGoalTree(data.project_id);
                        if (window._sodaTTS) window._sodaTTS.speak(
                            'La generación del proyecto ha finalizado. Iniciando la aplicación.'
                        );
                        log('Pipeline completo — iniciando aplicación...', 'DONE');
                        // Switch graph to file-level view after generation
                        setTimeout(() => cySetMode('files'), 1500);
                        break;

                    case 'APP_OUTPUT':
                        (function() {
                            const line = payload.message || '';
                            const cls = 'console-app-line' +
                                (line.startsWith('[PROCESO]') || line.startsWith('[ERROR]') ? ' app-info' : '');
                            function _appendLine(id) {
                                const c = document.getElementById(id);
                                if (!c) return;
                                const div = document.createElement('div');
                                div.className = cls;
                                div.textContent = line;
                                c.appendChild(div);
                                c.scrollTop = c.scrollHeight;
                            }
                            _appendLine('console');
                            _appendLine('testui-console');
                        })();
                        break;

                    case 'APP_RUNNING':
                        log(payload.message || 'Aplicación corriendo', 'DONE');
                        (function() {
                            const msg = payload.message || '';
                            function _appendUrl(id) {
                                const c = document.getElementById(id);
                                if (!c) return;
                                const div = document.createElement('div');
                                div.className = 'console-app-line app-url';
                                div.textContent = msg;
                                c.appendChild(div);
                                c.scrollTop = c.scrollHeight;
                            }
                            _appendUrl('console');
                            _appendUrl('testui-console');
                        })();
                        if (data.url && data.mode !== 'screenshot') {
                            loadTestUI(data.url);
                        } else if (data.mode === 'screenshot') {
                            loadTestUIScreenshot(data.project_id || currentProjectId);
                        }
                        if (window._sodaTTS) window._sodaTTS.speak('La aplicación está corriendo.');
                        break;

                    case 'APP_EXITED':
                        _stopScreenshotPolling();
                        (function() {
                            const msg = payload.message || 'Proceso terminado';
                            function _appendExit(id) {
                                const c = document.getElementById(id);
                                if (!c) return;
                                const div = document.createElement('div');
                                div.className = 'console-app-line app-exit';
                                div.textContent = msg;
                                c.appendChild(div);
                                c.scrollTop = c.scrollHeight;
                            }
                            _appendExit('console');
                            _appendExit('testui-console');
                        })();
                        break;

                    case 'ITERATION_DONE':
                        setAiActivity(null);
                        clearAiWorking();
                        hideQuestion();
                        showLaunchPanel(data.project_id, data.run_command || '', data.workspace, data.install_command);
                        if (window._sodaTTS) window._sodaTTS.speak(
                            data.iteration
                                ? `La iteración número ${data.iteration} ha finalizado. Puede ejecutar la aplicación para verificar los cambios.`
                                : 'La iteración ha finalizado. Puede ejecutar la aplicación para verificar los cambios.'
                        );
                        log(`Iteración ${data.iteration || ''} completa — ejecutá la app para ver los cambios.`, 'DONE');
                        break;

                    case 'FAILED':
                        setStatus('failed');
                        setProgress(
                            parseFloat(document.getElementById('progress-fill').style.width) || 0,
                            'Fallido', 'failed'
                        );
                        stopTimer();
                        unlockInput();
                        _unlockMutating();
                        setAiActivity(null);
                        clearAiWorking();
                        if (window._sodaTTS) window._sodaTTS.speak(
                            'El pipeline de generación ha fallado. Revise la consola para obtener más detalles sobre el error.'
                        );
                        break;
                }
                // Dispatch generic DOM event so inline scripts can hook any WS event
                document.dispatchEvent(new CustomEvent('SODA_WS_EVENT', { detail: payload }));
                } catch (err) {
                    console.error("Error processing WS message:", err);
                }
            };

            ws.onopen = () => {
                // Restore any question that was waiting before this connection
                fetch('/api/question').then(r => r.json()).then(d => {
                    if (d.waiting && d.question) showQuestion(d.question);
                }).catch(() => {});
            };

            ws.onclose = () => setTimeout(connectWS, 3000);
            ws.onerror = () => ws.close();
        }

        // --- User question ---
        function showQuestion(text) {
            document.getElementById('question-text').textContent = text;
            const qBox = document.getElementById('question-box');
            if (!qBox.classList.contains('visible')) {
                document.getElementById('answer-input').value = '';
            }
            qBox.classList.add('visible');
            document.getElementById('answer-btn').disabled = false;
            setTimeout(() => document.getElementById('answer-input').focus(), 50);
        }

        function hideQuestion() {
            document.getElementById('question-box').classList.remove('visible');
            document.getElementById('answer-input').value = '';
        }

        async function submitAnswer() {
            const input = document.getElementById('answer-input');
            const btn = document.getElementById('answer-btn');
            const text = input.value.trim();
            if (!text) { input.focus(); return; }

            btn.disabled = true;
            btn.textContent = 'Enviando…';
            try {
                const res = await fetch('/api/answer', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({answer: text, project_id: currentProjectId}),
                });
                if (res.ok) {
                    log(`Tu respuesta: ${text}`, 'LOG');
                    hideQuestion();
                } else {
                    const err = await res.json();
                    log(err.message || 'Error al enviar respuesta', 'FAILED');
                }
            } catch(e) {
                log('No se pudo conectar con el servidor', 'FAILED');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Responder';
            }
        }

        async function skipAnswer() {
            try {
                await fetch('/api/answer', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({answer: ''}),
                });
            } catch(e) {}
            log('Pregunta omitida — el pipeline continúa.', 'LOG');
            hideQuestion();
        }

        // --- Mic / STT ---
        let _mediaRecorder = null;
        let _audioChunks = [];

        async function toggleMic() {
            const btn = document.getElementById('mic-btn');
            if (_mediaRecorder && _mediaRecorder.state === 'recording') {
                _mediaRecorder.stop();
                return;
            }
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                    ? 'audio/webm;codecs=opus'
                    : 'audio/webm';
                _mediaRecorder = new MediaRecorder(stream, { mimeType });
                _audioChunks = [];

                _mediaRecorder.ondataavailable = e => { if (e.data.size > 0) _audioChunks.push(e.data); };

                _mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach(t => t.stop());
                    btn.classList.remove('recording');
                    btn.innerHTML = '<i class="fa fa-microphone"></i>';
                    btn.disabled = true;

                    const blob = new Blob(_audioChunks, { type: mimeType });
                    const form = new FormData();
                    form.append('audio', blob, 'recording.webm');

                    const input = document.getElementById('answer-input');
                    input.placeholder = 'Transcribiendo…';
                    try {
                        const r = await fetch('/api/stt/transcribe', { method: 'POST', body: form });
                        const d = await r.json();
                        if (d.text) {
                            input.value = d.text;
                            input.focus();
                            input.style.height = '68px';
                        } else {
                            input.placeholder = 'No se pudo transcribir. Escribí tu respuesta.';
                        }
                    } catch (e) {
                        input.placeholder = 'Error al transcribir. Escribí tu respuesta.';
                    } finally {
                        input.placeholder = input.placeholder.startsWith('Transcrib') || input.placeholder.startsWith('No se') || input.placeholder.startsWith('Error')
                            ? input.placeholder
                            : 'Escribí tu respuesta… (Ctrl+Enter para enviar)';
                        btn.disabled = false;
                    }
                };

                _mediaRecorder.start();
                btn.classList.add('recording');
                btn.innerHTML = '<i class="fa fa-stop"></i>';
            } catch (e) {
                log('No se pudo acceder al micrófono: ' + e.message, 'HEALTH_WARN');
            }
        }

        // --- Copilot suggestion ---
        function showCopilotSuggestion(phase, message, change) {
            document.getElementById('copilot-phase').textContent = phase ? `[${phase}]` : '';
            document.getElementById('copilot-message').textContent = message;
            document.getElementById('copilot-change').textContent = change;
            document.getElementById('copilot-box').classList.add('visible');
        }

        function hideCopilotSuggestion() {
            document.getElementById('copilot-box').classList.remove('visible');
        }

        // Debounce helper
        function debounce(fn, ms) {
            let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
        }

        document.addEventListener('DOMContentLoaded', () => {
            const answerInput = document.getElementById('answer-input');
            if (answerInput) {
                answerInput.addEventListener('keydown', e => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitAnswer();
                });
                // Reset the server-side timeout while the user is composing a response
                const extendTimeout = debounce(() => {
                    fetch('/api/answer/extend', { method: 'POST' }).catch(() => {});
                }, 500);
                answerInput.addEventListener('input', extendTimeout);
            }
        });

        // --- Progress bar ---
        // Weights: pre-dev 0→20%, dev 20→90% (per file), post 90→100%
        const PHASE_PCT = {
            capabilities:  [1,  4,  'Seleccionando capacidades…'],
            wisdom:        [4,  8,  'Analizando descripción…'],
            requirements:  [8,  13, 'Generando blueprint…'],
            architecture:  [13, 19, 'Diseñando arquitectura…'],
            planning:      [19, 21, 'Construyendo plan de ejecución…'],
            development:   [21, 21, 'Generando código…'],
            validation:    [85, 91, 'Validando y corrigiendo código…'],
            docs:          [91, 94, 'Generando documentación…'],
            evolution:     [94, 99, 'Capturando aprendizajes…'],
        };
        const DEV_START = 21;
        const DEV_END   = 85;

        let _startTime    = null;
        let _timerInterval = null;
        let _totalFiles   = 0;
        let _doneFiles    = 0;
        let _totalModules = 0;
        let _doneModules  = 0;
        let _currentPhase = null;
        let _phaseAnimFrame = null;

        function setProgress(pct, label, state = '') {
            const fill = document.getElementById('progress-fill');
            fill.style.width = Math.min(100, Math.max(0, pct)) + '%';
            if (state) fill.className = state;
            else if (!fill.className) fill.className = '';
            document.getElementById('progress-pct').textContent = Math.round(pct) + '%';
            if (label !== undefined) document.getElementById('progress-label').textContent = label;
        }

        // Animate bar smoothly toward a target within a phase range
        function _animateToPhaseEnd(phase) {
            const entry = PHASE_PCT[phase];
            if (!entry) return;
            const [, end, label] = entry;
            const fill = document.getElementById('progress-fill');
            const current = parseFloat(fill.style.width) || 0;
            if (current >= end) return;
            // Drift toward phase end slowly (never actually reaches it — the next event will push it further)
            const step = (end - current) * 0.015;
            if (step > 0.05) {
                setProgress(current + step, label);
                _phaseAnimFrame = requestAnimationFrame(() => _animateToPhaseEnd(phase));
            }
        }

        function startPhaseProgress(phase) {
            if (_phaseAnimFrame) cancelAnimationFrame(_phaseAnimFrame);
            _currentPhase = phase;
            const entry = PHASE_PCT[phase];
            if (!entry) return;
            const [start, , label] = entry;
            const fill = document.getElementById('progress-fill');
            const current = parseFloat(fill.style.width) || 0;
            if (current < start) setProgress(start, label);
            else document.getElementById('progress-label').textContent = label;
            _animateToPhaseEnd(phase);
        }

        function advanceDevProgress(filename) {
            if (_phaseAnimFrame) cancelAnimationFrame(_phaseAnimFrame);
            _doneFiles++;
            const pct = _totalFiles > 0
                ? DEV_START + (_doneFiles / _totalFiles) * (DEV_END - DEV_START)
                : DEV_START + (_doneFiles * 3);
            setProgress(pct, `Generando… ${_doneFiles}${_totalFiles > 0 ? '/'+_totalFiles : ''} archivos`);
        }

        function startTimer() {
            _startTime = Date.now();
            if (_timerInterval) clearInterval(_timerInterval);
            _timerInterval = setInterval(_tickTimer, 1000);
        }

        function stopTimer() {
            if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }
            if (_phaseAnimFrame) { cancelAnimationFrame(_phaseAnimFrame); _phaseAnimFrame = null; }
        }

        function _tickTimer() {
            if (!_startTime) return;
            const elapsed = Math.floor((Date.now() - _startTime) / 1000);
            const pct = parseFloat(document.getElementById('progress-fill').style.width) || 0;
            let timeStr = _fmt(elapsed);
            if (pct > 2 && pct < 99) {
                const totalEst = elapsed / (pct / 100);
                const rem = Math.max(0, Math.floor(totalEst - elapsed));
                timeStr += ' · ~' + _fmt(rem) + ' restante';
            }
            document.getElementById('progress-time').textContent = timeStr;
        }

        function _fmt(s) {
            if (s < 60) return s + 's';
            return Math.floor(s / 60) + 'm ' + String(s % 60).padStart(2, '0') + 's';
        }

        function resetProgress() {
            stopTimer();
            _totalFiles  = 0;
            _doneFiles   = 0;
            _totalModules = 0;
            _doneModules  = 0;
            _currentPhase = null;
            _startTime    = null;
            const fill = document.getElementById('progress-fill');
            fill.className = '';
            setProgress(0, 'Listo');
            document.getElementById('progress-time').textContent = '';
        }

        // --- Settings ---
        async function openSettings() {
            try {
                const status = await fetch('/api/env').then(r => r.json());
                ['ANTHROPIC_API_KEY','GEMINI_API_KEY','OLLAMA_BASE_URL','TELEGRAM_BOT_TOKEN'].forEach(key => {
                    const dot = document.getElementById('dot-' + key);
                    if (dot) dot.className = status[key] ? 'settings-set' : 'settings-unset';
                    const inp = document.getElementById('input-' + key);
                    if (inp) inp.value = '';
                });
            } catch(e) {}
            document.getElementById('settings-overlay').classList.add('open');
        }

        function closeSettings() {
            document.getElementById('settings-overlay').classList.remove('open');
        }

        async function saveSettings() {
            const keys = ['ANTHROPIC_API_KEY','GEMINI_API_KEY','OLLAMA_BASE_URL','TELEGRAM_BOT_TOKEN'];
            const payload = {};
            keys.forEach(key => {
                const val = (document.getElementById('input-' + key)?.value || '').trim();
                if (val) payload[key] = val;
            });
            if (Object.keys(payload).length === 0) { closeSettings(); return; }
            try {
                const res = await fetch('/api/env', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload),
                });
                if (res.ok) {
                    closeSettings();
                    log('API keys guardadas y aplicadas.', 'LOG');
                } else {
                    log('Error al guardar las keys.', 'FAILED');
                }
            } catch(e) {
                log('No se pudo conectar con el servidor.', 'FAILED');
            }
        }

        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSettings(); });

        // --- Token counter ---
        async function updateTokens() {
            try {
                const data = await fetch('/api/tokens').then(r => r.json());
                const tokens = data.total_tokens_estimate || 0;
                const el = document.getElementById('token-display');
                el.textContent = tokens >= 1000 ? `~${(tokens/1000).toFixed(1)}k tkn` : `${tokens} tkn`;
                el.className = '';
                if (data.health_level >= 2) el.classList.add('warn');
                el.title = `Sesión: ${data.total_calls} llamadas | ${data.error_count} errores | ${data.health_reason}\n(Este contador NO es el saldo de tu cuenta — SODA reintenta automáticamente si hay límite de cuota)`;
            } catch(e) {}
        }
        setInterval(updateTokens, 3000);

        // --- AI Status pills ---
        const _AI_PILL_MAP = { qwen: 'pill-qwen', claude: 'pill-claude', gemini: 'pill-gemini', deepseek: 'pill-deepseek' };
        async function updateAiStatus() {
            try {
                const data = await fetch('/api/ai/status').then(r => r.json());
                for (const [key, obj] of Object.entries(data)) {
                    const el = document.getElementById(_AI_PILL_MAP[key]);
                    if (!el) continue;
                    const ai = el.dataset.ai;
                    const statusStr = obj.ok ? 'ok' : (key === 'qwen' ? 'offline' : 'unconfigured');
                    
                    // Don't overwrite 'working' or 'error' states set by live events
                    if (el.classList.contains('working')) continue;
                    if (el.classList.contains('error') && statusStr === 'ok') {
                        // recovery confirmed by poll
                    } else if (el.classList.contains('error')) continue;
                    
                    el.className = `ai-pill ${statusStr} ${ai}`;
                    const tips = { ok: 'Disponible', unconfigured: 'Sin clave API', offline: 'Offline / No responde', error: 'Error' };
                    el.title = `${ai}: ${tips[statusStr] || statusStr}`;
                    if (key === 'qwen') _setOllamaBtn(statusStr === 'offline' || statusStr === 'error');
                }
            } catch(e) {}
        }
        updateAiStatus();
        setInterval(updateAiStatus, 12000);

        // --- Auto-confirm toggle ---
        let _autoConfirm = false;

        async function toggleAutoConfirm() {
            _autoConfirm = !_autoConfirm;
            _applyAutoConfirmUI();
            try {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ auto_confirm: _autoConfirm }),
                });
            } catch(e) {}
        }

        function _applyAutoConfirmUI() {
            const btn = document.getElementById('auto-confirm-btn');
            if (_autoConfirm) {
                btn.classList.add('active');
                btn.title = 'Auto-sí ACTIVADO — las preguntas se responden automáticamente';
            } else {
                btn.classList.remove('active');
                btn.title = 'Activar respuesta automática a preguntas de instalación y ejecución';
            }
        }

        // Load initial config
        fetch('/api/config').then(r => r.json()).then(cfg => {
            _autoConfirm = !!cfg.auto_confirm;
            _applyAutoConfirmUI();
        }).catch(() => {});

        function setAiPillWorking(ai) {
            document.querySelectorAll('.ai-pill').forEach(p => p.classList.remove('working'));
            const pill = document.querySelector(`.ai-pill[data-ai="${ai}"]`);
            if (pill) {
                if (pill.classList.contains('error') || pill.classList.contains('unconfigured') || pill.classList.contains('offline')) {
                    pill.className = `ai-pill ok ${ai}`;
                }
                pill.classList.add('working');
            }
            if (ai === 'Qwen') _setOllamaBtn(false);
        }

        function setAiPillError(ai) {
            document.querySelectorAll('.ai-pill').forEach(p => p.classList.remove('working'));
            const pill = document.querySelector(`.ai-pill[data-ai="${ai}"]`);
            if (pill) pill.className = `ai-pill error ${ai}`;
            if (ai === 'Qwen') _setOllamaBtn(true);
        }

        function _setOllamaBtn(visible) {
            const btn = document.getElementById('ollama-start-btn');
            if (btn) btn.style.display = visible ? 'inline-block' : 'none';
        }

        async function startOllama() {
            const btn = document.getElementById('ollama-start-btn');
            btn.textContent = '⏳ Iniciando…';
            btn.classList.add('starting');
            btn.disabled = true;
            try {
                const res = await fetch('/api/ollama/start', { method: 'POST' }).then(r => r.json());
                if (res.status === 'started' || res.status === 'already_running') {
                    btn.style.display = 'none';
                    const pill = document.getElementById('pill-qwen');
                    if (pill) pill.className = 'ai-pill ok Qwen';
                    log('Ollama iniciado correctamente.', 'HEALTH_WARN');
                } else {
                    btn.textContent = '▶ Iniciar';
                    btn.classList.remove('starting');
                    btn.disabled = false;
                    log(`Ollama: ${res.message || res.status}`, 'HEALTH_WARN');
                }
            } catch(e) {
                btn.textContent = '▶ Iniciar';
                btn.classList.remove('starting');
                btn.disabled = false;
            }
        }

        function clearAiWorking() {
            document.querySelectorAll('.ai-pill.working').forEach(p => p.classList.remove('working'));
        }

        // --- AI Activity bar ---
        function setAiActivity(ai, message, file) {
            const bar = document.getElementById('ai-activity-bar');
            const txt = document.getElementById('ai-activity-text');
            if (!ai) { bar.classList.remove('visible'); return; }
            const fileName = (file || '').split(/[\\/]/).pop();
            const filePart = fileName ? ` → <span class="af">${escapeHtml(fileName)}</span>` : '';
            txt.innerHTML = `<span class="ai-badge ${escapeHtml(ai)}">${escapeHtml(ai)}</span> ${escapeHtml(message)}${filePart}`;
            bar.classList.add('visible');
        }

        connectWS();

        // Load last project on startup
        fetch('/api/lineage').then(r => r.json()).then(data => {
            const history = data.history || [];
            const last = history.filter(p => p.state === 'done').pop();
            if (last) {
                currentProjectId = last.project_id;
                const name = last.description ? last.description.slice(0, 40) : last.project_id;
                document.getElementById('project-name').textContent = name;
                document.getElementById('project-name').title = `${last.project_id} — ${last.description || ''}`;
                loadProjectFiles(last.project_id);
                loadGoalTree(last.project_id);
                recursosInit();
                _cyRenderModules([], last.project_id); // pre-load module graph
            }
        }).catch(() => {});

        function loadProjectFiles(projectId) {
            fetch(`/api/projects/${encodeURIComponent(projectId)}/files`)
                .then(r => r.json())
                .then(data => {
                    const fileList = document.getElementById('file-list');
                    fileList.innerHTML = '';
                    files = {};
                    Object.entries(data.files || {}).forEach(([filename, code]) => {
                        files[filename] = code;
                        const item = document.createElement('div');
                        item.className = 'file-item';
                        item.dataset.file = filename;
                        item.innerHTML = `<span class="file-icon">${iconFromFilename(filename)}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(filename)}</span>`;
                        item.onclick = () => openFile(filename);
                        fileList.appendChild(item);
                    });
                    const firstFile = Object.keys(data.files || {})[0];
                    if (firstFile) {
                        // Wait for Monaco to be ready before opening
                        const tryOpen = () => editor ? openFile(firstFile) : setTimeout(tryOpen, 200);
                        tryOpen();
                    }
                }).catch(() => {});
        }

        // Load initial env status dots (for settings panel)
        fetch('/api/env').then(r => r.json()).then(status => {
            ['ANTHROPIC_API_KEY','GEMINI_API_KEY','OLLAMA_BASE_URL','TELEGRAM_BOT_TOKEN'].forEach(key => {
                const dot = document.getElementById('dot-' + key);
                if (dot) dot.className = status[key] ? 'settings-set' : 'settings-unset';
            });
        }).catch(() => {});
        updateTokens();
        _cyInit(); // pre-init Cytoscape container

        // Restore locked state if server already running when UI opens
        fetch('/api/status').then(r => r.json()).then(d => {
            if (d.running) {
                document.getElementById('description-input').disabled = true;
                document.getElementById('run-btn').disabled = true;
                document.getElementById('run-btn').textContent = 'Running…';
            }
        }).catch(() => {});

        // --- Top-level tab switching ---
        function switchTopTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => {
                c.classList.remove('active');
                c.style.display = 'none';
            });
            
            const btn = document.querySelector(`.tab[data-tab="${tabName}"]`);
            let content = document.getElementById(tabName + '-tab');
            if (!content) content = document.getElementById(tabName);
            
            if (btn) btn.classList.add('active');
            if (content) {
                content.classList.add('active');
                content.style.display = (tabName === 'main' || tabName === 'testui') ? 'flex' : 'block';
            }
            
            if (tabName === 'status') loadStatusTab();
            if (tabName === 'config') loadConfigTab();
            if (tabName === 'open') initOpenTab();
            if (tabName === 'codigo') initCodigoTab();
        }
        window.switchTopTab = switchTopTab;

        // ── Import from Code ─────────────────────────────────────────────────
        let importEditor = null;
        let _lastAnalysis = null;
        const NAME_RE_IMPORT = /^[a-zA-Z0-9_\-]{1,60}$/;

        function initImportEditor() {
            if (importEditor) { importEditor.layout(); return; }
            const container = document.getElementById('import-editor-container');
            if (!container || !window.monaco) {
                // Monaco not ready yet — retry once
                setTimeout(initImportEditor, 300);
                return;
            }
            importEditor = monaco.editor.create(container, {
                value: '// Pegá tu código aquí...\n',
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                readOnly: false,
                minimap: { enabled: false },
                fontSize: 12,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
            });
            // Auto-detect language when filename changes
            document.getElementById('import-filename').addEventListener('input', function () {
                const lang = langFromFilename(this.value || 'main.py');
                if (importEditor) {
                    const model = importEditor.getModel();
                    if (model) monaco.editor.setModelLanguage(model, lang);
                }
            });
        }

        async function analyzeImportedCode() {
            const code = importEditor ? importEditor.getValue().trim() : '';
            const filename = (document.getElementById('import-filename').value || 'main.py').trim();
            if (!code || code === '// Pegá tu código aquí...') {
                alert('Primero pegá tu código en el editor.');
                return;
            }
            const btn = document.getElementById('import-analyze-btn');
            const loading = document.getElementById('import-loading');
            const panel = document.getElementById('import-analysis-panel');
            btn.disabled = true;
            loading.style.display = 'flex';
            panel.classList.remove('visible');
            document.getElementById('import-intent-section').style.display = 'none';
            document.getElementById('import-error').textContent = '';

            try {
                const res = await fetch('/api/analyze_code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code, filename }),
                });
                const data = await res.json();
                if (!res.ok || data.status === 'error') {
                    document.getElementById('import-error').textContent = data.message || 'Error al analizar el código';
                    return;
                }
                _lastAnalysis = data.analysis;
                _renderAnalysis(data.analysis);
            } catch (e) {
                document.getElementById('import-error').textContent = 'No se pudo conectar con el servidor';
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        }

        function _renderAnalysis(a) {
            // Language badge
            document.getElementById('import-lang-badge').textContent = a.language || '?';
            // Framework badges
            const fws = (a.frameworks || []).slice(0, 6);
            document.getElementById('import-frameworks').innerHTML = fws
                .map(f => `<span class="import-fw-badge">${f}</span>`).join(' ');
            // Summary
            document.getElementById('import-summary').textContent = a.summary || '';
            // Suggestions
            const sugList = document.getElementById('import-suggestions-list');
            sugList.innerHTML = (a.suggestions || []).map(s =>
                `<div class="import-sug-item" onclick="document.getElementById('import-intent').value='${s.replace(/'/g,"\\'")}'">${s}</div>`
            ).join('');
            // Show panel + intent section
            document.getElementById('import-analysis-panel').classList.add('visible');
            document.getElementById('import-intent-section').style.display = 'flex';
            // Pre-fill project name from filename
            const base = (document.getElementById('import-filename').value || 'proyecto').replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_\-]/g, '_');
            if (!document.getElementById('import-project-name').value)
                document.getElementById('import-project-name').value = base;
        }

        async function startFromCode() {
            const code = importEditor ? importEditor.getValue().trim() : '';
            const filename = (document.getElementById('import-filename').value || 'main.py').trim();
            const intent = (document.getElementById('import-intent').value || '').trim();
            const projectName = (document.getElementById('import-project-name').value || '').trim();
            const temperature = document.getElementById('import-temperature').value;
            const errEl = document.getElementById('import-error');
            errEl.textContent = '';

            if (!intent)       { errEl.textContent = 'Describí qué querés hacer con el código.'; return; }
            if (!projectName)  { errEl.textContent = 'El nombre del proyecto es obligatorio.'; return; }
            if (!NAME_RE_IMPORT.test(projectName)) { errEl.textContent = 'Nombre inválido: solo letras, números, guiones y guiones bajos.'; return; }

            const btn = document.getElementById('import-go-btn');
            btn.disabled = true;
            btn.textContent = 'Iniciando…';

            try {
                const res = await fetch('/api/run_from_code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code, filename, intent,
                        project_name: projectName,
                        analysis: _lastAnalysis || {},
                        copilot_temperature: temperature,
                    }),
                });
                const data = await res.json();
                if (!res.ok) {
                    errEl.textContent = data.message || 'Error al iniciar el pipeline';
                    btn.disabled = false;
                    btn.textContent = '🚀 Crear proyecto desde este código';
                    return;
                }
                // Switch to main tab to watch the pipeline
                switchTopTab('main');
            } catch (e) {
                errEl.textContent = 'No se pudo conectar con el servidor';
                btn.disabled = false;
                btn.textContent = '🚀 Crear proyecto desde este código';
            }
        }

        document.querySelectorAll('#tab-bar .tab').forEach(btn => {
            btn.addEventListener('click', () => switchTopTab(btn.dataset.tab));
        });

        function loadStatusTab() {
            fetch('/api/ai/status').then(r => r.json()).then(d => {
                const list = document.getElementById('driver-status-list');
                if (!list) return;
                list.innerHTML = Object.entries(d).map(([name, info]) => `
                    <div class="driver-status">
                        <div class="ds-title">${name}</div>
                        <div class="ds-model">${info.model || '—'}</div>
                        <div class="ds-health ${info.ok ? 'ok' : 'err'}">${info.ok ? '● Online' : '● Offline'}</div>
                        <div class="ds-latency">Latencia: ${info.avg_latency_s != null ? info.avg_latency_s.toFixed(2)+'s' : '—'}</div>
                        <div class="ds-cost">Costo sesión: $${(info.total_cost_usd||0).toFixed(4)}</div>
                    </div>`).join('');
            }).catch(() => {});
            fetch('/api/usage/summary').then(r => r.json()).then(d => {
                const tbody = document.getElementById('usage-table-body');
                if (!tbody) return;
                const rows = (d.rows || []);
                tbody.innerHTML = rows.length ? rows.map(r => `
                    <tr><td>${r.date||'—'}</td><td>${r.driver||'—'}</td><td>${r.model||'—'}</td>
                    <td>${r.tokens_in||0}</td><td>${r.tokens_out||0}</td>
                    <td>${r.avg_latency_s!=null?r.avg_latency_s.toFixed(2)+'s':'—'}</td>
                    <td>$${(r.total_cost_usd||0).toFixed(4)}</td></tr>`).join('')
                    : '<tr><td colspan="7" style="color:#555;">Sin datos aún</td></tr>';
            }).catch(() => {});
            loadProcesses();
            loadExecutionErrors();
        }

        // ── Process management ────────────────────────────────────────────────

        async function loadProcesses() {
            try {
                const d = await fetch('/api/processes').then(r => r.json());
                const procs = d.processes || [];
                const list  = document.getElementById('processes-list');
                const empty = document.getElementById('processes-empty');
                if (!procs.length) {
                    list.innerHTML = '';
                    empty.style.display = '';
                    return;
                }
                empty.style.display = 'none';
                list.innerHTML = procs.map(p => `
                    <div class="proc-card" id="proc-${p.project_id}">
                        <span class="proc-dot ${p.alive ? 'alive' : 'dead'}"></span>
                        <span class="proc-name">${escapeHtml(p.project_id)}</span>
                        <span class="proc-cmd">${escapeHtml(p.command)}</span>
                        <span class="proc-pid">PID ${p.pid}</span>
                        <button class="proc-kill" onclick="killProcess('${p.project_id}')">✕ Terminar</button>
                    </div>`).join('');
            } catch(e) {}
        }

        async function killProcess(projectId) {
            if (!confirm(`¿Terminar el proceso de "${projectId}"?`)) return;
            try {
                await fetch(`/api/kill/${encodeURIComponent(projectId)}`, { method: 'POST' });
                log(`Proceso '${projectId}' terminado.`, 'LOG');
                loadProcesses();
            } catch(e) {
                log(`Error al terminar proceso: ${e}`, 'FAILED');
            }
        }

        // ── Execution errors ──────────────────────────────────────────────────

        async function loadExecutionErrors() {
            try {
                const d = await fetch('/api/execution_errors?limit=15').then(r => r.json());
                const errors = d.errors || [];
                const list   = document.getElementById('exec-errors-list');
                const empty  = document.getElementById('exec-errors-empty');
                if (!errors.length) {
                    list.innerHTML = '';
                    empty.style.display = '';
                    return;
                }
                empty.style.display = 'none';
                list.innerHTML = errors.map(e => {
                    const ts  = (e.ts || '').replace('T', ' ').slice(0, 19);
                    const msg = (e.message || '').slice(0, 300);
                    return `<div class="exec-err">
                        <div class="exec-err-header">
                            <span class="exec-err-phase">${escapeHtml(e.phase || '?')}</span>
                            <span class="exec-err-proj">${escapeHtml(e.project_id || '?')}</span>
                            <span class="exec-err-ts">${ts}</span>
                        </div>
                        <div class="exec-err-msg">${escapeHtml(msg)}</div>
                    </div>`;
                }).join('');
            } catch(e) {}
        }

        // ── Config tab ─────────────────────────────────────────────────────

        const CFG_KEYS = [
            'ANTHROPIC_API_KEY','GEMINI_API_KEY',
            'OLLAMA_BASE_URL','OLLAMA_MODEL','TELEGRAM_BOT_TOKEN'
        ];
        const CFG_MODEL_KEYS = ['CLAUDE_MODEL','GEMINI_MODEL'];

        async function loadConfigTab() {
            // Load which keys are set
            try {
                const env = await fetch('/api/env').then(r => r.json());
                CFG_KEYS.forEach(k => {
                    const inp = document.getElementById('cfg-' + k);
                    if (inp) inp.placeholder = env[k] ? '(configurado — dejá vacío para no cambiar)' : inp.placeholder;
                });
            } catch(e) {}
            // Load AI status dots
            try {
                const st = await fetch('/api/ai/status').then(r => r.json());
                _setCfgDot('claude',   !!(st.claude?.ok));
                _setCfgDot('gemini',   !!(st.gemini?.ok));
                _setCfgDot('ollama',   !!(st.qwen?.ok));
                _setCfgDot('telegram', false); // no live check
            } catch(e) {}
            // Load saved model preferences from soda_config.json via /api/config
            try {
                const cfg = await fetch('/api/config').then(r => r.json()).catch(() => ({}));
                if (cfg.claude_model)  { const s = document.getElementById('cfg-CLAUDE_MODEL');  if(s) s.value = cfg.claude_model; }
                if (cfg.gemini_model)  { const s = document.getElementById('cfg-GEMINI_MODEL');  if(s) s.value = cfg.gemini_model; }
                if (cfg.ollama_model)  { const inp = document.getElementById('cfg-OLLAMA_MODEL'); if(inp) inp.value = cfg.ollama_model; }
                if (cfg.ollama_base_url) { const inp = document.getElementById('cfg-OLLAMA_BASE_URL'); if(inp) inp.value = cfg.ollama_base_url; }
            } catch(e) {}
        }

        function _setCfgDot(provider, ok) {
            const dot = document.getElementById('cfg-dot-' + provider);
            if (!dot) return;
            dot.className = 'cfg-status-dot ' + (ok ? 'ok' : 'err');
        }

        async function testProvider(provider) {
            const btn = event.target;
            const msgEl = document.getElementById('cfg-msg-' + provider);
            btn.classList.add('testing');
            btn.textContent = 'Probando…';
            if (msgEl) { msgEl.textContent = ''; msgEl.className = 'cfg-test-msg'; }
            try {
                const r = await fetch(`/api/ai/test/${provider}`);
                const d = await r.json();
                if (d.ok) {
                    if (msgEl) { msgEl.textContent = `OK — ${d.model || provider} (${d.latency_ms || '?'}ms)`; msgEl.className = 'cfg-test-msg ok'; }
                    _setCfgDot(provider, true);
                } else {
                    if (msgEl) { msgEl.textContent = d.error || 'Error'; msgEl.className = 'cfg-test-msg err'; }
                    _setCfgDot(provider, false);
                }
            } catch(e) {
                if (msgEl) { msgEl.textContent = 'Sin respuesta del servidor'; msgEl.className = 'cfg-test-msg err'; }
            } finally {
                btn.classList.remove('testing');
                btn.textContent = provider === 'ollama' ? 'Probar' : 'Probar conexión';
            }
        }

        async function saveConfig() {
            const msgEl = document.getElementById('cfg-save-msg');
            msgEl.textContent = 'Guardando…';
            // 1. Save API keys
            const keyPayload = {};
            CFG_KEYS.forEach(k => {
                const val = (document.getElementById('cfg-' + k)?.value || '').trim();
                if (val) keyPayload[k] = val;
            });
            // 2. Save model preferences + URLs
            const cfgPayload = {};
            const claudeModel = document.getElementById('cfg-CLAUDE_MODEL')?.value;
            const geminiModel = document.getElementById('cfg-GEMINI_MODEL')?.value;
            const ollamaModel = (document.getElementById('cfg-OLLAMA_MODEL')?.value || '').trim();
            const ollamaUrl   = (document.getElementById('cfg-OLLAMA_BASE_URL')?.value || '').trim();
            if (claudeModel) cfgPayload.claude_model = claudeModel;
            if (geminiModel) cfgPayload.gemini_model = geminiModel;
            if (ollamaModel) cfgPayload.ollama_model = ollamaModel;
            if (ollamaUrl)   cfgPayload.ollama_base_url = ollamaUrl;
            try {
                if (Object.keys(keyPayload).length > 0) {
                    await fetch('/api/env', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(keyPayload) });
                }
                if (Object.keys(cfgPayload).length > 0) {
                    await fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfgPayload) });
                }
                // Clear key fields (they were saved)
                CFG_KEYS.forEach(k => { const inp = document.getElementById('cfg-' + k); if(inp) inp.value = ''; });
                msgEl.textContent = 'Cambios guardados correctamente.';
                msgEl.style.color = '#4ec9b0';
                setTimeout(() => { msgEl.textContent = ''; }, 3000);
                loadConfigTab(); // refresh dots
            } catch(e) {
                msgEl.textContent = 'Error al guardar.';
                msgEl.style.color = '#e06c75';
            }
        }

        // --- Nuevo Proyecto form ---
        function startNewProject() {
            const name = (document.getElementById('new-project-name').value || '').trim();
            const desc = (document.getElementById('new-project-desc').value || '').trim();
            const errEl = document.getElementById('new-project-error');
            if (!name) { errEl.textContent = 'El nombre es obligatorio'; errEl.style.display = ''; return; }
            if (!desc) { errEl.textContent = 'La descripción es obligatoria'; errEl.style.display = ''; return; }
            errEl.style.display = 'none';
            // Copy to main form and fire
            document.getElementById('project-name-input').value = name;
            document.getElementById('description-input').value = desc;
            switchTopTab('main');
            setTimeout(startRun, 80);
        }
    


// ---- Custom providers ----
let _knownProviders = [];

async function loadKnownProviders() {
    try {
        const r = await fetch('/api/ai/known-providers');
        const d = await r.json();
        _knownProviders = d.providers || [];
        const sel = document.getElementById('modal-known-select');
        _knownProviders.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = `${p.display_name} — ${p.default_model}`;
            sel.appendChild(opt);
        });
    } catch(e) {}
}

function onKnownProviderSelect(name) {
    const p = _knownProviders.find(x => x.name === name);
    if (!p) return;
    document.getElementById('modal-name').value = p.name;
    document.getElementById('modal-model').value = p.default_model;
    document.getElementById('modal-base-url').value = p.base_url;
}

function openAddProviderModal() {
    document.getElementById('add-provider-modal').classList.add('open');
    document.getElementById('modal-msg').textContent = '';
    if (_knownProviders.length === 0) loadKnownProviders();
}
function closeAddProviderModal() {
    document.getElementById('add-provider-modal').classList.remove('open');
    ['modal-name','modal-api-key','modal-model','modal-base-url'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('modal-known-select').value = '';
    document.getElementById('modal-msg').textContent = '';
}

async function saveCustomProvider() {
    const name = document.getElementById('modal-name').value.trim();
    const api_key = document.getElementById('modal-api-key').value.trim();
    const model = document.getElementById('modal-model').value.trim();
    const base_url = document.getElementById('modal-base-url').value.trim();
    const driver_type = document.getElementById('modal-driver-type').value;
    const msgEl = document.getElementById('modal-msg');

    if (!name) { msgEl.textContent = 'El nombre es obligatorio.'; return; }
    if (!api_key) { msgEl.textContent = 'La API key es obligatoria.'; return; }

    const btn = document.getElementById('modal-save-btn');
    btn.disabled = true;
    btn.textContent = 'Guardando…';
    msgEl.textContent = '';

    try {
        const r = await fetch('/api/ai/providers', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({name, display_name: name.charAt(0).toUpperCase()+name.slice(1), api_key, model, base_url, driver_type})
        });
        const d = await r.json();
        if (d.status === 'saved') {
            closeAddProviderModal();
            loadCustomProviders();
        } else {
            msgEl.textContent = d.error || 'Error al guardar.';
        }
    } catch(e) {
        msgEl.textContent = 'Error de red.';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Guardar proveedor';
    }
}

async function deleteCustomProvider(name) {
    if (!confirm(`¿Eliminar el proveedor "${name}"?`)) return;
    try {
        await fetch(`/api/ai/providers/${name}`, {method:'DELETE'});
        loadCustomProviders();
    } catch(e) {}
}

async function testCustomProvider(name) {
    const msgEl = document.getElementById(`custom-msg-${name}`);
    if (msgEl) msgEl.textContent = 'Probando…';
    try {
        const r = await fetch(`/api/ai/test-custom/${name}`);
        const d = await r.json();
        if (msgEl) msgEl.textContent = d.ok ? `OK · ${d.model} · ${d.latency_ms}ms` : `Error: ${d.error}`;
        if (msgEl) msgEl.style.color = d.ok ? '#4caf50' : '#f44336';
    } catch(e) {
        if (msgEl) msgEl.textContent = 'Error de red.';
    }
}

async function loadCustomProviders() {
    try {
        const r = await fetch('/api/ai/providers');
        const d = await r.json();
        const grid = document.getElementById('custom-providers-grid');
        const empty = document.getElementById('custom-providers-empty');
        const providers = d.providers || [];
        grid.innerHTML = '';
        if (providers.length === 0) {
            empty.style.display = 'block';
            return;
        }
        empty.style.display = 'none';
        providers.forEach(p => {
            const card = document.createElement('div');
            card.className = 'cfg-card custom-prov-card';
            card.innerHTML = `
                <button class="custom-prov-delete" onclick="deleteCustomProvider('${p.name}')">✕ Eliminar</button>
                <div class="cfg-card-header">
                    <span class="cfg-card-icon">🔌</span>
                    <span class="cfg-card-name">${p.display_name}</span>
                    <span class="cfg-card-role">${p.driver_type}</span>
                    <span class="cfg-status-dot" style="background:${p.has_key?'#4caf50':'#555'}"></span>
                </div>
                <div class="cfg-field">
                    <span class="cfg-label">Modelo</span>
                    <span style="color:#aaa;font-size:12px;">${p.model || '—'}</span>
                </div>
                ${p.base_url ? `<div class="cfg-field"><span class="cfg-label">Base URL</span><span style="color:#777;font-size:11px;word-break:break-all;">${p.base_url}</span></div>` : ''}
                <div class="cfg-row" style="margin-top:8px;">
                    <button class="cfg-btn cfg-btn-test" onclick="testCustomProvider('${p.name}')">Probar conexión</button>
                    <span class="cfg-test-msg" id="custom-msg-${p.name}"></span>
                </div>
            `;
            grid.appendChild(card);
        });
    } catch(e) {}
}

// Load custom providers when config tab is shown
document.addEventListener('DOMContentLoaded', () => {
    const cfgTab = document.getElementById('config-tab');
    if (cfgTab) {
        const observer = new MutationObserver(() => {
            if (cfgTab.classList.contains('active')) loadCustomProviders();
        });
        observer.observe(cfgTab, {attributes: true, attributeFilter: ['class']});
    }
    loadKnownProviders();
});

// ══════════════════════════════════════════════════════════════════════════════
// OPEN EXISTING PROJECT
// ══════════════════════════════════════════════════════════════════════════════

let _openAnalysis = null;
let _openAnswers  = {};
let _openSelectedAction = null;
const _OPEN_NAME_RE = /^[a-zA-Z0-9_\-]{1,60}$/;

const _ACTION_META = {
    fix_bugs:         { icon: '🐛', color: 'var(--red)',    label: 'Corregir bugs' },
    refactor:         { icon: '⚙️',  color: 'var(--cyan)',   label: 'Refactorizar' },
    add_tests:        { icon: '🧪', color: 'var(--green)',  label: 'Añadir tests' },
    add_docs:         { icon: '📚', color: 'var(--amber)',  label: 'Documentar' },
    add_feature:      { icon: '✨', color: 'var(--violet)', label: 'Nueva funcionalidad' },
    migrate_language: { icon: '🔀', color: 'var(--violet)', label: 'Migrar lenguaje' },
    run_and_test:     { icon: '▶',  color: 'var(--green)',  label: 'Ejecutar y probar' },
    full_pipeline:    { icon: '🚀', color: 'var(--cyan)',   label: 'Pipeline completo' },
};

function initOpenTab() {
    // Load migration targets
    fetch('/api/open_project/migration_targets').then(r => r.json()).then(d => {
        const sel = document.getElementById('open-migrate-sel');
        if (!sel) return;
        (d.targets || []).forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t.charAt(0).toUpperCase() + t.slice(1);
            sel.appendChild(opt);
        });
    }).catch(() => {});
}

async function openBrowse() {
    const btn = document.querySelector('.open-btn-browse');
    if (btn) { btn.disabled = true; btn.textContent = 'Abriendo…'; }
    try {
        const d = await fetch('/api/open_project/browse').then(r => r.json());
        if (d.path) {
            document.getElementById('open-path-input').value = d.path;
        }
    } catch(e) {}
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa fa-folder"></i> Explorar…'; }
}

async function openAnalyze() {
    const path = (document.getElementById('open-path-input').value || '').trim();
    if (!path) { alert('Ingresá la ruta del proyecto primero.'); return; }

    const loading = document.getElementById('open-loading');
    const panel   = document.getElementById('open-analysis-panel');
    const analyzeBtn = document.getElementById('open-analyze-btn');

    loading.classList.add('active');
    panel.classList.remove('visible');
    analyzeBtn.disabled = true;
    _openAnalysis = null;
    _openAnswers  = {};
    _openSelectedAction = null;

    try {
        const r = await fetch('/api/open_project/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path}),
        });
        const d = await r.json();
        if (d.status !== 'ok') throw new Error(d.message || 'Error de análisis');
        _openAnalysis = d.analysis;
        _openRenderAnalysis(d.analysis);
        panel.classList.add('visible');
    } catch(e) {
        alert('Error al analizar: ' + e.message);
    } finally {
        loading.classList.remove('active');
        analyzeBtn.disabled = false;
    }
}

function _openRenderAnalysis(a) {
    // ── Overview card ──
    const stack = a.stack || {};
    const quality = a.quality || {};
    const score = quality.score || 0;
    const scoreColor = score >= 7 ? 'var(--green)' : score >= 4 ? 'var(--amber)' : 'var(--red)';
    const issues = (quality.issues || []).slice(0, 5);
    const filesCount = a._file_count || 0;

    const badgesHtml = [
        stack.language && `<span class="open-badge open-badge-lang">${escapeHtml(stack.language)}</span>`,
        stack.framework && `<span class="open-badge open-badge-fw">${escapeHtml(stack.framework)}</span>`,
        stack.database  && `<span class="open-badge open-badge-db">${escapeHtml(stack.database)}</span>`,
        a.domain        && `<span class="open-badge open-badge-domain">${escapeHtml(a.domain)}</span>`,
        ...(stack.other || []).map(o => `<span class="open-badge open-badge-fw">${escapeHtml(o)}</span>`),
    ].filter(Boolean).join('');

    const issuesHtml = issues.map(i =>
        `<div class="open-issue"><span class="open-issue-dot"></span><span>${escapeHtml(i)}</span></div>`
    ).join('');

    const archHtml = a.architecture
        ? `<div style="font-size:11px;color:var(--t3);margin-bottom:8px;">Arquitectura: <span style="color:var(--t2);">${escapeHtml(a.architecture)}</span></div>`
        : '';

    const effortHtml = a.estimated_effort
        ? `<div style="font-size:11px;color:var(--amber);margin-top:8px;">${escapeHtml(a.estimated_effort)}</div>`
        : '';

    document.getElementById('open-card-overview').innerHTML = `
        <div class="open-purpose">${escapeHtml(a.purpose || '—')}</div>
        <div class="open-stack-badges">${badgesHtml}</div>
        ${archHtml}
        <div class="open-quality-bar">
            <span class="open-quality-label">Calidad</span>
            <div class="open-quality-track">
                <div class="open-quality-fill" style="width:${score * 10}%;background:${scoreColor};"></div>
            </div>
            <span class="open-quality-score" style="color:${scoreColor};">${score}/10</span>
        </div>
        ${issuesHtml ? `<div class="open-issues-list">${issuesHtml}</div>` : ''}
        ${effortHtml}
        <div class="open-files-count">${filesCount} archivo${filesCount !== 1 ? 's' : ''} analizados</div>
    `;

    // ── Action cards ──
    const grid = document.getElementById('open-actions-grid');
    const actions = a.suggested_actions || Object.keys(_ACTION_META).map(id => ({id, priority: 'medium'}));
    grid.innerHTML = actions.map(ac => {
        const meta = _ACTION_META[ac.id] || { icon: '⚡', color: 'var(--cyan)', label: ac.label || ac.id };
        return `<div class="open-action-card" data-action="${escapeHtml(ac.id)}"
                    style="--action-color:${meta.color}"
                    onclick="openSelectAction('${escapeHtml(ac.id)}')">
            <div class="open-action-icon">${meta.icon}</div>
            <div class="open-action-name">${escapeHtml(ac.label || meta.label)}</div>
            <div class="open-action-desc">${escapeHtml((ac.description || '').slice(0, 80))}</div>
            ${ac.priority ? `<span class="open-action-priority ${ac.priority}">${ac.priority}</span>` : ''}
        </div>`;
    }).join('');

    // Pre-fill project name
    const pathVal = (document.getElementById('open-path-input').value || '').trim();
    const suggested = (pathVal.split(/[/\\]/).filter(Boolean).pop() || 'proyecto') + '_soda';
    const nameInput = document.getElementById('open-project-name-input');
    if (nameInput && !nameInput.value) nameInput.value = suggested.replace(/[^a-zA-Z0-9_\-]/g, '_').slice(0, 60);

    document.getElementById('open-intent-section').style.display = 'flex';

    // Render AI-generated questions if present
    _openRenderQuestions(a.questions || []);
}

function _openRenderQuestions(questions) {
    const panel = document.getElementById('open-questions-panel');
    const list  = document.getElementById('open-questions-list');
    if (!panel || !list) return;

    if (!questions || questions.length === 0) {
        panel.classList.remove('visible');
        list.innerHTML = '';
        return;
    }

    list.innerHTML = questions.map((q, i) => {
        const opts = (q.options || []).map(opt =>
            `<button class="open-question-opt" onclick="openSelectAnswer('${escapeHtml(q.id || 'q'+i)}', this, '${escapeHtml(opt)}')">${escapeHtml(opt)}</button>`
        ).join('');
        return `<div class="open-question-item" data-qid="${escapeHtml(q.id || 'q'+i)}">
            <div class="open-question-text">${escapeHtml(q.question)}</div>
            <div class="open-question-opts">${opts}</div>
        </div>`;
    }).join('');
    panel.classList.add('visible');
}

function openSelectAnswer(qid, btn, answer) {
    _openAnswers[qid] = answer;
    // Toggle selected state within this question
    const item = btn.closest('.open-question-item');
    if (item) item.querySelectorAll('.open-question-opt').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
}

function openSelectAction(actionId) {
    _openSelectedAction = actionId;
    document.querySelectorAll('.open-action-card').forEach(c => {
        c.classList.toggle('selected', c.dataset.action === actionId);
    });
    const migrateRow = document.getElementById('open-migrate-row');
    if (migrateRow) migrateRow.classList.toggle('visible', actionId === 'migrate_language');
}

async function openLaunch() {
    const path    = (document.getElementById('open-path-input').value || '').trim();
    const intent  = (document.getElementById('open-intent').value || '').trim();
    const name    = (document.getElementById('open-project-name-input').value || '').trim();
    const action  = _openSelectedAction || 'full_pipeline';
    const errEl   = document.getElementById('open-error');
    const langSel = document.getElementById('open-migrate-sel');
    const targetLang = langSel ? langSel.value : '';

    errEl.textContent = '';
    if (!path) { errEl.textContent = 'Falta la ruta del proyecto.'; return; }
    if (!_OPEN_NAME_RE.test(name)) { errEl.textContent = 'Nombre inválido (letras, números, _ y -)'; return; }
    if (action === 'migrate_language' && !targetLang) { errEl.textContent = 'Elegí el lenguaje destino.'; return; }

    const btn = document.getElementById('open-launch-btn');
    btn.disabled = true;
    btn.textContent = 'Iniciando…';

    try {
        const r = await fetch('/api/open_project/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                path, action, intent, project_name: name,
                analysis: _openAnalysis || {},
                answers: _openAnswers || {},
                target_language: targetLang,
            }),
        });
        const d = await r.json();
        if (d.status === 'started') {
            switchTopTab('main');  // switch to main pipeline view
        } else if (d.status === 'busy') {
            errEl.textContent = 'Pipeline en ejecución. Esperá a que termine.';
        } else {
            errEl.textContent = d.message || 'Error al iniciar';
        }
    } catch(e) {
        errEl.textContent = 'Error de conexión: ' + e.message;
    } finally {
        btn.disabled = false;
        btn.textContent = '🚀 Procesar proyecto';
    }
}

// ══════════════════════════════════════════════════════════════════════════════
// EMBEDDED TERMINAL — REMOVED (output now streams to main console)
// ══════════════════════════════════════════════════════════════════════════════

// stub: initTerminalTab may still be referenced from legacy code
function initTerminalTab() {}
function termRun() {}
function termStop() {}
function termClear() {}
function termDiagnose() {}
function termCloseDiag() {}
function termRunSuggestedCmd() {}
function onTermProjectChange() {}

let _term = null;           // kept as null — terminal tab removed

// ── all terminal implementations deleted — stubs declared above ──

function _deletedTerminalTab_placeholder() {
    // initTerminalTab, termRun, termStop, termClear, termDiagnose,
    // termCloseDiag, termRunSuggestedCmd, onTermProjectChange,
    // _initXterm, _termSetStatus, _termSetAlive — all removed.
}

// (terminal implementations removed — stubs defined above)

// ── Recursos (sidebar panel en main tab) ─────────────────────────────────────

let _recursosProjectId = null;
let _recursosIntentQueue = [];
let _recursosIntentCurrent = null;
let _recursosSidebarOpen = true;

function recursosInit() {
    const pid = currentProjectId;
    if (!pid) { _recursosClear(); return; }
    _recursosProjectId = pid;
    recursosFetch();
}

function _recursosClear() {
    const list = document.getElementById('recursos-list');
    if (list) list.innerHTML = '<div style="color:var(--t4);font-size:10px;padding:4px;">Sin proyecto seleccionado.</div>';
    const badge = document.getElementById('recursos-count-badge');
    if (badge) { badge.style.display = 'none'; }
}

function recursosToggleSidebar() {
    _recursosSidebarOpen = !_recursosSidebarOpen;
    const body = document.getElementById('recursos-sb-body');
    const arrow = document.getElementById('recursos-sb-arrow');
    if (body) body.classList.toggle('collapsed', !_recursosSidebarOpen);
    if (arrow) arrow.textContent = _recursosSidebarOpen ? '▾' : '▸';
}

async function recursosFetch() {
    const pid = _recursosProjectId;
    if (!pid) return;
    try {
        const r = await fetch(`/api/projects/${pid}/resources`);
        const data = await r.json();
        _recursosRender(data.resources || {});
    } catch(e) {
        const list = document.getElementById('recursos-list');
        if (list) list.innerHTML = '<div style="color:var(--red);font-size:10px;">Error cargando recursos.</div>';
    }
}

function _recursosRender(manifest) {
    const list = document.getElementById('recursos-list');
    const badge = document.getElementById('recursos-count-badge');
    const keys = Object.keys(manifest);
    if (badge) {
        if (keys.length) { badge.textContent = keys.length; badge.style.display = ''; }
        else { badge.style.display = 'none'; }
    }
    if (!list) return;
    if (!keys.length) {
        list.innerHTML = '<div style="color:var(--t4);font-size:10px;padding:4px 2px;">Sin recursos. Subí archivos, enlaces o texto.</div>';
        return;
    }
    list.innerHTML = keys.map(key => _recursosItem(key, manifest[key])).join('');
}

function _recursosItem(key, r) {
    const label = r.label || r.filename || key;
    const type = r.type || 'file';
    const intent = r.intent || '';
    const iconMap = { file:'fa-file-o', link:'fa-link', text:'fa-align-left' };
    let ico = iconMap[type] || 'fa-file-o';
    if (type === 'file' && r.mime_type) {
        if (r.mime_type.startsWith('image/')) ico = 'fa-image';
        else if (r.mime_type.includes('pdf')) ico = 'fa-file-pdf-o';
        else if (r.mime_type.includes('zip') || r.mime_type.includes('tar')) ico = 'fa-file-archive-o';
    }
    const intentClass = intent ? 'has-intent' : '';
    return `<div class="ritem" onclick="recursosAskIntent('${_esc(key)}','${_esc(label)}')" title="${_esc(intent || 'Definir uso...')}">
        <i class="fa ${ico} ritem-icon ${intentClass}"></i>
        <span class="ritem-name">${_esc(label)}</span>
        <button class="ritem-del" onclick="event.stopPropagation();recursosDelete('${_esc(key)}')" title="Eliminar">✕</button>
    </div>`;
}

function _esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function recursosDrop(e) {
    e.preventDefault();
    document.getElementById('recursos-sb-dropzone').classList.remove('drag');
    recursosHandleFiles(e.dataTransfer.files);
}

async function recursosHandleFiles(fileList) {
    if (!_recursosProjectId) { alert('Seleccioná un proyecto primero.'); return; }
    const keys = [];
    for (const file of fileList) {
        const fd = new FormData();
        fd.append('file', file);
        const r = await fetch(`/api/projects/${_recursosProjectId}/resources/upload`, { method:'POST', body:fd });
        const data = await r.json();
        if (data.status === 'ok') keys.push({ key: data.key, label: file.name });
    }
    recursosFetch();
    _recursosEnqueueIntent(keys);
}

async function recursosAddText() {
    if (!_recursosProjectId) { alert('Seleccioná un proyecto primero.'); return; }
    const inp = document.getElementById('recursos-link-input');
    const val = (inp.value || '').trim();
    if (!val) return;
    const isUrl = /^https?:\/\//i.test(val);
    const body = isUrl ? { url: val, label: val.replace(/^https?:\/\//,'').slice(0,50) } : { text: val };
    const r = await fetch(`/api/projects/${_recursosProjectId}/resources/link`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    const data = await r.json();
    if (data.status === 'ok') {
        inp.value = '';
        recursosFetch();
        _recursosEnqueueIntent([{ key: data.key, label: body.label || val.slice(0,50) }]);
    }
}

function _recursosEnqueueIntent(items) {
    _recursosIntentQueue.push(...items);
    if (!_recursosIntentCurrent) _recursosNextIntent();
}

function _recursosNextIntent() {
    if (!_recursosIntentQueue.length) { _recursosIntentCurrent = null; return; }
    _recursosIntentCurrent = _recursosIntentQueue.shift();
    const box = document.getElementById('recursos-intent-box');
    document.getElementById('recursos-intent-label').textContent =
        `¿Qué querés hacer con "${_recursosIntentCurrent.label}"?`;
    document.getElementById('recursos-intent-input').value = '';
    box.style.display = 'flex';
    setTimeout(() => document.getElementById('recursos-intent-input').focus(), 50);
}

async function recursosSubmitIntent() {
    if (!_recursosIntentCurrent) return;
    const intent = (document.getElementById('recursos-intent-input').value || '').trim();
    if (intent) {
        await fetch(`/api/projects/${_recursosProjectId}/resources/${encodeURIComponent(_recursosIntentCurrent.key)}/intent`, {
            method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({intent})
        });
    }
    document.getElementById('recursos-intent-box').style.display = 'none';
    recursosFetch();
    _recursosNextIntent();
}

function recursosSkipIntent() {
    document.getElementById('recursos-intent-box').style.display = 'none';
    _recursosNextIntent();
}

function recursosAskIntent(key, label) {
    _recursosIntentQueue.unshift({ key, label });
    if (!_recursosIntentCurrent) _recursosNextIntent();
}

async function recursosDelete(key) {
    if (!_recursosProjectId) return;
    if (!confirm('¿Eliminar este recurso?')) return;
    await fetch(`/api/projects/${_recursosProjectId}/resources/${encodeURIComponent(key)}`, { method:'DELETE' });
    recursosFetch();
}

async function recursosApplyAll() {
    if (!_recursosProjectId) { alert('Seleccioná un proyecto primero.'); return; }
    const btn = document.getElementById('recursos-apply-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Aplicando…';
    try {
        const r = await fetch(`/api/projects/${_recursosProjectId}/resources/apply`, {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({keys:[]})
        });
        const data = await r.json();
        if (data.status === 'busy') {
            alert('Pipeline en ejecución. Esperá a que termine.');
        } else if (data.status === 'error') {
            alert(data.message || 'Error aplicando recursos.');
        } else {
            switchTopTab('main');
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa fa-magic"></i> Aplicar al proyecto';
    }
}

async function setGeminiModel(model) {
  try {
    await fetch("/api/models/gemini", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({model})});
  } catch(e) { console.error(e); }
}
async function loadGeminiModel() {
  try {
    const r = await fetch("/api/models/gemini");
    const d = await r.json();
    const s = document.getElementById("gemini-model-select");
    if(s) s.value = d.current;
  } catch(e) { console.error(e); }
}
document.addEventListener("DOMContentLoaded", loadGeminiModel);
