# Guide de déploiement — Morixa Hub

---

## Étape 1 — Neon (base de données PostgreSQL gratuite)

1. Allez sur **https://neon.tech** → "Sign up" (gratuit, pas de carte bancaire)
2. Cliquez "New Project" → donnez un nom : `morixa-hub`
3. Choisissez la région la plus proche (Europe ou Africa si disponible)
4. Une fois créé, copiez la **Connection string** qui ressemble à :

   ```


   postgresql://username:password@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

5. Gardez-la de côté, vous en aurez besoin dans les étapes suivantes.

---

## Étape 2 — Désinstaller pyodbc, installer les nouveaux paquets

Dans votre terminal PowerShell :

```powershell
# Désactiver l'ancien driver SQL Server
pip uninstall pyodbc -y

# Installer les nouveaux paquets
pip install -r requirements.txt
```

---

## Étape 3 — Tester localement avec Neon

Créez un fichier `.env` à la racine du projet (copiez `.env.example`) :

```
DATABASE_URL=postgresql://username:password@ep-xxx.neon.tech/neondb?sslmode=require
SECRET_KEY=votre_cle_generee
JWT_SECRET=votre_autre_cle_generee
USE_R2=false
```

Puis ajoutez ce bloc en haut de `app.py` pour charger `.env` :

```python
from dotenv import load_dotenv
load_dotenv()
```

Lancez l'app et vérifiez que tout fonctionne :

```powershell
python app.py
```

Si vous voyez `Running on http://127.0.0.1:5000` sans erreur, la connexion Neon fonctionne.
`db.create_all()` va créer automatiquement toutes vos tables sur Neon.

---

## Étape 4 — GitHub

1. Créez un compte sur **https://github.com** si vous n'en avez pas
2. Créez un nouveau dépôt privé appelé `morixa-hub`
3. Dans votre terminal :

```powershell
cd C:\Users\DIDO\Desktop\medhub-v1

# Créer le .gitignore pour ne pas uploader les secrets
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
echo "uploads/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore

# Initialiser git
git init
git add .
git commit -m "Initial commit — Morixa Hub"

# Connecter à votre dépôt GitHub (remplacez YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/morixa-hub.git
git branch -M main
git push -u origin main
```

---

## Étape 5 — Render (serveur Flask gratuit)

1. Allez sur **https://render.com** → "Sign up with GitHub"
2. Cliquez "New +" → "Web Service"
3. Sélectionnez votre dépôt `morixa-hub`
4. Configurez :
   - **Name** : `morixa-hub-api`
   - **Runtime** : Python 3
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn "app:create_app()"`
   - **Instance Type** : Free
5. Descendez vers "Environment Variables" et ajoutez :

| Variable       | Valeur                                                                  |
| -------------- | ----------------------------------------------------------------------- |
| `DATABASE_URL` | votre URL Neon copiée à l'étape 1                                       |
| `SECRET_KEY`   | générez avec `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_SECRET`   | générez une autre clé                                                   |
| `USE_R2`       | `false` pour l'instant                                                  |
| `FLASK_DEBUG`  | `false`                                                                 |

6. Cliquez "Create Web Service" → attendez 2-3 minutes
7. Render vous donnera une URL du type : `https://morixa-hub-api.onrender.com`

---

## Étape 6 — Mettre à jour le frontend

Dans **tous** vos fichiers HTML, remplacez :

```javascript
const API = "http://localhost:5000/api";
// ou
fetch("http://localhost:5000/api/...");
```

Par :

```javascript
const API = "https://morixa-hub-api.onrender.com/api";
```

La façon la plus propre est d'ajouter une seule ligne dans `api.js` :

```javascript
const API_BASE =
  window.location.hostname === "localhost"
    ? "http://localhost:5000/api"
    : "https://morixa-hub-api.onrender.com/api";
```

Et remplacer tous les `http://localhost:5000/api` dans `api.js` par `API_BASE`.

---

## Étape 7 — Cloudflare R2 (fichiers uploadés)

À faire après que Render fonctionne :

1. Allez sur **https://dash.cloudflare.com** → "R2 Object Storage"
2. Créez un bucket : `morixa-uploads`
3. Activez l'accès public sur le bucket
4. Allez dans "Manage R2 API Tokens" → créez un token avec permission "Object Read & Write"
5. Copiez `Account ID`, `Access Key ID`, `Secret Access Key`
6. Dans Render, ajoutez ces variables d'environnement :

| Variable               | Valeur                          |
| ---------------------- | ------------------------------- |
| `USE_R2`               | `true`                          |
| `R2_ACCOUNT_ID`        | votre Account ID Cloudflare     |
| `R2_ACCESS_KEY_ID`     | votre Access Key                |
| `R2_SECRET_ACCESS_KEY` | votre Secret Key                |
| `R2_BUCKET_NAME`       | `morixa-uploads`                |
| `R2_PUBLIC_URL`        | URL publique de votre bucket R2 |

---

## Résultat final

| Service         | URL                                   | Coût             |
| --------------- | ------------------------------------- | ---------------- |
| Backend Flask   | `https://morixa-hub-api.onrender.com` | Gratuit          |
| Base de données | Neon PostgreSQL                       | Gratuit (0.5 GB) |
| Fichiers        | Cloudflare R2                         | Gratuit (10 GB)  |
| Frontend        | Servi par Flask                       | Inclus           |

**Note** : Le plan gratuit de Render "endort" l'app après 15 min d'inactivité.
Le premier chargement peut prendre 30-60 secondes. Pour les tests utilisateurs,
c'est acceptable. En production réelle, il faudra passer au plan payant ($7/mois).
