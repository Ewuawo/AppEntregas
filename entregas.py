import os
import requests
from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Leemos la URL de conexión desde una variable de entorno
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    # Render a veces da la URL con "postgres://", pero psycopg2 espera "postgresql://"
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        db_url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    else:
        db_url = DATABASE_URL
        
    # Aiven requiere SSL, y psycopg2 lo maneja si la URL tiene sslmode=require
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entregas (
            id SERIAL PRIMARY KEY,
            direccion TEXT NOT NULL,
            destinatario TEXT,
            estado TEXT DEFAULT 'pendiente',
            latitud REAL,
            longitud REAL
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# Llamamos a init_db() solo si la URL existe
if DATABASE_URL:
    init_db()

# ... (El resto de tu código: obtener_coordenadas, listar_entregas, agregar_entrega, completar_entrega, etc. queda IGUAL, pero usando get_db_connection() y cursores de psycopg2)

# --- FUNCIÓN: Geocodificación con Georef ---
def obtener_coordenadas(direccion):
    url = "https://apis.datos.gob.ar/georef/api/direcciones"
    
    # Intento 1: Dirección exacta limitada a la localidad de Corrientes
    params_exacto = {
        "direccion": direccion,
        "provincia": "Corrientes",
        "localidad": "Corrientes",
        "max": 1
    }
    
    try:
        response = requests.get(url, params=params_exacto, timeout=5)
        data = response.json()
        
        if data.get("direcciones") and len(data["direcciones"]) > 0:
            ubicacion = data["direcciones"][0].get("ubicacion")
            if ubicacion:
                lat, lon = float(ubicacion["lat"]), float(ubicacion["lon"])
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
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM entregas WHERE estado = %s ORDER BY id ASC', ('pendiente',))
    entregas = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(entregas)

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
    
    # Le avisamos al HTML si encontró o no la dirección
    return jsonify({"mensaje": "Entrega agregada", "id": nuevo_id, "encontrado": lat is not None}), 201

@app.route("/api/entregas/<int:id>/completar", methods=["PUT"])
def completar_entrega(id):
    conn = get_db_connection()
    conn.execute('UPDATE entregas SET estado = "entregado" WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({"mensaje": "Entrega completada"}), 200

if __name__ == "__main__":
    app.run(debug=True)