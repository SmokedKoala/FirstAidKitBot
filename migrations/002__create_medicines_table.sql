CREATE TABLE IF NOT EXISTS medicines (
    id BIGSERIAL PRIMARY KEY,
    ean13_code TEXT NOT NULL,
    medicine_name TEXT NOT NULL
);
