# Preguntas de prueba

Base de conocimiento de ejemplo (empresa ficticia **Agroandina**), generada con `python tools/make_sample_kb.py`.
Copia los archivos a `base_conocimiento/`, pulsa **Sincronizar** y prueba estas preguntas. La comprobación automática
(34 preguntas, verifica la respuesta **y** que cite la fuente/página correcta) está en `python tools/qa_check.py`.

| Archivo | Qué prueba |
|---|---|
| `manual_sensor_AG200.pdf`, `contrato_servicios.pdf` | PDF con texto (tablas, códigos exactos, cifras) |
| `informe_ventas_2026.pdf` | PDF con un **gráfico en imagen**: las cifras por trimestre solo están en la imagen |
| `guia_instalacion_riego.pdf` | PDF de **4 páginas**; la pág. 3 tiene una **imagen** (sensores por zona) |
| `plan_estrategico_2027.pdf` | PDF de **7 páginas**; **imágenes** en la pág. 4 (presupuesto) y la pág. 6 (cronograma) |
| `acta_reunion_escaneada.pdf` | PDF **escaneado**: no tiene texto, solo imagen |
| `organigrama.png` | Imagen suelta |
| `mensaje_del_gerente.wav` | Audio (voz en español) |
| `capacitacion_seguridad.mp4` | Video con diapositivas y narración |

## Preguntas por archivo

| Archivo | Pregunta | Respuesta esperada |
|---|---|---|
| manual | ¿Cuál es el rango de temperatura de operación del sensor AG-200? | -10 °C a 60 °C |
| manual | ¿Qué significa el error E-4471? | Sensor de humedad desconectado |
| manual | ¿Cada cuánto se debe calibrar el sensor? | Cada 6 meses |
| contrato | ¿Cuántos días de aviso previo se necesitan para cancelar el contrato y qué penalización hay? | 30 días; 10 % del valor restante |
| contrato | ¿Cuál es el valor mensual del contrato de servicios? | 4.200 dólares |
| informe (**gráfico**) | ¿En qué trimestre fueron más altas las ventas de 2026 y cuánto se vendió? | T3, 210 millones |
| informe (**gráfico**) | ¿Cuánto se vendió en el primer trimestre de 2026? | 120 millones |
| informe | ¿Qué línea de producto tiene la mayor participación en las ventas? | Sensores de riego (48 %) |
| acta (**escaneada**) | ¿Cuál es el presupuesto aprobado para el proyecto Colibri? | 85.000 dólares |
| acta (**escaneada**) | ¿Quiénes asistieron a la reunión del 14 de marzo? | Carlos Ruiz, María González, Luis Pardo y Ana Torres |
| acta (**escaneada**) | ¿Cuál es la fecha de entrega del proyecto Colibri? | 30 de junio de 2027 |
| organigrama (**imagen**) | ¿Quién es el jefe de ingeniería? | Luis Pardo |
| organigrama (**imagen**) | ¿Quién es el gerente general? | Carlos Ruiz |
| organigrama (**imagen**) | ¿Qué cargo tiene Ana Torres? | Coordinadora de compras |
| audio | ¿Cuántos sensores se planea instalar en 2027 y en cuántas fincas? | 500 sensores en 12 fincas |
| audio | ¿Cuál es la fecha de lanzamiento oficial? | 12 de noviembre |
| video | ¿Cada cuántos metros hay un extintor y de qué tipo? | Cada 15 metros, tipo ABC |
| video | ¿Dónde está el punto de encuentro en una emergencia? | Parqueadero norte |
| video | ¿Qué equipo de protección es obligatorio en la zona de instalación? | Casco, gafas y guantes de nitrilo |
| guía, **pág. 2** | ¿Cada cuántos metros se marcan los puntos de instalación? | 15 metros |
| guía, **pág. 3 (imagen)** | ¿Cuántos sensores lleva la Zona B? | 18 |
| guía, **pág. 4** | ¿Cuánto hay que esperar para la primera lectura de un sensor? | 10 minutos |
| guía, **pág. 2** | ¿Cuál es la presión de trabajo del sistema de riego? | 2,5 bar |
| plan, **pág. 2** | ¿Cuántos clientes activos tenía la empresa al cierre de 2026? | 38 |
| plan, **pág. 3** | ¿A cuántos minutos se quiere reducir el tiempo de instalación por sensor? | 30 (desde 45) |
| plan, **pág. 4 (imagen)** | ¿Cuánto se invertirá en tecnología en 2027? | 120 mil dólares |
| plan, **pág. 5** | ¿Qué riesgos tienen probabilidad alta? | Rotación del personal técnico y variación del tipo de cambio |
| plan, **pág. 6 (imagen)** | ¿Cuándo se hará el piloto y en cuántas fincas? | Junio, en 3 fincas |
| plan, **pág. 7** | ¿Cuándo es la próxima revisión del plan estratégico? | 15 de enero de 2027 |

## Preguntas que cruzan archivos

| Pregunta | Respuesta esperada | Fuentes |
|---|---|---|
| ¿Cuánto tarda hoy instalar un sensor y a cuánto se quiere reducir? | 45 min → 30 min | guía pág. 1 + plan pág. 3 |
| ¿Quién es la responsable del proyecto Colibri y cuál es su cargo? | María González, directora de proyectos | acta + organigrama |
| ¿De qué ciudad es el proveedor de sensores? | Bogotá (Andina SA) | manual, informe y acta |

## Preguntas sin respuesta (la app debe decirlo, sin inventar)

| Pregunta | Respuesta esperada |
|---|---|
| ¿Cuál es el salario del gerente general? | No está en los documentos |
| ¿Cuánto cuesta cada sensor AG-200? | No está en los documentos |

Para ver la evidencia: abre **Fuentes** bajo cada respuesta. En los PDF con texto aparece la página con el fragmento resaltado;
en audio y video, el reproductor posicionado en el minuto citado.
