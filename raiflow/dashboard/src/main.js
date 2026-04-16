'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  step: 1, mode: 'interceptor',
  framework: null, frameworkName: null,
  targetUrl: 'http://localhost:7860', port: 8080,
  auditLogs: [], lastCount: 0,
  pollTimer: null, auditDone: false, reportData: null,
};

const FRAMEWORKS = [
  { id: 'eu_ai_act', name: 'EU AI Act', flag: '🇪🇺',
    jurisdiction: 'European Union · Regulation (EU) 2024/1689',
    desc: 'Covers risk management, data governance, transparency, and human oversight for high-risk AI systems.',
    tags: ['Risk Mgmt', 'Data Gov', 'Transparency', 'Human Oversight'] },
  { id: 'nist_ai_rmf', name: 'NIST AI RMF', flag: '🇺🇸',
    jurisdiction: 'United States · NIST AI RMF 1.0',
    desc: 'Framework for managing AI risks across four core functions: Govern, Map, Measure, and Manage.',
    tags: ['Faithfulness', 'Safety', 'Privacy', 'Attribution'] },
];

const EU_ARTICLES = [
  { id: 'Article 9',  name: 'Risk Management',   icon: '⚠️' },
  { id: 'Article 10', name: 'Data Governance',    icon: '📊' },
  { id: 'Article 11', name: 'Technical Docs',     icon: '📋' },
  { id: 'Article 12', name: 'Record Keeping',     icon: '📝' },
  { id: 'Article 13', name: 'Transparency',       icon: '🔍' },
  { id: 'Article 14', name: 'Human Oversight',    icon: '👥' },
];

