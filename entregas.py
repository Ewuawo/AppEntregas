from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_FILE = os.path.join(app.root_path, "entregas.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    # Mismos ajustes de velocidad que usamos en trámites
    conn.execute('PRAGMA journal_mode = WAL;')
    conn.execute('PRAGMA synchronous = NORMAL;')
    conn.execute('PRAGMA busy_timeout = 5000;')
    return conn

# Creamos la tabla automáticamente si no existe
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direccion TEXT NOT NULL,
            destinatario TEXT,
            estado TEXT DEFAULT 'pendiente',
            latitud REAL,
            longitud REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("entregas.html")

@app.route("/api/entregas", methods=["GET"])
def listar_entregas():
    conn = get_db_connection()
    entregas = conn.execute('SELECT * FROM entregas WHERE estado = "pendiente"').fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in entregas])

@app.route("/api/entregas", methods=["POST"])
def agregar_entrega():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO entregas (direccion, destinatario) VALUES (?, ?)
    ''', (data.get("direccion"), data.get("destinatario")))
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return jsonify({"mensaje": "Entrega agregada", "id": nuevo_id}), 201

if __name__ == "__main__":
    # host='0.0.0.0' permite que el celular se conecte por Wi-Fi
    app.run(debug=True, host='0.0.0.0', port=5001)