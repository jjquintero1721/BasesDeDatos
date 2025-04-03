from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from datetime import datetime
from decimal import Decimal
import os
import hashlib
from flask import session, redirect, url_for

app = Flask(__name__)
import os
import secrets

# Generar clave secreta más segura (actualizar esta línea en App.py)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configuración de la base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'lavadovehiculos'
}

# Función para obtener conexión a la base de datos
def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn, conn.cursor(dictionary=True)

# Página principal - Dashboard
@app.route('/')
def index():
    conn, cursor = get_db_connection()
    
    # Obtener tipos de vehículos para el dropdown
    cursor.execute("SELECT ID, Tipo FROM vehiculos WHERE estado = 'Activo'")
    tipos_vehiculos = cursor.fetchall()
    
    # Obtener tipos de lavado para el dropdown
    cursor.execute("SELECT ID, nombre FROM tiposlavado WHERE estado = 'Activo'")
    tipos_lavado = cursor.fetchall()
    
    # Obtener empleados activos
    cursor.execute("SELECT ID, nombre, apellidos FROM empleados WHERE estado = 'Activo'")
    empleados = cursor.fetchall()
    
    # Obtener servicios pendientes
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT COUNT(*) as pendientes 
        FROM servicio 
        WHERE DATE(fecha) = %s AND hora_entrega IS NULL
    """, (today,))
    result = cursor.fetchone()
    pendientes = result['pendientes'] if result and 'pendientes' in result else 0
    
    # Obtener ingresos diarios
    cursor.execute("""
        SELECT SUM(precio) as ingresos 
        FROM servicio 
        WHERE DATE(fecha) = %s
    """, (today,))
    result = cursor.fetchone()
    ingresos = float(result['ingresos']) if result and result['ingresos'] else 0
    
    # Verificar insumos con stock bajo
    cursor.execute("""
        SELECT COUNT(*) as alertas 
        FROM inventario 
        WHERE stock < 10 AND estado = 'Disponible'
    """)
    result = cursor.fetchone()
    alertas = result['alertas'] if result and 'alertas' in result else 0
    
    conn.close()
    
    return render_template(
        'index.html', 
        tipos_vehiculos=tipos_vehiculos,
        tipos_lavado=tipos_lavado,
        empleados=empleados,
        pendientes=pendientes,
        ingresos=ingresos,
        alertas=alertas
    )

# RF001 - Registro de Vehículos
@app.route('/registro', methods=['GET', 'POST'])
def registro_vehiculo():
    if request.method == 'POST':
        conn, cursor = get_db_connection()
        
        placa = request.form.get('placa')
        tipo_vehiculo = request.form.get('tipo_vehiculo')
        tipo_lavado = request.form.get('tipo_lavado')
        empleado_recibe = request.form.get('empleado_recibe')
        empleado_lava = request.form.get('empleado_lava')
        
        # Obtener hora actual
        now = datetime.now()
        
        # Obtener precio del tipo de lavado
        cursor.execute("SELECT costo FROM tiposlavado WHERE ID = %s", (tipo_lavado,))
        result = cursor.fetchone()
        precio = result['costo'] if result else 0
        
        # Insertar el servicio
        cursor.execute("""
            INSERT INTO servicio 
            (fecha, id_emp_recibe, id_emp_lava, id_tipovehiculo, id_tipolavado, hora_recibe, placa, precio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (now, empleado_recibe, empleado_lava, tipo_vehiculo, tipo_lavado, now.strftime('%H:%M:%S'), placa, precio))
        
        conn.commit()
        conn.close()
        
        flash('Vehículo registrado correctamente', 'success')
        return redirect(url_for('servicios_pendientes'))
    
    # Si es GET, obtener datos para los dropdowns
    conn, cursor = get_db_connection()
    
    cursor.execute("SELECT ID, Tipo FROM vehiculos WHERE estado = 'Activo'")
    tipos_vehiculos = cursor.fetchall()
    
    cursor.execute("SELECT ID, nombre FROM tiposlavado WHERE estado = 'Activo'")
    tipos_lavado = cursor.fetchall()
    
    cursor.execute("SELECT ID, nombre, apellidos FROM empleados WHERE estado = 'Activo'")
    empleados = cursor.fetchall()
    
    conn.close()
    
    return render_template(
        'registro.html', 
        tipos_vehiculos=tipos_vehiculos, 
        tipos_lavado=tipos_lavado, 
        empleados=empleados
    )

