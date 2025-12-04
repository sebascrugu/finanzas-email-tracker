# Directorio de Datos

Este directorio almacena la base de datos SQLite local del proyecto y todos los datos relacionados.

## Estructura

```
data/
├── finanzas.db          # Base de datos principal (generada automáticamente)
├── raw/                 # Datos originales sin procesar
│   ├── bac_pdf/         # PDFs de estados de cuenta del BAC
│   └── sinpe_sms/       # SMS o screenshots de SINPE Móvil
├── processed/           # Datos extraídos y procesados
└── test_fixtures/       # Datos de prueba y fixtures

```

## Archivos

- `finanzas.db` - Base de datos principal (generada automáticamente)

## Notas

- Este directorio está en `.gitignore` para proteger tus datos
- La base de datos se crea automáticamente al ejecutar la aplicación por primera vez
- No compartas archivos `.db` o archivos raw ya que contienen información sensible
- Los archivos en `raw/` y `processed/` contienen información financiera personal

## Respaldo

Se recomienda hacer respaldos periódicos de la base de datos:

```bash
# Crear respaldo
cp data/finanzas.db data/finanzas_backup_$(date +%Y%m%d).db

# O usando sqlite3
sqlite3 data/finanzas.db ".backup data/finanzas_backup.db"
```


