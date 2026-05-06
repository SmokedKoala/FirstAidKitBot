CREATE TABLE IF NOT EXISTS first_aid_kits (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_first_aid_kits (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    first_aid_kit_id BIGINT NOT NULL REFERENCES first_aid_kits(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, first_aid_kit_id)
);

CREATE TABLE IF NOT EXISTS first_aid_kit_medicines (
    id BIGSERIAL PRIMARY KEY,
    first_aid_kit_id BIGINT NOT NULL REFERENCES first_aid_kits(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    number_of_drugs INTEGER NOT NULL CHECK (number_of_drugs >= 0),
    expiration_date DATE NOT NULL,
    description TEXT NOT NULL
);