// ── Step navigation ───────────────────────────────────────────────────────────
function goStep(n) {
  if (n === 2 && !validateStep1()) return;
  if (n === 3 && !validateStep2()) return;
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  document.getElementById('step-' + n).classList.add('active');
  document.querySelectorAll('.step').forEach(s => {
    const sn = parseInt(s.dataset.step);
    s.classList.toggle('active', sn === n);
    s.classList.toggle('done',   sn < n);
  });
  document.querySelectorAll('.step-line').forEach((l, i) => l.classList.toggle('done', i < n - 1));
  state.step = n;
  if (n === 2) renderFrameworks();
  if (n === 3) populateConfig();
  if (n === 5) renderReportPreview();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Step 1 ────────────────────────────────────────────────────────────────────
function selectOption(mode) {
  state.mode = mode;
  document.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('opt-' + mode).classList.add('selected');
  document.querySelectorAll('.connect-form').forEach(f => f.classList.add('hidden'));
  document.getElementById('form-' + mode).classList.remove('hidden');
}

function validateStep1() {
  if (state.mode === 'interceptor') {
    const url = document.getElementById('targetUrl').value.trim();
    if (!url) { alert('Please enter your app URL.'); return false; }
    state.targetUrl = url;
    state.port = parseInt(document.getElementById('interceptorPort').value) || 8080;
  }
  return true;
}

document.getElementById('interceptorPort').addEventListener('input', function(e) {
  document.getElementById('portPreview').textContent = e.target.value || '8080';
});

function copyCode(id) {
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(function() {
    const btn = document.getElementById(id).closest('.code-block').querySelector('button');
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy'; }, 1500);
  });
}

// ── Step 2 ────────────────────────────────────────────────────────────────────
function renderFrameworks() {
  document.getElementById('framework-grid').innerHTML = FRAMEWORKS.map(function(fw) {
    return '<div class="framework-card ' + (state.framework === fw.id ? 'selected' : '') + '" onclick="selectFramework(\'' + fw.id + '\',\'' + fw.name + '\')">' +
      '<div class="fw-flag">' + fw.flag + '</div>' +
      '<div class="fw-name">' + fw.name + '</div>' +
      '<div class="fw-jurisdiction">' + fw.jurisdiction + '</div>' +
      '<div class="fw-desc">' + fw.desc + '</div>' +
      '<div class="fw-tags">' + fw.tags.map(function(t) { return '<span class="fw-tag">' + t + '</span>'; }).join('') + '</div>' +
      '</div>';
  }).join('');
}

function selectFramework(id, name) {
  state.framework = id; state.frameworkName = name;
  document.querySelectorAll('.framework-card').forEach(function(c) { c.classList.remove('selected'); });
  document.querySelectorAll('.framework-card').forEach(function(c) {
    if (c.querySelector('.fw-name') && c.querySelector('.fw-name').textContent === name) {
      c.classList.add('selected');
    }
  });
}

function validateStep2() {
  if (!state.framework) { alert('Please select a compliance framework.'); return false; }
  return true;
}

// ── Step 3 ────────────────────────────────────────────────────────────────────
function populateConfig() {
  var modeLabel = state.mode === 'interceptor' ? 'HTTP Interceptor → proxy on port ' + state.port
    : state.mode === 'decorator' ? 'Python @shield decorator' : 'Direct response paste';
  document.getElementById('cfg-target').textContent =
    state.mode === 'interceptor' ? state.targetUrl : state.mode === 'direct' ? 'Pasted response' : 'Your decorated function';
  document.getElementById('cfg-framework').textContent = state.frameworkName;
  document.getElementById('cfg-mode').textContent = modeLabel;
}

function startAudit() {
  var btn = document.getElementById('btnRun');
  btn.disabled = true; btn.textContent = '⏳ Auditing…';
  var livePanel = document.getElementById('live-panel');
  livePanel.style.display = 'block';
  document.getElementById('live-feed').innerHTML = '';
  document.getElementById('live-count').textContent = '0';
  state.auditDone = false;
  addLiveLog('system', 'Audit started — Framework: ' + state.frameworkName);
  if (state.mode === 'direct') { runDirectAudit(); } else { runInterceptorAudit(); }
}

function runDirectAudit() {
  var raw = (document.getElementById('directPaste') || {}).value || '';
  raw = raw.trim();
  if (!raw) { addLiveLog('fail', 'No response pasted.'); resetRunBtn(); return; }
  var data;
  try { data = JSON.parse(raw); } catch(e) { addLiveLog('fail', 'Invalid JSON.'); resetRunBtn(); return; }
  addLiveLog('shield', 'Running PII check…');
  setTimeout(function() { addLiveLog('shield', 'Running toxicity check…'); }, 400);
  setTimeout(function() { addLiveLog('shield', 'Running faithfulness check…'); }, 800);
  setTimeout(function() {
    state.auditLogs = [buildSyntheticEvent(data)];
    state.auditDone = true;
    addLiveLog('pass', 'Audit complete');
    finishAudit();
  }, 1400);
}

function logEvent(e) {
  var s = (e.audit_fast || {}).scores || {};
  var pii   = s.pii_clean    === 1.0 ? '✅' : '❌ PII';
  var tox   = s.toxicity_safe === 1.0 ? '✅' : '❌ Toxic';
  var faith = s.faithfulness != null ? ' Faith:' + Math.round(s.faithfulness * 100) + '%' : '';
  var ts    = (e.timestamp || '').split('T')[1] || '';
  addLiveLog('shield', '[' + ts.slice(0,8) + '] ' + e.function + ' | PII:' + pii + ' Tox:' + tox + faith);
}

function runInterceptorAudit() {
  addLiveLog('system', 'Target: ' + state.targetUrl);

  // Load all existing events immediately — don't wait for new ones
  fetch('/api/logs').then(function(r) { return r.json(); }).then(function(logs) {
    if (logs.length > 0) {
      // Show last 5 existing events
      var recent = logs.slice(-5);
      addLiveLog('system', 'Found ' + logs.length + ' existing audit event(s) — showing latest ' + recent.length);
      recent.forEach(logEvent);
      state.lastCount = logs.length;
      state.auditLogs = logs;
      document.getElementById('live-count').textContent = logs.length;
      // Complete immediately with existing data
      state.auditDone = true;
      addLiveLog('pass', 'Audit complete — ' + logs.length + ' event(s) loaded');
      finishAudit();
      return;
    }

    // No existing events — wait for new ones
    state.lastCount = 0;
    addLiveLog('system', 'No existing events. Send queries through the interceptor now:');
    addLiveLog('system', 'python -m raiflow.interceptor --target ' + state.targetUrl + ' --port ' + state.port);

    var waited = 0;
    state.pollTimer = setInterval(function() {
      waited += 3;
      fetch('/api/logs').then(function(r) { return r.json(); }).then(function(logs) {
        if (logs.length > state.lastCount) {
          var fresh = logs.slice(state.lastCount);
          fresh.forEach(logEvent);
          state.lastCount = logs.length;
          state.auditLogs = logs;
          document.getElementById('live-count').textContent = logs.length;
        }
        if (state.auditLogs.length > 0 && waited >= 5 && !state.auditDone) {
          state.auditDone = true;
          clearInterval(state.pollTimer);
          addLiveLog('pass', 'Audit complete — ' + state.auditLogs.length + ' event(s) captured');
          finishAudit();
        }
      }).catch(function() {});
      if (waited >= 120 && !state.auditDone) {
        clearInterval(state.pollTimer);
        addLiveLog('warn', 'Timeout — no events received. Make sure your app is running.');
        resetRunBtn();
      }
    }, 3000);
  }).catch(function() {
    addLiveLog('fail', 'Cannot reach RaiFlow server at port 8000.');
    resetRunBtn();
  });
}

function finishAudit() {
  resetRunBtn();
  addLiveLog('system', 'Navigating to results…');
  setTimeout(function() { buildResults(); goStep(4); }, 1200);
}

function resetRunBtn() {
  var btn = document.getElementById('btnRun');
  btn.disabled = false; btn.textContent = '▶ Start Audit';
}

function addLiveLog(type, msg) {
  var feed = document.getElementById('live-feed');
  var el = document.createElement('div');
  el.className = 'log-entry ' + type;
  var ts = new Date().toLocaleTimeString([], { hour12: false });
  el.innerHTML = '<span class="ts">' + ts + '</span><span class="tag">[' + type.toUpperCase() + ']</span><span>' + msg + '</span>';
  feed.appendChild(el);
  feed.scrollTop = feed.scrollHeight;
}

// ── Step 4: Results ───────────────────────────────────────────────────────────
function buildResults() {
  if (!state.auditLogs.length) return;
  var latest = state.auditLogs[state.auditLogs.length - 1];
  var report = latest.audit_report;
  if (!report || !report.sections) return;
  state.reportData = { latest: latest, report: report };

  var sectionScores = report.sections.map(function(s) {
    var scores = s.stages.map(function(st) { return st.final_score || 0; });
    return scores.reduce(function(a, b) { return a + b; }, 0) / (scores.length || 1);
  });
  var overall = sectionScores.reduce(function(a, b) { return a + b; }, 0) / (sectionScores.length || 1);
  var pct = Math.round(overall * 100);

  var circle = document.getElementById('score-circle');
  document.getElementById('score-num').textContent = pct + '%';
  circle.className = 'score-circle ' + (pct >= 75 ? 'pass' : pct >= 50 ? 'warn' : 'fail');

  var risk = pct >= 80 ? 'Low' : pct >= 60 ? 'Medium' : pct >= 40 ? 'High' : 'Critical';
  var riskColor = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--amber)' : pct >= 40 ? 'var(--orange)' : 'var(--red)';
  document.getElementById('risk-level').textContent = risk;
  document.getElementById('risk-level').style.color = riskColor;
  document.getElementById('checks-run').textContent = report.sections.reduce(function(a, s) { return a + s.stages.length; }, 0);
  document.getElementById('result-framework').textContent = state.frameworkName;
  var violations = report.sections.reduce(function(a, s) { return a + s.stages.filter(function(st) { return !st.passed; }).length; }, 0);
  document.getElementById('violations-count').textContent = violations;
  document.getElementById('violations-count').style.color = violations === 0 ? 'var(--green)' : 'var(--red)';

  var articles = state.framework === 'eu_ai_act' ? EU_ARTICLES
    : report.sections.map(function(s) { return { id: s.section_id, name: s.section_id, icon: '📋' }; });

  document.getElementById('heatmap').innerHTML = articles.map(function(article) {
    var section = report.sections.find(function(s) { return s.section_id === article.id; });
    var score = 0, status = 'unknown';
    if (section && section.stages && section.stages.length) {
      var sc = section.stages.map(function(st) { return st.final_score || 0; });
      score = sc.reduce(function(a, b) { return a + b; }, 0) / sc.length;
      var p = Math.round(score * 100);
      status = p >= 75 ? 'compliant' : p >= 50 ? 'partial' : 'non-compliant';
    }
    return '<div class="heatmap-cell ' + status + '">' +
      '<span class="heatmap-icon">' + article.icon + '</span>' +
      '<span class="heatmap-id">' + article.id.replace('Article ', 'Art.') + '</span>' +
      '<span class="heatmap-name">' + article.name + '</span>' +
      '<span class="heatmap-score">' + Math.round(score * 100) + '%</span></div>';
  }).join('');

  document.getElementById('findings').innerHTML = report.sections.map(function(section) {
    var sc = section.stages.map(function(st) { return st.final_score || 0; });
    var avg = sc.reduce(function(a, b) { return a + b; }, 0) / (sc.length || 1);
    var p2 = Math.round(avg * 100);
    var cls = p2 >= 75 ? 'pass' : p2 >= 50 ? 'warn' : 'fail';
    var label = p2 >= 75 ? 'PASS' : p2 >= 50 ? 'PARTIAL' : 'FAIL';
    var stages = section.stages.map(function(st) {
      var sp = Math.round((st.final_score || 0) * 100);
      var sc2 = sp >= 75 ? 'pass' : sp < 30 ? 'fail' : 'warn';
      var col = sp >= 75 ? 'var(--green)' : sp < 30 ? 'var(--red)' : 'var(--amber)';
      return '<div class="stage-row"><span class="stage-name">' + st.stage + '</span>' +
        '<div class="stage-track"><div class="stage-fill ' + sc2 + '" style="width:' + sp + '%"></div></div>' +
        '<span class="stage-pct" style="color:' + col + '">' + sp + '%</span></div>';
    }).join('');
    return '<div class="finding-card"><div class="finding-header">' +
      '<span class="finding-title">' + section.section_id + '</span>' +
      '<span class="finding-badge ' + cls + '">' + label + ' · ' + p2 + '%</span></div>' + stages + '</div>';
  }).join('');
}