@app.route('/servicios/pendientes')
def servicios_pendientes():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT s.*, v.Tipo as tipo_vehiculo, t.nombre as tipo_lavado, 
               CONCAT(e1.nombre, ' ', e1.apellidos) as recibido_por,
               CONCAT(e2.nombre, ' ', e2.apellidos) as lavado_por
        FROM servicio s
        JOIN vehiculos v ON s.id_tipovehiculo = v.ID
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        JOIN empleados e1 ON s.id_emp_recibe = e1.ID
        JOIN empleados e2 ON s.id_emp_lava = e2.ID
        WHERE s.hora_entrega IS NULL
        ORDER BY s.fecha DESC
    """)
    
    servicios = cursor.fetchall()
    
    # Obtener insumos para el modal - MODIFICADO para asegurar que devuelva resultados
    cursor.execute("""
        SELECT i.ID, i.nombre, inv.stock 
        FROM insumos i
        JOIN inventario inv ON i.ID = inv.id_insumo
        WHERE inv.stock > 0 AND i.estado = 'Disponible'
        ORDER BY i.nombre
    """)
    insumos = cursor.fetchall()
    
    # Para depuración
    print(f"Número de insumos encontrados: {len(insumos)}")
    for insumo in insumos:
        print(f"Insumo: {insumo['nombre']}, ID: {insumo['ID']}, Stock: {insumo['stock']}")
    
    conn.close()
    
    return render_template('servicios_pendientes.html', servicios=servicios, insumos=insumos)

# Función API para obtener insumos disponibles (para cargar por AJAX en el modal)
@app.route('/api/insumos-disponibles')
def api_insumos_disponibles():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT i.ID, i.nombre, inv.stock 
        FROM insumos i
        JOIN inventario inv ON i.ID = inv.id_insumo
        WHERE inv.stock > 0 AND i.estado = 'Disponible'
        ORDER BY i.nombre
    """)
    
    insumos = cursor.fetchall()
    conn.close()
    
    # Convertir a lista de diccionarios para enviar como JSON
    insumos_list = []
    for insumo in insumos:
        insumos_list.append({
            'ID': insumo['ID'],
            'nombre': insumo['nombre'],
            'stock': insumo['stock']
        })
    
    return jsonify(insumos_list)
# RF005 - Historial de Servicios
@app.route('/historial', methods=['GET'])
def historial_vehiculo():
    placa = request.args.get('placa', '')
    
    if not placa:
        return render_template('historial.html', servicios=None, placa='')
    
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT s.*, v.Tipo as tipo_vehiculo, t.nombre as tipo_lavado, 
               CONCAT(e1.nombre, ' ', e1.apellidos) as recibido_por,
               CONCAT(e2.nombre, ' ', e2.apellidos) as lavado_por
        FROM servicio s
        JOIN vehiculos v ON s.id_tipovehiculo = v.ID
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        JOIN empleados e1 ON s.id_emp_recibe = e1.ID
        JOIN empleados e2 ON s.id_emp_lava = e2.ID
        WHERE s.placa = %s
        ORDER BY s.fecha DESC
    """, (placa,))
    
    servicios = cursor.fetchall()
    conn.close()
    
    return render_template('historial.html', servicios=servicios, placa=placa)

# RF003 - Registro de Insumos Utilizados
@app.route('/insumos/usar', methods=['POST'])
def usar_insumos():
    servicio_id = request.form.get('servicio_id')
    insumo_id = request.form.get('insumo_id')
    cantidad = int(request.form.get('cantidad'))
    
    conn, cursor = get_db_connection()
    
    # Verificar stock disponible
    cursor.execute("SELECT stock FROM inventario WHERE id_insumo = %s", (insumo_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        flash('Insumo no encontrado', 'danger')
        return redirect(url_for('servicios_pendientes'))
        
    stock_actual = result['stock']
    
    if stock_actual < cantidad:
        conn.close()
        flash('No hay suficiente stock disponible', 'danger')
        return redirect(url_for('servicios_pendientes'))
    
    # Actualizar inventario
    cursor.execute("UPDATE inventario SET stock = stock - %s WHERE id_insumo = %s", (cantidad, insumo_id))
    conn.commit()
    conn.close()
    
    flash('Insumo utilizado correctamente', 'success')
    return redirect(url_for('servicios_pendientes'))

# RF006 - Tiempo Promedio por Tipo de Lavado
@app.route('/reportes/tiempo')
def tiempo_promedio():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT t.nombre, 
               AVG(TIME_TO_SEC(TIMEDIFF(s.hora_entrega, s.hora_recibe)))/60 as minutos_promedio,
               COUNT(s.ID) as total_servicios
        FROM servicio s
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        WHERE s.hora_entrega IS NOT NULL
        GROUP BY t.ID
        ORDER BY t.nombre
    """)
    
    tiempos = cursor.fetchall()
    conn.close()
    
    return render_template('reporte_tiempo.html', tiempos=tiempos)

