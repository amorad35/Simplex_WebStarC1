from fractions import Fraction
from itertools import combinations
import math


def F(value):
    """Convierte enteros, decimales o fracciones en Fraction."""
    text = str(value).strip().replace(',', '.')
    if text == '':
        return Fraction(0)
    return Fraction(text)


def fmt(value):
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fmt_dec(value, nd=4):
    return f"{float(Fraction(value)):.{nd}f}"

def row_to_fmt_list(row):
    return [fmt(v) for v in row]


def build_row_operation_detail(base_name, old_row, factor, entering_row, new_row, is_z=False):
    if factor == 0:
        formula = f"{base_name}: la fila no cambia porque el coeficiente en la columna pivote es 0."
    elif factor > 0:
        formula = f"Fila nueva {base_name} = FV - {fmt(factor)} * FE"
    else:
        formula = f"Fila nueva {base_name} = FV + {fmt(-factor)} * FE"

    return {
        'target': 'Z' if is_z else base_name,
        'factor': fmt(factor),
        'formula': formula,
        'old_row': row_to_fmt_list(old_row),
        'entering_row': row_to_fmt_list(entering_row),
        'new_row': row_to_fmt_list(new_row),
        'is_z': is_z
    }

def parse_model(payload):
    objective = str(payload.get('objective', 'max')).lower().strip()

    if objective not in ('max', 'min'):
        raise ValueError('El objetivo debe ser max o min.')

    c = [F(v) for v in payload.get('c', [])]
    A = [[F(v) for v in row] for row in payload.get('A', [])]
    signs = [str(s).strip() for s in payload.get('signs', [])]
    b = [F(v) for v in payload.get('b', [])]

    if not c:
        raise ValueError('Debe ingresar al menos una variable.')

    if not A:
        raise ValueError('Debe ingresar al menos una restricción.')

    if len(A) != len(signs) or len(A) != len(b):
        raise ValueError('La cantidad de restricciones no coincide con signos o recursos.')

    for i, row in enumerate(A, start=1):
        if len(row) != len(c):
            raise ValueError(f'La restricción {i} no tiene la misma cantidad de variables que Z.')

    for s in signs:
        if s not in ('<=', '>=', '='):
            raise ValueError('Los signos válidos son <=, >= o =.')

    return A, signs, b, c, objective


def model_text(A, signs, b, c, objective):
    tipo = 'Maximizar' if objective == 'max' else 'Minimizar'

    z_terms = []
    for j, coef in enumerate(c):
        z_terms.append(f"{fmt(coef)}x{j + 1}")

    restricciones = []

    for i, row in enumerate(A):
        terms = []
        for j, coef in enumerate(row):
            terms.append(f"{fmt(coef)}x{j + 1}")

        restricciones.append(
            f"R{i + 1}: " + ' + '.join(terms) + f" {signs[i]} {fmt(b[i])}"
        )

    return {
        'objective': f"{tipo} Z = " + ' + '.join(z_terms),
        'constraints': restricciones,
        'note': 'Condición: x1, x2, ... >= 0'
    }


def table_to_dict(table, names, base, title, pivot=None):
    rows = []

    for i, row in enumerate(table[:-1]):
        base_name = names[base[i]] if i < len(base) and base[i] < len(names) else '-'

        rows.append({
            'base': base_name,
            'values': [fmt(v) for v in row[:-1]],
            'rhs': fmt(row[-1])
        })

    rows.append({
        'base': 'Z',
        'values': [fmt(v) for v in table[-1][:-1]],
        'rhs': fmt(table[-1][-1])
    })

    return {
        'title': title,
        'headers': names[:],
        'rows': rows,
        'pivot': pivot
    }


