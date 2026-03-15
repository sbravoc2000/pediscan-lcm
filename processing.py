"""
processing.py — Segmentación y análisis geométrico de huellas plantares
========================================================================
PediScan LCM · Laboratorio de Ciencias del Movimiento · UPC

Flujo principal:
  1. load_image_from_bytes / load_image_from_path
  2. segment_footprint  → máscara binaria global
  3. find_feet          → lista de dicts por pie
  4. extract_measurements → mediciones geométricas por pie
"""

import cv2
import numpy as np
import math

from config import (
    KERNEL_SIZE, MORPH_ITER_CLOSE, MORPH_ITER_OPEN, MIN_CONTOUR_AREA,
    PEDIGRAFO_MODE, GREEN_DIFF_GR, GREEN_DIFF_GB
)
from utils import (
    max_width_in_region, min_width_nonzero_in_region,
    row_widths_with_positions, row_of_max_width, row_of_min_width,
    centroid_x_of_region, angle_between_vectors,
    robust_max_width_in_bbox
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CARGA DE IMAGEN
# ─────────────────────────────────────────────────────────────────────────────

def load_image_from_bytes(uploaded_file):
    """
    Carga imagen desde UploadedFile de Streamlit.
    Retorna imagen BGR como NumPy array.
    """
    uploaded_file.seek(0)
    file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen. Verifica el formato (JPG/PNG).")
    return img


def load_image_from_path(path):
    """Carga imagen desde ruta de archivo."""
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {path}")
    return img


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEGMENTACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def segment_footprint(img, mode=None, invert=False,
                      green_diff_gr=None, green_diff_gb=None):
    """
    Segmenta la huella plantar según el tipo de pedígrafo.

    Modos disponibles (configurable en config.py → PEDIGRAFO_MODE):

    ── Modo "otsu" ──────────────────────────────────────────────────────────────
    Para pedígrafía clásica: huella OSCURA sobre fondo CLARO (tinta/papel).
    Pasos: escala de grises → suavizado → umbral Otsu → morfología.
    Activar invert=True para huella clara sobre fondo oscuro.

    ── Modo "green" (pedígrafo LED) ─────────────────────────────────────────────
    Para pedígrafos con iluminación LED verde (como el del LCM).
    La huella presiona sobre el vidrio y la zona de contacto se ilumina en
    verde brillante (canal G >> canal R y canal G > canal B).
    El fondo y la piel visible tienen predominancia azul-cián (B >= G).

    Criterio de segmentación verde:
        (G - R) > GREEN_DIFF_GR  AND  (G - B) > GREEN_DIFF_GB
    → Detecta exclusivamente el verde del LED sin confundir con piel ni fondo.

    Parámetros ajustables en config.py:
        GREEN_DIFF_GR  → reducir si se pierde huella; aumentar si entra fondo
        GREEN_DIFF_GB  → idem
        KERNEL_SIZE, MORPH_ITER_CLOSE, MORPH_ITER_OPEN → morfología

    Retorna:
        mask — uint8, 255 = huella, 0 = fondo
    """
    # Prioridad: parámetro explícito > config.py
    active_mode    = mode       if mode       is not None else PEDIGRAFO_MODE
    active_diff_gr = green_diff_gr if green_diff_gr is not None else GREEN_DIFF_GR
    active_diff_gb = green_diff_gb if green_diff_gb is not None else GREEN_DIFF_GB

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (KERNEL_SIZE, KERNEL_SIZE)
    )

    if active_mode == "green":
        # ── Segmentación por canal verde (pedígrafo LED) ──────────────────
        b_ch = img[:, :, 0].astype(np.float32)
        g_ch = img[:, :, 1].astype(np.float32)
        r_ch = img[:, :, 2].astype(np.float32)

        green_mask = (
            ((g_ch - r_ch) > active_diff_gr) &
            ((g_ch - b_ch) > active_diff_gb)
        ).astype(np.uint8) * 255

        closed = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel,
                                   iterations=MORPH_ITER_CLOSE)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel,
                                   iterations=MORPH_ITER_OPEN)
        return opened

    else:
        # ── Segmentación Otsu (pedígrafía tinta/papel) ────────────────────
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        flag = cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        if invert:
            flag = cv2.THRESH_BINARY + cv2.THRESH_OTSU

        _, thresh = cv2.threshold(blurred, 0, 255, flag)
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel,
                                   iterations=MORPH_ITER_CLOSE)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel,
                                   iterations=MORPH_ITER_OPEN)
        return opened


