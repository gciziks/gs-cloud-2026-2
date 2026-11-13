CREATE TABLE IF NOT EXISTS relatos (
 id bigserial PRIMARY KEY,
 codigo_ibge integer NOT NULL,
 bairro varchar(80) NOT NULL,
 referencia varchar(120) NOT NULL,
 situacao varchar(20) NOT NULL CHECK (situacao IN ('agua_na_calcada','rua_intransitavel','imovel_atingido')),
 ip_hash char(64),
 criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS relatos_municipio_criado ON relatos (codigo_ibge, criado_em DESC);
CREATE INDEX IF NOT EXISTS relatos_ip_criado ON relatos (ip_hash, criado_em);
