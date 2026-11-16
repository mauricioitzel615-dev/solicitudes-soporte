# Sistema automatizado de gestión de solicitudes

Backend de la práctica de segundo parcial. Implementado en Python con Flask y SQLAlchemy; usa PostgreSQL en producción y SQLite localmente si no se configura `DATABASE_URL`.

## Ejecutar localmente

1. Instala Python 3.11 o posterior.
2. En esta carpeta crea un entorno e instala dependencias:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. Para desarrollo local puedes dejar `DATABASE_URL` sin configurar (usa `solicitudes.db`). Ejecuta `python app.py`. La API queda en `http://localhost:5000`.

## API

### Registrar solicitud

`POST /api/solicitudes` con `Content-Type: application/json`:

```json
{
  "nombre": "Ana Pérez",
  "correo": "ana@example.com",
  "categoria": "Software",
  "prioridad": "Alta",
  "descripcion": "No puedo iniciar sesión en el sistema"
}
```

Respuesta `201`: solicitud con folio `ST-AAAAMMDD-000001`, estado inicial `Pendiente` e identificador. Categorías aceptadas: `Hardware`, `Software`, `Red`, `Accesos`, `Otro`. Prioridades: `Baja`, `Media`, `Alta`, `Urgente`.

### Consultar

- `GET /api/solicitudes` lista registros; admite `page`, `per_page` (máximo 100), `categoria`, `prioridad` y `estado`.
- `GET /api/solicitudes/ST-AAAAMMDD-000001` consulta por folio.
- `PATCH /api/solicitudes/ST-AAAAMMDD-000001` cambia estado enviando `{"estado":"En proceso"}`. Estados: `Pendiente`, `En proceso`, `Resuelta`, `Cancelada`.
- `GET /health` comprueba la conexión a la base de datos.

Cuando `N8N_API_TOKEN` está configurado, `POST` y `PATCH` requieren encabezado `X-API-Key` con ese valor. Las consultas son públicas para facilitar el dashboard de la práctica; se recomienda restringirlas antes de usar datos reales.

## Despliegue en Neon y Render

1. Crea un proyecto PostgreSQL en Neon y copia la cadena de conexión pooled, con SSL (`sslmode=require`).
2. Sube el contenido de esta carpeta a un repositorio Git.
3. En Render crea un **Web Service** conectado al repositorio. Runtime: Python. Build command: `pip install -r requirements.txt`. Start command: `gunicorn app:app`.
4. En Render > Environment agrega `DATABASE_URL` (cadena Neon) y `N8N_API_TOKEN` (secreto aleatorio largo). Render asigna `PORT` automáticamente.
5. Espera el despliegue y visita `/health`. Debe responder `{"database":"connected","status":"ok"}`.

La tabla se crea automáticamente al iniciar. Para una entrega productiva conviene gestionar cambios de esquema con migraciones; para esta práctica el esquema inicial se crea sin pasos manuales.

## Google Forms, Sheets y n8n

1. Crea un Google Form con nombre, correo, categoría, prioridad y descripción. Vincúlalo a una hoja de cálculo desde la pestaña Respuestas.
2. En n8n crea un workflow con disparador **Google Sheets Trigger** (nueva fila). Mapea las columnas del formulario a los cinco nombres JSON mostrados arriba.
3. Añade nodo **HTTP Request**: `POST https://TU-SERVICIO.onrender.com/api/solicitudes`, autenticación mediante encabezado `X-API-Key` guardado como credencial/variable y `Content-Type: application/json`; envía el JSON mapeado.
4. Añade nodo **Google Sheets: Update Row** para guardar el `folio` y el `estado` recibido en la fila original. Si tu disparador no ofrece actualización de fila, conserva el número de fila de entrada y usa Google Sheets Append/Update según el nodo disponible.
5. Añade nodo Gmail después de la respuesta HTTP. Destinatario: correo del solicitante; asunto: `Solicitud recibida: {{$json.folio}}`; cuerpo: confirma el folio, la categoría y el estado inicial.
6. Activa el workflow y verifica la ejecución en n8n. Mantén la URL y el token como secretos; no los escribas en hojas compartidas.

## Dashboard en Google Sheets

En una segunda pestaña crea métricas con la tabla de respuestas. Para una vista dinámica basada en las columnas de categoría y prioridad se pueden usar tablas dinámicas (Insertar > Tabla dinámica): conteo de solicitudes por categoría y por prioridad. Para total, usa `=COUNTA('Respuestas de formulario 1'!A2:A)` (ajusta el nombre de la hoja y la columna a tu formulario). Inserta gráficos de barras para categoría y prioridad y una tarjeta/celda destacada para el total. Si se sincronizan folio y estado desde n8n, conserva esas columnas al final de la hoja.

## Alcance de esta entrega

Se entrega el backend y su guía. La creación real del servicio en Render, la base Neon, el Form, la hoja y el workflow requiere acceso a las cuentas del alumno y no se realiza desde este código. No compartas contraseñas; basta con que despliegues y pegues los nombres de columnas si quieres que adapte el mapeo de n8n.
