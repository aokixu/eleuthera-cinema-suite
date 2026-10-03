from pathlib import Path
p=Path('verify_enter_approval.py');s=p.read_text(encoding='utf-8').replace("assert all(row['approved'] for row in w.breakdown_data())", "assert all(row['approved'] for row in w.breakdown_data())\nw.approved_to_budget(); assert w.budget.rowCount()==100\nw.approved_to_budget(); assert w.budget.rowCount()==100");p.write_text(s,encoding='utf-8')
Path('EDICION-Y-APROBACION.md').write_text('''# Edición y aprobación masiva

Desglose incluye Aprobar todos y Desmarcar todos. Cambian todas las casillas de Aprobado; Presupuestar aprobados mantiene su función y evita conceptos duplicados.

Enter inserta explícitamente un párrafo. Antes, el comportamiento nativo de Qt normalizaba el formato de un párrafo vacío y consumía la pulsación, mientras el editor volvía a aplicar ese formato: los siguientes Enter no agregaban líneas. La corrección conserva el formato de guion y agrupa la inserción para deshacer. El formateo conserva la posición del cursor y no selecciona el separador del párrafo anterior.

También se restaura la altura de página cuando Qt reajusta el área visible al crecer el documento, manteniendo la paginación durante la escritura.

Pruebas: Enter repetido, insertar en medio, escribir, borrar, deshacer/rehacer, crecer a otra página y desplazar el cursor; aprobación/desmarcado de 100 elementos y envío al presupuesto sin duplicados. Pasaron las pruebas generales de páginas, flujo de trabajo e importación.

Compilaciones actualizadas: dist/Edicion-libre.
''',encoding='utf-8')
