# Lecturas eficientes para la PWA

`GET /mermas/sucursales/{ids}` conserva `mermas` y añade:

- `limit`: opcional, entre 1 y 200. El móvil solicita 20. Sin limit se mantiene el listado completo anterior.
- `offset`: posición inicial, desde cero.
- `fecha_inicio` y `fecha_fin`: fechas ISO opcionales, extremos inclusivos.
- `total`: número de cabeceras que cumplen los filtros.
- `resumen`: totalRegistros, totalImporte, mermasHoy, mermasMes y mermasUltimos30Dias.

El resumen se calcula sobre todo el conjunto filtrado, no sobre la página.
Se usa la misma relación Cantidad × Precio del detalle existente. El importe se
obtiene con SUM en SQL y no requiere que el móvil descargue cada detalle.
No se modifica el esquema de la base de datos.

El middleware de lecturas añade ETag y Cache-Control privado a respuestas JSON
operativas exitosas de hasta 2 MiB. Devuelve 304 sin cuerpo si coinciden. Siempre
ejecuta el endpoint y su autorización antes de comparar: el ahorro es de tráfico,
no una caché de resultados SQL. No modifica escrituras ni respuestas de error.
GZip comprime respuestas desde 1024 bytes y CORS expone ETag al frontend.

Publicar este backend antes del frontend que usa la nueva paginación y resumen.
La PWA conserva listados cinco minutos y renueva el módulo afectado al guardar.

Pruebas locales sin conectar a MySQL:

```
.venv\Scripts\python.exe -m unittest discover -s tests -p test_read_cache.py
```

Las pruebas verifican filtros/paginación SQL con un cursor simulado, cierres de
conexión, validación ETag y compresión. Comprobar tiempos y planes SQL contra la
base de datos del entorno de pruebas antes de cuantificar el ahorro real.
