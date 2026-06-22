# Pour définir un secret permanent sur Windows PowerShell, générez-en un :

python -c "import secrets; print(secrets.token_hex(32))"

# Puis définissez-le pour la session courante :

# $env:JWT_SECRET = "la_chaine_generee_ci_dessus"

# Ou en permanent via Paramètres système > Variables d'environnement.
"# Morixa-Hub" 
