# Directorio de Datos

Este directorio almacena la base de datos SQLite local del proyecto.

## Archivos

- `finanzas.db` - Base de datos principal (generada automáticamente)

## Notas

- Este directorio está en `.gitignore` para proteger tus datos
- La base de datos se crea automáticamente al ejecutar la aplicación por primera vez
- No compartas archivos `.db` ya que contienen información sensible

## Respaldo

Se recomienda hacer respaldos periódicos de la base de datos:

```bash
# Crear respaldo
cp data/finanzas.db data/finanzas_backup_$(date +%Y%m%d).db

# O usando sqlite3
sqlite3 data/finanzas.db ".backup data/finanzas_backup.db"
```


