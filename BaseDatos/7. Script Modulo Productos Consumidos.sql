CREATE TABLE IF NOT EXISTS met_prodconsumidos (
    idProdConsumido INT AUTO_INCREMENT PRIMARY KEY,
    idCentro VARCHAR(4) NOT NULL,
    idColaborador INT NOT NULL,              -- Nómina del colaborador (sin FK, solo captura)
    CodigoBarras VARCHAR(20) NOT NULL,        -- Producto marcado
    Cantidad DECIMAL(10, 2) NOT NULL DEFAULT 1,
    idUsuario INT NOT NULL,           -- Quién generó el folio (cajero/supervisor)
    FechaRegistro DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Comentario VARCHAR(200) NULL,
    CONSTRAINT fk_prodconsumidos_sucursal
        FOREIGN KEY (idCentro) REFERENCES sucursales(IdCentro),
    CONSTRAINT fk_prodconsumidos_catalogo
        FOREIGN KEY (CodigoBarras) REFERENCES catalogo(CodigoBarras),
    CONSTRAINT fk_prodconsumidos_usrregistro
        FOREIGN KEY (idUsuario) REFERENCES usuarios(IdUsuarios)
) ENGINE=InnoDB;

CREATE INDEX idx_prodconsumidos_centro_fecha
    ON met_prodconsumidos (idCentro, FechaRegistro);

-- El Folio ya no se almacena en la tabla; se calcula al vuelo en la vista
-- para evitar depender de columnas generadas (STORED) y de triggers.
CREATE OR REPLACE VIEW vw_met_prodconsumidos AS
SELECT
    idProdConsumido,
    CONCAT('PC', LPAD(idProdConsumido, 8, '0')) AS Folio,
    idCentro,
    idColaborador,
    CodigoBarras,
    Cantidad,
    idUsuario,
    FechaRegistro,
    Comentario
FROM met_prodconsumidos;