# RF007 - Reporte de Ingresos Diarios
@app.route('/reportes/ingresos')
def ingresos_diarios():
    fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT s.*, v.Tipo as tipo_vehiculo, t.nombre as tipo_lavado
        FROM servicio s
        JOIN vehiculos v ON s.id_tipovehiculo = v.ID
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        WHERE DATE(s.fecha) = %s
        ORDER BY s.hora_recibe
    """, (fecha,))
    
    servicios = cursor.fetchall()
    
    # Calcular total manejando valores nulos
    total = 0
    for s in servicios:
        precio = s.get('precio')
        if precio is not None:
            total += float(precio)
    
    conn.close()
    
    now = datetime.now().strftime('%Y-%m-%d')
    return render_template('reporte_ingresos.html', servicios=servicios, fecha=fecha, total=total, now=now)

# RF008 - Identificación de Insumos con Stock Bajo
@app.route('/insumos/stock-bajo')
def insumos_stock_bajo():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT i.*, inv.stock
        FROM insumos i
        JOIN inventario inv ON i.ID = inv.id_insumo
        WHERE inv.stock < 10 AND i.estado = 'Disponible'
        ORDER BY inv.stock ASC
    """)
    
    insumos = cursor.fetchall()
    conn.close()
    
    return render_template('insumos_stock_bajo.html', insumos=insumos)

# Reponer insumos
@app.route('/insumos/reponer', methods=['POST'])
def reponer_insumos():
    insumo_id = request.form.get('insumo_id')
    cantidad = int(request.form.get('cantidad'))
    
    conn, cursor = get_db_connection()
    
    # Actualizar inventario
    cursor.execute("UPDATE inventario SET stock = stock + %s WHERE id_insumo = %s", (cantidad, insumo_id))
    conn.commit()
    conn.close()
    
    flash('Insumo repuesto correctamente', 'success')
    return redirect(url_for('insumos_stock_bajo'))

# RF009 - Carga de Trabajo por Empleado
@app.route('/carga-trabajo')
def carga_trabajo():
    conn, cursor = get_db_connection()
    
    # Asegurarse de contar correctamente los servicios pendientes para cada empleado
    cursor.execute("""
        SELECT e.ID, e.nombre, e.apellidos, 
               COUNT(s.ID) as carga
        FROM empleados e
        LEFT JOIN servicio s ON e.ID = s.id_emp_lava AND s.hora_entrega IS NULL
        WHERE e.estado = 'Activo'
        GROUP BY e.ID
        ORDER BY carga DESC
    """)
    
    empleados = cursor.fetchall()
    
    # Asegurar que todos los empleados tengan un valor de carga, incluso si es 0
    for emp in empleados:
        if 'carga' not in emp or emp['carga'] is None:
            emp['carga'] = 0
    
    conn.close()
    
    return render_template('carga_trabajo.html', empleados=empleados)

# RF010 - Gestión de Turnos
@app.route('/turnos')
def turnos():
    conn, cursor = get_db_connection()
    
    cursor.execute("SELECT * FROM empleados WHERE estado = 'Activo'")
    empleados = cursor.fetchall()
    
    cursor.execute("SELECT * FROM jornadas WHERE estado = 'Activo'")
    jornadas = cursor.fetchall()
    
    cursor.execute("""
        SELECT t.*, e.nombre, e.apellidos, j.hora_inicio, j.hora_final
        FROM turnosempleados t
        JOIN empleados e ON t.id_empleado = e.ID
        JOIN jornadas j ON t.id_jornada = j.ID
        ORDER BY t.dia, j.hora_inicio
    """)
    turnos = cursor.fetchall()
    
    conn.close()
    
    return render_template('turnos.html', empleados=empleados, jornadas=jornadas, turnos=turnos)

