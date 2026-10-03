from pathlib import Path
Path('perf-import/numbered-scenes.txt').write_text('\n\n'.join(f'{i}. EXT. CARRETERA - DIA\n\nUna camioneta avanza por la carretera.' for i in range(1,151)),encoding='utf-8')
Path('GUION-PAGINADO.md').write_text('''# Editor paginado y escenas numeradas

El editor ahora ocupa el ancho de su panel, sin el relleno de 68 px que desplazaba la barra hacia el texto. El documento utiliza páginas de proporción carta, márgenes, separación visible y número de página. La barra de desplazamiento queda en el borde del editor. Qt realiza la paginación real del texto; no se crean cientos de widgets por guion. Los paneles laterales siguen siendo ajustables.

El importador de PDF, TXT y Fountain reconoce encabezados numerados (1. EXT., 14A INT., 27) INT/EXT.) sin eliminar el número del texto. Desglose y plan separan ese prefijo al identificar la locación. Los proyectos guardados conservan sus formatos manuales: para corregir un PDF importado anteriormente como texto, vuelve a importar el PDF original.

Verificación: páginas múltiples, ancho útil, edición/deshacer, escenas numeradas y falsos positivos, ubicación de escenas, cancelación e importaciones consecutivas. También pasaron las pruebas generales del editor, suite y flujo de trabajo. El PDF de prueba de 150 páginas conservó su contenido y cargó en 10,33 s; no es una garantía para todos los archivos.

Ejecutables: dist/Guion-paginado, Standard y Professional. Las compilaciones anteriores se conservan.
''',encoding='utf-8')
