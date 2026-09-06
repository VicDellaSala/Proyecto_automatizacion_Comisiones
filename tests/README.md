# Pruebas de Access Commerce

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
Pinpagos. Las columnas públicas de registros no pendientes mantienen sus valores
históricos; no se reabren pagos ni se modifica la regla provisional de pagos.

Fuera de alcance: mapeo temporal TX, observaciones,
pagos y motor de comisiones. Durante las pruebas se observó además que el
buscador genérico puede confundir ESTATUS con una columna TX cuando falta
CON TX; esa ruta ajena a Access queda pendiente y no se modificó.

Los sufijos TX mensuales se conservan como parte del encabezado; no se equipara
la columna con _1 a la columna sin sufijo. No se asignan meses hasta confirmar
el significado de _1. Los archivos de entrada reales se analizan desde sus
rutas originales, fuera del repositorio, sin incorporarlos a fixtures o logs.
