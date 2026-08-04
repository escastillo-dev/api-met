-- ====================================================
-- Módulo: Recuperaciones
-- Tablas: rec_tipos_recuperacion, rec_proveedores,
--         rec_proveedor_zona, rec_recuperaciones,
--         rec_recuperacion_detalle, rec_evidencias
-- ====================================================

-- 1. Catálogo de tipos de recuperación
CREATE TABLE IF NOT EXISTS rec_tipos_recuperacion (
    idTipoRecuperacion INT AUTO_INCREMENT PRIMARY KEY,
    Tipo               VARCHAR(45) NOT NULL,
    estatus            TINYINT     NOT NULL DEFAULT 1
);

INSERT IGNORE INTO rec_tipos_recuperacion (idTipoRecuperacion, Tipo) VALUES
(1, roveedor'),
(2, 'Invitado'),
(3, 'Cajero'),
(4, 'Colaborador'),
(5, 'Empacador'),
(6, 'Otro');'

-- 2. Proveedores
CREATE TABLE IF NOT EXISTS rec_proveedores (
    idProveedor     INT           AUTO_INCREMENT PRIMARY KEY,
    proveedor       VARCHAR(100)  NOT NULL,
    contacto        VARCHAR(100)  NULL,
    telefono        VARCHAR(20)   NULL,
    estatus         TINYINT       NOT NULL DEFAULT 1,
    fechaAlta       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Proveedor por zona (un proveedor puede atender varias zonas)
CREATE TABLE IF NOT EXISTS rec_proveedor_zona (
    idProveedorZona INT AUTO_INCREMENT PRIMARY KEY,
    idProveedor     INT NOT NULL,
    idZona          INT NOT NULL,
    CONSTRAINT fk_rpz_proveedor FOREIGN KEY (idProveedor) REFERENCES rec_proveedores(idProveedor),
    CONSTRAINT fk_rpz_zona      FOREIGN KEY (idZona)      REFERENCES zonas(idZona),
    CONSTRAINT uq_rpz           UNIQUE (idProveedor, idZona)
);

-- 4. Encabezado de recuperación
CREATE TABLE IF NOT EXISTS rec_recuperaciones (
    idRecuperacion     INT          AUTO_INCREMENT PRIMARY KEY,
    idCentro           VARCHAR(4)   NOT NULL,
    idTipoRecuperacion INT          NOT NULL,
    idProveedor        INT          NULL,       -- obligatorio si tipo = 1 (Proveedor)
    nombreInfractor    VARCHAR(100) NULL,       -- obligatorio si tipo != 1
    comentario         VARCHAR(255) NULL,
    idUsuario          INT          NOT NULL,
    fechaHora          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estatus            TINYINT      NOT NULL DEFAULT 1,  -- 1=activa, 0=cancelada
    CONSTRAINT fk_rec_centro    FOREIGN KEY (idCentro)           REFERENCES sucursales(idCentro),
    CONSTRAINT fk_rec_tipo      FOREIGN KEY (idTipoRecuperacion) REFERENCES rec_tipos_recuperacion(idTipoRecuperacion),
    CONSTRAINT fk_rec_proveedor FOREIGN KEY (idProveedor)        REFERENCES rec_proveedores(idProveedor),
    CONSTRAINT fk_rec_usuario   FOREIGN KEY (idUsuario)          REFERENCES usuarios(IdUsuarios)
);

CREATE INDEX idx_rec_centro_fecha ON rec_recuperaciones (idCentro, fechaHora);
CREATE INDEX idx_rec_tipo         ON rec_recuperaciones (idTipoRecuperacion);
CREATE INDEX idx_rec_proveedor    ON rec_recuperaciones (idProveedor);
CREATE INDEX idx_rec_estatus      ON rec_recuperaciones (estatus);

-- 5. Detalle de recuperación
CREATE TABLE IF NOT EXISTS rec_recuperacion_detalle (
    idDetalle      INT          AUTO_INCREMENT PRIMARY KEY,
    idRecuperacion INT          NOT NULL,
    CodigoBarras   VARCHAR(20)  NOT NULL,
    cantidad       DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_rdet_recuperacion FOREIGN KEY (idRecuperacion) REFERENCES rec_recuperaciones(idRecuperacion),
    CONSTRAINT fk_rdet_catalogo     FOREIGN KEY (CodigoBarras)   REFERENCES catalogo(CodigoBarras)
);

CREATE INDEX idx_rdet_recuperacion ON rec_recuperacion_detalle (idRecuperacion);

-- 6. Evidencias
CREATE TABLE IF NOT EXISTS rec_evidencias (
    idEvidencia    INT          AUTO_INCREMENT PRIMARY KEY,
    idRecuperacion INT          NOT NULL,
    rutaArchivo    VARCHAR(255) NOT NULL,
    tipoArchivo    VARCHAR(45)  NULL,
    fechaRegistro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idUsuario      INT          NOT NULL,
    CONSTRAINT fk_rev_recuperacion FOREIGN KEY (idRecuperacion) REFERENCES rec_recuperaciones(idRecuperacion),
    CONSTRAINT fk_rev_usuario      FOREIGN KEY (idUsuario)      REFERENCES usuarios(IdUsuarios)
);
