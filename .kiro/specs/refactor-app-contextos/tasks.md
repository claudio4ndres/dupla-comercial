# Implementation Plan: refactor-app-contextos

## Overview

Extraer el estado de `App.tsx` en tres Contextos React especializados
(`SesionContext`, `SolicitudContext`, `BandejaContext`) siguiendo el ciclo
TDD **rojo → verde → refactor** y la estrategia de migración en tres
iteraciones del diseño. Cada iteración termina con `npm test` en verde.
Ningún test existente en `App.test.tsx` puede romperse.

---

## Tasks

- [x] 1. Preparar infraestructura de tests de contextos

  - Instalar `fast-check` como dependencia de desarrollo en `apps/web`.
  - Crear el directorio `src/contextos/` (vacío por ahora).
  - Verificar que `npm test` sigue en verde antes de tocar `App.tsx`.
  - _Requisitos: 5.1, 6.1_

---

## Iteración 1 — SesionContext

- [x] 2. Crear `SesionContext` con TDD

  - [x] 2.1 🔴 Escribir test de inicialización de `SesionContext`
    - Crear `src/contextos/SesionContext.test.tsx`.
    - Test: el hook `useSesion()` lanzado fuera del provider arroja
      `"useSesion debe usarse dentro de SesionProvider"`.
    - Test: montado dentro del provider, devuelve las propiedades
      `sesion`, `empresa`, `setEmpresa`, `cerrarSesion`, `pantalla`, `irA`.
    - Ejecutar `npm test` y verificar que **falla** (el archivo no existe).
    - _Requisitos: 1.5, 6.2, 6.4_

  - [x] 2.2 🟢 Implementar `SesionContext.tsx`
    - Crear `src/contextos/SesionContext.tsx`.
    - Definir la interfaz `SesionContextValor` con todos los campos del diseño.
    - Crear `SesionContext` con valor inicial `undefined`.
    - Implementar `SesionProvider`: mover desde `App.tsx` los estados
      `sesion`, `empresa`, `pantalla` y las funciones `cerrarSesion`, `irA`,
      `setEmpresa`.
    - Mover los tres `useEffect`: suscripción a Supabase Auth, carga de
      `obtenerEmpresa`, actualización de variables CSS `--brand` / `--brand-soft`.
    - Exportar el hook `useSesion()` con la guarda de error descriptivo.
    - Ejecutar `npm test` y verificar que los tests de `SesionContext.test.tsx`
      **pasan**.
    - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 6.4_

  - [ ]* 2.3 Escribir property test — Property 1: white-label reactivo
    - En `SesionContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier color hex de 6 dígitos arbitrario, al llamar `setEmpresa`
      con ese color, `--brand` y `--brand-soft` en `document.documentElement`
      deben reflejar inmediatamente el valor nuevo.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 1: White-label reactivo**
    - **Valida: Requisitos 1.4, 7.5**

- [x] 3. Integrar `SesionProvider` en el árbol y adaptar `App.tsx` (Iteración 1)

  - [x] 3.1 Envolver `App` con `SesionProvider` en `main.tsx`
    - Importar `SesionProvider` y envolverlo alrededor de `<App />` en
      `main.tsx`.
    - _Requisitos: 4.5_

  - [x] 3.2 Eliminar de `App.tsx` el estado y efectos migrados a `SesionContext`
    - Borrar de `App.tsx`: `useState` de `sesion`, `empresa`, `pantalla`.
    - Borrar los tres `useEffect` de sesión, empresa y white-label.
    - Borrar las funciones `cerrarSesion` e `irA` (ahora viven en el provider).
    - Reemplazar todas las referencias por `const { sesion, empresa, pantalla,
      irA, cerrarSesion, setEmpresa } = useSesion()`.
    - _Requisitos: 4.1, 4.2, 4.3_

  - [x] 3.3 Checkpoint — `npm test` en verde tras Iteración 1
    - Ejecutar `npm test` y verificar que los **12 tests de `App.test.tsx`** y
      los nuevos tests de `SesionContext.test.tsx` pasan sin errores.
    - Asegurar que no hay regresión en el comportamiento observable.
    - _Requisitos: 5.1, 5.2, 5.3, 5.4_

---

## Iteración 2 — SolicitudContext

- [x] 4. Crear `SolicitudContext` con TDD

  - [x] 4.1 🔴 Escribir tests de inicialización de `SolicitudContext`
    - Crear `src/contextos/SolicitudContext.test.tsx`.
    - Test: el hook `useSolicitud()` lanzado fuera del provider arroja
      `"useSolicitud debe usarse dentro de SolicitudProvider"`.
    - Test: montado dentro del provider (con mock de `SesionProvider`),
      devuelve las propiedades del diseño: `solicitudActual`, `mensajes`,
      `componentes`, `tareas`, `fuentes`, `enviando`, `recursos`,
      `abrirSolicitud`, `iniciarChat`, `enviarMensaje`, `generarPropuesta`.
    - Ejecutar `npm test` y verificar que **falla**.
    - _Requisitos: 2.6, 2.7, 6.2, 6.4_

  - [x] 4.2 🟢 Implementar `SolicitudContext.tsx`
    - Crear `src/contextos/SolicitudContext.tsx`.
    - Definir la interfaz `SolicitudContextValor` con todos los campos del diseño.
    - Implementar `SolicitudProvider`: mover desde `App.tsx` los estados
      `solicitudActual`, `tipo`, `mensajes`, `componentes`, `tareas`, `fuentes`,
      `enviando`, `recursos`.
    - Mover el `useEffect` de carga de `obtenerRecursosDrive`.
    - Mover las funciones `abrirSolicitud`, `iniciarChat`, `enviarMensaje`,
      `generarPropuesta`.
    - `SolicitudProvider` consume `useSesion()` internamente para obtener
      `empresa` e `irA`.
    - Exportar el hook `useSolicitud()` con guarda de error descriptivo.
    - Ejecutar `npm test` y verificar que los tests de `SolicitudContext.test.tsx`
      **pasan**.
    - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.4_

  - [ ]* 4.3 Escribir property test — Property 2: `iniciarChat` limpia y rehidrata
    - En `SolicitudContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier solicitud (id y remitente arbitrarios) y cualquier tipo
      confirmado, cuando se llama `iniciarChat`:
      - El primer mensaje contiene el remitente de la solicitud.
      - Se invocó `obtenerHistorialConversacion` con el id exacto.
      - Se invocó `obtenerCotizacionEnCurso` con el id exacto.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 2: `iniciarChat` limpia y rehidrata para toda solicitud**
    - **Valida: Requisitos 2.3, 7.6**

  - [ ]* 4.4 Escribir property test — Property 3: `enviarMensaje` agrega y actualiza
    - En `SolicitudContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier string de texto (incluyendo caracteres especiales), cuando
      se llama `enviarMensaje(texto)`:
      - La lista de mensajes contiene el mensaje del usuario con `rol: 'usuario'`
        y el texto enviado.
      - Se llamó a `conversarConJavo` exactamente una vez.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 3: `enviarMensaje` agrega el mensaje y actualiza estado**
    - **Valida: Requisitos 2.4**

- [x] 5. Integrar `SolicitudProvider` y adaptar `App.tsx` (Iteración 2)

  - [x] 5.1 Envolver con `SolicitudProvider` en `main.tsx`
    - Añadir `SolicitudProvider` dentro de `SesionProvider` en `main.tsx`.
    - _Requisitos: 4.5_

  - [x] 5.2 Eliminar de `App.tsx` el estado y funciones migrados a `SolicitudContext`
    - Borrar de `App.tsx`: `useState` de `solicitudActual`, `tipo`, `mensajes`,
      `componentes`, `tareas`, `fuentes`, `enviando`, `recursos`.
    - Borrar el `useEffect` de `obtenerRecursosDrive`.
    - Borrar las funciones `abrirSolicitud`, `iniciarChat`, `enviarMensaje`,
      `generarPropuesta`.
    - Reemplazar todas las referencias por `const { ... } = useSolicitud()`.
    - _Requisitos: 4.1, 4.2_

  - [x] 5.3 Checkpoint — `npm test` en verde tras Iteración 2
    - Ejecutar `npm test` y verificar que los **12 tests de `App.test.tsx`** y
      todos los tests de los contextos pasan sin errores.
    - _Requisitos: 5.1, 5.4, 5.5_

---

## Iteración 3 — BandejaContext

- [x] 6. Crear `BandejaContext` con TDD

  - [x] 6.1 🔴 Escribir tests de inicialización de `BandejaContext`
    - Crear `src/contextos/BandejaContext.test.tsx`.
    - Test: el hook `useBandeja()` lanzado fuera del provider arroja
      `"useBandeja debe usarse dentro de BandejaProvider"`.
    - Test: montado dentro del provider (con mocks de `SesionProvider` y
      `SolicitudProvider`), devuelve las propiedades del diseño: `solicitudes`,
      `cargandoSolicitudes`, `errorSolicitudes`, `reintentoSolicitudes`,
      `setReintentoSolicitudes`, `propuestas`, `cargandoPropuestas`,
      `errorPropuestas`, `reintentoPropuestas`, `setReintentoPropuestas`,
      `cargandoTareas`, `errorTareas`, `reintentoTareas`, `setReintentoTareas`,
      `abrirPropuestaDesdeLista`.
    - Ejecutar `npm test` y verificar que **falla**.
    - _Requisitos: 3.1, 3.8, 6.2, 6.4_

  - [x] 6.2 🟢 Implementar `BandejaContext.tsx`
    - Crear `src/contextos/BandejaContext.tsx`.
    - Definir la interfaz `BandejaContextValor` con todos los campos del diseño.
    - Implementar `BandejaProvider`: mover desde `App.tsx` los estados de
      solicitudes, propuestas y tareas globales (listas + cargando + error +
      reintento).
    - Mover los tres `useEffect` de carga: solicitudes (con auto-refresh de 20 s),
      propuestas y tareas globales.
    - Mover la función `abrirPropuestaDesdeLista`.
    - `BandejaProvider` consume `useSesion()` para `pantalla`, `empresa`, `irA`
      y `useSolicitud()` para `tareas.length` y `setSolicitudActual`.
    - Exportar el hook `useBandeja()` con guarda de error descriptivo.
    - Ejecutar `npm test` y verificar que los tests de `BandejaContext.test.tsx`
      **pasan**.
    - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 6.4_

  - [ ]* 6.3 Escribir property test — Property 4: carga reactiva de solicitudes
    - En `BandejaContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier valor no nulo de `estadoCorreo.proveedor` (`'gmail'`,
      `'outlook'`, `'imap'`), cuando `pantalla === 'inbox'`, el provider debe
      llamar a `obtenerSolicitudesOError` al menos una vez y, tras ~20 s, llamarla
      de nuevo.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 4: Carga reactiva de solicitudes para cualquier proveedor conectado**
    - **Valida: Requisitos 3.2, 7.3**

  - [ ]* 6.4 Escribir property test — Property 5: bandera de error ante cualquier fallo
    - En `BandejaContext.test.tsx`, agregar test con `fast-check`.
    - Para cada una de las tres cargas, si la función rechaza con un error, la
      bandera de error asociada pasa a `true` y las otras dos no se ven afectadas.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 5: Bandera de error activada ante cualquier fallo de carga**
    - **Valida: Requisitos 3.6**

  - [ ]* 6.5 Escribir property test — Property 6: reintento siempre dispara nueva carga
    - En `BandejaContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier entero N, al incrementar `reintentoSolicitudes`,
      `reintentoPropuestas` o `reintentoTareas` a N+1, la carga correspondiente
      se ejecuta exactamente una vez más.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 6: Reintento siempre dispara nueva carga**
    - **Valida: Requisitos 3.7**

  - [ ]* 6.6 Escribir property test — Property 9: cambio de empresa reinicia bandeja
    - En `BandejaContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier empresa nueva distinta de la activa, cuando `SesionContext`
      actualiza `empresa`, la lista de solicitudes se vacía y las cargas de datos
      se vuelven a ejecutar con el nuevo contexto de empresa.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 9: Cambio de empresa reinicia bandeja y recarga datos del nuevo tenant**
    - **Valida: Requisitos 7.4**

