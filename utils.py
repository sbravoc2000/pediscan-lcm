"""
utils.py — Funciones auxiliares de PediScan LCM
================================================
Funciones de bajo nivel reutilizadas por processing.py y reporting.py.
"""

import cv2
import numpy as np
import math


# ─────────────────────────────────────────────────────────────────────────────
# Dibujo en imagen
# ─────────────────────────────────────────────────────────────────────────────

def draw_label(img, text, position,
               color_text=(255, 255, 255),
               color_bg=(25, 25, 25),
               font_scale=0.45,
               thickness=1):
    """
    Dibuja texto con rectángulo de fondo sólido para legibilidad sobre la imagen.

    Parámetros:
        img        — imagen BGR (modificada in-place)
        text       — cadena de texto a mostrar
        position   — tupla (x, y) esquina inferior izquierda del texto
        color_text — color del texto en BGR
        color_bg   — color del fondo en BGR
        font_scale — escala de la fuente
        thickness  — grosor del trazo
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = int(position[0]), int(position[1])
    # Rectángulo de fondo
    cv2.rectangle(img,
                  (x - 2, y - th - 4),
                  (x + tw + 4, y + baseline + 2),
                  color_bg, cv2.FILLED)
    # Texto
    cv2.putText(img, text, (x, y), font, font_scale,
                color_text, thickness, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# Geometría angular
# ─────────────────────────────────────────────────────────────────────────────

def angle_between_vectors(p1, vertex, p2):
    """
    Calcula el ángulo (grados) en 'vertex' entre los rayos vertex→p1 y vertex→p2.

    Parámetros:
        p1, p2, vertex — tuplas (x, y)

    Retorna:
        ángulo en grados (0–180), o 0.0 si algún vector tiene magnitud cero.
    """
    v1 = (p1[0] - vertex[0], p1[1] - vertex[1])
    v2 = (p2[0] - vertex[0], p2[1] - vertex[1])

    dot  = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)

    if mag1 < 1e-6 or mag2 < 1e-6:
        return 0.0

    cos_val = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_val))


# ─────────────────────────────────────────────────────────────────────────────
# Operaciones sobre filas de máscara binaria
# ─────────────────────────────────────────────────────────────────────────────

def row_bounds(row):
    """
    Retorna (x_min, x_max) de píxeles activos en una fila 1D, o None si está vacía.
    """
    nonzero = np.where(row > 0)[0]
    if len(nonzero) == 0:
        return None
    return int(nonzero[0]), int(nonzero[-1])


def max_width_in_region(region_mask):
    """Ancho máximo (px) entre todas las filas activas de la región."""
    widths = []
    for row in region_mask:
        b = row_bounds(row)
        if b:
            widths.append(b[1] - b[0])
    return max(widths) if widths else 0


def min_width_nonzero_in_region(region_mask):
    """Ancho mínimo no nulo (px) entre filas activas de la región."""
    widths = []
    for row in region_mask:
        b = row_bounds(row)
        if b:
            w = b[1] - b[0]
            if w > 0:
                widths.append(w)
    return min(widths) if widths else 0


def row_widths_with_positions(region_mask, offset_x, offset_y):
    """
    Retorna lista de (x_izq, x_der, ancho, y_global) para cada fila activa.
    Las coordenadas son absolutas (offset incluido).
    """
    results = []
    for i, row in enumerate(region_mask):
        b = row_bounds(row)
        if b:
            results.append((
                b[0] + offset_x,   # x izquierdo absoluto
                b[1] + offset_x,   # x derecho absoluto
                b[1] - b[0],       # ancho
                i + offset_y       # y global
            ))
    return results


def row_of_max_width(rows):
    """
    De una lista (x_izq, x_der, ancho, y_global), devuelve la fila de ancho máximo.
    Retorna (x_izq, x_der, y_global) o None.
    """
    if not rows:
        return None
    best = max(rows, key=lambda r: r[2])
    return (best[0], best[1], best[3])


def row_of_min_width(rows):
    """
    De una lista (x_izq, x_der, ancho, y_global), devuelve la fila de ancho mínimo no nulo.
    Retorna (x_izq, x_der, y_global) o None.
    """
    nonempty = [r for r in rows if r[2] > 0]
    if not nonempty:
        return None
    best = min(nonempty, key=lambda r: r[2])
    return (best[0], best[1], best[3])


def robust_max_width_in_bbox(region_mask, offset_x, offset_y,
                              img_w, img_h,
                              bbox_w, margin_bbox=3, margin_img=10,
                              trim_px=0):
    """
    Calcula el ancho máximo del antepié de forma robusta, evitando artefactos
    de borde que causan que la línea Wa salga fuera del pie real.

    Problemas que resuelve:
        1. Píxeles sueltos pegados al borde del bounding box (xi==0 o xd==bbox_w)
           causados por la morfología o por el pie tocando el límite de la imagen.
        2. Píxeles pegados al borde global de la imagen (pie cortado en el encuadre).

    Parámetros:
        region_mask   — máscara binaria de la región (antepié)
        offset_x/y    — coordenadas absolutas del origen de la región
        img_w, img_h  — dimensiones globales de la imagen original
        bbox_w        — ancho del bounding box del pie
        margin_bbox   — píxeles de margen desde el borde del bbox a descartar
        margin_img    — píxeles de margen desde el borde global de la imagen
        trim_px       — corrección manual: recorta N px de cada extremo del resultado

    Retorna:
        (xi_abs, xd_abs, ancho, y_global) o None si no hay candidatos
    """
    candidates = []
    for i, row in enumerate(region_mask):
        nz = np.where(row > 0)[0]
        if len(nz) < 2:
            continue
        xi, xd = int(nz[0]), int(nz[-1])
        xi_abs = xi + offset_x
        xd_abs = xd + offset_x

        # Descartar si toca borde del bbox
        if xi <= margin_bbox or xd >= (bbox_w - margin_bbox):
            continue
        # Descartar si toca borde global de imagen
        if xi_abs <= margin_img or xd_abs >= (img_w - margin_img):
            continue

        candidates.append((xi_abs, xd_abs, xd - xi, i + offset_y))

    if not candidates:
        # Fallback sin restricción de borde (solo margen bbox)
        for i, row in enumerate(region_mask):
            nz = np.where(row > 0)[0]
            if len(nz) < 2:
                continue
            xi, xd = int(nz[0]), int(nz[-1])
            candidates.append((xi + offset_x, xd + offset_x,
                                xd - xi, i + offset_y))

    if not candidates:
        return None

    xi_abs, xd_abs, ancho, y_g = max(candidates, key=lambda r: r[2])

    # Aplicar corrección manual de trim
    if trim_px > 0:
        xi_abs = xi_abs + trim_px
        xd_abs = xd_abs - trim_px
        ancho  = max(0, xd_abs - xi_abs)

    return (xi_abs, xd_abs, ancho, y_g)


def centroid_x_of_region(region_mask):
    """
    Retorna la mediana horizontal (centroide-x) de todos los píxeles activos
    en la región. Útil para detectar hacia qué lado se desplaza el arco.
    """
    cols = []
    for row in region_mask:
        nz = np.where(row > 0)[0]
        if len(nz) > 0:
            cols.extend(nz.tolist())
    return float(np.median(cols)) if cols else 0.0
