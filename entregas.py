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
import requests

def obtener_coordenadas(direccion):
    url = "https://apis.datos.gob.ar/georef/api/direcciones"
    
    # Intento 1: Dirección exacta limitada a la localidad de Corrientes
    params_exacto = {
        "direccion": direccion,
        "provincia": "Corrientes",
        "localidad": "Corrientes", # <-- Esto es la clave
        "max": 1
    }
    
    try:
        response = requests.get(url, params=params_exacto, timeout=5)
        data = response.json()
        
        if data.get("direcciones") and len(data["direcciones"]) > 0:
            ubicacion = data["direcciones"][0].get("ubicacion")
            if ubicacion:
                lat, lon = float(ubicacion["lat"]), float(ubicacion["lon"])
                # Corrientes Capital está aprox entre lat -27.3 a -27.6 y lon -58.7 a -58.9
                # Verificamos que no se haya ido a otra provincia o localidad lejana
                if -27.7 < lat < -27.3 and -59.0 < lon < -58.6:
                    return lat, lon
                
        # Intento 2: Si falló la altura exacta, buscar solo la calle
        calle = direccion.split()[0] 
        params_calle = {
            "direccion": calle,
            "provincia": "Corrientes",
            "localidad": "Corrientes",
            "max": 1
        }
        response_calle = requests.get(url, params=params_calle, timeout=5)
        data_calle = response_calle.json()
        
        if data_calle.get("direcciones") and len(data_calle["direcciones"]) > 0:
            ubicacion_calle = data_calle["direcciones"][0].get("ubicacion")
            if ubicacion_calle:
                lat, lon = float(ubicacion_calle["lat"]), float(ubicacion_calle["lon"])
                if -27.7 < lat < -27.3 and -59.0 < lon < -58.6:
                    return lat, lon

    except Exception as e:
        print(f"Error consultando Georef para '{direccion}':", e)
    
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
    
    
    return jsonify({"mensaje": "Entrega agregada", "id": nuevo_id}), 201

if __name__ == "__main__":
    app.run(debug=True)