def prepare_two_phase(A, signs, b, c, objective):
    m = len(A)
    n = len(c)

    A = [row[:] for row in A]
    b = b[:]
    signs = signs[:]

    # Si el lado derecho queda negativo, se cambia toda la restricción.
    for i in range(m):
        if b[i] < 0:
            A[i] = [-v for v in A[i]]
            b[i] = -b[i]

            if signs[i] == '<=':
                signs[i] = '>='
            elif signs[i] == '>=':
                signs[i] = '<='

    names = [f'x{j + 1}' for j in range(n)]
    rows = [row[:] for row in A]
    base = []
    artificial = []
    added = []

    for i, sign in enumerate(signs):
        if sign == '<=':
            for r in rows:
                r.append(Fraction(0))

            rows[i][-1] = Fraction(1)
            names.append(f's{i + 1}')
            base.append(len(names) - 1)
            added.append(f'R{i + 1}: se agrega variable de holgura s{i + 1}.')

        elif sign == '>=':
            for r in rows:
                r.append(Fraction(0))

            rows[i][-1] = Fraction(-1)
            names.append(f'e{i + 1}')

            for r in rows:
                r.append(Fraction(0))

            rows[i][-1] = Fraction(1)
            names.append(f'a{i + 1}')

            base.append(len(names) - 1)
            artificial.append(len(names) - 1)

            added.append(f'R{i + 1}: se agrega exceso e{i + 1} y artificial a{i + 1}.')

        elif sign == '=':
            for r in rows:
                r.append(Fraction(0))

            rows[i][-1] = Fraction(1)
            names.append(f'a{i + 1}')

            base.append(len(names) - 1)
            artificial.append(len(names) - 1)

            added.append(f'R{i + 1}: se agrega variable artificial a{i + 1}.')

    table_no_z = [rows[i] + [b[i]] for i in range(m)]
    total_vars = len(names)

    # Fase 1: Max W = - suma de artificiales
    c1 = [Fraction(0)] * total_vars
    for idx in artificial:
        c1[idx] = Fraction(-1)

    # Fase 2: función objetivo original
    # Para minimización se convierte internamente a maximización multiplicando por -1.
    c2 = [Fraction(0)] * total_vars
    for j in range(n):
        c2[j] = c[j] if objective == 'max' else -c[j]

    return table_no_z, names, base, artificial, c1, c2, n, added


def build_objective_row(table_no_z, base, c):
    cols = len(table_no_z[0])

    zrow = [-c[j] for j in range(cols - 1)] + [Fraction(0)]

    for i, basic in enumerate(base):
        cb = c[basic]

        if cb != 0:
            for j in range(cols):
                zrow[j] += cb * table_no_z[i][j]

    return zrow