# Añadir turno
@app.route('/turnos/add', methods=['POST'])
def add_turno():
    empleado = request.form.get('empleado')
    dia = request.form.get('dia')
    jornada = request.form.get('jornada')
    
    conn, cursor = get_db_connection()
    
    # Verificar si ya existe un turno para ese empleado en ese día y jornada
    cursor.execute("""
        SELECT * FROM turnosempleados 
        WHERE id_empleado = %s AND dia = %s AND id_jornada = %s
    """, (empleado, dia, jornada))
    
    existe = cursor.fetchone()
    
    if existe:
        flash('El empleado ya tiene asignado ese turno', 'warning')
    else:
        # Insertar nuevo turno
        cursor.execute("""
            INSERT INTO turnosempleados (dia, id_empleado, id_jornada)
            VALUES (%s, %s, %s)
        """, (dia, empleado, jornada))
        conn.commit()
        flash('Turno asignado correctamente', 'success')
    
    conn.close()
    
    return redirect(url_for('turnos'))

# Completar un servicio
@app.route('/completar-servicio/<int:id>', methods=['POST'])
def completar_servicio(id):
    conn, cursor = get_db_connection()
    
    hora_entrega = datetime.now().strftime('%H:%M:%S')
    
    cursor.execute("UPDATE servicio SET hora_entrega = %s WHERE ID = %s", (hora_entrega, id))
    conn.commit()
    conn.close()
    
    flash('Servicio completado correctamente', 'success')
    return redirect(url_for('servicios_pendientes'))

# Filtros personalizados para Jinja2
@app.template_filter('default_if_none')
def default_if_none(value, default_value=0):
    return default_value if value is None else value

@app.template_filter('safe_round')
def safe_round(value, precision=2):
    if value is None:
        return 0
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return 0

# Estas funciones deben añadirse al archivo App.py existente

# RQ-UF44 - Evaluación del servicio
@app.route('/evaluar/<string:placa>', methods=['GET', 'POST'])
def evaluar_servicio(placa):
    if request.method == 'POST':
        servicio_id = request.form.get('servicio_id')
        tiempo_espera = request.form.get('tiempo_espera')
        amabilidad_personal = request.form.get('amabilidad_personal')
        calidad_servicio = request.form.get('calidad_servicio')
        
        conn, cursor = get_db_connection()
        
        # Verificar que el servicio existe y corresponde a la placa
        cursor.execute("SELECT ID FROM servicio WHERE ID = %s AND placa = %s", (servicio_id, placa))
        if not cursor.fetchone():
            conn.close()
            flash('El servicio no existe o no corresponde a la placa indicada', 'danger')
            return redirect(url_for('evaluar_servicio', placa=placa))
        
        # Insertar evaluación
        cursor.execute("""
            INSERT INTO evaluaciones (id_servicio, tiempo_espera, amabilidad_personal, calidad_servicio, fecha_evaluacion)
            VALUES (%s, %s, %s, %s, %s)
        """, (servicio_id, tiempo_espera, amabilidad_personal, calidad_servicio, datetime.now()))
        
        conn.commit()
        conn.close()
        
        flash('¡Gracias por evaluar nuestro servicio!', 'success')
        return render_template('evaluacion_exitosa.html')
    
    # Obtener servicios de la placa para mostrar en el formulario
    conn, cursor = get_db_connection()
    cursor.execute("""
        SELECT s.ID, s.fecha, t.nombre as tipo_lavado, v.Tipo as tipo_vehiculo
        FROM servicio s
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        JOIN vehiculos v ON s.id_tipovehiculo = v.ID
        WHERE s.placa = %s AND s.hora_entrega IS NOT NULL
        ORDER BY s.fecha DESC
        LIMIT 5
    """, (placa,))
    
    servicios = cursor.fetchall()
    conn.close()
    
    return render_template('evaluar_servicio.html', placa=placa, servicios=servicios)

