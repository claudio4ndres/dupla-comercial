# Spec 007 · Exportar la cotización a Excel con el theme Capsulab

- **Estado:** borrador
- **Tipo:** full-stack (backend generación xlsx · frontend descarga)
- **Relacionada con:** spec 004 (propuesta/cotización) · spec 005 (Javo valoriza con el Drive)

## 1. Problema y por qué

La cotización ya se resuelve en la app (componentes valorizados, spec 004/005), pero
el GP necesita **bajarla a un Excel real** con el formato que Capsulab ya usa con sus
clientes (el archivo modelo `PF - Fuchs cerros.xlsx`). Hoy el botón "⤓ Excel" de la
pantalla de propuesta sólo muestra un `alert`. Sin export, el GP tiene que rehacer a
mano la planilla — justo el trabajo que Dupla promete ahorrar.

El Excel generado debe **respetar el theme de Capsulab** (la "cara" de la agencia
frente al cliente), no un formato genérico.

## 2. Usuarios y contexto

- **Usuario:** el GP, en la **pantalla de propuesta**, presiona "⤓ Excel" y descarga
  la cotización de **esa** solicitud.
- **Aislamiento:** la cotización es la de la empresa del usuario (RLS, regla de oro #2).
  Un usuario nunca descarga la cotización de otra empresa.
- **Fuente de datos:** la propuesta persistida (spec 004): `componentes_propuesta`
  (nombre, detalle, cantidad, valor_unitario) de la propuesta de la solicitud.

## 3. El theme (extraído del archivo modelo `PF - Fuchs cerros.xlsx`)

Hoja de cotización ("Consolidado"):

- **Banda de título:** fila superior, fondo **negro** `FF000000`, fuente **Arial 25
  bold blanca** `FFFFFFFF`, fusionada a lo ancho de la tabla.
- **Encabezado:** fondo **verde** `FF8ED873`, Arial 11 bold. Columnas en este orden:
  `Item · PROVEEDOR · DESCRIPCIÓN · Cantidad · días · valor unitario · COSTO · MARGEN ·
  VALOR FINAL`.
- **Filas de datos:** `COSTO = Cantidad × días × valor unitario`;
  `VALOR FINAL = COSTO / (1 − margen)`; `MARGEN = 1 − COSTO / VALOR FINAL` (derivado).
  El archivo modelo usa `VALOR FINAL = COSTO / 0.6` → margen **40 %**.
- **Subtotal:** fila **amarilla** `FFFFFF00` "SUB TOTAL COSTOS" con `SUM(COSTO)` y
  `SUM(VALOR FINAL)`.
- **Valor venta:** fila **cian** `FF00FFFF` "VALOR VENTA" = subtotal de VALOR FINAL.
- **Formatos:** valores en pesos (formato contable CLP), MARGEN en `0%`. Fuente Arial.

> El archivo modelo es la versión **interna** (muestra COSTO + MARGEN + VALOR FINAL).
> Es la que el GP necesita para trabajar la cotización. El `valor_unitario` de cada
> componente es el **costo** unitario (lo que Javo trae del Drive); el margen se aplica
> en la planilla para llegar al precio de venta.

## 4. Criterios de aceptación

- **CA1.** `GET /solicitudes/{id}/cotizacion.xlsx` devuelve un `.xlsx` válido
  (content-type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
  `Content-Disposition: attachment`).
- **CA2.** El libro tiene una hoja con: banda de título negra (Arial 25 blanca), fila
  de encabezado verde `FF8ED873` con las 9 columnas, una fila por componente, fila de
  subtotal amarilla y fila de valor venta cian.
- **CA3.** `COSTO = Cantidad × días × valor unitario` y
  `VALOR FINAL = COSTO / (1 − margen)`. El margen por defecto es **0.40** y es
  configurable por query param `?margen=`.
- **CA4.** Sólo la cotización de la empresa del usuario (RLS). Solicitud de otra empresa
  o sin propuesta → **404**. Sin token → **401**.
- **CA5.** El botón "⤓ Excel" de la pantalla de propuesta descarga el archivo de la
  solicitud activa. Si el backend cae/404, no rompe la UI.
- **CA6.** TDD: cada pieza (generador, endpoint, cliente front) tiene su test que falló
  primero. El generador se prueba abriendo los bytes con openpyxl (sin motor de cálculo
  externo): se asertan valores, fórmulas, fills y fuentes.

## 5. Fuera de alcance

- Export a PPT (sigue como `alert`, otra spec).
- Multi-hoja (una hoja por locación/escenario como el archivo modelo): por ahora **una
  hoja consolidada**.
- ✅ Versión cliente (sólo precios de venta, sin COSTO/MARGEN ni proveedor):
  **implementada** como `?vista=cliente` (botón «⤓ Excel cliente»). El costo nunca se
  escribe en el archivo. Default sigue siendo `interno`.
- Persistir el archivo en Storage: se genera al vuelo en cada descarga.
