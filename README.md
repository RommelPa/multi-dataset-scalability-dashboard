<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/1sXDomzSN6Xv_TdTS1NhwzSo03Pr434TA

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Balance transformer (Excel -> Dashboard)

- La ingesta selecciona una sola hoja por año aplicando esta prioridad de versiones: `R2` > `R1` > `V1` > `REVn` > hoja base (sin sufijo). Ejemplos: `2020 R2` desplaza a `2020 R1`, `2016 (rev3)` desplaza a `2016` base.
- Ejemplos de nombres soportados y desempate: `2018-R2 (LDS)`, `2020 R2`, `2021-R1`, `2025V1`, `2016 (rev3)`. Se detecta el año con regex `\b(19|20)\d{2}\b` y se elige la versión con mayor ranking (R2 > R1 > V1 > REVn > base; para REV se toma el `n` mayor).
- Dentro de la hoja, se ubica la tabla titulada `BALANCE DE ENERGÍA EN MWh - AÑO {YYYY}` y se normalizan las descripciones (trim, mayúsculas, colapsar espacios, reemplazar guiones y quitar `:`) para mapear filas:
  - `A EMP. DISTRIBUIDORAS` → Regulados
  - `A CLIENTES LIBRES` → Libres
  - `COES` / `COES-SPOT` → COES - SPOT
  - `PÉRDIDAS SISTEMAS TRANSMISIÓN` → Pérdidas
  - `SERVICIOS AUXILIARES` / `CONSUMO PROPIO DE CENTRALES` → Servicios Auxiliares
- Venta de energía oficial = Regulados + Libres. Los gráficos que muestran barras apiladas + línea usan TotalMercados = Regulados + Libres + COES para reflejar el apilado visual; los KPI/labels usan la definición oficial.
