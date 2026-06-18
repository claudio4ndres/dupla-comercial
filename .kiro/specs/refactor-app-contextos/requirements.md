# Requirements Document

## Introduction

`App.tsx` concentra actualmente más de 20 `useState`, más de 300 líneas de código
y todos los efectos de carga de datos del frontend de Dupla Comercial. Cualquier
nueva feature obliga a agregar más estado en ese único archivo, lo que aumenta el
riesgo de regresión, dificulta el testeo unitario y encarece el mantenimiento.

Este refactor extrae el estado por dominio en tres **Contextos React** —
`SesionContext`, `SolicitudContext` y `BandejaContext` — sin cambiar ningún
comportamiento observable para el usuario. `App.tsx` queda como orquestador
de layout (Sidebar + Topbar + pantalla activa), delegando estado y efectos a cada
contexto.

El criterio de éxito más importante es negativo: **ningún test existente en
`App.test.tsx` puede romperse** tras el refactor.

---

## Glossary

- **App.tsx**: Componente raíz del frontend. Actualmente contiene todo el estado global y
  los efectos de carga. Tras el refactor queda solo como orquestador de layout.
- **Contexto React**: Mecanismo de React (`createContext` + `useContext`) para compartir
  estado entre componentes sin pasar props por varios niveles.
- **SesionContext**: Contexto responsable de la sesión de usuario (Supabase Auth) y de la
  empresa activa (tenant).
- **SolicitudContext**: Contexto responsable de la solicitud actualmente seleccionada, el
  tipo confirmado, el hilo de mensajes del chat con Javo, los componentes de cotización,
  las tareas asociadas y las fuentes citadas.
- **BandejaContext**: Contexto responsable de la lista de solicitudes, propuestas y tareas
  globales, junto con sus estados de carga, error y reintento.
- **Pantalla**: Estado de navegación simple por valor (`'configuracion'` | `'inbox'` |
  `'detail'` | `'chat'` | `'propuestas'` | `'propuesta'` | `'tareas'`). Permanece en
  `App.tsx` ya que es estado de layout.
- **Provider**: Componente que envuelve el árbol React y expone el valor de un contexto a
  sus descendientes.
- **Hook de contexto**: Función del tipo `useSesion()`, `useSolicitud()` o `useBandeja()`
  que encapsula la llamada a `useContext` y lanza un error si se usa fuera del Provider.
- **Tenant**: Empresa cliente del SaaS. El aislamiento de datos entre tenants se garantiza
  con RLS en la base de datos.
- **RLS**: Row Level Security de Supabase/Postgres. Filtra datos por `empresa_id` en el
  backend; el frontend no implementa filtros de seguridad propios.
- **Regresión**: Comportamiento que antes funcionaba y dejó de funcionar tras un cambio
  de código.

---

## Requirements

### Requirement 1: Extracción de SesionContext

**User Story:** Como desarrollador, quiero que el estado de sesión y empresa
activa viva en su propio contexto, para poder leer y actualizar la sesión desde cualquier
componente sin pasar props.

#### Acceptance Criteria

1. THE Sistema SHALL crear un `SesionContext` que exponga: `sesion` (`Sesion | null |
   undefined`), `empresa` (`Empresa`), `setEmpresa`, `cerrarSesion` y `pantalla`
   (`Pantalla`), `irA`.
2. WHEN el `SesionProvider` se monta, THE Sistema SHALL inicializar la sesión leyendo
   la sesión activa desde Supabase Auth y suscribirse a los cambios de autenticación
   (`onAuthStateChange`), exactamente igual que lo hace hoy `App.tsx`.
3. WHEN `sesion` cambia a un valor no nulo, THE Sistema SHALL solicitar al backend los
   datos reales de la empresa (`obtenerEmpresa`) y actualizar `empresa` con la respuesta.
4. WHEN `empresa` cambia, THE Sistema SHALL actualizar las variables CSS `--brand` y
   `--brand-soft` en el elemento raíz del documento, exactamente igual que hoy.
5. THE Sistema SHALL exponer un hook `useSesion()` que lance un error descriptivo en
   español si se llama fuera del `SesionProvider`.
6. WHEN el componente `App` usa `useSesion()`, THE Sistema SHALL leer `sesion`, `empresa`,
   `pantalla` e `irA` desde el contexto sin necesidad de recibirlos como props.

---

### Requirement 2: Extracción de SolicitudContext

**User Story:** Como desarrollador, quiero que todo el estado de la solicitud
activa (chat, componentes, tareas, fuentes) viva en su propio contexto, para poder
trabajar con la conversación de Javo sin que ese estado quede mezclado con el layout.

#### Acceptance Criteria