def simplex_iterations(table, names, base, title, steps):
    steps.append(table_to_dict(table, names, base, f'{title} - tabla inicial'))

    iteration = 0

    while True:
        z = table[-1]
        coefficients = z[:-1]

        negative_cols = [j for j, value in enumerate(coefficients) if value < 0]

        if not negative_cols:
            steps.append({
                'title': f'{title} - criterio de parada',
                'message': 'No hay coeficientes negativos en la fila Z. La tabla es óptima para esta fase.'
            })
            break

        # Columna pivote: el coeficiente más negativo de la fila Z
        pivot_col = min(negative_cols, key=lambda j: coefficients[j])

        ratios = []
        ratio_text = []

        for i, row in enumerate(table[:-1]):
            if row[pivot_col] > 0:
                ratio = row[-1] / row[pivot_col]
                ratios.append((ratio, i))
                ratio_text.append(
                    f"{names[base[i]]}: {fmt(row[-1])} / {fmt(row[pivot_col])} = {fmt(ratio)}"
                )
            else:
                ratio_text.append(
                    f"{names[base[i]]}: no aplica porque la columna pivote no es positiva"
                )

        if not ratios:
            raise ValueError('El problema es no acotado: no existe fila pivote válida.')

        _, pivot_row = min(ratios, key=lambda item: (item[0], item[1]))

        pivot = table[pivot_row][pivot_col]
        leaving = names[base[pivot_row]]
        entering = names[pivot_col]

        iteration += 1

        steps.append({
            'title': f'{title} - iteración {iteration}',
            'message': f'Entra {entering}, sale {leaving}, pivote = {fmt(pivot)}.',
            'ratios': ratio_text
        })

        # Guardamos copia de la tabla antes de modificarla
        old_table = [row[:] for row in table]

        # Fila entrante vieja
        old_pivot_row = old_table[pivot_row][:]

        # FE = fila pivote / pivote
        new_pivot_row = [v / pivot for v in old_pivot_row]

        row_operations = []

        # Paso 1: detalle de la fila entrante
        row_operations.append({
            'type': 'pivot_row',
            'target': entering,
            'leaving': leaving,
            'pivot': fmt(pivot),
            'formula': f"Fila nueva {entering} = FV / pivote = fila vieja {leaving} / {fmt(pivot)}",
            'old_row': row_to_fmt_list(old_pivot_row),
            'new_row': row_to_fmt_list(new_pivot_row)
        })

        # Reemplazamos la fila pivote
        table[pivot_row] = new_pivot_row[:]

        # Paso 2: actualizar las demás filas
        for i in range(len(table)):
            if i == pivot_row:
                continue

            old_row = old_table[i][:]
            factor = old_row[pivot_col]

            if factor != 0:
                new_row = [
                    old_row[j] - factor * new_pivot_row[j]
                    for j in range(len(old_row))
                ]
            else:
                new_row = old_row[:]

            table[i] = new_row[:]

            if i == len(table) - 1:
                base_name = 'Z'
                is_z = True
            else:
                base_name = names[base[i]]
                is_z = False

            row_operations.append(
                build_row_operation_detail(
                    base_name=base_name,
                    old_row=old_row,
                    factor=factor,
                    entering_row=new_pivot_row,
                    new_row=new_row,
                    is_z=is_z
                )
            )

        # Cambiamos la base
        base[pivot_row] = pivot_col

        steps.append({
            'title': f'{title} - operaciones fila por fila {iteration}',
            'message': f'Se calcula primero la fila entrante {entering} y luego se actualizan las demás filas con respecto a FE.',
            'headers': names[:],
            'row_operations': row_operations
        })

        steps.append(table_to_dict(
            table,
            names,
            base,
            f'{title} - tabla después de iteración {iteration}',
            pivot={
                'row': pivot_row,
                'col': pivot_col,
                'entering': entering,
                'leaving': leaving,
                'value': fmt(pivot)
            }
        ))

    return table, base


def pivot_row_to_column(table, base, row_index, col_index):
    pivot = table[row_index][col_index]

    table[row_index] = [v / pivot for v in table[row_index]]

    for r in range(len(table)):
        if r == row_index:
            continue

        factor = table[r][col_index]

        if factor != 0:
            table[r] = [
                table[r][k] - factor * table[row_index][k]
                for k in range(len(table[r]))
            ]

    base[row_index] = col_index


def remove_artificial_columns(table, names, base, artificial, c2, steps):
    rows_to_remove = set()

    # Si alguna artificial quedó básica con valor cero, se intenta sacarla de la base.
    for i, basic in enumerate(base[:]):
        if basic in artificial:
            candidates = [
                j for j in range(len(names))
                if j not in artificial and table[i][j] != 0
            ]

            if candidates:
                pivot_row_to_column(table, base, i, candidates[0])
                steps.append({
                    'title': 'Fase 1 - limpieza',
                    'message': f'Se pivotea la fila {i + 1} para retirar una variable artificial de la base.'
                })

            elif table[i][-1] == 0:
                rows_to_remove.add(i)
                steps.append({
                    'title': 'Fase 1 - limpieza',
                    'message': f'La fila {i + 1} es redundante y se elimina.'
                })

            else:
                raise ValueError('No se pudo retirar una variable artificial. El modelo no es factible.')

    if rows_to_remove:
        table = [row for i, row in enumerate(table) if i not in rows_to_remove]
        base = [basic for i, basic in enumerate(base) if i not in rows_to_remove]

    keep = [j for j in range(len(names)) if j not in artificial]
    mapping = {old: new for new, old in enumerate(keep)}

    new_names = [names[j] for j in keep]
    new_c2 = [c2[j] for j in keep]
    new_table = [[row[j] for j in keep] + [row[-1]] for row in table]
    new_base = [mapping[basic] for basic in base]

    return new_table, new_names, new_base, new_c2


