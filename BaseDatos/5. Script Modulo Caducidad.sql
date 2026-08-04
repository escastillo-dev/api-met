-- Módulo: Próximos a caducar
-- Tablas: met_cad_registros, met_cad_acciones, met_cad_cierres

CREATE TABLE IF NOT EXISTS met_cad_registros (
    idCad INT AUTO_INCREMENT PRIMARY KEY,
    idCentro VARCHAR(4) NOT NULL,
    CodigoBarras VARCHAR(20) NOT NULL,
    fechaCaducidad DATE NOT NULL,
    cantidadDetectada DECIMAL(10, 2) NOT NULL,
    FechaRegistro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idUsuarios INT NOT NULL,
    diasAlerta INT NOT NULL DEFAULT 30,
    estatus CHAR(1) NOT NULL DEFAULT 'A',
    nota VARCHAR(200) NULL,
    CONSTRAINT fk_cad_registros_sucursal
        FOREIGN KEY (idCentro) REFERENCES sucursales(idCentro),
    CONSTRAINT fk_cad_registros_catalogo
        FOREIGN KEY (CodigoBarras) REFERENCES catalogo(CodigoBarras),
    CONSTRAINT fk_cad_registros_usuario
        FOREIGN KEY (idUsuarios) REFERENCES usuarios(IdUsuarios),
    CONSTRAINT chk_cad_registros_estatus
        CHECK (estatus IN ('A','C'))
);

CREATE INDEX idx_cad_registros_centro_fecha
    ON met_cad_registros (idCentro, fechaCaducidad);

CREATE INDEX idx_cad_registros_producto_fecha
    ON met_cad_registros (CodigoBarras, fechaCaducidad);

CREATE INDEX idx_cad_registros_estatus_fecha
    ON met_cad_registros (estatus, fechaCaducidad);


CREATE TABLE IF NOT EXISTS met_cad_acciones (
    idAccion INT AUTO_INCREMENT PRIMARY KEY,
    idCad INT NOT NULL,
    fechaHora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idTipoAccion INT NOT NULL,
    cantidad DECIMAL(10, 2) NULL,
    resultado VARCHAR(45) NULL,
    comentario VARCHAR(200) NULL,
    idUsuarios INT NOT NULL,
    CONSTRAINT fk_met_cad_acciones_registro
        FOREIGN KEY (idCad) REFERENCES met_cad_registros(idCad),
    CONSTRAINT fk_met_cad_acciones_tipo
        FOREIGN KEY (idTipoAccion) REFERENCES met_cad_tipoacciones(idAccionCad),
    CONSTRAINT fk_met_cad_acciones_usuario
        FOREIGN KEY (idUsuarios) REFERENCES usuarios(IdUsuarios)
);

CREATE INDEX idx_met_cad_acciones_idcad_fecha
    ON met_cad_acciones (idCad, fechaHora);


CREATE TABLE IF NOT EXISTS met_cad_cierres (
    idCierre INT AUTO_INCREMENT PRIMARY KEY,
    idCad INT NOT NULL,
    fechaCierre DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resultadoFinal VARCHAR(45) NOT NULL,
    cantidadSalida DECIMAL(10, 2) NULL,
    cantidadMerma DECIMAL(10, 2) NULL,
    comentario VARCHAR(200) NULL,
    idUsuarios INT NOT NULL,
    CONSTRAINT fk_met_cad_cierres_registro
        FOREIGN KEY (idCad) REFERENCES met_cad_registros(idCad),
    CONSTRAINT fk_met_cad_cierres_usuario
        FOREIGN KEY (idUsuarios) REFERENCES usuarios(IdUsuarios),
    CONSTRAINT uq_met_cad_cierres_idcad UNIQUE (idCad)
);

CREATE INDEX idx_met_cad_cierres_fecha
    ON met_cad_cierres (fechaCierre);
