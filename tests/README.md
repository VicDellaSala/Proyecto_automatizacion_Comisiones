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
CANAL DE VENTA=FREELANCER no clasifica la venta. BANCO=BANCARIBE con dos componentes
en VENDEDOR asigna 10 + 10 y conserva el texto completo, incluidos ambos nombres.
Bancaribe sin barra sigue como agente normal; no activa Freelancer. OFICINA/Tesoro
no aplica reparto de Jornada. Jornada exige coincidencia de BANCO y canal.

Las filas sin importes se completan únicamente cuando no hay dudas.
ESTATUS CXC define la modalidad. Las ventas normales usan CANAL como beneficiario
y fuente de tarifa, sin fallback a VENDEDOR ni a la columna de Jornada.
`normalizar_canal` centraliza los alias exactos OCCIDENTE/ORIENTE/CENTRO hacia
REGION OCCIDENTE/REGION ORIENTE/REGION CENTRO. CENTRO TIPO II es independiente.
Las nuevas se exportan con CANAL y beneficiario canónicos; los valores históricos
existentes se conservan y solo se normalizan internamente para el cálculo.
CANAL exactamente CREDICARDPOS usa VENDEDOR como Freelancer (10), o Persona/Bancaribe
(10 + 10), después de la detección de Jornada BT y sujeto a la excepción Bancaribe
sin barra. CREDICARDPOS nunca se asigna como agente. Bancos o roles sin persona
identificada requieren revisión. Un beneficiario desconocido conserva el cálculo interno
y requiere revisión. Los importes ya presentes, incluidos ceros y repartos parciales,
se conservan y se comparan con la regla; no se corrige el total silenciosamente.
La interfaz muestra la regla, los montos pendientes y los descuadres. El motor
no escribe ESTATUS, TX, Access, observaciones ni fechas de pago.

Fuera de alcance: mapeo temporal TX y reglas de distribución no confirmadas.

La revisión manual consta de tres controles sobre `__ORIGEN=VENTAS_NUEVAS`:
seriales repetidos (permitiendo elegir una histórica o nueva del grupo), serial operativo vs
todos los candidatos R34 y Tesoro no Jornada. Las decisiones usan `__ROW_ID` y
una firma de la evidencia para invalidarse si cambia el conflicto. Los tests
de `test_revision_manual.py` comprueban eliminación, observación DESINSTALADO,
elección de serial, recálculo de Jornada, persistencia de sesión simulada,
defaults que no bloquean descarga y exportación efectiva conservando el orden.
Las decisiones explícitas permiten desinstalar o eliminar la fila elegida.
DESINSTALADO colorea toda la fila con fuente roja, preservando los demás formatos.
La normalización compartida expande notación científica con Decimal sin inventar
dígitos perdidos en mantisas redondeadas. Pinpagos comparte el selector de serial
del procesamiento. Se conserva la copia ZIP de baja memoria.

La fuente de SERIAL R34 para todos los equipos prioriza el prefijo textual de
TERMINAL. La extracción está anclada al inicio, conserva los dígitos y elimina
el relleno inicial según la regla existente. Sin prefijo válido, solo se acepta
un SERIAL fiable: se conserva el texto original del CSV y se rechazan floats y
mantisas científicas resumidas como fuente definitiva. La falta de fuente fiable
aparece en revisión sin proponer ceros reconstruidos. Los tests de
`test_fuente_serial_r34.py` verifican CSV por chunks, prefijos, fallback y paridad
entre la revisión y el procesamiento automático para Castle, Zappy y Pinpagos.

`test_tipos_canal.py` reproduce asignaciones de None a campos numéricos de
revalidación, textos en columnas antes vacías y la conversión Oficina/Jornada.
La asignación usa tipos explícitos por columna y omite campos sin cambios;
las fórmulas o marcas mixtas históricas no se convierten a números ni se borran.

TX mensual (reglas confirmadas): actual corresponde al período del reporte y `_1`
al anterior, incluyendo enero/diciembre. FECHA REPORTE determina el origen; un
período ausente se diagnostica, no se deduce del nombre del archivo. R34 conserva
ANO_PROCESO/MES_PROCESO por registro y solicita respaldo manual solo para registros
sin período válido. Su monto prevalece sobre Ventas en la misma clave/año/mes;
las diferencias quedan internas. Solo se actualizan períodos explícitos de fuentes.

CON TX evalúa todo el historial: >1000, =1000, positivos menores, ceros/guiones,
y finalmente N/A si no hay datos utilizables. Un CON_TX previo se conserva.
Los vacíos e inválidos se distinguen internamente. Las observaciones N/A canónicas
se generan para ventas nuevas sin nota útil; se conservan las notas históricas.
Las columnas TX nuevas se insertan junto al bloque mediante XML, copiando estilos
y ajustando referencias. No se carga el workbook completo durante la exportación.

`test_tx_mensual.py` cubre calendario, prioridades, historial acumulativo, ausencia,
invalidación, respaldo de período, actualizaciones por `_1`, creación y exportación
con referencias a columnas desplazadas y tablas. Los datos de prueba son ficticios.
Los archivos reales nunca se incorporan al repositorio ni a los logs.

Validación 5.6: Pinpagos tiene total fijo de 15 USD, independiente de modalidad,
fecha y precio. Tesoro y Bancaribe especial distribuyen 7.50 + 7.50. Un reparto
indeterminado conserva el total conocido y deja los componentes pendientes;
los registros PAGADO conservan sus importes históricos para auditoría.
Jornada Tesoro y el reparto Bancaribe confirmado no requieren Access para pago.
La presencia real en Access sigue diagnosticándose sin inventar coincidencias.
`test_excepciones_pago.py` comprueba las excepciones y los negativos de detección.
El R34 admite el alias exacto MONTO_TRANS_BS_ACUM_MES_1 para el período anterior.
# Paso 2: alcance ampliado confirmado

La revisión de seriales incluye filas nuevas e históricas y muestra el período
de venta y de cada evidencia R34, junto con la fuente TERMINAL/SERIAL. Los registros
sintéticos de TX `_1` no constituyen evidencia de serial. Elegir un serial solo
actualiza el identificador público y su copia interna: no recalcula comisiones,
TX, estatus ni observaciones. Los tests cubren históricos PENDIENTE/PAGADO,
fuentes exactas y cambios de período que reabren una decisión.
