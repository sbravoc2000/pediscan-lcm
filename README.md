# 👣 PediScan LCM

> Análisis de pedígrafía plantar estática · Laboratorio de Ciencias del Movimiento · UPC

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Software ligero y local para analizar imágenes de pedígrafía plantar estática con pedígrafo LED. Detecta ambos pies automáticamente, calcula cuatro índices validados y genera imagen anotada y tabla Excel lista para informes deportivos.

## ✨ Qué hace

- Detecta y segmenta automáticamente ambas huellas plantares
- Calcula CSI, SI, Clarke's Angle y Arch Index (índices validados)
- Genera imagen anotada con líneas geométricas y etiquetas
- Exporta recortes individuales por pie (para Word/PDF)
- Exporta tabla Excel con formato y colores por categoría
- Acumula tabla grupal de todos los evaluados en sesión
- Funciona 100% local, sin internet, sin GPU, sin cloud

## Instalación rápida

```bash
git clone https://github.com/TU_USUARIO/pediscan-lcm.git
cd pediscan-lcm
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
streamlit run app.py
```

Ver README completo para detalles de uso, índices y referencias.

## Referencias metodológicas

- CSI: Forriol & Pascual (1990). Foot Ankle, 11(2), 101-104.
- SI: Staheli et al. (1987). J Bone Joint Surg Am, 69(3), 426-428.
- Clarke: Clarke (1933). Res Q Am Assoc Health Phys Educ, 4(3), 99-107.
- AI: Cavanagh & Rodgers (1987). J Biomech, 20(5), 547-551.

## Nota

No constituye diagnóstico clínico.
Desarrollado en el LCM - UPC, Lima, Peru.