// ── Step 5: Report ────────────────────────────────────────────────────────────
function renderReportPreview() {
  if (!state.reportData) return;
  var report = state.reportData.report;
  var now = new Date().toLocaleString();
  var html = '<h2>RaiFlow Compliance Report</h2><p>Generated: ' + now + ' &nbsp;·&nbsp; Framework: ' + state.frameworkName + '</p><h2>Executive Summary</h2>';
  report.sections.forEach(function(s) {
    var sc = s.stages.map(function(st) { return st.final_score || 0; });
    var avg = sc.reduce(function(a, b) { return a + b; }, 0) / (sc.length || 1);
    var p = Math.round(avg * 100);
    var cls = p >= 75 ? 'rp-pass' : p >= 50 ? 'rp-warn' : 'rp-fail';
    var label = p >= 75 ? '✅ PASS' : p >= 50 ? '⚠️ PARTIAL' : '❌ FAIL';
    html += '<div class="rp-row"><span>' + s.section_id + '</span><span class="' + cls + '">' + label + ' (' + p + '%)</span></div>';
  });
  html += '<h2>Recommendations</h2>';
  report.sections.forEach(function(s) {
    s.stages.filter(function(st) { return (st.final_score || 1) < 0.75; }).forEach(function(st) {
      html += '<p>⚠ <strong>' + s.section_id + ' — ' + st.stage + ':</strong> Score ' + Math.round((st.final_score || 0) * 100) + '% is below threshold. Review compliance measures for this area.</p>';
    });
  });
  html += '<p style="margin-top:16px;font-size:12px;color:var(--muted)">Disclaimer: RaiFlow is a compliance assistance tool and does not constitute legal advice.</p>';
  document.getElementById('report-preview').innerHTML = html;
}