@app.route('/generar-enlace', methods=['GET', 'POST'])
def generar_enlace():
    if request.method == 'POST':
        placa = request.form.get('placa')
        
        if not placa:
            flash('Debe ingresar una placa', 'danger')
            return redirect(url_for('index'))
        
        # Verificar que la placa existe en el sistema
        conn, cursor = get_db_connection()
        cursor.execute("SELECT ID FROM servicio WHERE placa = %s LIMIT 1", (placa,))
        if not cursor.fetchone():
            conn.close()
            flash('No se encontraron servicios para esta placa', 'warning')
            return redirect(url_for('index'))
        
        conn.close()
        
        # Generar URL para la evaluación
        enlace = url_for('evaluar_servicio', placa=placa, _external=True)
        
        return render_template('enlace_evaluacion.html', enlace=enlace, placa=placa)
    
    return render_template('generar_enlace.html')

@app.route('/reporte/evaluaciones')
def reporte_evaluaciones():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT e.*, s.placa, s.fecha as fecha_servicio, 
               t.nombre as tipo_lavado, v.Tipo as tipo_vehiculo
        FROM evaluaciones e
        JOIN servicio s ON e.id_servicio = s.ID
        JOIN tiposlavado t ON s.id_tipolavado = t.ID
        JOIN vehiculos v ON s.id_tipovehiculo = v.ID
        ORDER BY e.fecha_evaluacion DESC
    """)
    
    evaluaciones = cursor.fetchall()
    
    # Calcular promedios
    cursor.execute("""
        SELECT 
            AVG(tiempo_espera) as promedio_tiempo_espera,
            AVG(amabilidad_personal) as promedio_amabilidad,
            AVG(calidad_servicio) as promedio_calidad
        FROM evaluaciones
    """)
    
    promedios = cursor.fetchone()
    conn.close()
    
    return render_template('reporte_evaluaciones.html', evaluaciones=evaluaciones, promedios=promedios)

# RQ-UF45 - Módulo de cotización de productos
@app.route('/proveedor/registro', methods=['GET', 'POST'])
def registro_proveedor():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        telefono = request.form.get('telefono')
        
        # Validaciones
        if password != password_confirm:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('registro_proveedor'))
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'danger')
            return redirect(url_for('registro_proveedor'))
        
        # Hashear la contraseña
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn, cursor = get_db_connection()
        
        # Verificar si ya existe un proveedor con ese correo
        cursor.execute("SELECT ID FROM proveedores WHERE correo = %s", (correo,))
        if cursor.fetchone():
            conn.close()
            flash('Ya existe un proveedor registrado con ese correo', 'danger')
            return redirect(url_for('registro_proveedor'))
        
        # Insertar proveedor con contraseña
        cursor.execute("""
            INSERT INTO proveedores (nombre, correo, password, telefono, fecha_registro, estado)
            VALUES (%s, %s, %s, %s, %s, 'Activo')
        """, (nombre, correo, hashed_password, telefono, datetime.now()))
        
        conn.commit()
        
        # Obtener el ID del proveedor recién creado
        cursor.execute("SELECT LAST_INSERT_ID() as id")
        proveedor_id = cursor.fetchone()['id']
        
        conn.close()
        
        # Iniciar sesión automáticamente
        session['proveedor_id'] = proveedor_id
        session['proveedor_nombre'] = nombre
        session['proveedor_logueado'] = True
        
        flash('Proveedor registrado correctamente. Ahora puede cotizar productos.', 'success')
        return redirect(url_for('cotizar_productos', proveedor_id=proveedor_id))
    
    return render_template('registro_proveedor.html')

@app.route('/proveedor/<int:proveedor_id>/cotizar', methods=['GET', 'POST'])
def cotizar_productos(proveedor_id):
    
    if 'proveedor_logueado' not in session or not session['proveedor_logueado'] or session['proveedor_id'] != proveedor_id:
        flash('Debes iniciar sesión para acceder a esta página', 'warning')
        return redirect(url_for('login_proveedor'))
    
    conn, cursor = get_db_connection()
    
    # Verificar que el proveedor existe
    cursor.execute("SELECT * FROM proveedores WHERE ID = %s", (proveedor_id,))
    proveedor = cursor.fetchone()
    
    if not proveedor:
        conn.close()
        flash('Proveedor no encontrado', 'danger')
        return redirect(url_for('login_proveedor'))
    
    if request.method == 'POST':
        insumo_id = request.form.get('insumo_id')
        precio = request.form.get('precio')
        
        # Verificar si ya existe una cotización para este proveedor e insumo
        cursor.execute("""
            SELECT ID FROM cotizaciones
            WHERE id_proveedor = %s AND id_insumo = %s
        """, (proveedor_id, insumo_id))
        
        cotizacion_existente = cursor.fetchone()
        
        if cotizacion_existente:
            # Actualizar cotización existente
            cursor.execute("""
                UPDATE cotizaciones
                SET precio = %s, fecha_cotizacion = %s
                WHERE ID = %s
            """, (precio, datetime.now(), cotizacion_existente['ID']))
            flash('Cotización actualizada correctamente', 'success')
        else:
            # Insertar nueva cotización
            cursor.execute("""
                INSERT INTO cotizaciones (id_proveedor, id_insumo, precio, fecha_cotizacion, estado)
                VALUES (%s, %s, %s, %s, 'Pendiente')
            """, (proveedor_id, insumo_id, precio, datetime.now()))
            flash('Cotización registrada correctamente', 'success')
        
        conn.commit()
    
    # Obtener insumos publicados para cotizar
    cursor.execute("""
        SELECT i.*, ip.ID as id_publicado
        FROM insumos i
        JOIN insumos_publicados ip ON i.ID = ip.id_insumo
        WHERE ip.estado = 'Activo'
        ORDER BY i.nombre
    """)
    
    insumos_publicados = cursor.fetchall()
    
    # Obtener cotizaciones existentes del proveedor
    cursor.execute("""
        SELECT c.*, i.nombre as nombre_insumo
        FROM cotizaciones c
        JOIN insumos i ON c.id_insumo = i.ID
        WHERE c.id_proveedor = %s
        ORDER BY c.fecha_cotizacion DESC
    """, (proveedor_id,))
    
    cotizaciones = cursor.fetchall()
    
    conn.close()
    
    return render_template('cotizar_productos.html', 
                          proveedor=proveedor, 
                          insumos_publicados=insumos_publicados, 
                          cotizaciones=cotizaciones)

@app.route('/admin/insumos/publicar', methods=['GET', 'POST'])
def gestionar_productos_publicados():
    conn, cursor = get_db_connection()
    
    if request.method == 'POST':
        insumo_id = request.form.get('insumo_id')
        accion = request.form.get('accion')
        
        if accion == 'publicar':
            # Verificar si ya está publicado
            cursor.execute("SELECT ID FROM insumos_publicados WHERE id_insumo = %s", (insumo_id,))
            if cursor.fetchone():
                # Actualizar estado si ya existe
                cursor.execute("""
                    UPDATE insumos_publicados
                    SET estado = 'Activo', fecha_publicacion = %s
                    WHERE id_insumo = %s
                """, (datetime.now(), insumo_id))
            else:
                # Insertar nuevo registro
                cursor.execute("""
                    INSERT INTO insumos_publicados (id_insumo, fecha_publicacion, estado)
                    VALUES (%s, %s, 'Activo')
                """, (insumo_id, datetime.now()))
            
            flash('Insumo publicado correctamente para cotización', 'success')
            
        elif accion == 'despublicar':
            cursor.execute("""
                UPDATE insumos_publicados
                SET estado = 'Inactivo'
                WHERE id_insumo = %s
            """, (insumo_id,))
            
            flash('Insumo retirado de cotizaciones', 'success')
        
        conn.commit()
    
    # Obtener todos los insumos
    cursor.execute("""
        SELECT i.*, 
               CASE WHEN ip.estado = 'Activo' THEN 1 ELSE 0 END as publicado
        FROM insumos i
        LEFT JOIN insumos_publicados ip ON i.ID = ip.id_insumo
        WHERE i.estado = 'Disponible'
        ORDER BY i.nombre
    """)
    
    insumos = cursor.fetchall()
    
    conn.close()
    
    return render_template('gestionar_productos_publicados.html', insumos=insumos)

@app.route('/reporte/cotizaciones')
def reporte_cotizaciones():
    conn, cursor = get_db_connection()
    
    cursor.execute("""
        SELECT c.*, i.nombre as nombre_insumo, i.precio as precio_actual,
               p.nombre as nombre_proveedor, p.correo, p.telefono
        FROM cotizaciones c
        JOIN insumos i ON c.id_insumo = i.ID
        JOIN proveedores p ON c.id_proveedor = p.ID
        ORDER BY i.nombre, c.precio ASC
    """)
    
    cotizaciones = cursor.fetchall()
    
    # Agrupar cotizaciones por insumo
    insumos_cotizados = {}
    for cotizacion in cotizaciones:
        if cotizacion['id_insumo'] not in insumos_cotizados:
            insumos_cotizados[cotizacion['id_insumo']] = {
                'nombre': cotizacion['nombre_insumo'],
                'precio_actual': cotizacion['precio_actual'],
                'cotizaciones': []
            }
        
        insumos_cotizados[cotizacion['id_insumo']]['cotizaciones'].append({
            'id': cotizacion['ID'],
            'proveedor': cotizacion['nombre_proveedor'],
            'correo': cotizacion['correo'],
            'telefono': cotizacion['telefono'],
            'precio': cotizacion['precio'],
            'fecha': cotizacion['fecha_cotizacion'],
            'estado': cotizacion['estado']
        })
    
    conn.close()
    
    return render_template('reporte_cotizaciones.html', insumos_cotizados=insumos_cotizados)

@app.route('/proveedor/login', methods=['GET', 'POST'])
def login_proveedor():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        
        # Hashear contraseña
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn, cursor = get_db_connection()
        
        # Buscar proveedor por correo
        cursor.execute("SELECT * FROM proveedores WHERE correo = %s", (correo,))
        proveedor = cursor.fetchone()
        
        if proveedor and proveedor['password'] == hashed_password:
            # Guardar información en la sesión
            session['proveedor_id'] = proveedor['ID']
            session['proveedor_nombre'] = proveedor['nombre']
            session['proveedor_logueado'] = True
            
            flash(f'Bienvenido, {proveedor["nombre"]}', 'success')
            return redirect(url_for('cotizar_productos', proveedor_id=proveedor['ID']))
        else:
            flash('Credenciales incorrectas. Por favor, inténtalo de nuevo.', 'danger')
        
        conn.close()
    
    return render_template('login_proveedor.html')

@app.route('/proveedor/logout')
def logout_proveedor():
    # Limpiar sesión
    session.pop('proveedor_id', None)
    session.pop('proveedor_nombre', None)
    session.pop('proveedor_logueado', None)
    
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('login_proveedor'))

# Ruta para el portal de proveedores
@app.route('/proveedor/portal')
def portal_proveedores():
    # Verificar si el proveedor está logueado
    if 'proveedor_logueado' not in session or not session['proveedor_logueado']:
        flash('Debes iniciar sesión para acceder a esta página', 'warning')
        return redirect(url_for('login_proveedor'))
    
    proveedor_id = session['proveedor_id']
    
    conn, cursor = get_db_connection()
    
    # Obtener información del proveedor
    cursor.execute("SELECT * FROM proveedores WHERE ID = %s", (proveedor_id,))
    proveedor = cursor.fetchone()
    
    if not proveedor:
        conn.close()
        flash('Proveedor no encontrado', 'danger')
        return redirect(url_for('login_proveedor'))
    
    # Obtener cotizaciones recientes del proveedor
    cursor.execute("""
        SELECT c.*, i.nombre as nombre_insumo
        FROM cotizaciones c
        JOIN insumos i ON c.id_insumo = i.ID
        WHERE c.id_proveedor = %s
        ORDER BY c.fecha_cotizacion DESC
        LIMIT 5
    """, (proveedor_id,))
    
    cotizaciones_recientes = cursor.fetchall()
    
    # Obtener insumos publicados para cotizar
    cursor.execute("""
        SELECT i.*, ip.ID as id_publicado
        FROM insumos i
        JOIN insumos_publicados ip ON i.ID = ip.id_insumo
        WHERE ip.estado = 'Activo'
        ORDER BY i.nombre
        LIMIT 5
    """)
    
    insumos_publicados = cursor.fetchall()
    
    conn.close()
    
    return render_template('portal_proveedores.html', 
                          proveedor=proveedor, 
                          cotizaciones_recientes=cotizaciones_recientes, 
                          insumos_publicados=insumos_publicados)
    
if __name__ == '__main__':
    app.run(debug=True)