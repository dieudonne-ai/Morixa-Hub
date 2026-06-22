"""
services/storage.py
Couche d'abstraction pour le stockage de fichiers.
  - En dev  : stockage local dans /uploads
  - En prod : Cloudflare R2 (compatible S3)
"""

import os
import boto3
from botocore.config import Config as BotoConfig
from flask import current_app
from werkzeug.utils import secure_filename


def _get_r2_client():
    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def save_file(file_obj, filename, subfolder="uploads"):
    """
    Sauvegarde un fichier.
    Retourne (path_or_key, url) selon l'environnement.
    """
    cfg = current_app.config
    fname = secure_filename(filename)

    if cfg.get("USE_R2"):
        key = f"{subfolder}/{fname}"
        client = _get_r2_client()
        client.upload_fileobj(
            file_obj,
            cfg["R2_BUCKET_NAME"],
            key,
            ExtraArgs={"ContentDisposition": f'attachment; filename="{fname}"'},
        )
        url = f"{cfg['R2_PUBLIC_URL']}/{key}" if cfg.get("R2_PUBLIC_URL") else key
        return key, url
    else:
        folder = os.path.join(cfg["UPLOAD_FOLDER"], subfolder)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, fname)
        file_obj.save(path)
        return path, path


def get_file_response(path_or_key, filename):
    """
    Retourne soit send_from_directory (local) soit une URL signée R2.
    """
    from flask import send_from_directory, redirect
    cfg = current_app.config

    if cfg.get("USE_R2"):
        client = _get_r2_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": cfg["R2_BUCKET_NAME"], "Key": path_or_key},
            ExpiresIn=3600,
        )
        return redirect(url)
    else:
        directory = os.path.dirname(path_or_key)
        return send_from_directory(directory, filename, as_attachment=True)


def delete_file(path_or_key):
    """Supprime un fichier (local ou R2)."""
    cfg = current_app.config
    if cfg.get("USE_R2"):
        client = _get_r2_client()
        client.delete_object(Bucket=cfg["R2_BUCKET_NAME"], Key=path_or_key)
    else:
        if os.path.exists(path_or_key):
            os.remove(path_or_key)