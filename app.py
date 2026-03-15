"""
app.py — Interfaz principal de PediScan LCM
============================================
Análisis de pedígrafía plantar estática

Ejecución:
    streamlit run app.py

Laboratorio de Ciencias del Movimiento (LCM) · UPC
"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
from datetime import date

from processing import (
    load_image_from_bytes, segment_footprint,
    find_feet, extract_measurements
)
from metrics import calculate_all_metrics
from reporting import draw_annotations, generate_interpretation, crop_foot_images
from export_excel import generate_excel


# ─────────────────────────────────────────────────────────────────────────────
# Configuración de página
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PediScan LCM",
    page_icon="👣",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("👣 PediScan LCM")
st.caption(
    "Análisis de pedígrafía plantar estática · "
    "Laboratorio de Ciencias del Movimiento · UPC"
)
st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Panel lateral — configuración del evaluado y opciones
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("Datos del evaluado")
    evaluado_id   = st.text_input("ID / Nombre", value="EVA-001",
                                   help="Identificador del atleta evaluado")
    evaluado_fecha = st.date_input("Fecha de evaluación", value=date.today())

    st.markdown("---")
    st.subheader("🔬 Tipo de pedígrafo")

    pedigrafo_mode = st.radio(
        "Modo de segmentación",
        options=["green", "otsu"],
        index=0,
        format_func=lambda x: (
            "🟢 LED verde (vidrio iluminado)" if x == "green"
            else "⚫ Tinta / papel (Otsu)"
        ),
        help=(
            "LED verde: pedígrafo con iluminación LED bajo vidrio (LCM)\n"
            "Tinta/papel: pedígrafía clásica de tinta oscura sobre papel blanco"
        )
    )

    if pedigrafo_mode == "green":
        st.caption("📷 Imagen esperada: huella verde brillante sobre fondo azul/claro")
        with st.expander("🔧 Ajuste fino (opcional)", expanded=False):
            green_diff_gr = st.slider(
                "Umbral G-R (verde vs rojo)",
                min_value=10, max_value=80, value=40, step=5,
                help="Reducir si se pierde huella; aumentar si entra fondo rojo"
            )
            green_diff_gb = st.slider(
                "Umbral G-B (verde vs azul)",
                min_value=0, max_value=40, value=10, step=5,
                help="Reducir si se pierde arco; aumentar si entra fondo azul"
            )
    else:
        green_diff_gr, green_diff_gb = 40, 10
        st.caption("📷 Imagen esperada: huella oscura sobre fondo claro (papel)")
        invert_mask = st.checkbox(
            "Invertir máscara",
            value=False,
            help="Activar si la huella es CLARA sobre fondo OSCURO"
        )

    invert_mask = False  # solo aplica en modo otsu, inicializar

    st.markdown("---")
    st.subheader("📐 Orientación de la imagen")

    swap_sides = st.checkbox(
        "Intercambiar derecho / izquierdo",
        value=False,
        help="Activar si la asignación de lados aparece invertida"
    )
    heel_at_bottom = st.radio(
        "Posición del talón",
        options=["Talón abajo (dedos arriba)", "Talón arriba (dedos abajo)"],
        index=0,
        help="Indica hacia qué extremo de la imagen apunta el talón"
    )
    heel_down = (heel_at_bottom == "Talón abajo (dedos arriba)")

    st.markdown("---")
    st.subheader("✏️ Ajuste manual de líneas")
    st.caption("Usa estos controles si alguna línea cae fuera del pie real.")
    trim_wa = st.slider(
        "Recorte Wa (naranja) — px por extremo",
        min_value=0, max_value=60, value=0, step=2,
        help=(
            "Si la línea naranja sale del pie hacia afuera, aumenta este valor. "
            "Se recortarán N píxeles de cada extremo. "
            "Aplica igual a ambos pies."
        )
    )

    st.markdown("---")
    if pedigrafo_mode == "green":
        st.info(
            "**Pedígrafo LED (LCM)**\n\n"
            "• Ambos pies visibles y separados\n"
            "• Huella verde brillante sobre fondo azul\n"
            "• Buena iluminación LED activa\n"
            "• Sin escala física requerida"
        )
        st.warning(
            "⚠️ **Nota sobre Arch Index (AI):**\n"
            "En pedígrafía LED, toda la planta contacta el vidrio → "
            "el AI será sistemáticamente alto. "
            "**CSI y SI son los índices más confiables** con este tipo de imagen."
        )
    else:
        st.info(
            "**Pedígrafía clásica**\n\n"
            "• Huella oscura sobre fondo blanco\n"
            "• Sin zonas muy saturadas\n"
            "• Contraste claro/oscuro definido"
        )

    st.markdown("---")
    st.subheader("📚 Referencias")
    st.caption(
        "CSI: Forriol & Pascual (1990)\n"
        "SI: Staheli et al. (1987)\n"
        "Clarke: Clarke (1933)\n"
        "AI: Cavanagh & Rodgers (1987)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Carga de imagen
# ─────────────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "📂 Cargar imagen de pedígrafía",
    type=["jpg", "jpeg", "png"],
    help="Una imagen con ambas huellas plantares estáticas"
)

if uploaded is None:
    st.info("👆 Cargue una imagen de pedígrafía para iniciar el análisis.")

    # Mostrar leyenda de colores
    with st.expander("🎨 Leyenda de anotaciones", expanded=False):
        st.markdown("""
        | Color | Trazo |
        |---|---|
        | 🟢 Verde | Contorno de la huella |
        | 🟠 Naranja | Wa: ancho máximo antepié |
        | 🔴 Rojo | Wm: ancho mínimo mediopié |
        | 🟣 Magenta | Wh: ancho máximo retropié |
        | 🟡 Amarillo | Ángulo de Clarke |
        | 🫒 Oliva | Divisiones en tercios |
        """)
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Procesamiento principal
# ─────────────────────────────────────────────────────────────────────────────
success = False
feet_data = []
annotated = None
img_bgr = None
interpretation = ""

with st.spinner("⏳ Procesando imagen..."):
    try:
        # 1. Cargar imagen
        img_bgr = load_image_from_bytes(uploaded)

        # 2. Segmentar según modo del pedígrafo
        mask = segment_footprint(
            img_bgr,
            mode=pedigrafo_mode,
            invert=invert_mask,
            green_diff_gr=green_diff_gr,
            green_diff_gb=green_diff_gb
        )

        # 3. Detectar pies
        feet = find_feet(mask, swap_sides=swap_sides)

        img_h_px, img_w_px = img_bgr.shape[:2]

        # 4. Medir y calcular por pie
        for foot in feet:
            meas = extract_measurements(
                foot,
                heel_at_bottom=heel_down,
                img_w=img_w_px,
                img_h=img_h_px,
                trim_wa_px=trim_wa
            )
            met  = calculate_all_metrics(meas)
            feet_data.append({"foot": foot, "measurements": meas, "metrics": met})

        # 5. Anotar imagen
        annotated = draw_annotations(img_bgr, feet_data)

        # 6. Recortes individuales por pie
        crops = crop_foot_images(img_bgr, annotated, feet_data, padding=25)

        # 7. Interpretación
        interpretation = generate_interpretation(feet_data)

        success = True

    except ValueError as ve:
        st.error(f"⚠️ {ve}")
    except Exception as e:
        st.error(f"Error inesperado durante el procesamiento: {e}")
        st.exception(e)

if not success:
    st.warning(
        "**Sugerencias para mejorar la detección:**\n"
        "- Asegúrate de que ambos pies estén visibles con buen contraste\n"
        "- Intenta activar 'Invertir máscara' en el panel lateral\n"
        "- Verifica que la imagen no tenga fondo muy oscuro o muy saturado"
    )
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Visualización de resultados
# ─────────────────────────────────────────────────────────────────────────────
st.success("✅ Análisis completado")

col_orig, col_ann = st.columns(2)

with col_orig:
    st.subheader("Imagen original")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    st.image(img_rgb, use_container_width=True)

with col_ann:
    st.subheader("Imagen anotada")
    ann_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
    st.image(ann_rgb, use_container_width=True)

    # Leyenda compacta
    st.caption(
        "🟢 Contorno  "
        "🟠 Wa  "
        "🔴 Wm  "
        "🟣 Wh  "
        "🟡 Clarke  "
        "🫒 Tercios"
    )

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Vista individual por pie (recortes)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🦶 Vista individual por pie")
st.caption("Recortes listos para insertar en Word o informe PDF.")

if crops:
    cols_crops = st.columns(len(crops) * 2)
    for i, crop in enumerate(crops):
        side_label = crop["side"].capitalize()
        with cols_crops[i * 2]:
            st.caption(f"**Pie {side_label} — original**")
            orig_rgb = cv2.cvtColor(crop["original"], cv2.COLOR_BGR2RGB)
            st.image(orig_rgb, use_container_width=True)
        with cols_crops[i * 2 + 1]:
            st.caption(f"**Pie {side_label} — anotado**")
            ann_rgb = cv2.cvtColor(crop["anotada"], cv2.COLOR_BGR2RGB)
            st.image(ann_rgb, use_container_width=True)

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Tabla de resultados individuales
# ─────────────────────────────────────────────────────────────────────────────
st.subheader(f"📊 Resultados individuales — {evaluado_id} · {evaluado_fecha}")

rows = []
for fd in feet_data:
    side = fd["foot"]["side"]
    met  = fd["metrics"]
    rows.append({
        "Pie":              side.capitalize(),
        "CSI (%)":          met["CSI"],
        "Cat. CSI":         met["cat_CSI"],
        "SI":               met["SI"],
        "Cat. SI":          met["cat_SI"],
        "Clarke (°)":       met["Clarke"],
        "Cat. Clarke":      met["cat_Clarke"],
        "AI":               met["AI"],
        "Cat. AI":          met["cat_AI"],
        "Categoría final":  met["cat_final"],
        "Concordancia":     f"{met['concordance']}/4",
    })

df_individual = pd.DataFrame(rows)

# Color de fondo por categoría en la columna final
def _highlight_cat(val):
    colors = {
        "pie plano":   "background-color: #cc3333; color: white",
        "pie cavo":    "background-color: #1a3e8c; color: white",
        "pie normal":  "background-color: #1f7a1f; color: white",
    }
    return colors.get(val, "background-color: #555555; color: white")

styled = df_individual.style.applymap(
    _highlight_cat, subset=["Categoría final"]
)
st.dataframe(styled, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Interpretación automática
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📝 Interpretación automática")
st.info(interpretation)

if pedigrafo_mode == "green":
    st.caption(
        "⚠️ Nota metodológica — pedígrafo LED: el Arch Index (AI) en este tipo "
        "de imagen tiende a ser alto porque toda la planta contacta el vidrio. "
        "Para la clasificación final, se priorizan CSI y SI como índices más "
        "confiables. El AI se reporta como dato auxiliar."
    )

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Tabla grupal acumulada (sesión)
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📋 Tabla grupal acumulada")
st.caption(
    "Añade cada evaluado a la tabla grupal procesando su imagen y "
    "presionando el botón. Los datos persisten durante la sesión."
)

# Construir fila para la tabla grupal
group_row = {
    "ID":     evaluado_id,
    "Fecha":  str(evaluado_fecha),
}
for fd in feet_data:
    side = fd["foot"]["side"]
    met  = fd["metrics"]
    s = "D" if side == "derecho" else "I"
    group_row[f"CSI_{s}"]    = met["CSI"]
    group_row[f"SI_{s}"]     = met["SI"]
    group_row[f"Clarke_{s}"] = met["Clarke"]
    group_row[f"AI_{s}"]     = met["AI"]
    group_row[f"Cat_{s}"]    = met["cat_final"]

# Estado de sesión para persistencia
if "group_table" not in st.session_state:
    st.session_state.group_table = []

col_add, col_clear, _ = st.columns([1, 1, 4])
with col_add:
    if st.button("➕ Añadir a tabla grupal"):
        # Evitar duplicados por ID
        ids_existentes = [r.get("ID") for r in st.session_state.group_table]
        if evaluado_id in ids_existentes:
            st.warning(f"El ID '{evaluado_id}' ya está en la tabla. "
                       f"Cambia el ID o limpia la tabla para reemplazarlo.")
        else:
            st.session_state.group_table.append(group_row)
            st.success(f"✅ {evaluado_id} añadido ({len(st.session_state.group_table)} registros).")

with col_clear:
    if st.button("🗑️ Limpiar tabla"):
        st.session_state.group_table = []
        st.rerun()

if st.session_state.group_table:
    df_group = pd.DataFrame(st.session_state.group_table)
    st.dataframe(df_group, use_container_width=True)
    st.caption(f"Total: {len(df_group)} evaluados registrados")
else:
    st.caption("La tabla grupal está vacía. Procesa evaluados y presiona '➕ Añadir'.")


# ─────────────────────────────────────────────────────────────────────────────
# Exportaciones
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("💾 Exportar")

# ── Fila 1: imagen completa + Excel ──────────────────────────────────────────
exp1, exp2, exp3 = st.columns(3)

with exp1:
    _, buf = cv2.imencode(".png", annotated)
    st.download_button(
        label="📷 Imagen anotada completa (PNG)",
        data=buf.tobytes(),
        file_name=f"pediscan_{evaluado_id}_{evaluado_fecha}.png",
        mime="image/png",
        use_container_width=True
    )

with exp2:
    excel_bytes = generate_excel(
        evaluado_id, str(evaluado_fecha),
        feet_data, interpretation,
        group_rows=st.session_state.group_table if st.session_state.group_table else None
    )
    st.download_button(
        label="📊 Resultados Excel (con formato)",
        data=excel_bytes,
        file_name=f"pediscan_{evaluado_id}_{evaluado_fecha}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

with exp3:
    csv_ind = df_individual.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📄 Resultados individuales (CSV)",
        data=csv_ind,
        file_name=f"pediscan_ind_{evaluado_id}_{evaluado_fecha}.csv",
        mime="text/csv",
        use_container_width=True
    )

# ── Fila 2: recortes PNG por pie ──────────────────────────────────────────────
if crops:
    st.markdown("**Recortes por pie (para Word / informe):**")
    crop_cols = st.columns(len(crops) * 2)
    for i, crop in enumerate(crops):
        side = crop["side"]

        # Original
        with crop_cols[i * 2]:
            _, buf_orig = cv2.imencode(".png", crop["original"])
            st.download_button(
                label=f"🦶 Pie {side} — original",
                data=buf_orig.tobytes(),
                file_name=f"pie_{side}_original_{evaluado_id}.png",
                mime="image/png",
                use_container_width=True
            )
        # Anotado
        with crop_cols[i * 2 + 1]:
            _, buf_ann = cv2.imencode(".png", crop["anotada"])
            st.download_button(
                label=f"📐 Pie {side} — anotado",
                data=buf_ann.tobytes(),
                file_name=f"pie_{side}_anotado_{evaluado_id}.png",
                mime="image/png",
                use_container_width=True
            )

# ── Tabla grupal CSV ──────────────────────────────────────────────────────────
if st.session_state.group_table:
    df_g  = pd.DataFrame(st.session_state.group_table)
    csv_g = df_g.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📋 Tabla grupal completa (CSV)",
        data=csv_g,
        file_name=f"pediscan_grupal_{evaluado_fecha}.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pie de página
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "**PediScan LCM** · Herramienta de apoyo técnico para evaluación deportiva · "
    "No constituye diagnóstico clínico · LCM · UPC"
)
