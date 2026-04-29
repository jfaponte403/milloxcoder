# Milloxcoder

## Register
product

## Users
Estudiantes y desarrolladores que aprenden o demuestran el algoritmo de
Huffman. Lo usan en sesiones de estudio o presentaciones, normalmente en un
portatil Windows. Quieren entender el algoritmo, no solo ejecutarlo: ver las
frecuencias, el arbol, los codigos resultantes y las metricas de teoria de la
informacion (entropia, redundancia, eficiencia).

## Product Purpose
Aplicacion de escritorio educativa que codifica y decodifica archivos (imagen
y audio) con Huffman, revelando cada paso del proceso en lugar de esconderlo
tras un boton. Adicionalmente, calcula y visualiza metricas de teoria de la
informacion sobre la fuente codificada.

## Tone
Claro, tecnico, ligero. La app es una clase visualizada, no una caja negra.
Voz en espanol, sin jerga innecesaria, sin em dashes.

## Brand
- Nombre: Milloxcoder.
- Posicionamiento: visualizador del algoritmo, no solo compresor.
- Personalidad: precision academica con un acento calido. No es software
  empresarial gris; tampoco un editor IDE oscuro lleno de configuraciones.

## Anti-references
- Convertidores opacos tipo CloudConvert: aqui el proceso ES el producto.
- Tools "minimalistas" gris-sobre-blanco que parecen plantillas.
- Dashboards SaaS con la cliche big-number-pequena-label-y-gradient.
- Cards identicas repetidas en grid.

## Strategic principles
- El proceso es el producto. Stepper, log, arbol y dashboard de teoria de la
  informacion son tan importantes como el resultado.
- Sin perdida y verificable. Decodificar siempre debe reconstruir bytes
  identicos al archivo original.
- Sin dependencias innecesarias. Tkinter puro, Pillow opcional para exportar
  imagen del arbol y para previsualizar.
- Una accion principal por momento. Cargar, codificar, revisar, decodificar,
  guardar.
