const objectiveSelect = document.getElementById('objective');
const numVarsInput = document.getElementById('numVars');
const numRestrictionsInput = document.getElementById('numRestrictions');
const inputArea = document.getElementById('inputArea');
const results = document.getElementById('results');
const message = document.getElementById('message');

function showMessage(text, type = 'ok') {
  message.textContent = text;
  message.className = `message ${type}`;
}

function clearMessage() {
  message.className = 'message hidden';
  message.textContent = '';
}

function getAutoSign() {
  return objectiveSelect.value === 'max' ? '<=' : '>=';
}

function updateAutoSigns() {
  const sign = getAutoSign();

  document.querySelectorAll('.sign-badge').forEach(el => {
    el.textContent = sign;
  });
}

function normalizeNumber(value) {
  const clean = String(value).trim();

  if (clean === '') {
    return '0';
  }

  return clean;
}

function buildInputs() {
  clearMessage();
  results.innerHTML = '';

  const n = Number(numVarsInput.value);
  const m = Number(numRestrictionsInput.value);

  if (!Number.isInteger(n) || !Number.isInteger(m) || n < 1 || m < 1 || n > 10 || m > 10) {
    showMessage('Usa valores entre 1 y 10 para variables y restricciones.', 'error');
    return;
  }

  inputArea.style.setProperty('--vars', n);

  const autoSign = getAutoSign();

  let html = '';

  html += '<h3>Función objetivo Z</h3>';
  html += '<div class="objective-row">';
  html += '<div class="row-title">Z =</div>';

  for (let j = 0; j < n; j++) {
    html += `
      <label class="input-with-name compact coef-field">
        <input class="coef-z" value="" placeholder="0" data-j="${j}">
        <span>x${j + 1}</span>
      </label>
    `;
  }

  html += '</div>';

  html += '<h3>Restricciones</h3>';

  for (let i = 0; i < m; i++) {
    html += `<div class="restriction-row" data-i="${i}">`;
    html += `<div class="row-title">R${i + 1}</div>`;

    for (let j = 0; j < n; j++) {
      html += `
        <label class="input-with-name compact coef-field">
          <input class="coef-a" value="" placeholder="0" data-i="${i}" data-j="${j}">
          <span>x${j + 1}</span>
        </label>
      `;
    }

    html += `
      <div class="sign-display">
        <span class="sign-badge" data-i="${i}">${autoSign}</span>
      </div>
    `;

    html += `
      <label class="compact rhs-field">
        <input class="rhs" value="" placeholder="0" data-i="${i}">
      </label>
    `;

    html += '</div>';
  }

  inputArea.innerHTML = html;
}

function clearData() {
  document.querySelectorAll('.coef-z, .coef-a, .rhs').forEach(input => {
    input.value = '';
  });

  results.innerHTML = '';
  clearMessage();
  updateAutoSigns();

  showMessage('Datos limpiados. Los campos vacíos se tomarán como 0.', 'ok');
}

function setExampleImage() {
  objectiveSelect.value = 'max';
  numVarsInput.value = 3;
  numRestrictionsInput.value = 3;

  buildInputs();

  setZ([3, 4, 5]);

  setRestriction(0, [3, 1, 5], 150);
  setRestriction(1, [1, 4, 1], 120);
  setRestriction(2, [2, 0, 2], 105);

  updateAutoSigns();
}

function setExampleGraph() {
  objectiveSelect.value = 'max';
  numVarsInput.value = 2;
  numRestrictionsInput.value = 3;

  buildInputs();

  setZ([3, 5]);

  setRestriction(0, [1, 0], 4);
  setRestriction(1, [0, 2], 12);
  setRestriction(2, [3, 2], 18);

  updateAutoSigns();
}

function setZ(values) {
  document.querySelectorAll('.coef-z').forEach((input, j) => {
    input.value = values[j] ?? '';
  });
}

function setRestriction(i, values, rhs) {
  values.forEach((value, j) => {
    const input = document.querySelector(`.coef-a[data-i="${i}"][data-j="${j}"]`);

    if (input) {
      input.value = value;
    }
  });

  const rhsInput = document.querySelector(`.rhs[data-i="${i}"]`);

  if (rhsInput) {
    rhsInput.value = rhs;
  }
}

