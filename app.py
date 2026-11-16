import os
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
database_url = os.getenv("DATABASE_URL", "sqlite:///solicitudes.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

CATEGORIES = {"Hardware", "Software", "Red", "Accesos", "Otro"}
PRIORITIES = {"Baja", "Media", "Alta", "Urgente"}
STATUSES = {"Pendiente", "En proceso", "Resuelta", "Cancelada"}


class Solicitud(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    folio = db.Column(db.String(24), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(254), nullable=False)
    categoria = db.Column(db.String(40), nullable=False, index=True)
    prioridad = db.Column(db.String(20), nullable=False, index=True)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(24), nullable=False, default="Pendiente", index=True)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def as_dict(self):
        return {
            "id": self.id, "folio": self.folio, "nombre": self.nombre,
            "correo": self.correo, "categoria": self.categoria,
            "prioridad": self.prioridad, "descripcion": self.descripcion,
            "estado": self.estado,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
        }


def error(message, status):
    return jsonify({"error": message}), status


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        app.logger.exception("Database health check failed")
        return error("Base de datos no disponible", 503)


@app.post("/api/solicitudes")
def crear_solicitud():
    token = os.getenv("N8N_API_TOKEN")
    if token and request.headers.get("X-API-Key") != token:
        return error("No autorizado", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("El cuerpo debe ser JSON", 400)
    required = ("nombre", "correo", "categoria", "prioridad", "descripcion")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        return jsonify({"error": "Faltan campos obligatorios", "campos": missing}), 400
    vals = {key: data[key].strip() for key in required}
    if len(vals["nombre"]) > 120 or len(vals["correo"]) > 254 or len(vals["descripcion"]) > 5000:
        return error("Se excedió el máximo de caracteres permitido", 400)
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", vals["correo"]):
        return error("Correo electrónico no válido", 400)
    if vals["categoria"] not in CATEGORIES:
        return jsonify({"error": "Categoría no válida", "permitidas": sorted(CATEGORIES)}), 400
    if vals["prioridad"] not in PRIORITIES:
        return jsonify({"error": "Prioridad no válida", "permitidas": sorted(PRIORITIES)}), 400
    solicitud = Solicitud(**vals, folio="TEMP")
    db.session.add(solicitud)
    db.session.flush()
    solicitud.folio = f"ST-{datetime.now(timezone.utc):%Y%m%d}-{solicitud.id:06d}"
    db.session.commit()
    return jsonify(solicitud.as_dict()), 201


@app.get("/api/solicitudes")
def listar_solicitudes():
    query = Solicitud.query
    for field, allowed in (("estado", STATUSES), ("categoria", CATEGORIES), ("prioridad", PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in allowed:
                return error(f"Filtro {field} no válido", 400)
            query = query.filter(getattr(Solicitud, field) == value)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    if page < 1 or per_page < 1:
        return error("page y per_page deben ser positivos", 400)
    per_page = min(per_page, 100)
    result = query.order_by(Solicitud.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({"items": [s.as_dict() for s in result.items], "total": result.total, "page": page, "per_page": per_page, "pages": result.pages})


@app.get("/api/solicitudes/<folio>")
def obtener_solicitud(folio):
    solicitud = Solicitud.query.filter_by(folio=folio).first()
    return jsonify(solicitud.as_dict()) if solicitud else error("Solicitud no encontrada", 404)


@app.patch("/api/solicitudes/<folio>")
def actualizar_estado(folio):
    token = os.getenv("N8N_API_TOKEN")
    if token and request.headers.get("X-API-Key") != token:
        return error("No autorizado", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("estado") not in STATUSES:
        return jsonify({"error": "Indica un estado válido", "permitidos": sorted(STATUSES)}), 400
    solicitud = Solicitud.query.filter_by(folio=folio).first()
    if not solicitud:
        return error("Solicitud no encontrada", 404)
    solicitud.estado = data["estado"]
    db.session.commit()
    return jsonify(solicitud.as_dict())


@app.errorhandler(HTTPException)
def http_error(exc):
    return error(exc.description, exc.code or 500)


@app.errorhandler(Exception)
def unexpected_error(exc):
    db.session.rollback()
    app.logger.exception("Unhandled server error")
    return error("Error interno del servidor", 500)


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