1. THE Sistema SHALL crear un `SolicitudContext` que exponga: `solicitudActual`
   (`Solicitud | null`), `tipo` (`TipoConfirmado`), `mensajes` (`Mensaje[]`),
   `componentes` (`Componente[]`), `tareas` (`Tarea[]`), `fuentes` (`Fuente[]`),
   `enviando` (`boolean`), `recursos` (`RecursoDrive[]`), y las acciones `abrirSolicitud`,
   `iniciarChat`, `enviarMensaje`, `generarPropuesta`.
2. WHEN `SolicitudProvider` se monta, THE Sistema SHALL cargar los recursos del Drive
   (`obtenerRecursosDrive`) al cambiar la empresa, exactamente igual que hoy.
3. WHEN `iniciarChat` es llamado con una solicitud y un tipo confirmado, THE Sistema
   SHALL limpiar el estado previo de mensajes, componentes, tareas y fuentes, insertar el
   mensaje inicial de Javo, y luego rehidratar el historial y la cotización en curso desde
   el backend, exactamente igual que hoy.
4. WHEN `enviarMensaje` es llamado, THE Sistema SHALL agregar el mensaje del usuario a la
   lista, llamar a `conversarConJavo` y actualizar mensajes, componentes, tareas y fuentes
   con la respuesta, exactamente igual que hoy.
5. WHEN `generarPropuesta` es llamado, THE Sistema SHALL persistir los componentes y tareas
   del chat mediante `guardarPropuesta` y luego navegar a la pantalla `'propuesta'`,
   exactamente igual que hoy.
6. THE Sistema SHALL exponer un hook `useSolicitud()` que lance un error descriptivo en
   español si se llama fuera del `SolicitudProvider`.
7. IF `useSolicitud()` es llamado fuera del `SolicitudProvider`, THEN THE Sistema SHALL
   lanzar un error con el mensaje `"useSolicitud debe usarse dentro de SolicitudProvider"`.

---

### Requirement 3: Extracción de BandejaContext

**User Story:** Como desarrollador, quiero que la lista de solicitudes, propuestas
y tareas globales con sus estados de carga viva en su propio contexto, para poder añadir
nuevas listas en el futuro sin tocar `App.tsx`.

#### Acceptance Criteria

1. THE Sistema SHALL crear un `BandejaContext` que exponga: `solicitudes` (`Solicitud[]`),
   `cargandoSolicitudes` (`boolean`), `errorSolicitudes` (`boolean`),
   `reintentoSolicitudes` (`number`), `setReintentoSolicitudes`; `propuestas`
   (`PropuestaResumen[]`), `cargandoPropuestas` (`boolean`), `errorPropuestas` (`boolean`),
   `reintentoPropuestas` (`number`), `setReintentoPropuestas`; `cargandoTareas`
   (`boolean`), `errorTareas` (`boolean`), `reintentoTareas` (`number`),
   `setReintentoTareas`; y la acción `abrirPropuestaDesdeLista`.
2. WHEN `pantalla` es `'inbox'` y `estadoCorreo.proveedor` no es nulo, THE Sistema SHALL
   cargar las solicitudes desde el backend e iniciar un auto-refresh cada 20 segundos,
   exactamente igual que hoy.
3. WHEN `pantalla` cambia a `'inbox'` y `estadoCorreo.proveedor` es nulo, THE Sistema
   SHALL limpiar la lista de solicitudes, exactamente igual que hoy.
4. WHEN `pantalla` es `'propuestas'`, THE Sistema SHALL cargar la lista de propuestas
   desde el backend, exactamente igual que hoy.
5. WHEN `pantalla` es `'tareas'` y no hay tareas en el contexto de solicitud activa, THE
   Sistema SHALL cargar la lista global de tareas desde el backend, exactamente igual que
   hoy.
6. IF cualquiera de las cargas falla, THEN THE Sistema SHALL establecer la bandera de error
   correspondiente en `true` para que el componente receptor pueda mostrar el banner de
   reintento. La bandera de error solo se activa cuando la solicitud HTTP falla; la creación
   exitosa del contexto no activa ninguna bandera de error.
7. WHEN el valor de `reintentoSolicitudes`, `reintentoPropuestas` o `reintentoTareas`
   aumenta, THE Sistema SHALL volver a ejecutar la carga correspondiente.
8. THE Sistema SHALL exponer un hook `useBandeja()` que lance un error descriptivo en
   español si se llama fuera del `BandejaProvider`.

---

### Requirement 4: Reducción de App.tsx a orquestador de layout

**User Story:** Como desarrollador, quiero que `App.tsx` sea responsable
únicamente del layout visual y la lógica de sesión de alto nivel, para que el archivo
sea fácil de leer y no crezca con cada nueva feature.

#### Acceptance Criteria

