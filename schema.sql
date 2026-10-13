PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS tipos_prenda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    prefijo TEXT UNIQUE NOT NULL
);


CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    tipo_id INTEGER,
    costo REAL DEFAULT 0,
    precio REAL DEFAULT 0,
    porcentaje_ganancia REAL DEFAULT 30,
    stock_actual INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (tipo_id) REFERENCES tipos_prenda(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS variantes_producto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER NOT NULL,
    codigo TEXT UNIQUE NOT NULL,
    talle TEXT,
    color TEXT,
    cantidad_por_unidad INTEGER NOT NULL DEFAULT 1,
    costo REAL DEFAULT 0,
    precio REAL DEFAULT 0,
    porcentaje_ganancia REAL DEFAULT 30,
    stock_actual INTEGER DEFAULT 0,
    stock_minimo INTEGER DEFAULT 0,
    FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE
);

-- productos.stock_actual es siempre la suma del stock de sus variantes.
-- Lo mantienen estos triggers: el código nunca lo escribe a mano.
-- (La columna existe para poder filtrar/ordenar productos por stock.)
CREATE TRIGGER IF NOT EXISTS trg_stock_producto_insert
AFTER INSERT ON variantes_producto
BEGIN
    UPDATE productos
    SET stock_actual = (SELECT COALESCE(SUM(stock_actual), 0)
                        FROM variantes_producto WHERE producto_id = NEW.producto_id)
    WHERE id = NEW.producto_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_stock_producto_update
AFTER UPDATE OF stock_actual, producto_id ON variantes_producto
BEGIN
    UPDATE productos
    SET stock_actual = (SELECT COALESCE(SUM(stock_actual), 0)
                        FROM variantes_producto WHERE producto_id = productos.id)
    WHERE id IN (NEW.producto_id, OLD.producto_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_stock_producto_delete
AFTER DELETE ON variantes_producto
BEGIN
    UPDATE productos
    SET stock_actual = (SELECT COALESCE(SUM(stock_actual), 0)
                        FROM variantes_producto WHERE producto_id = OLD.producto_id)
    WHERE id = OLD.producto_id;
END;

CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cliente TEXT,
    metodo_pago TEXT,
    tipo_tarjeta TEXT,
    monto_pagado REAL,
    vuelto REAL,
    total REAL DEFAULT 0,
    ganancia REAL DEFAULT 0,
    estado TEXT DEFAULT 'realizada',
    tiene_cambio INTEGER DEFAULT 0,
    total_base REAL DEFAULT 0,
    ganancia_base REAL DEFAULT 0
);


CREATE TABLE IF NOT EXISTS venta_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER,
    producto_id INTEGER,
    variante_id INTEGER,
    cantidad INTEGER,
    precio_unitario REAL,
    costo_unitario REAL,
    subtotal REAL,
    ganancia_item REAL,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
    FOREIGN KEY (producto_id) REFERENCES productos(id),
    FOREIGN KEY (variante_id) REFERENCES variantes_producto(id)
);


CREATE TABLE IF NOT EXISTS movimientos_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variante_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    motivo TEXT,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (variante_id) REFERENCES variantes_producto(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT
);


CREATE TABLE IF NOT EXISTS cambios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER NOT NULL,
    codigo TEXT UNIQUE,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    monto_diferencia REAL DEFAULT 0,   -- positivo = ingresó dinero, negativo = salió, 0 = sin diferencia
    ganancia REAL DEFAULT 0,
    metodo_pago TEXT,                  -- null si monto_diferencia = 0
    observaciones TEXT,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cambio_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cambio_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,          -- 'devuelto' (vuelve al stock) o 'nuevo' (sale del stock)
    variante_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario REAL NOT NULL,
    costo_unitario REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (cambio_id) REFERENCES cambios(id) ON DELETE CASCADE,
    FOREIGN KEY (variante_id) REFERENCES variantes_producto(id)
);

-- Configuración inicial
INSERT OR IGNORE INTO configuracion (clave, valor)
VALUES ('porcentaje_ganancia_default', '30');
