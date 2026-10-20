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
    # Endpoint de Georef
    url = "https://apis.datos.gob.ar/georef/api/direcciones"
    
    # Intento 1: Buscar la dirección exacta en Corrientes
    params_exacto = {
        "direccion": direccion,
        "provincia": "Corrientes",
        "max": 1
    }
    
    try:
        response = requests.get(url, params=params_exacto, timeout=5)
        data = response.json()
        
        # Si encuentra algo...
        if data.get("direcciones") and len(data["direcciones"]) > 0:
            ubicacion = data["direcciones"][0].get("ubicacion")
            if ubicacion:
                return float(ubicacion["lat"]), float(ubicacion["lon"])
                
        # Intento 2: Si falló, intentamos buscar solo la calle (por si la altura no existe)
        # Ej: Si "Bolivar 1334" falla, buscamos "Bolivar"
        calle = direccion.split()[0] # Agarramos la primera palabra
        params_calle = {
            "direccion": calle,
            "provincia": "Corrientes",
            "max": 1
        }
        response_calle = requests.get(url, params=params_calle, timeout=5)
        data_calle = response_calle.json()
        
        if data_calle.get("direcciones") and len(data_calle["direcciones"]) > 0:
            ubicacion_calle = data_calle["direcciones"][0].get("ubicacion")
            if ubicacion_calle:
                return float(ubicacion_calle["lat"]), float(ubicacion_calle["lon"])

    except Exception as e:
        print(f"Error consultando Georef para '{direccion}':", e)
    
    # Si no encontró nada de nada
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