def solve_simplex(A, signs, b, c, objective='max'):
    steps = []

    table_no_z, names, base, artificial, c1, c2, n_original, added = prepare_two_phase(
        A,
        signs,
        b,
        c,
        objective
    )

    steps.append({
        'title': 'Forma estándar',
        'message': 'Se agregan variables de holgura, exceso o artificiales según el signo de cada restricción.',
        'items': added
    })

    if artificial:
        table = [row[:] for row in table_no_z]
        table.append(build_objective_row(table, base, c1))

        steps.append({
            'title': 'Fase 1',
            'message': 'Como hay restricciones >= o =, primero se eliminan las variables artificiales.'
        })

        table, base = simplex_iterations(table, names, base, 'Fase 1', steps)

        if table[-1][-1] != 0:
            raise ValueError('El problema no tiene solución factible. La Fase 1 no llegó a valor 0.')

        table_no_z, names, base, c2 = remove_artificial_columns(
            table[:-1],
            names,
            base,
            artificial,
            c2,
            steps
        )

    else:
        table_no_z = [row[:] for row in table_no_z]

    table2 = [row[:] for row in table_no_z]
    table2.append(build_objective_row(table2, base, c2))

    steps.append({
        'title': 'Fase 2',
        'message': 'Se optimiza la función objetivo original.'
    })

    table2, base = simplex_iterations(table2, names, base, 'Fase 2', steps)

    values = {name: Fraction(0) for name in names}

    for i, basic in enumerate(base):
        values[names[basic]] = table2[i][-1]

    transformed_value = table2[-1][-1]
    objective_value = transformed_value if objective == 'max' else -transformed_value

    decision_values = []

    for j in range(n_original):
        name = f'x{j + 1}'
        val = values.get(name, Fraction(0))

        decision_values.append({
            'name': name,
            'value': fmt(val),
            'decimal': fmt_dec(val)
        })

    return {
        'steps': steps,
        'final_table': table_to_dict(table2, names, base, 'Tabla final'),
        'decision_values': decision_values,
        'objective_value': {
            'fraction': fmt(objective_value),
            'decimal': fmt_dec(objective_value)
        },
        'objective_label': 'máxima' if objective == 'max' else 'mínima',
        'all_values': {k: fmt(v) for k, v in values.items()}
    }


def feasible(point, A, signs, b):
    x, y = point

    if x < 0 or y < 0:
        return False

    for row, sign, rhs in zip(A, signs, b):
        value = row[0] * x + row[1] * y

        if sign == '<=' and value > rhs:
            return False

        if sign == '>=' and value < rhs:
            return False

        if sign == '=' and value != rhs:
            return False

    return True


def intersect_lines(l1, l2):
    a1, a2, b1, _ = l1
    d1, d2, b2, _ = l2

    det = a1 * d2 - a2 * d1

    if det == 0:
        return None

    x = (b1 * d2 - a2 * b2) / det
    y = (a1 * b2 - b1 * d1) / det

    return x, y


