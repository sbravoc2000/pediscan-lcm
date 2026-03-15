"""
config.py — Parámetros y puntos de corte de PediScan LCM
=========================================================
Editar este archivo para ajustar clasificaciones sin modificar la lógica principal.
Todos los umbrales son parametrizables aquí.

Laboratorio de Ciencias del Movimiento (LCM) — UPC
"""

# ── Chippaux-Smirak Index (CSI) ────────────────────────────────────────────
# Fórmula : CSI = (Wm / Wa) × 100   [porcentaje]
# Referencia: Forriol F, Pascual J (1990). Foot Ankle, 11(2), 101–104.
#             Chippaux C, Smirak M (1952). Bull Acad Natl Med, 136, 451–457.
CSI_LIMITE_CAVO  = 30.0    # < 30 %    → pie cavo
CSI_LIMITE_PLANO = 45.0    # > 45 %    → pie plano
                            # 30–45 %  → pie normal

# ── Staheli Index (SI) ───────────────────────────────────────────────────────
# Fórmula : SI = Wm / Wh   [adimensional]
# Referencia: Staheli LT et al. (1987). J Bone Joint Surg Am, 69(3), 426–428.
SI_LIMITE_CAVO  = 0.54     # < 0.54    → pie cavo
SI_LIMITE_PLANO = 0.89     # > 0.89    → pie plano
                            # 0.54–0.89 → pie normal

# ── Clarke's Angle ────────────────────────────────────────────────────────────
# Referencia base: Clarke HH (1933). Res Q Am Assoc Health, 4(3), 99–107.
# NOTA METODOLÓGICA: Estos umbrales están adaptados para la implementación
# digital (ángulo geométrico en imagen). La medición clínica manual con
# transportador tiene un rango nominal distinto (normal: 31–42°).
# Estos valores pueden recalibrarse en función de datos propios en config.py.
CLARKE_LIMITE_PLANO = 15.0  # < 15°    → pie plano
CLARKE_LIMITE_CAVO  = 32.0  # > 32°    → pie cavo
                             # 15–32°   → pie normal

# ── Arch Index (AI) — Cavanagh & Rodgers ─────────────────────────────────────
# Fórmula : AI = área_mediopié / (área_mediopié + área_retropié)
# Referencia: Cavanagh PR, Rodgers MM (1987). J Biomech, 20(5), 547–551.
AI_LIMITE_CAVO  = 0.21     # < 0.21    → pie cavo
AI_LIMITE_PLANO = 0.26     # > 0.26    → pie plano
                            # 0.21–0.26 → pie normal

# ── Regla de consenso ─────────────────────────────────────────────────────────
# Si ≥ CONSENSUS_THRESHOLD índices coinciden → esa categoría final
CONSENSUS_THRESHOLD = 3

# ── Etiquetas de categorías ───────────────────────────────────────────────────
CAT_CAVO          = "pie cavo"
CAT_NORMAL        = "pie normal"
CAT_PLANO         = "pie plano"
CAT_INDETERMINADO = "discordante / indeterminado"

# ── Colores para anotaciones (formato BGR — OpenCV) ───────────────────────────
COLOR_CONTORNO   = (0,  200,   0)   # verde         — contorno del pie
COLOR_ANTEPE     = (0,  140, 255)   # naranja        — Wa: ancho máx antepié
COLOR_MEDIOPE    = (0,    0, 210)   # rojo           — Wm: ancho mín mediopié
COLOR_RETROPE    = (190,  0, 190)   # magenta        — Wh: ancho máx retropié
COLOR_TERCIO     = (80,  80,   0)   # oliva          — divisiones de tercios
COLOR_CLARKE     = (0,  210, 210)   # amarillo       — puntos Clarke
COLOR_TEXTO      = (255, 255, 255)  # blanco         — texto etiquetas
COLOR_FONDO_TXT  = (25,  25,  25)  # gris oscuro    — fondo de etiquetas

# ── Parámetros de segmentación ────────────────────────────────────────────────
KERNEL_SIZE      = 9     # tamaño del kernel morfológico (px)
MORPH_ITER_CLOSE = 4     # iteraciones de cierre (rellena huecos)
MORPH_ITER_OPEN  = 2     # iteraciones de apertura (elimina artefactos)
MIN_CONTOUR_AREA = 5000  # área mínima (px²) para considerar un contorno como pie

# ── Tipo de imagen de pedígrafía ──────────────────────────────────────────────
# "otsu"  → huella OSCURA sobre fondo CLARO (tinta sobre papel blanco)
#            usa umbral de Otsu en escala de grises
# "green" → huella VERDE BRILLANTE sobre fondo AZUL/CLARO (LED de pedígrafo)
#            usa diferencia de canales BGR para aislar el verde del LED
PEDIGRAFO_MODE = "green"   # cambiar a "otsu" si las imágenes son tinta/papel

# ── Umbrales de segmentación verde (solo se usan en modo "green") ─────────────
# La huella en un pedígrafo LED tiene canal G mucho mayor que R y B:
#   Huella verde típica: G-R ≈ +80, G-B ≈ +40
#   Fondo azul/piel:     G-R ≈ +45, G-B ≈ -25 (B domina sobre G)
# Reducir GREEN_DIFF_GR / GREEN_DIFF_GB si no se detectan suficientes píxeles
# Aumentar si se captura demasiado fondo
GREEN_DIFF_GR  = 40   # mínimo de (G - R) para considerar píxel como huella
GREEN_DIFF_GB  = 10   # mínimo de (G - B) para considerar píxel como huella

# ── Nota sobre AI en pedígrafo LED ───────────────────────────────────────────
# En pedígrafos de tinta, el mediopié NO deja huella cuando hay arco →
#   AI bajo. En pedígrafos LED (presión sobre vidrio), toda la planta
#   contacta y se ilumina → AI sistemáticamente más alto.
# Por eso, en imágenes de pedígrafo LED, CSI y SI son los índices
# más confiables. El AI se reporta como dato auxiliar con esta nota.
