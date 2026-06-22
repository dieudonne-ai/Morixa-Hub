"""
migration.py — À placer à la racine du projet et exécuter UNE SEULE FOIS.
Ajoute les colonnes manquantes à la table users existante.

Exécution :
    (.venv) python migration.py
"""

from app import create_app
from models import db

app = create_app()

MIGRATIONS = [
    # (description, SQL à exécuter)
    (
        "Ajout colonne verif_level dans users",
        "ALTER TABLE users ADD verif_level NVARCHAR(20) DEFAULT 'none' NOT NULL"
    ),
    (
        "Ajout colonne license_number dans users",
        "ALTER TABLE users ADD license_number NVARCHAR(100) NULL"
    ),
]

def column_exists(conn, table, column):
    result = conn.execute(db.text(
        f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME = '{table}' AND COLUMN_NAME = '{column}'"
    ))
    return result.scalar() > 0

with app.app_context():
    with db.engine.connect() as conn:
        for description, sql in MIGRATIONS:
            # Extraire le nom de la colonne depuis le SQL
            col_name = sql.split("ADD ")[1].split(" ")[0]
            if column_exists(conn, "users", col_name):
                print(f"⏭  Déjà présente : {col_name}")
            else:
                conn.execute(db.text(sql))
                conn.commit()
                print(f"✅ {description}")

    # Créer les nouvelles tables (verification_requests, repo_stars, follows)
    db.create_all()
    print("✅ Nouvelles tables créées (si absentes)")

print("\n🎉 Migration terminée. Vous pouvez relancer python app.py")