# Seguridad

## Reporte responsable

No publiques en un Issue información que permita comprometer instalaciones, datos de usuarios o material privado de firma. Para una futura publicación pública, Team Eleuthera deberá definir un canal privado de contacto para vulnerabilidades sensibles.

## Material que nunca debe entrar al repositorio

- `private_key.pem` u otras claves privadas.
- Archivos de licencia `.ecplic` emitidos a usuarios.
- Tokens, contraseñas o secretos en `.env`.
- Datos personales o proyectos privados de usuarios.
- Herramientas privadas de emisión/firma de licencias.

La clave pública utilizada para verificar firmas puede formar parte del cliente; la clave privada de firma no.