- [x] 7. Integrar `BandejaProvider` y reducir `App.tsx` a orquestador (Iteración 3)

  - [x] 7.1 Insertar `BandejaProvider` en `main.tsx` en el orden correcto
    - Añadir `BandejaProvider` entre `SesionProvider` y `SolicitudProvider` en
      `main.tsx`, dejando el árbol `SesionProvider → BandejaProvider →
      SolicitudProvider → App`.
    - _Requisitos: 4.5_

  - [x] 7.2 Eliminar de `App.tsx` el estado y efectos migrados a `BandejaContext`
    - Borrar de `App.tsx`: `useState` de `solicitudes`, `cargandoSolicitudes`,
      `errorSolicitudes`, `reintentoSolicitudes`, `propuestas`,
      `cargandoPropuestas`, `errorPropuestas`, `reintentoPropuestas`,
      `cargandoTareas`, `errorTareas`, `reintentoTareas`.
    - Borrar los tres `useEffect` de carga (solicitudes + auto-refresh,
      propuestas, tareas globales).
    - Borrar la función `abrirPropuestaDesdeLista`.
    - Reemplazar todas las referencias por `const { ... } = useBandeja()`.
    - Verificar que `App.tsx` solo declara `useState` de `menuAbierto`
      (estado local de UI) y mantiene `estadoCorreo` / funciones de conexión
      de proveedor según la decisión de diseño.
    - _Requisitos: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 7.3 Escribir property test — Property 7: providers aislados
    - En un archivo de tests independiente (puede ser `SesionContext.test.tsx`
      o un nuevo `contextos.independencia.test.tsx`), agregar test con
      `fast-check`.
    - Para cada uno de los tres providers, verificar que puede montarse sin los
      otros dos y que el hook correspondiente devuelve un valor no nulo con el
      tipo correcto.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 7: Providers aislados — montaje independiente**
    - **Valida: Requisitos 6.1, 6.3**

  - [ ]* 7.4 Escribir property test — Property 8: navegación conserva estado del contexto
    - En `SolicitudContext.test.tsx`, agregar test con `fast-check`.
    - Para cualquier solicitud activa con componentes y mensajes cargados, al
      simular el cambio de pantalla de `'chat'` a `'propuesta'` (y volver), los
      componentes y mensajes del `SolicitudContext` no deben modificarse.
    - Ejecutar `npm test` y verificar que **pasa**.
    - **Property 8: Navegación conserva el estado de los contextos**
    - **Valida: Requisitos 7.2**