function collectPayload() {
  const n = Number(numVarsInput.value);
  const m = Number(numRestrictionsInput.value);

  const c = Array.from({ length: n }, (_, j) => {
    const input = document.querySelector(`.coef-z[data-j="${j}"]`);
    return normalizeNumber(input.value);
  });

  const A = [];
  const signs = [];
  const b = [];

  const autoSign = getAutoSign();

  for (let i = 0; i < m; i++) {
    const row = [];

    for (let j = 0; j < n; j++) {
      const input = document.querySelector(`.coef-a[data-i="${i}"][data-j="${j}"]`);
      row.push(normalizeNumber(input.value));
    }

    const rhsInput = document.querySelector(`.rhs[data-i="${i}"]`);

    A.push(row);
    signs.push(autoSign);
    b.push(normalizeNumber(rhsInput.value));
  }

  return {
    objective: objectiveSelect.value,
    c,
    A,
    signs,
    b
  };
}

async function solve() {
  clearMessage();
  results.innerHTML = '<section class="card"><b>Resolviendo...</b></section>';

  try {
    const response = await fetch('/solve', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(collectPayload())
    });

    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || 'No se pudo resolver el modelo.');
    }

    renderResults(data);

  } catch (error) {
    results.innerHTML = '';
    showMessage(error.message, 'error');
  }
}