def graphical_solution(A, signs, b, c, objective='max'):
    if len(c) != 2:
        return {
            'available': False,
            'message': 'El método gráfico tradicional solo se muestra cuando hay exactamente 2 variables. Con 3 o más variables se usa simplex.'
        }

    lines = []
    intercepts = []

    for i, (row, rhs) in enumerate(zip(A, b), start=1):
        a1, a2 = row

        lines.append((a1, a2, rhs, f'R{i}'))

        intercepts.append({
            'name': f'R{i}',
            'equation': f'{fmt(a1)}x1 + {fmt(a2)}x2 {signs[i - 1]} {fmt(rhs)}',
            'x_intercept': 'No aplica' if a1 == 0 else fmt(rhs / a1),
            'y_intercept': 'No aplica' if a2 == 0 else fmt(rhs / a2)
        })

    # Ejes de no negatividad: x1 = 0 y x2 = 0
    lines_with_axes = lines + [
        (Fraction(1), Fraction(0), Fraction(0), 'x1=0'),
        (Fraction(0), Fraction(1), Fraction(0), 'x2=0')
    ]

    candidates = set()

    for l1, l2 in combinations(lines_with_axes, 2):
        p = intersect_lines(l1, l2)

        if p and feasible(p, A, signs, b):
            candidates.add(p)

    candidates = sorted(candidates, key=lambda p: (float(p[0]), float(p[1])))

    if not candidates:
        return {
            'available': True,
            'message': 'No se encontraron vértices factibles.',
            'vertices': [],
            'svg': ''
        }

    vertices = []
    evaluated = []

    for p in candidates:
        z = c[0] * p[0] + c[1] * p[1]

        item = {
            'x1': fmt(p[0]),
            'x2': fmt(p[1]),
            'z': fmt(z),
            'z_decimal': fmt_dec(z),
            'formula': f'Z = {fmt(c[0])}({fmt(p[0])}) + {fmt(c[1])}({fmt(p[1])}) = {fmt(z)}'
        }

        vertices.append(item)
        evaluated.append((p, z))

    best = max(evaluated, key=lambda item: item[1]) if objective == 'max' else min(
        evaluated,
        key=lambda item: item[1]
    )

    svg = build_svg(A, signs, b, candidates, best[0])

    return {
        'available': True,
        'message': 'Método gráfico disponible porque el modelo tiene 2 variables.',
        'intercepts': intercepts,
        'vertices': vertices,
        'best': {
            'x1': fmt(best[0][0]),
            'x2': fmt(best[0][1]),
            'z': fmt(best[1]),
            'z_decimal': fmt_dec(best[1])
        },
        'svg': svg
    }


