"""
reporting.py — Generación de imagen anotada e interpretación textual
=====================================================================
PediScan LCM · Laboratorio de Ciencias del Movimiento · UPC

Funciones:
    draw_annotations   — dibuja trazos, etiquetas y resultados sobre la imagen
    generate_interpretation — genera texto técnico breve por pie y bilateral
"""

import cv2
import numpy as np

from config import (
    COLOR_CONTORNO, COLOR_ANTEPE, COLOR_MEDIOPE, COLOR_RETROPE,
    COLOR_TERCIO, COLOR_CLARKE, COLOR_TEXTO, COLOR_FONDO_TXT,
    CAT_PLANO, CAT_CAVO, CAT_NORMAL, CAT_INDETERMINADO
)
from utils import draw_label


# ─────────────────────────────────────────────────────────────────────────────
# RECORTES INDIVIDUALES POR PIE
# ─────────────────────────────────────────────────────────────────────────────

def crop_foot_images(img_original, annotated, feet_data, padding=30):
    """
    Genera recortes individuales de cada pie, tanto de la imagen original
    como de la imagen anotada. Listos para insertar en Word o PDF.

    Parámetros:
        img_original — imagen BGR original
        annotated    — imagen BGR con anotaciones
        feet_data    — lista de dicts con foot/measurements/metrics
        padding      — margen en px alrededor del bbox del pie

    Retorna:
        lista de dicts:
        [{"side": "derecho", "original": ndarray, "anotada": ndarray}, ...]
    """
    crops = []
    ih, iw = img_original.shape[:2]

    for fd in feet_data:
        x, y, w, h = fd["foot"]["bbox"]
        side       = fd["foot"]["side"]

        # Aplicar padding con límites de imagen
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(iw, x + w + padding)
        y2 = min(ih, y + h + padding)

        crop_orig = img_original[y1:y2, x1:x2].copy()
        crop_ann  = annotated[y1:y2, x1:x2].copy()

        crops.append({
            "side":     side,
            "original": crop_orig,
            "anotada":  crop_ann,
        })

    return crops



