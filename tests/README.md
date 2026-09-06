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

Pendiente para cerrar la prioridad 1: archivo real de Access Commerce,
confirmación de su columna exacta y ejemplos conocidos de un afiliado presente
y otro ausente. Se conservan los alias exactos existentes; encabezados
ambiguos detienen el procesamiento en lugar de elegir una columna por posición.
No se asume que 00123 equivale a 123 ni se reconstruyen ceros perdidos en Excel.

El contador de UI refleja filas verificadas contra el Access cargado y excluye
Pinpagos. Las columnas públicas de registros no pendientes mantienen sus valores
históricos; no se reabren pagos ni se modifica la regla provisional de pagos.

Fuera de alcance: lista de PERTENENCIA R34, mapeo temporal TX, observaciones,
pagos y motor de comisiones. Durante las pruebas se observó además que el
buscador genérico puede confundir ESTATUS con una columna TX cuando falta
CON TX; esa ruta ajena a Access queda pendiente y no se modificó.