def build_svg(A, signs, b, vertices, optimum):
    # Gráfico SVG simple, sin librerías externas.
    # No busca ser perfecto, sino útil para clase.
    width, height = 760, 520

    pad_left = 70
    pad_bottom = 60
    pad_top = 30
    pad_right = 30

    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    xs = [float(p[0]) for p in vertices] + [float(optimum[0]), 1.0]
    ys = [float(p[1]) for p in vertices] + [float(optimum[1]), 1.0]

    max_x = max(xs) * 1.25 + 1
    max_y = max(ys) * 1.25 + 1

    # Asegurar que las rectas se vean aunque los vértices estén pequeños.
    for row, rhs in zip(A, b):
        a1, a2 = float(row[0]), float(row[1])
        rr = float(rhs)

        if abs(a1) > 1e-12:
            max_x = max(max_x, abs(rr / a1) * 1.15 + 1)

        if abs(a2) > 1e-12:
            max_y = max(max_y, abs(rr / a2) * 1.15 + 1)

    def sx(x):
        return pad_left + float(x) / max_x * plot_w

    def sy(y):
        return pad_top + plot_h - float(y) / max_y * plot_h

    elements = []

    elements.append(
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img">'
    )

    elements.append('<rect width="100%" height="100%" fill="white"/>')

    elements.append(
        f'<line x1="{pad_left}" y1="{pad_top + plot_h}" '
        f'x2="{pad_left + plot_w}" y2="{pad_top + plot_h}" stroke="black"/>'
    )

    elements.append(
        f'<line x1="{pad_left}" y1="{pad_top}" '
        f'x2="{pad_left}" y2="{pad_top + plot_h}" stroke="black"/>'
    )

    elements.append(
        f'<text x="{pad_left + plot_w - 20}" y="{height - 18}" font-size="14">x1</text>'
    )

    elements.append(
        f'<text x="18" y="{pad_top + 15}" font-size="14">x2</text>'
    )

    # Rejilla sencilla.
    for k in range(1, 6):
        x = pad_left + plot_w * k / 5
        y = pad_top + plot_h * k / 5

        elements.append(
            f'<line x1="{x}" y1="{pad_top}" '
            f'x2="{x}" y2="{pad_top + plot_h}" stroke="#eee"/>'
        )

        elements.append(
            f'<line x1="{pad_left}" y1="{y}" '
            f'x2="{pad_left + plot_w}" y2="{y}" stroke="#eee"/>'
        )

    colors = [
        '#2563eb',
        '#16a34a',
        '#dc2626',
        '#9333ea',
        '#ea580c',
        '#0891b2',
        '#4f46e5'
    ]

    for idx, (row, rhs) in enumerate(zip(A, b), start=1):
        a1, a2 = float(row[0]), float(row[1])
        rr = float(rhs)

        color = colors[(idx - 1) % len(colors)]
        points = []

        # Intersecciones con los bordes del rectángulo visible.
        for x in [0, max_x]:
            if abs(a2) > 1e-12:
                y = (rr - a1 * x) / a2

                if -1e-9 <= y <= max_y + 1e-9:
                    points.append((x, y))

        for y in [0, max_y]:
            if abs(a1) > 1e-12:
                x = (rr - a2 * y) / a1

                if -1e-9 <= x <= max_x + 1e-9:
                    points.append((x, y))

        # Quitar duplicados aproximados.
        unique = []

        for p in points:
            if not any(
                abs(p[0] - q[0]) < 1e-7 and abs(p[1] - q[1]) < 1e-7
                for q in unique
            ):
                unique.append(p)

        if len(unique) >= 2:
            p1, p2 = unique[0], unique[1]

            elements.append(
                f'<line x1="{sx(p1[0])}" y1="{sy(p1[1])}" '
                f'x2="{sx(p2[0])}" y2="{sy(p2[1])}" '
                f'stroke="{color}" stroke-width="2"/>'
            )

            mx = (sx(p1[0]) + sx(p2[0])) / 2
            my = (sy(p1[1]) + sy(p2[1])) / 2

            elements.append(
                f'<text x="{mx + 5}" y="{my - 5}" font-size="13" fill="{color}">R{idx}</text>'
            )

    if len(vertices) >= 3:
        cx = sum(float(p[0]) for p in vertices) / len(vertices)
        cy = sum(float(p[1]) for p in vertices) / len(vertices)

        ordered = sorted(
            vertices,
            key=lambda p: math.atan2(float(p[1]) - cy, float(p[0]) - cx)
        )

        polygon = ' '.join(f'{sx(p[0])},{sy(p[1])}' for p in ordered)

        elements.append(
            f'<polygon points="{polygon}" fill="#60a5fa" opacity="0.18" '
            f'stroke="#2563eb" stroke-dasharray="4 4"/>'
        )

    for p in vertices:
        x = sx(p[0])
        y = sy(p[1])

        elements.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#111827"/>')

        elements.append(
            f'<text x="{x + 7}" y="{y - 7}" font-size="12">({fmt(p[0])},{fmt(p[1])})</text>'
        )

    ox = sx(optimum[0])
    oy = sy(optimum[1])

    elements.append(
        f'<circle cx="{ox}" cy="{oy}" r="7" fill="#f59e0b" stroke="#111827"/>'
    )

    elements.append(
        f'<text x="{ox + 10}" y="{oy + 18}" font-size="13" font-weight="700">Óptimo</text>'
    )

    elements.append('</svg>')

    return ''.join(elements)


def solve_payload(payload):
    A, signs, b, c, objective = parse_model(payload)

    simplex_result = solve_simplex(A, signs, b, c, objective)
    graph = graphical_solution(A, signs, b, c, objective)

    return {
        'ok': True,
        'model': model_text(A, signs, b, c, objective),
        'simplex': simplex_result,
        'graph': graph
    }