# Design System

## Register
product

## Color
Estrategia: restrained. Fondos calidos casi-blancos con neutros tintados,
texto warm-near-black, un unico acento vermellon (<10% de la superficie).

Nunca `#fff` ni `#000`. Todos los neutros estan tintados hacia el calido.

| Rol             | Hex      | Uso                                   |
|-----------------|----------|---------------------------------------|
| bg              | #FAF7F2  | fondo principal de la app             |
| surface         | #FFFEFB  | paneles, tarjetas, log                |
| surface raised  | #F4F1EA  | metric blocks, badges                 |
| border          | #E5DFD3  | bordes de paneles                     |
| border subtle   | #EFEAE0  | divisores                             |
| ink             | #1F1B17  | texto primario                        |
| ink muted       | #6B635A  | texto secundario, labels              |
| ink subtle      | #A29B91  | placeholders, hints                   |
| accent          | #D74F2A  | botones primarios, paso activo        |
| accent hover    | #BC4220  | hover de primarios                    |
| accent active   | #9F3717  | pressed                               |
| accent soft     | #F8E3D8  | fondo suave del acento                |
| ok              | #2E7D32  | exito en log y validaciones           |
| warn            | #B45309  | advertencias                          |
| tree leaf       | #1F1B17  | nodos hoja del arbol                  |
| tree inner      | #B5AB9D  | nodos internos                        |
| tree edge       | #C9C0B2  | aristas                               |
| chart bar fg    | #D74F2A  | barras del dashboard                  |
| chart bar bg    | #ECE6DA  | tracks del dashboard                  |

## Typography
Familia primaria: Segoe UI (fallback Helvetica). Mono: Consolas (fallback
Courier New).

Escala (Tkinter pt):
- display: 22, weight 700
- h1: 14, weight 700
- h2: 11, weight 700, mayusculas con tracking visual
- body: 10, weight 400
- small: 9, weight 400
- micro: 8, weight 400
- mono: 9
- mono small: 8
- metric value: 20, weight 700
- metric value secondary: 15, weight 700

Cap line length en logs/output ~85 caracteres.

## Spacing scale (px)
4, 8, 12, 16, 20, 28, 36, 48. Variar el ritmo. No usar el mismo padding en
todo.

## Components
- RoundedButton (radio 6, padx 14, pady 8)
  - Primary: bg accent, fg #ffffff, weight 700
  - Secondary: bg surface raised, fg ink, borde border subtle
  - Ghost: bg transparente al fondo, fg ink muted, hover fg ink
- StepperBar: linea horizontal con 6 dots numerados. Estados: pendiente
  (outline ink subtle), activo (fill accent), completado (fill ink).
- MetricBlock: label small uppercase + valor display. NO grid uniforme:
  metricas principales mas grandes que las secundarias.
- HBarChart: barra horizontal en canvas para comparativas (H vs L).
- ColumnChart: columnas pequenas para distribuciones (longitudes de codigo).
- Card: surface con borde 1px subtle, padding 16-20.
- Empty state: copy + icono de canvas opcional, centrado.

## Motion
Sin animacion CSS (Tkinter). Hover y active solo cambian color. Cursor
"watch" en operaciones largas (encode/decode).

## Anti-references
- Gris uniforme en toda la UI.
- 5 metric cards iguales en una fila (rule violation: identical card grids).
- Em dashes en el copy (`—` o `--`).
- Tabs con padding inflado.
- Side-stripe borders como acento.
- Gradient text.
- Big-number/small-label/gradient hero (cliche SaaS).