# ─────────────────────────────────────────────────────────────────────────────
# 3. DETECCIÓN Y ASIGNACIÓN DE PIES
# ─────────────────────────────────────────────────────────────────────────────

def find_feet(mask, swap_sides=False):
    """
    Detecta los dos pies en la máscara binaria global.

    Estrategia:
        - Detectar contornos externos
        - Filtrar por área mínima (MIN_CONTOUR_AREA)
        - Tomar los dos de mayor área
        - Asignar lado por posición horizontal:
          centroide-x menor → izquierdo, mayor → derecho
          (vista estándar desde abajo; usar swap_sides si la imagen es desde arriba)

    Retorna:
        lista de dicts con {contour, bbox, mask, cx, side}
        ordenados [izquierdo, derecho]
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)

    valid = [c for c in contours if cv2.contourArea(c) >= MIN_CONTOUR_AREA]
    if not valid:
        raise ValueError(
            "No se detectaron huellas en la imagen.\n"
            "Verifica: contraste suficiente, fondo claro, sin saturación."
        )

    # Ordenar por área descendente y tomar los dos mayores
    valid = sorted(valid, key=cv2.contourArea, reverse=True)[:2]

    feet = []
    for cnt in valid:
        x, y, w, h = cv2.boundingRect(cnt)

        # Máscara individual (solo este contorno, relleno)
        foot_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(foot_mask, [cnt], -1, 255, cv2.FILLED)

        feet.append({
            "contour": cnt,
            "bbox":    (x, y, w, h),
            "mask":    foot_mask,
            "cx":      x + w // 2,
        })

    # Ordenar por posición horizontal
    feet = sorted(feet, key=lambda f: f["cx"])

    # Asignar lados
    if len(feet) == 2:
        if not swap_sides:
            feet[0]["side"] = "izquierdo"
            feet[1]["side"] = "derecho"
        else:
            feet[0]["side"] = "derecho"
            feet[1]["side"] = "izquierdo"
        # Re-ordenar para que [0]=derecho, [1]=izquierdo (convención clínica)
        feet = sorted(feet, key=lambda f: f["side"])  # 'd' < 'i' → derecho primero
    else:
        feet[0]["side"] = "único"

    return feet


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXTRACCIÓN DE MEDICIONES POR PIE
# ─────────────────────────────────────────────────────────────────────────────

def extract_measurements(foot, heel_at_bottom=True,
                          img_w=9999, img_h=9999, trim_wa_px=0):
    """
    Divide la huella en tres tercios longitudinales y extrae mediciones.

    División del bounding box (eje vertical, eje Y):
        heel_at_bottom=True  (defecto):
            tercio superior → antepié  (metatarso + dedos)
            tercio medio    → mediopié (arco longitudinal)
            tercio inferior → retropié (talón)

        heel_at_bottom=False:
            se invierten antepié y retropié

    Todas las medidas internas están en píxeles.
    Los índices (CSI, SI, AI) son adimensionales (razones), por lo tanto
    invariantes a escala y válidos sin calibración en cm.

    Retorna dict con mediciones geométricas y posiciones para dibujo.
    """
    mask = foot["mask"]
    x, y, w, h = foot["bbox"]

    # Recortar la huella de la máscara global
    foot_region = mask[y:y + h, x:x + w]

    # Índices de división en tercios
    t1 = h // 3
    t2 = 2 * (h // 3)

    if heel_at_bottom:
        reg_antepe  = foot_region[:t1,    :]
        reg_mediope = foot_region[t1:t2,  :]
        reg_retrope = foot_region[t2:,    :]
        oy_antepe   = y
        oy_mediope  = y + t1
        oy_retrope  = y + t2
    else:
        # Talón arriba: invertir
        reg_retrope = foot_region[:t1,    :]
        reg_mediope = foot_region[t1:t2,  :]
        reg_antepe  = foot_region[t2:,    :]
        oy_retrope  = y
        oy_mediope  = y + t1
        oy_antepe   = y + t2

    # ── Ancho máximo antepié (Wa) — con detección robusta de borde ───────────
    # Usa robust_max_width_in_bbox para evitar líneas que salgan del pie real
    wa_result = robust_max_width_in_bbox(
        reg_antepe,
        offset_x=x, offset_y=oy_antepe,
        img_w=img_w, img_h=img_h,
        bbox_w=w,
        trim_px=trim_wa_px
    )
    if wa_result:
        wa_xi, wa_xd, Wa, wa_y = wa_result
        line_antepe = (wa_xi, wa_xd, wa_y)
    else:
        Wa = max_width_in_region(reg_antepe)
        line_antepe = row_of_max_width(
            row_widths_with_positions(reg_antepe, x, oy_antepe)
        )

    # ── Ancho mínimo mediopié (Wm) ────────────────────────────────────────────
    Wm = min_width_nonzero_in_region(reg_mediope)

    # ── Ancho máximo retropié (Wh) ────────────────────────────────────────────
    Wh = max_width_in_region(reg_retrope)

    # ── Áreas para Arch Index ─────────────────────────────────────────────────
    # Según Cavanagh & Rodgers (1987):
    #   - Se excluye el tercio de dedos (antepié) del denominador
    #   - AI = área_mediopié / (área_mediopié + área_retropié)
    area_antepe  = int(np.sum(reg_antepe  > 0))
    area_mediope = int(np.sum(reg_mediope > 0))
    area_retrope = int(np.sum(reg_retrope > 0))
    area_sin_dedos = area_mediope + area_retrope   # denominador del AI

    # ── Posiciones absolutas para dibujo de líneas ────────────────────────────
    y_div1 = y + t1   # línea divisoria antepié / mediopié
    y_div2 = y + t2   # línea divisoria mediopié / retropié

    rows_mediope = row_widths_with_positions(reg_mediope, x, oy_mediope)
    rows_retrope = row_widths_with_positions(reg_retrope, x, oy_retrope)

    line_mediope = row_of_min_width(rows_mediope)
    line_retrope = row_of_max_width(rows_retrope)

    # ── Ángulo de Clarke ──────────────────────────────────────────────────────
    clarke_angle, clarke_pts = _compute_clarke_angle(
        reg_antepe, reg_mediope, reg_retrope,
        x, oy_antepe, oy_mediope, oy_retrope,
        foot["side"]
    )

    return {
        # Medidas en píxeles (solo uso interno / técnico)
        "Wa":             Wa,
        "Wm":             Wm,
        "Wh":             Wh,
        "L":              h,
        "area_antepe":    area_antepe,
        "area_mediope":   area_mediope,
        "area_retrope":   area_retrope,
        "area_sin_dedos": area_sin_dedos,
        # Coordenadas para dibujo
        "y_div1":         y_div1,
        "y_div2":         y_div2,
        "bbox":           (x, y, w, h),
        "line_antepe":    line_antepe,     # (x_izq, x_der, y) o None
        "line_mediope":   line_mediope,
        "line_retrope":   line_retrope,
        # Clarke
        "clarke_angle":   clarke_angle,
        "clarke_pts":     clarke_pts,      # (P_fore, P_mid, P_heel) o None
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. ÁNGULO DE CLARKE — implementación geométrica digital
# ─────────────────────────────────────────────────────────────────────────────

def _compute_clarke_angle(reg_antepe, reg_mediope, reg_retrope,
                          ox, oy_ante, oy_mid, oy_retro, side_label):
    """
    Implementación digital del ángulo de Clarke.

    Definición implementada:
    ─────────────────────────────────────────────────────────────────────────
    El arco longitudinal crea una concavidad en el borde MEDIAL del pie.
    En la pedígrafía, esto produce un estrechamiento del mediopié en el lado
    medial (el arco no deja huella porque se eleva del suelo).

    Se detecta automáticamente el lado del arco comparando el desplazamiento
    del centroide-x del mediopié respecto al antepié/retropié:
        - Si cx_medio > cx_promedio_extremos: contacto del mediopié está a la
          izquierda → arco en el lado DERECHO de la imagen
        - Si cx_medio < cx_promedio_extremos: arco en el lado IZQUIERDO

    Puntos clave:
        P_fore — punto más medial del antepié (borde del arco, antepié)
        P_mid  — punto más medial del mediopié (donde el arco empieza a levantar)
        P_heel — punto más medial del retropié

    El ángulo se mide en el vértice P_fore (antepié medial), entre:
        ray 1: P_fore → P_heel  (hacia el talón, a lo largo del borde medial)
        ray 2: P_fore → P_mid   (hacia la concavidad del arco)

    Comportamiento esperado:
        pie plano → P_mid casi alineado con P_heel → ángulo pequeño (~0–14°)
        pie normal→ P_mid desplazado moderadamente   → ángulo medio (~15–31°)
        pie cavo  → P_mid muy desplazado              → ángulo grande (>32°)

    Nota metodológica:
        Los umbrales clínicos originales (Clarke, 1933) son distintos porque
        la medición con transportador en imagen física usa otra referencia.
        Los umbrales en config.py están calibrados para esta implementación.
    ─────────────────────────────────────────────────────────────────────────
    """

    # Centroides horizontales de cada región
    cx_ante  = centroid_x_of_region(reg_antepe)
    cx_medio = centroid_x_of_region(reg_mediope)
    cx_retro = centroid_x_of_region(reg_retrope)

    if cx_ante == 0 or cx_medio == 0 or cx_retro == 0:
        return 0.0, None

    cx_extremos = (cx_ante + cx_retro) / 2.0

    # El arco desplaza el contacto del mediopié HACIA EL LADO CONTRARIO
    # cx_medio < cx_extremos  → contacto del medio está a la izquierda
    #                          → arco en el lado DERECHO (mayor x)
    arch_on_right = (cx_medio < cx_extremos)

    def get_arch_border_pts(region, arch_right, offset_y):
        """
        Retorna el punto del borde del arco en la fila más representativa.
        Para arco en derecha: borde derecho de cada fila (max x).
        Para arco en izquierda: borde izquierdo (min x).
        """
        pts = []
        for i, row in enumerate(region):
            nz = np.where(row > 0)[0]
            if len(nz) == 0:
                continue
            px = int(nz[-1]) + ox if arch_right else int(nz[0]) + ox
            pts.append((px, i + offset_y))
        return pts

    pts_fore = get_arch_border_pts(reg_antepe,  arch_on_right, oy_ante)
    pts_mid  = get_arch_border_pts(reg_mediope, arch_on_right, oy_mid)
    pts_heel = get_arch_border_pts(reg_retrope, arch_on_right, oy_retro)

    if not pts_fore or not pts_mid or not pts_heel:
        return 0.0, None

    # P_fore: punto extremo medial del antepié (vértice del ángulo)
    # P_mid:  punto extremo medial del mediopié (donde el arco es más evidente)
    # P_heel: punto extremo medial del retropié
    if arch_on_right:
        # Arco en derecha → borde medial del arco = max x
        P_fore = max(pts_fore, key=lambda p: p[0])
        P_mid  = max(pts_mid,  key=lambda p: p[0])
        P_heel = max(pts_heel, key=lambda p: p[0])
    else:
        # Arco en izquierda → borde medial del arco = min x
        P_fore = min(pts_fore, key=lambda p: p[0])
        P_mid  = min(pts_mid,  key=lambda p: p[0])
        P_heel = min(pts_heel, key=lambda p: p[0])

    # Ángulo en P_fore entre rayos P_fore→P_heel y P_fore→P_mid
    angle = angle_between_vectors(P_heel, P_fore, P_mid)

    return round(angle, 1), (P_fore, P_mid, P_heel)
