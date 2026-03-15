"""
metrics.py — Cálculo de índices plantares y clasificación
==========================================================
PediScan LCM · Laboratorio de Ciencias del Movimiento · UPC

Índices implementados y referencias metodológicas:
───────────────────────────────────────────────────────────────────────────────
1. Chippaux-Smirak Index (CSI)
   Fórmula : CSI = (Wm / Wa) × 100
   Puntos de corte (Forriol & Pascual, 1990):
       < 30 %   → pie cavo
       30–45 %  → pie normal
       > 45 %   → pie plano
   Ref: Forriol F, Pascual J (1990). Foot Ankle, 11(2), 101–104.
        Chippaux C, Smirak M (1952). Bull Acad Natl Med, 136, 451–457.

2. Staheli Index (SI)
   Fórmula : SI = Wm / Wh
   Puntos de corte (Staheli et al., 1987):
       < 0.54   → pie cavo
       0.54–0.89 → pie normal
       > 0.89   → pie plano
   Ref: Staheli LT, Chew DE, Corbett M (1987). J Bone Joint Surg Am, 69(3), 426–428.

3. Clarke's Angle (ángulo del arco)
   Referencia base: Clarke HH (1933). Res Q Am Assoc Health Phys Educ, 4(3), 99–107.
   Implementación digital: ver processing.py → _compute_clarke_angle()
   Puntos de corte ADAPTADOS para imagen digital (ver config.py):
       < 15°    → pie plano   (clínico: < 31°)
       15–32°   → pie normal  (clínico: 31–42°)
       > 32°    → pie cavo    (clínico: > 42°)
   NOTA: El ángulo calculado por software es una aproximación geométrica.
         Los umbrales en config.py pueden recalibrarse con datos propios.

4. Arch Index (AI) — Cavanagh & Rodgers
   Fórmula : AI = área_mediopié / (área_mediopié + área_retropié)
   Puntos de corte (Cavanagh & Rodgers, 1987):
       < 0.21   → pie cavo
       0.21–0.26 → pie normal
       > 0.26   → pie plano
   Ref: Cavanagh PR, Rodgers MM (1987). J Biomech, 20(5), 547–551.

Regla de consenso:
   Si ≥ CONSENSUS_THRESHOLD (defecto: 3 de 4) índices coinciden → esa categoría
   Si no → "discordante / indeterminado"
───────────────────────────────────────────────────────────────────────────────
"""

from collections import Counter

from config import (
    CSI_LIMITE_CAVO, CSI_LIMITE_PLANO,
    SI_LIMITE_CAVO, SI_LIMITE_PLANO,
    CLARKE_LIMITE_PLANO, CLARKE_LIMITE_CAVO,
    AI_LIMITE_CAVO, AI_LIMITE_PLANO,
    CONSENSUS_THRESHOLD,
    CAT_CAVO, CAT_NORMAL, CAT_PLANO, CAT_INDETERMINADO
)


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de índices
# ─────────────────────────────────────────────────────────────────────────────

def calc_csi(Wa, Wm):
    """
    Chippaux-Smirak Index.
    CSI = (Wm / Wa) × 100  [%]
    Wm = ancho mínimo del mediopié (px)
    Wa = ancho máximo del antepié  (px)
    """
    if not Wa or Wa == 0:
        return None
    return round((Wm / Wa) * 100, 2)


def calc_si(Wm, Wh):
    """
    Staheli Index.
    SI = Wm / Wh  [adimensional]
    Wm = ancho mínimo del mediopié (px)
    Wh = ancho máximo del retropié (px)
    """
    if not Wh or Wh == 0:
        return None
    return round(Wm / Wh, 3)


