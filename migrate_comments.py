
from app import create_app
from models import db

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Rendre post_id nullable (un commentaire appartient
        # soit à un post, soit à un repo — jamais les deux)
        try:
            conn.execute(db.text(
                "ALTER TABLE comments ALTER COLUMN post_id INT NULL"
            ))
            conn.commit()
            print("✅ post_id est maintenant nullable")
        except Exception as e:
            print(f"⏭  Déjà nullable ou erreur : {e}")

        # Ajouter repo_id s'il n'existe pas
        try:
            conn.execute(db.text(
                "ALTER TABLE comments ADD repo_id INT NULL "
                "REFERENCES repositories(id) ON DELETE CASCADE"
            ))
            conn.commit()
            print("✅ Colonne repo_id ajoutée dans comments")
        except Exception as e:
            print(f"⏭  Déjà présente ou erreur : {e}")

print("Migration terminée.")