function renderResults(data) {
  let html = '';

  html += '<section class="summary-box">';
  html += '<h2>Resumen del modelo</h2>';

  html += '<div class="model-preview">';
  html += `<p><b>${escapeHtml(data.model.objective)}</b></p>`;

  data.model.constraints.forEach(c => {
    html += `<p>${escapeHtml(c)}</p>`;
  });

  html += `<p>${escapeHtml(data.model.note)}</p>`;
  html += '</div>';

  html += '<h2 style="margin-top:18px">Resultado final</h2>';
  html += '<div class="summary-grid">';

  data.simplex.decision_values.forEach(item => {
    html += `
      <div class="summary-item">
        <span>${item.name}</span>
        <strong>${item.value}</strong>
        <small>Decimal: ${item.decimal}</small>
      </div>
    `;
  });

  html += `
    <div class="summary-item">
      <span>Z ${data.simplex.objective_label}</span>
      <strong>${data.simplex.objective_value.fraction}</strong>
      <small>Decimal: ${data.simplex.objective_value.decimal}</small>
    </div>
  `;

  html += '</div>';
  html += '</section>';

  html += '<section class="card">';
  html += '<h2>Simplex paso a paso</h2>';

  data.simplex.steps.forEach(step => {
    html += '<div class="step">';
    html += `<h3>${escapeHtml(step.title)}</h3>`;

    if (step.message) {
      html += `<p>${escapeHtml(step.message)}</p>`;
    }

    if (step.items) {
      html += `
        <ul class="info-list">
          ${step.items.map(x => `<li>${escapeHtml(x)}</li>`).join('')}
        </ul>
      `;
    }

    if (step.ratios) {
      html += `
        <ul class="info-list">
          ${step.ratios.map(x => `<li>${escapeHtml(x)}</li>`).join('')}
        </ul>
      `;
    }

    if (step.headers && step.rows) {
      html += renderTable(step);
    }

    if (step.row_operations) {
      html += renderRowOperations(step);
    }

    html += '</div>';
  });

  html += '</section>';

  html += '<section class="card">';
  html += '<h2>Método gráfico</h2>';
  html += `<p>${escapeHtml(data.graph.message)}</p>`;

  if (data.graph.available && data.graph.intercepts) {
    html += '<h3>Interceptos</h3>';

    html += `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Restricción</th>
              <th>Ecuación</th>
              <th>Corte x1</th>
              <th>Corte x2</th>
            </tr>
          </thead>
          <tbody>
    `;

    data.graph.intercepts.forEach(r => {
      html += `
        <tr>
          <td>${escapeHtml(r.name)}</td>
          <td>${escapeHtml(r.equation)}</td>
          <td>${escapeHtml(r.x_intercept)}</td>
          <td>${escapeHtml(r.y_intercept)}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;
  }

  if (data.graph.available && data.graph.vertices && data.graph.vertices.length) {
    html += '<h3>Vértices factibles y evaluación de Z</h3>';

    html += `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>x1</th>
              <th>x2</th>
              <th>Evaluación</th>
              <th>Z decimal</th>
            </tr>
          </thead>
          <tbody>
    `;

    data.graph.vertices.forEach(v => {
      html += `
        <tr>
          <td>${escapeHtml(v.x1)}</td>
          <td>${escapeHtml(v.x2)}</td>
          <td>${escapeHtml(v.formula)}</td>
          <td>${escapeHtml(v.z_decimal)}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
        </table>
      </div>
    `;

    html += `
      <p>
        <b>Mejor punto:</b>
        x1 = ${escapeHtml(data.graph.best.x1)},
        x2 = ${escapeHtml(data.graph.best.x2)},
        Z = ${escapeHtml(data.graph.best.z)}
      </p>
    `;

    if (data.graph.svg) {
      html += `<div class="graph-box">${data.graph.svg}</div>`;
    }
  }

  html += '</section>';

  results.innerHTML = html;
  showMessage('Ejercicio resuelto correctamente.', 'ok');
}

function renderTable(step) {
  let html = '';

  html += '<div class="table-wrap">';
  html += '<table>';
  html += '<thead>';
  html += '<tr>';
  html += '<th>Base</th>';

  step.headers.forEach(h => {
    html += `<th>${escapeHtml(h)}</th>`;
  });

  html += '<th>CR</th>';
  html += '</tr>';
  html += '</thead>';
  html += '<tbody>';

  step.rows.forEach(row => {
    html += '<tr>';
    html += `<td>${escapeHtml(row.base)}</td>`;

    row.values.forEach(v => {
      html += `<td>${escapeHtml(v)}</td>`;
    });

    html += `<td>${escapeHtml(row.rhs)}</td>`;
    html += '</tr>';
  });

  html += '</tbody>';
  html += '</table>';
  html += '</div>';

  return html;
}

function renderRowOperations(step) {
  let html = '';

  html += '<div class="row-ops-block">';

  step.row_operations.forEach(op => {
    html += '<div class="row-op-card">';

    if (op.type === 'pivot_row') {
      html += `<h4>Fila entrante: ${escapeHtml(op.target)}</h4>`;
      html += `<p><b>${escapeHtml(op.formula)}</b></p>`;

      html += `
        <div class="mini-table-wrap">
          <table class="mini-table">
            <thead>
              <tr>
                <th>Tipo</th>
                ${step.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}
                <th>CR</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>FV</td>
                ${op.old_row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}
              </tr>
              <tr>
                <td>FE</td>
                ${op.new_row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}
              </tr>
            </tbody>
          </table>
        </div>
      `;
    } else {
      html += `<h4>Actualización de fila: ${escapeHtml(op.target)}</h4>`;
      html += `<p><b>${escapeHtml(op.formula)}</b></p>`;

      html += `
        <div class="mini-table-wrap">
          <table class="mini-table">
            <thead>
              <tr>
                <th>Tipo</th>
                ${step.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}
                <th>CR</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>FV</td>
                ${op.old_row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}
              </tr>
              <tr>
                <td>FE</td>
                ${op.entering_row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}
              </tr>
              <tr>
                <td>FN</td>
                ${op.new_row.map(v => `<td>${escapeHtml(v)}</td>`).join('')}
              </tr>
            </tbody>
          </table>
        </div>
      `;
    }

    html += '</div>';
  });

  html += '</div>';

  return html;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

document.getElementById('buildBtn').addEventListener('click', buildInputs);
document.getElementById('exampleImageBtn').addEventListener('click', setExampleImage);
document.getElementById('exampleGraphBtn').addEventListener('click', setExampleGraph);
document.getElementById('solveBtn').addEventListener('click', solve);
document.getElementById('clearBtn').addEventListener('click', clearData);

objectiveSelect.addEventListener('change', () => {
  updateAutoSigns();
});

buildInputs();
setExampleImage();