- [x] 8. Checkpoint final — `npm test` en verde tras Iteración 3
  - Ejecutar `npm test` y verificar que los **12 tests de `App.test.tsx`** y
    todos los tests de los tres contextos pasan sin errores.
  - Confirmar que `App.tsx` tiene menos de 150 líneas (sin imports).
  - Confirmar que `App.tsx` no declara ningún `useState` excepto `menuAbierto`
    (y `estadoCorreo` según la decisión de diseño).
  - _Requisitos: 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 7.1_

---

## Notes

- Las sub-tareas marcadas con `*` son opcionales y pueden saltarse para un MVP más rápido;
  las propiedades PBT son la red de seguridad extra pero los tests de ejemplo en cada `.test.tsx`
  ya validan el comportamiento esencial.
- El ciclo TDD es **obligatorio** en cada sub-tarea numerada sin `*`: primero escribe el test que
  falla (🔴), luego la implementación mínima que lo hace pasar (🟢), luego refactoriza (♻️).
- `estadoCorreo` y las funciones `conectarProveedor` / `desconectarProveedor` permanecen en
  `App.tsx` durante este refactor (decisión de diseño) y pueden moverse a `BandejaContext` en
  una iteración posterior.
- Cada tarea termina con `npm test` en verde antes de avanzar a la siguiente.
- Commits en español, mensajes descriptivos (p. ej. `refactor: extraer SesionContext desde App.tsx`).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "3.1"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.3"] },
    { "id": 6, "tasks": ["4.1"] },
    { "id": 7, "tasks": ["4.2"] },
    { "id": 8, "tasks": ["4.3", "4.4", "5.1"] },
    { "id": 9, "tasks": ["5.2"] },
    { "id": 10, "tasks": ["5.3"] },
    { "id": 11, "tasks": ["6.1"] },
    { "id": 12, "tasks": ["6.2"] },
    { "id": 13, "tasks": ["6.3", "6.4", "6.5", "6.6", "7.1"] },
    { "id": 14, "tasks": ["7.2"] },
    { "id": 15, "tasks": ["7.3", "7.4"] }
  ]
}
```
