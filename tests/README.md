# Pruebas de procesamiento

Ejecutar desde la raíz, con las dependencias de requirements.txt instaladas:

```sh
python -m unittest discover -s tests -v
```

Los datos son sintéticos; no representan afiliados operativos confirmados.
Las pruebas cubren presencia y ausencia, números/texto, sufijo .0, ceros
iniciales conservados, marcadores vacíos, encabezados parciales/ambiguos,
revalidación, Pinpagos y separación entre Access actual y marcas históricas.
La prueba integrada verifica filtros de ventas, TX de 1 Bs y exportación
del mismo libro por ZIP/XML, conservando las otras partes y una fórmula.
No constituye una validación de memoria con libros grandes ni de apertura
en Microsoft Excel.

Access se cruza por su columna AFILIADO, con aliases exactos y sin coincidencias
parciales. Sus encabezados ambiguos siguen deteniendo el procesamiento.
No se asume que 00123 equivale a 123 ni se reconstruyen ceros perdidos en Excel.

En Comisiones se conservan los encabezados originales asociados a las posiciones
del DataFrame. El bloque operativo reconocido es CONCATENAR, AFILIADO, TERMINAL,
FECHA, VENDEDOR, EQUIPO, SERIAL. Se usa en preparación, comparación de ventas,
R34, Access y revalidación. Los bloques auxiliares existentes se conservan.
Los tests usan bloques con valores ficticios diferentes para detectar una
selección incorrecta que quedaría oculta si ambas columnas fueran iguales.
Un diseño desconocido con identidades repetidas requiere confirmación.

La lista blanca R34 acepta únicamente CREDICARD POS, CREDICARDPOS y
CREDICARDPOS CDM después de normalizar mayúsculas y espacios. Las pruebas
verifican positivos y negativos repartidos entre varios chunks.

El contador de UI refleja filas verificadas contra el Access cargado y excluye
Pinpagos. Los registros no pendientes conservan sus valores históricos de Access;
no se reabren pagos ni se modifica la regla provisional de pagos.

OBSERVACION se identifica junto a ESTATUS y MES DE CIERRE, conservando la
observación del bloque CXC. Las notas históricas y manuales se preservan
literalmente. Solo las notas automáticas identificadas en la sesión pueden
recalcularse. Al cargar nuevamente un libro, todo texto existente es histórico.
Los casos N/A o N/D se señalan para revisión aunque conserven una nota anterior.
Las observaciones no modifican ESTATUS, fechas ni componentes de comisión.

La generación se aplica a pendientes y ventas nuevas, y continúa durante la
sesión para esas filas si pasan a Aplica Pago. La generación sobre celdas vacías
de registros previamente PAGADO/DESINSTALADO queda pendiente de confirmación.
No se inventa una observación de pago para REVISAR 1000 o estados desconocidos.

CON TX se normaliza también en filas históricas: las variantes conocidas se
unifican, manteniendo separados N/A, N/D, SIN TX y C/P SIN TX. Se conserva el texto
de etiquetas desconocidas. La columna se resuelve mediante encabezados exactos
para que su ausencia nunca provoque escribir etiquetas TX en ESTATUS.

El motor de distribución está centralizado en reglas_comisiones.py. Las pruebas
cubren Comodato por FECHA, los cortes inclusivos, Al Contado, precios editables,
equivalencias explícitas del 16%, Tesoro/Jornada y Freelancer/Bancaribe.
La modalidad determina la tarifa de Al Contado antes de repartir banco/resto;
la excepción Zappy/Jornada de total 25 se limita a Comodato.

El resultado incluye beneficiarios, componentes, total, regla aplicada,
advertencia, requiere_revision, diferencia y monto_pendiente_asignacion.
El cuadre usa aritmética decimal: diferencia = componentes menos total.
No se extrapolan bancos o agentes desconocidos ni se inventan beneficiarios.
Un rol FREELANCER explícito puede tomar el nombre de VENDEDOR; un nombre libre
sin rol no autoriza esa inferencia. OFICINA/Tesoro sigue requiriendo aclaración
si no hay evidencia explícita de jornada.

Las ventas nuevas sin importes se completan únicamente cuando no hay dudas.
Los importes ya presentes, incluidos ceros e históricos vacíos/incompletos,
se conservan y se comparan con la regla; no se corrige el total silenciosamente.
La interfaz muestra la regla, los montos pendientes y los descuadres. El motor
no escribe ESTATUS, TX, Access, observaciones ni fechas de pago.

Fuera de alcance: mapeo temporal TX y reglas de distribución no confirmadas.

Los sufijos TX mensuales se conservan como parte del encabezado; no se equipara
la columna con _1 a la columna sin sufijo. No se asignan meses hasta confirmar
el significado de _1. Los archivos de entrada reales se analizan desde sus
rutas originales, fuera del repositorio, sin incorporarlos a fixtures o logs.