function downloadReport() {
  if (!state.reportData) return;
  var report = state.reportData.report;
  var now = new Date();
  var sections = report.sections.map(function(s) {
    var sc = s.stages.map(function(st) { return st.final_score || 0; });
    var avg = sc.reduce(function(a, b) { return a + b; }, 0) / (sc.length || 1);
    var p = Math.round(avg * 100);
    var label = p >= 75 ? 'PASS' : p >= 50 ? 'PARTIAL' : 'FAIL';
    var color = p >= 75 ? '#22c55e' : p >= 50 ? '#f59e0b' : '#ef4444';
    var rows = s.stages.map(function(st) {
      var sp = Math.round((st.final_score || 0) * 100);
      var sc2 = sp >= 75 ? '#22c55e' : sp < 30 ? '#ef4444' : '#f59e0b';
      return '<tr><td style="padding:6px 12px;color:#94a3b8">' + st.stage + '</td>' +
        '<td style="padding:6px 12px"><div style="background:#1e2235;border-radius:3px;height:6px;overflow:hidden">' +
        '<div style="background:' + sc2 + ';width:' + sp + '%;height:100%"></div></div></td>' +
        '<td style="padding:6px 12px;color:' + sc2 + ';font-weight:700;text-align:right">' + sp + '%</td></tr>';
    }).join('');
    return '<div style="background:#0f1117;border:1px solid #1e2235;border-radius:12px;padding:20px;margin-bottom:16px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">' +
      '<span style="font-size:15px;font-weight:700;color:#e2e8f0">' + s.section_id + '</span>' +
      '<span style="background:' + color + '22;color:' + color + ';border:1px solid ' + color + '44;padding:3px 12px;border-radius:99px;font-size:12px;font-weight:700">' + label + ' · ' + p + '%</span></div>' +
      '<table style="width:100%;border-collapse:collapse">' + rows + '</table></div>';
  }).join('');

  var html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>RaiFlow Compliance Report</title>' +
    '<style>@import url(\'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap\');' +
    'body{font-family:Inter,sans-serif;background:#080a0f;color:#e2e8f0;margin:0;padding:40px}' +
    'h1{font-size:28px;font-weight:800;background:linear-gradient(90deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}' +
    'h2{font-size:14px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.07em;margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid #1e2235}' +
    '.meta{color:#64748b;font-size:13px;margin-bottom:32px}.disclaimer{color:#475569;font-size:11px;margin-top:32px;padding-top:16px;border-top:1px solid #1e2235}</style></head>' +
    '<body><h1>RaiFlow Compliance Report</h1>' +
    '<div class="meta">Generated: ' + now.toLocaleString() + ' &nbsp;·&nbsp; Framework: ' + state.frameworkName + '</div>' +
    '<h2>Section Results</h2>' + sections +
    '<div class="disclaimer">This report was generated by RaiFlow and does not constitute legal advice. Always consult qualified legal counsel for regulatory compliance matters.</div>' +
    '</body></html>';

  var win = window.open('', '_blank');
  win.document.write(html);
  win.document.close();
  win.onload = function() { win.focus(); win.print(); };
}

