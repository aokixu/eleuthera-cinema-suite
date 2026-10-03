# Eleuthera Cinema Suite Profesional

> **Estado: BETA** — software en desarrollo activo. Puede contener errores y cambiar entre versiones.

Eleuthera Cinema Suite Profesional es una suite de escritorio orientada al desarrollo y la producción cinematográfica. Reúne en una misma aplicación herramientas para trabajar con guion, desglose, planificación, presupuesto, análisis y documentación de proyecto.

El objetivo del repositorio público es permitir pruebas, revisión de código y contribuciones de otros desarrolladores sin incluir material privado de firma de licencias.

## Funciones principales

- Importación y trabajo con guiones y documentos de proyecto.
- Desglose de producción.
- Planificación.
- Presupuesto con herramientas de cálculo y organización.
- Análisis de escenas y personajes.
- Desarrollo de tratamiento y documentación.
- Importación/exportación de formatos utilizados por la suite, incluyendo PDF y hojas de cálculo donde corresponda.
- Flujo de proyecto integrado en una aplicación de escritorio.

## Tecnología

- Python 3
- PySide6 / Qt 6
- QtAwesome
- pypdf
- openpyxl
- NumPy
- sounddevice

Consulta `requirements.txt` para las dependencias exactas del proyecto.

## Ejecutar desde el código fuente

En Windows, desde PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python suite.py
```

## Beta y pruebas

Esta versión debe considerarse **BETA**. Antes de trabajar con material importante, conserva copias de seguridad de tus proyectos. Los reportes reproducibles son especialmente útiles: indica versión, pasos para reproducir el problema, resultado esperado y resultado obtenido.

## Contribuir

Las contribuciones son bienvenidas. Antes de modificar una parte grande del programa, abre un Issue explicando el problema o propuesta. Para cambios de código, utiliza una rama separada y envía un Pull Request pequeño y enfocado.

Consulta [CONTRIBUTING.md](CONTRIBUTING.md).

## Seguridad y licencias de la aplicación

El repositorio público puede contener el código necesario para **verificar** licencias, incluida una clave pública. Eso no equivale a publicar una clave privada.

**Nunca deben subirse al repositorio:** claves privadas, archivos `.ecplic`, herramientas privadas de emisión de licencias, secretos, tokens ni datos de clientes. Consulta [SECURITY.md](SECURITY.md).

## Licencia del código fuente

Eleuthera Cinema Suite Profesional es un proyecto **estrictamente sin fines de lucro**. El código puede usarse, estudiarse, modificarse, bifurcarse y compartirse gratuitamente, pero **no puede monetizarse**. Esto incluye vender el programa, cobrar por licencias o activaciones, incorporar publicidad, suscripciones, paywalls, compras dentro de la aplicación u otros mecanismos destinados a generar beneficio económico.

Consulta [LICENSE](LICENSE) para las condiciones completas. Esta licencia es *source-available/no comercial* y no una licencia Open Source aprobada por OSI.

## Autoría

Desarrollado por **Team Eleuthera — Francisco Contreras**.

---

Eleuthera Cinema Suite Profesional no pretende sustituir de inmediato décadas de desarrollo de otras herramientas de producción; su propósito es construir una alternativa integrada, accesible y útil para flujos reales de producción cinematográfica.