def calc_arch_index(area_mediope, area_sin_dedos):
    """
    Arch Index — Cavanagh & Rodgers (1987).
    AI = área_mediopié / (área_mediopié + área_retropié)
    El antepié (dedos) es excluido del denominador.
    """
    if not area_sin_dedos or area_sin_dedos == 0:
        return None
    return round(area_mediope / area_sin_dedos, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Clasificación individual
# ─────────────────────────────────────────────────────────────────────────────

def classify_csi(csi):
    if csi is None:
        return CAT_INDETERMINADO
    if csi < CSI_LIMITE_CAVO:
        return CAT_CAVO
    if csi > CSI_LIMITE_PLANO:
        return CAT_PLANO
    return CAT_NORMAL


def classify_si(si):
    if si is None:
        return CAT_INDETERMINADO
    if si < SI_LIMITE_CAVO:
        return CAT_CAVO
    if si > SI_LIMITE_PLANO:
        return CAT_PLANO
    return CAT_NORMAL


def classify_clarke(angle):
    if angle is None or angle == 0.0:
        return CAT_INDETERMINADO
    if angle < CLARKE_LIMITE_PLANO:
        return CAT_PLANO
    if angle > CLARKE_LIMITE_CAVO:
        return CAT_CAVO
    return CAT_NORMAL


def classify_ai(ai):
    if ai is None:
        return CAT_INDETERMINADO
    if ai < AI_LIMITE_CAVO:
        return CAT_CAVO
    if ai > AI_LIMITE_PLANO:
        return CAT_PLANO
    return CAT_NORMAL


# ─────────────────────────────────────────────────────────────────────────────
# Regla de consenso
# ─────────────────────────────────────────────────────────────────────────────

def consensus_classification(classifications):
    """
    Aplica regla de consenso entre los cuatro índices.

    Parámetro:
        classifications — lista de hasta 4 categorías (strings)

    Retorna:
        (categoria_final, concordancia)
        concordancia = nº de índices que coinciden en la categoría más frecuente

    Regla:
        Si ≥ CONSENSUS_THRESHOLD índices coinciden → esa categoría
        Si no → CAT_INDETERMINADO

    CONSENSUS_THRESHOLD es configurable en config.py (defecto: 3).
    """
    valid = [c for c in classifications if c != CAT_INDETERMINADO]

    if not valid:
        return CAT_INDETERMINADO, 0

    counts = Counter(valid)
    most_common_cat, count = counts.most_common(1)[0]

    if count >= CONSENSUS_THRESHOLD:
        return most_common_cat, count
    else:
        return CAT_INDETERMINADO, count


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def calculate_all_metrics(measurements):
    """
    Calcula los cuatro índices y la clasificación final.

    Entrada : dict de mediciones proveniente de extract_measurements()
    Retorna : dict con valores, clasificaciones individuales y categoría final.
    """
    Wa             = measurements["Wa"]
    Wm             = measurements["Wm"]
    Wh             = measurements["Wh"]
    area_mediope   = measurements["area_mediope"]
    area_sin_dedos = measurements["area_sin_dedos"]
    clarke_angle   = measurements.get("clarke_angle", 0.0)

    # ── Calcular índices ───────────────────────────────────────────────────
    csi    = calc_csi(Wa, Wm)
    si     = calc_si(Wm, Wh)
    ai     = calc_arch_index(area_mediope, area_sin_dedos)
    clarke = clarke_angle if clarke_angle else 0.0

    # ── Clasificar individualmente ─────────────────────────────────────────
    cat_csi    = classify_csi(csi)
    cat_si     = classify_si(si)
    cat_clarke = classify_clarke(clarke)
    cat_ai     = classify_ai(ai)

    # ── Consenso ──────────────────────────────────────────────────────────
    cat_final, concordance = consensus_classification(
        [cat_csi, cat_si, cat_clarke, cat_ai]
    )

    return {
        # Valores de índices (adimensionales, sin unidad real)
        "CSI":         csi,
        "SI":          si,
        "Clarke":      clarke,
        "AI":          ai,
        # Clasificaciones por índice
        "cat_CSI":     cat_csi,
        "cat_SI":      cat_si,
        "cat_Clarke":  cat_clarke,
        "cat_AI":      cat_ai,
        # Resultado integrado
        "cat_final":   cat_final,
        "concordance": concordance,
    }
