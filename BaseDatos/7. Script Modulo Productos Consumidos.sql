CREATE TABLE IF NOT EXISTS met_prodconsumidos (
    idProdConsumido INT AUTO_INCREMENT PRIMARY KEY,
    -- Folio calculado a partir del PK: único por diseño, sin necesidad de
    -- lógica adicional en la app ni riesgo de colisiones.
    Folio VARCHAR(20) AS (CONCAT('PC', LPAD(idProdConsumido, 8, '0'))) STORED,
    idCentro VARCHAR(4) NOT NULL,
    idColaborador INT NOT NULL,              -- Nómina del colaborador (usuarios.IdUsuarios)
    CodigoBarras VARCHAR(20) NOT NULL,        -- Producto marcado
    Cantidad DECIMAL(10, 2) NOT NULL DEFAULT 1,
    idUsuario INT NOT NULL,           -- Quién generó el folio (cajero/supervisor)
    FechaRegistro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Comentario VARCHAR(200) NULL,       
    CONSTRAINT uq_prodconsumidos_folio UNIQUE (Folio),
    CONSTRAINT fk_prodconsumidos_sucursal
        FOREIGN KEY (idCentro) REFERENCES sucursales(IdCentro),
    CONSTRAINT fk_prodconsumidos_catalogo
        FOREIGN KEY (CodigoBarras) REFERENCES catalogo(CodigoBarras),
    CONSTRAINT fk_prodconsumidos_usrregistro
        FOREIGN KEY (idUsuario) REFERENCES usuarios(IdUsuarios),
);

CREATE INDEX idx_prodconsumidos_centro_fecha
    ON met_prodconsumidos (idCentro, FechaRegistro);