def draw_annotations(img_original, feet_data):
    """
    Dibuja todas las anotaciones sobre una copia de la imagen original.

    Trazos por pie:
        - Contorno de la huella (verde)
        - Líneas de división en tercios (oliva)
        - Línea de ancho máximo del antepié / Wa (naranja)
        - Línea de ancho mínimo del mediopié / Wm (rojo)
        - Línea de ancho máximo del retropié / Wh (magenta)
        - Puntos y líneas del ángulo de Clarke (amarillo)
        - Bloque de resultados con categoría final

    Parámetros:
        img_original — imagen BGR original (NumPy array)
        feet_data    — lista de dicts:
                       [{"foot": ..., "measurements": ..., "metrics": ...}, ...]

    Retorna:
        imagen BGR anotada (nueva copia, no modifica el original)
    """
    annotated = img_original.copy()

    for fd in feet_data:
        foot  = fd["foot"]
        meas  = fd["measurements"]
        met   = fd["metrics"]
        side  = foot["side"]
        x, y, w, h = foot["bbox"]

        # ── Contorno del pie ──────────────────────────────────────────────
        cv2.drawContours(annotated, [foot["contour"]], -1,
                         COLOR_CONTORNO, 2, cv2.LINE_AA)

        # ── Líneas de tercios ─────────────────────────────────────────────
        y1 = meas["y_div1"]
        y2 = meas["y_div2"]
        margin = max(5, w // 6)
        cv2.line(annotated, (x + margin, y1), (x + w - margin, y1),
                 COLOR_TERCIO, 1, cv2.LINE_AA)
        cv2.line(annotated, (x + margin, y2), (x + w - margin, y2),
                 COLOR_TERCIO, 1, cv2.LINE_AA)

        # ── Ancho máximo antepié (Wa) — NARANJA ───────────────────────────
        la = meas["line_antepe"]
        if la:
            xi, xd, yl = la
            cv2.line(annotated, (xi, yl), (xd, yl), COLOR_ANTEPE, 2, cv2.LINE_AA)
            # Marcas en los extremos
            cv2.circle(annotated, (xi, yl), 4, COLOR_ANTEPE, -1)
            cv2.circle(annotated, (xd, yl), 4, COLOR_ANTEPE, -1)
            draw_label(annotated, f"Wa={meas['Wa']}px",
                       (xi, yl - 7), COLOR_TEXTO, COLOR_FONDO_TXT)

        # ── Ancho mínimo mediopié (Wm) — ROJO ────────────────────────────
        lm = meas["line_mediope"]
        if lm:
            xi, xd, yl = lm
            cv2.line(annotated, (xi, yl), (xd, yl), COLOR_MEDIOPE, 2, cv2.LINE_AA)
            cv2.circle(annotated, (xi, yl), 4, COLOR_MEDIOPE, -1)
            cv2.circle(annotated, (xd, yl), 4, COLOR_MEDIOPE, -1)
            draw_label(annotated, f"Wm={meas['Wm']}px",
                       (xi, yl - 7), COLOR_TEXTO, COLOR_FONDO_TXT)

        # ── Ancho máximo retropié (Wh) — MAGENTA ─────────────────────────
        lr = meas["line_retrope"]
        if lr:
            xi, xd, yl = lr
            cv2.line(annotated, (xi, yl), (xd, yl), COLOR_RETROPE, 2, cv2.LINE_AA)
            cv2.circle(annotated, (xi, yl), 4, COLOR_RETROPE, -1)
            cv2.circle(annotated, (xd, yl), 4, COLOR_RETROPE, -1)
            draw_label(annotated, f"Wh={meas['Wh']}px",
                       (xi, yl - 7), COLOR_TEXTO, COLOR_FONDO_TXT)

        # ── Ángulo de Clarke — AMARILLO ───────────────────────────────────
        if meas["clarke_pts"]:
            P_fore, P_mid, P_heel = meas["clarke_pts"]

            # Línea base medial: talón → antepié
            cv2.line(annotated, P_heel, P_fore,
                     COLOR_CLARKE, 1, cv2.LINE_AA)
            # Línea al arco
            cv2.line(annotated, P_fore, P_mid,
                     COLOR_CLARKE, 2, cv2.LINE_AA)

            # Puntos clave
            cv2.circle(annotated, P_fore, 6, COLOR_CLARKE, -1)
            cv2.circle(annotated, P_mid,  5, COLOR_CLARKE, -1)
            cv2.circle(annotated, P_heel, 5, COLOR_CLARKE, -1)

            draw_label(annotated,
                       f"Clarke={meas['clarke_angle']}°",
                       (P_fore[0] + 8, P_fore[1]),
                       COLOR_TEXTO, COLOR_FONDO_TXT, font_scale=0.42)

        # ── Bloque de resultados ──────────────────────────────────────────
        _draw_results_block(annotated, foot, meas, met)

    return annotated


def _draw_results_block(img, foot, meas, met):
    """Dibuja el bloque de resultados (métricas + categoría) sobre el pie."""
    x, y, w, h = foot["bbox"]
    side        = foot["side"].upper()
    cat         = met["cat_final"]
    bg_color    = _category_color(cat)

    # Posición: encima del pie si hay espacio, si no debajo
    block_y = y - 75
    if block_y < 5:
        block_y = y + h + 5

    # Título del pie
    draw_label(img, f"PIE {side}",
               (x, block_y),
               (0, 0, 0), bg_color, font_scale=0.55, thickness=2)

    # Líneas de métricas
    lines = [
        f"CSI={met['CSI']}%  [{met['cat_CSI']}]",
        f"SI={met['SI']}     [{met['cat_SI']}]",
        f"Clarke={met['Clarke']}° [{met['cat_Clarke']}]",
        f"AI={met['AI']}      [{met['cat_AI']}]",
        f"=> {cat.upper()}  ({met['concordance']}/4)",
    ]
    for i, line in enumerate(lines):
        draw_label(img, line,
                   (x, block_y + 18 + i * 16),
                   COLOR_TEXTO, COLOR_FONDO_TXT, font_scale=0.40)


def _category_color(category):
    """Devuelve color de fondo BGR según categoría para el bloque de resultados."""
    palette = {
        CAT_PLANO:         (0,  60, 200),   # rojo
        CAT_CAVO:          (180, 50,  0),   # azul oscuro
        CAT_NORMAL:        (30, 140, 30),   # verde
        CAT_INDETERMINADO: (80,  80, 80),   # gris
    }
    return palette.get(category, (80, 80, 80))


# ─────────────────────────────────────────────────────────────────────────────
# INTERPRETACIÓN AUTOMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

def generate_interpretation(feet_data):
    """
    Genera texto de interpretación técnica breve para cada pie.

    El texto es orientativo y prudente:
        - Usa lenguaje de patrón y tendencia, no diagnóstico
        - Indica número de índices concordantes
        - Incluye comparación bilateral si hay dos pies
        - Añade nota metodológica al final

    Retorna string con saltos de línea.
    """
    lines = []

    for fd in feet_data:
        side = fd["foot"]["side"]
        met  = fd["metrics"]
        cat  = met["cat_final"]
        conc = met["concordance"]

        desc = {
            CAT_NORMAL:        "patrón compatible con arco plantar normal",
            CAT_PLANO:         "patrón compatible con pie plano o arco reducido",
            CAT_CAVO:          "patrón compatible con pie cavo o arco elevado",
            CAT_INDETERMINADO: "clasificación discordante entre los índices",
        }.get(cat, cat)

        if cat == CAT_INDETERMINADO:
            msg = (f"Pie {side}: {desc} "
                   f"({conc}/4 índices en categoría más frecuente). "
                   f"Se recomienda revisión manual.")
        else:
            msg = (f"Pie {side}: {desc} "
                   f"({conc}/4 índices concordantes).")

        lines.append(msg)

    # Comparación bilateral
    if len(feet_data) == 2:
        cat_a = feet_data[0]["metrics"]["cat_final"]
        cat_b = feet_data[1]["metrics"]["cat_final"]
        if cat_a != cat_b:
            lines.append("Se observa asimetría en el patrón entre pie derecho e izquierdo.")
        else:
            lines.append("Patrón simétrico entre ambos pies.")

    lines.append(
        "\nNOTA: estas métricas son orientativas (pedígrafía estática, sin escala en cm). "
        "No constituyen diagnóstico clínico."
    )
    return "\n".join(lines)
