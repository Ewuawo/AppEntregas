from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import urllib.request
import urllib.parse
import json
import time

app = Flask(__name__)
DB_FILE = os.path.join(app.root_path, "entregas.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode = WAL;')
    conn.execute('PRAGMA synchronous = NORMAL;')
    conn.execute('PRAGMA busy_timeout = 5000;')
    return conn

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

# --- FUNCIÓN NUEVA: Geocodificación ---
def obtener_coordenadas(direccion):
    # Le agregamos "Corrientes, Argentina" para que busque en nuestra ciudad
    busqueda = f"{direccion}, Corrientes, Argentina"
    url = "https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(busqueda) + "&format=json&limit=1"
    
    # Nominatim exige que le digamos quiénes somos, si no, bloquea la petición
    req = urllib.request.Request(url, headers={'User-Agent': 'AppEntregasOficina/1.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print("Error buscando coordenadas:", e)
    
    return None, None

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
    direccion = data.get("direccion")
    
    # Buscamos las coordenadas antes de guardar
    lat, lon = obtener_coordenadas(direccion)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO entregas (direccion, destinatario, latitud, longitud) 
        VALUES (?, ?, ?, ?)
    ''', (direccion, data.get("destinatario"), lat, lon))
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    
    # Pequeña pausa para no saturar el servidor de mapas gratuito
    time.sleep(1) 
    
    return jsonify({"mensaje": "Entrega agregada", "id": nuevo_id}), 201

if __name__ == "__main__":
    app.run(debug=True)