// ── Synthetic event (direct paste mode) ──────────────────────────────────────
function buildSyntheticEvent(data) {
  var answer  = data.answer  || data.response || '';
  var context = data.context || '';
  var hasEmail = /[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/i.test(answer);
  var hasToxic = /\b(kill|bomb|hack|scam)\b/i.test(answer);
  var ansW = new Set((answer.toLowerCase().match(/\b\w+\b/g) || []));
  var ctxW = new Set((context.toLowerCase().match(/\b\w+\b/g) || []));
  var overlap = Array.from(ansW).filter(function(w) { return ctxW.has(w); }).length;
  var faith = ansW.size ? Math.min(1, overlap / ansW.size) : 0.5;
  return {
    timestamp: new Date().toISOString(), function: '[direct paste]',
    framework: state.framework, framework_name: state.frameworkName, model: 'lightweight',
    audit_fast: { passed: !hasEmail && !hasToxic,
      scores: { pii_clean: hasEmail ? 0 : 1, toxicity_safe: hasToxic ? 0 : 1, faithfulness: faith },
      violations: { pii_types: hasEmail ? ['email'] : [], toxicity_categories: hasToxic ? ['detected'] : [] } },
    audit_report: { policy: state.framework, sections: [{ section_id: 'Fast Audit', stages: [
      { stage: 'PII Check',    final_score: hasEmail ? 0.0 : 1.0, passed: !hasEmail,   threshold: 1.0, history: [] },
      { stage: 'Toxicity',     final_score: hasToxic ? 0.0 : 1.0, passed: !hasToxic,   threshold: 1.0, history: [] },
      { stage: 'Faithfulness', final_score: faith,                 passed: faith >= 0.5, threshold: 0.5, history: [] },
    ]}] },
  };
}

// ── Health ────────────────────────────────────────────────────────────────────
function checkHealth() {
  fetch('/api/health').then(function(r) {
    document.getElementById('status-text').textContent = r.ok ? 'Control Plane Online' : 'Degraded';
    document.getElementById('status-dot').style.background = r.ok ? 'var(--green)' : 'var(--amber)';
  }).catch(function() {
    document.getElementById('status-text').textContent = 'Offline';
    document.getElementById('status-dot').style.background = 'var(--red)';
  });
}

checkHealth();
setInterval(checkHealth, 30000);

window.goStep          = goStep;
window.selectOption    = selectOption;
window.selectFramework = selectFramework;
window.startAudit      = startAudit;
window.downloadReport  = downloadReport;
window.copyCode        = copyCode;