1. WHEN el refactor está completo, THE App.tsx SHALL contener solo: la lógica de layout
   (`Sidebar`, `Topbar`, área de contenido), la guarda de sesión (mostrar `Login` si no
   hay sesión, no renderizar si `sesion === undefined`) y la selección de pantalla
   (`if pantalla === 'inbox' → <Bandeja/>`, etc.).
2. THE App.tsx SHALL leer todo su estado desde los hooks de contexto (`useSesion`,
   `useSolicitud`, `useBandeja`) y NO SHALL declarar ningún `useState` propio (excepto
   `menuAbierto`, que es estado estrictamente local de UI).
3. THE Sistema SHALL mantener `menuAbierto` y su setter dentro de `App.tsx` porque es
   estado de presentación puro que no necesita compartirse.
4. WHEN el refactor está completo, THE App.tsx SHALL tener menos de 150 líneas de código
   (sin contar imports).
5. THE Sistema SHALL envolver el árbol de `App` con los tres providers en el orden
   `SesionProvider → BandejaProvider → SolicitudProvider` para garantizar el acceso
   correcto a dependencias entre contextos.

---

### Requirement 5: Compatibilidad total con los tests existentes

**User Story:** Como desarrollador, quiero que los tests actuales de `App.test.tsx`
sigan pasando sin modificación, para tener certeza de que el refactor no cambió ningún
comportamiento observable.

#### Acceptance Criteria

1. WHEN el refactor está completo, THE Sistema SHALL ejecutar la suite completa de
   `App.test.tsx` sin fallos ni errores.
2. THE Sistema SHALL mantener la prop `onNavegar` en el componente `App` con la misma
   firma que hoy (`(url: string) => void`), ya que varios tests la inyectan.
3. THE Sistema SHALL mantener el comportamiento de guardias de sesión: `null` en `sesion`
   muestra `<Login>`, `undefined` retorna `null` (sin flash al login).
4. WHEN un test monta `<App/>` con los mocks de Supabase y fetch, THE Sistema SHALL
   comportarse exactamente igual que la implementación actual: misma navegación, mismos
   estados de carga, mismo manejo de errores.
5. THE Sistema SHALL NO cambiar el contrato observable de ningún componente hijo (`Bandeja`,
   `Chat`, `Propuesta`, `Configuracion`, etc.) que los tests verifican por pantalla.

---

### Requirement 6: Testabilidad independiente de los contextos

**User Story:** Como desarrollador, quiero poder testear cada contexto de forma
aislada, para verificar su lógica sin necesidad de montar el árbol completo de `App`.

#### Acceptance Criteria

1. THE Sistema SHALL exportar cada Provider (`SesionProvider`, `SolicitudProvider`,
   `BandejaProvider`) como componente independiente que pueda montarse en un test sin
   depender de los otros.
2. THE Sistema SHALL exportar cada hook de contexto (`useSesion`, `useSolicitud`,
   `useBandeja`) desde su propio archivo para que los tests puedan importarlos
   directamente.
3. WHERE un test necesite verificar el estado de un contexto aislado, THE Sistema SHALL
   permitir envolver únicamente el `Provider` correspondiente alrededor de un componente
   de prueba sin requerir los otros dos providers.
4. THE Sistema SHALL tipar el valor de cada contexto con una interfaz TypeScript explícita
   (p. ej. `SesionContextValor`, `SolicitudContextValor`, `BandejaContextValor`) para
   facilitar el uso de `Partial<T>` en los mocks de tests.

---

### Requirement 7: Sin cambio de comportamiento observable para el usuario

**User Story:** Como usuario de Dupla Comercial, quiero que la aplicación siga
funcionando exactamente igual después del refactor, sin cambios en pantallas, flujos ni
tiempos de respuesta.

#### Acceptance Criteria

1. THE Sistema SHALL mantener el flujo completo: login → onboarding → bandeja → detalle
   → chat → propuesta → tareas, con el mismo comportamiento que antes del refactor.
2. WHEN el usuario navega entre pantallas, THE Sistema SHALL mantener el estado activo en
   los contextos (la solicitud activa, los componentes del chat, etc.) sin pérdida de
   datos.
3. THE Sistema SHALL mantener el auto-refresh de la bandeja con un intervalo nominal de 20
   segundos. Se acepta una tolerancia de ±2 segundos debida a latencia de red o tiempo de
   procesamiento (rango válido: 18–22 segundos).
4. WHEN el usuario cambia de empresa (tenant), THE Sistema SHALL resetear el estado
   relevante de la bandeja y recargar los datos del nuevo tenant, igual que hoy.
5. THE Sistema SHALL mantener el white-label: al cambiar de empresa, las variables CSS
   `--brand` y `--brand-soft` se actualizan inmediatamente.
6. THE Sistema SHALL mantener la rehidratación de la cotización en curso (`0009`) al
   entrar al chat de una solicitud con borrador previo.
