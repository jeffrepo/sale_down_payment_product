# Producto de anticipo en ventas — Odoo 19

Asocia un producto configurable por compañía a los anticipos de ventas por
porcentaje o importe fijo. El producto queda vinculado tanto a la línea del
pedido como a la factura de anticipo y a su deducción en la factura final.

En Odoo 19 estándar estas líneas pueden existir sin `product_id`. Este módulo
extiende la preparación de las líneas de anticipo mediante herencia de Odoo.

## Instalación

1. Clonar la rama `19.0` de este repositorio en una carpeta llamada
   `sale_down_payment_product` dentro del directorio de módulos personalizados.
2. Añadir el directorio **padre** a `addons_path`. `__manifest__.py` y
   `__init__.py` están directamente en la raíz del repositorio, junto a las
   carpetas internas del módulo (`models`, `views`, `i18n` y `tests`).
3. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar
   **Sales Down Payment Product** (`sale_down_payment_product`). Si se busca en
   Aplicaciones, quitar el filtro «Aplicaciones», ya que es un módulo técnico.

Requiere Odoo **19.0**. Su única dependencia directa es el módulo técnico `sale`.
Está pensado para una base que ya utiliza la aplicación Ventas. No utiliza
código Enterprise ni requiere la aplicación Website.

Si se actualiza desde la estructura anterior, el manifiesto debe quedar en
`sale_down_payment_product/__manifest__.py`, sin otra carpeta del mismo nombre
en su interior. Reiniciar Odoo, actualizar la lista de aplicaciones y actualizar
este módulo; no es necesario desinstalarlo ni perder su configuración.

## Dependencias web

Odoo utiliza módulos técnicos como `web` y `portal` para su interfaz y el portal
de clientes. Esos módulos son diferentes de la aplicación **Sitio web**
(`website`). El campo `website` del manifiesto solo contiene el enlace al
repositorio; no instala la aplicación.

La prueba de instalación en una base vacía comprueba expresamente que `website`
permanezca en estado `uninstalled`. Si ya está instalado en una base existente,
actualizar este módulo no lo desinstala. Identificar qué lo instaló requiere
revisar el registro de instalación y los módulos de esa base.

## Configuración y uso

1. Crear un producto, por ejemplo **Anticipo de clientes**, con tipo **Servicio**,
   disponible para venta y política de facturación **Cantidades pedidas**.
2. En la compañía correspondiente, ir a **Ventas → Configuración → Ajustes →
   Facturación → Producto de anticipo** y seleccionar el producto. Guardar.
3. Confirmar un pedido y pulsar **Crear factura**. Elegir un anticipo por
   porcentaje o importe fijo. La línea de factura tendrá el producto configurado.
4. Al crear la factura final con deducción de anticipos, Odoo reutilizará el
   producto de cada anticipo original.

El producto puede ser compartido o pertenecer a la compañía del pedido. La
configuración es independiente por compañía, incluso cuando otra compañía está
activa al abrir el asistente. La interfaz incluye traducción al español.

## Comportamiento

- Sin producto configurado, se conserva el flujo estándar sin producto.
- El precio de catálogo, los impuestos y la cuenta de ingresos del producto de
  anticipo **no sustituyen** los cálculos estándar de Odoo. Los importes,
  impuestos, distribución analítica y datos de redondeo proceden del pedido.
- La cuenta contable sigue la selección nativa de Odoo: cuenta de anticipos de
  la compañía cuando está configurada, o la cuenta que corresponda según los
  productos originales y la posición fiscal. El módulo no añade una cuenta
  contable alternativa.
- Una tarifa aplicada al producto de anticipo no debe descontar el importe una
  segunda vez. La línea de anticipo tiene descuento cero.
- Un pedido con impuestos o cuentas diferentes puede generar **varias líneas**
  de anticipo; todas reciben el producto configurado.
- Se conservan las descripciones nativas de las facturas de anticipo; el cambio
  consiste en asociar el producto real a la línea, aunque su etiqueta diga
  «Anticipo» o «Anticipo del … %».
- Si el producto se archiva o cambia a una configuración incompatible, se
  bloquean los nuevos anticipos con un mensaje para corregir los ajustes.
- Cambiar el producto configurado afecta a nuevos anticipos. No modifica
  pedidos ni facturas existentes; las deducciones conservan su producto original.
- No incluye migración de anticipos creados antes de instalar/configurar el
  módulo. Las facturas ordinarias mantienen los productos vendidos.

## Pruebas

La integración continua en GitHub Actions instala el módulo en la imagen oficial
`odoo:19.0`, con PostgreSQL 16, y ejecuta sus pruebas de integración. El registro
se conserva como artefacto de cada ejecución. Además, se comprueba que la
instalación limpia no instale la aplicación Website.

Cobertura: porcentaje, monto fijo, deducción final, publicación de facturas,
impuestos mixtos e incluidos en el precio, redondeo, cuentas y posición fiscal,
tarifas, cambio de producto, configuración vacía, validación y multicompañía.

En una base de datos desechable de un entorno Odoo 19:

```sh
odoo --database=down_payment_product_test \
  --init=sale_down_payment_product \
  --test-enable --test-tags=/sale_down_payment_product \
  --without-demo --stop-after-init
```

El directorio padre del repositorio debe estar incluido en `addons_path`. Añadir
las opciones de conexión a PostgreSQL propias del entorno.

## Licencia

LGPL-3.0. Ver `LICENSE` y `COPYING`.
